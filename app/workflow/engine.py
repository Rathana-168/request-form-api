"""Workflow runtime. Every status change of an in-progress request happens here."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.approvals.models import ApprovalTask, TaskStatus
from app.modules.forms.data import load_form_row
from app.modules.requests.models import (
    HistoryAction,
    Request,
    RequestHistory,
    RequestStatus,
)
from app.modules.users.models import Department, User, user_roles
from app.workflow.conditions import matches
from app.workflow.enums import WorkflowEvent
from app.workflow.events import dispatch
from app.workflow.models import AssigneeType, Workflow


class NoActiveWorkflowError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "NO_ACTIVE_WORKFLOW"

    def __init__(self, form_code: str):
        super().__init__(f"Form '{form_code}' has no active workflow")


class ActionNotAllowedError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "ACTION_NOT_ALLOWED"

    def __init__(self, action: str, step_name: str):
        super().__init__(f"'{action}' is not allowed at step '{step_name}'")


class CommentRequiredError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "COMMENT_REQUIRED"

    def __init__(self, action: str):
        super().__init__(f"A comment is required to {action}")


STEP_FIELDS = (
    "step_no", "name", "status", "action_label", "assignee_type", "assignee_field", "mode",
    "conditions", "skip_if_requester", "allow_reject", "allow_return", "return_to",
    "require_comment_on",
)

# --- entry points -------------------------------------------------------------


async def start(db: AsyncSession, request: Request, actor: User) -> None:
    """Submit / resubmit: snapshot the active workflow and open step 1."""
    workflow = await db.scalar(
        select(Workflow).where(Workflow.form_code == request.form_code, Workflow.is_active)
    )
    if not workflow:
        raise NoActiveWorkflowError(request.form_code)

    request.workflow_id = workflow.id
    request.workflow_snapshot = {
        "completed_status": workflow.completed_status,
        "steps": [
            {
                **{f: _plain(getattr(s, f)) for f in STEP_FIELDS},
                "assignee_user_id": str(s.assignee_user_id) if s.assignee_user_id else None,
                "assignee_role_id": str(s.assignee_role_id) if s.assignee_role_id else None,
            }
            for s in workflow.steps
        ],
    }
    await _open_step(db, request, 1, actor)


async def approve(db: AsyncSession, request: Request, task: ApprovalTask, actor: User,
                  comment: str | None) -> None:
    step = _step(request, task.step_no)
    _check(step, "approve", comment)
    _close_task(task, TaskStatus.APPROVED, comment)
    await _log(db, request, HistoryAction.APPROVED, actor, task.step_no, comment)

    if step["mode"] == "any":
        await _close_open_tasks(db, request, step_no=task.step_no)
    elif await _has_open_tasks(db, request, step_no=task.step_no):
        return  # "all" mode: wait for the others

    # Hook to event on step action
    await dispatch(db, WorkflowEvent.STEP_APPROVED, request, actor, step=step)
    await _open_step(db, request, task.step_no + 1, actor)


async def reject(db: AsyncSession, request: Request, task: ApprovalTask, actor: User,
                 comment: str | None) -> None:
    step = _step(request, task.step_no)
    _check(step, "reject", comment)
    _close_task(task, TaskStatus.REJECTED, comment)

    await _close_open_tasks(db, request)
    await dispatch(db, WorkflowEvent.STEP_REJECTED, request, actor, step=step)
    await dispatch(db, WorkflowEvent.REJECTED, request, actor, comment=comment)
    await _finish(db, request, RequestStatus.REJECTED, stage="rejected")
    await _log(db, request, HistoryAction.REJECTED, actor, task.step_no, comment)


async def return_back(db: AsyncSession, request: Request, task: ApprovalTask,
                      actor: User, comment: str | None) -> None:
    """Send back per the step's `return_to`: the requester, the previous approver, or step n."""
    step = _step(request, task.step_no)
    _check(step, "return", comment)
    _close_task(task, TaskStatus.RETURNED, comment)
    await _close_open_tasks(db, request)
    await _log(db, request, HistoryAction.RETURNED, actor, task.step_no, comment)

    target = await _return_target(db, request, step)
    if target is None:  # to the requester: they edit and resubmit from step 1
        request.status = RequestStatus.RETURNED
        request.current_step = None
        request.stage = "returned"
        await dispatch(db, WorkflowEvent.RETURNED, request, actor, comment=comment)
    else:
        await _open_step(db, request, target, actor)   # same function submit uses


async def cancel(db: AsyncSession, request: Request) -> None:
    """Requester cancelled: close whatever is still open."""
    pending = await db.scalars(select(ApprovalTask.assignee_id).where(
        ApprovalTask.request_id == request.id,
        ApprovalTask.status == TaskStatus.PENDING,
    ))
    pending_ids = list(pending)

    await _close_open_tasks(db, request)
    request.current_step = None
    request.stage = "cancelled"

    # email to user which has got the notification
    await dispatch(db, WorkflowEvent.CANCELLED, request, request.requester, user_ids=pending_ids)

async def available_actions(db: AsyncSession, request: Request, user: User) -> list[dict]:
    """What this user can do right now - the frontend renders these as buttons."""
    actions: list[dict] = []
    if request.requester_id == user.id:
        if request.status in (RequestStatus.DRAFT, RequestStatus.RETURNED):
            actions += [_action("edit", "Edit"), _action("submit", "Submit")]
        if request.status == RequestStatus.DRAFT:
            actions.append(_action("delete", "Delete"))
        if request.status in (RequestStatus.IN_PROGRESS, RequestStatus.RETURNED):
            actions.append(_action("cancel", "Cancel"))

    if request.status == RequestStatus.IN_PROGRESS:
        task = await db.scalar(select(ApprovalTask).where(
            ApprovalTask.request_id == request.id,
            ApprovalTask.step_no == request.current_step,
            ApprovalTask.assignee_id == user.id,
            ApprovalTask.status == TaskStatus.PENDING,
        ))
        if task:
            step = _step(request, task.step_no)
            need = set(step["require_comment_on"])
            actions.append(_action("approve", step["action_label"], task.id, "approve" in need))
            if step["allow_return"]:
                actions.append(_action("return", "Return", task.id, "return" in need))
            if step["allow_reject"]:
                actions.append(_action("reject", "Reject", task.id, "reject" in need))
    return actions

# --- internals ----------------------------------------------------------------
STEP_DEFAULTS = {
    "status": "in_review", "action_label": "Approve", "assignee_field": None,
    "allow_reject": True, "allow_return": True, "return_to": "requester",
    "require_comment_on": [],
}


def steps_of(request: Request) -> list[dict[str, Any]]:
    snap = request.workflow_snapshot or {}
    steps = snap if isinstance(snap, list) else snap.get("steps", [])  # list = older format
    return [{**STEP_DEFAULTS, **s} for s in steps]


def _completed_status(request: Request) -> str:
    snap = request.workflow_snapshot
    return snap.get("completed_status", "approved") if isinstance(snap, dict) else "approved"


async def _open_step(db: AsyncSession, request: Request, step_no: int, actor: User) -> None:
    """Open `step_no`, skipping steps whose condition fails or that have no approver."""
    steps = steps_of(request)
    data = await _form_data(db, request)

    while step_no <= len(steps):
        step = steps[step_no - 1]
        if not matches(step["conditions"], data):
            await _log(db, request, HistoryAction.SKIPPED, None, step_no, "Condition not met")
            step_no += 1
            continue

        approvers = await _resolve_approvers(db, request, step)
        if not approvers:
            await _log(db, request, HistoryAction.SKIPPED, None, step_no, "No approver")
            step_no += 1
            continue

        # Update Request
        request.current_step = step_no
        request.stage = step["status"]

        # Add approval task for next approver
        db.add_all(
            ApprovalTask(request_id=request.id, step_no=step_no, assignee_id=uid)
            for uid in approvers
        )
        await db.flush()
        await dispatch(db, WorkflowEvent.TASK_ASSIGNED, request, actor, step=step, user_ids=approvers)
        return

    # Past the last step: done
    await _finish(db, request, RequestStatus.APPROVED, stage=_completed_status(request))
    await _log(db, request, HistoryAction.COMPLETED, None, None, None)
    await dispatch(db, WorkflowEvent.APPROVED, request, actor)


async def _resolve_approvers(db: AsyncSession, request: Request,
                             step: dict[str, Any]) -> list[uuid.UUID]:
    requester = await db.get(User, request.requester_id)
    kind = AssigneeType(step["assignee_type"])
    ids: list[uuid.UUID] = []

    if kind is AssigneeType.USER and step["assignee_user_id"]:
        ids = [uuid.UUID(step["assignee_user_id"])]
    elif kind is AssigneeType.ROLE and step["assignee_role_id"]:
        ids = list(await db.scalars(
            select(user_roles.c.user_id).where(
                user_roles.c.role_id == uuid.UUID(step["assignee_role_id"])
            )
        ))
    elif kind is AssigneeType.REQUESTER_MANAGER and requester.manager_id:
        ids = [requester.manager_id]
    elif kind is AssigneeType.DEPARTMENT_HEAD and requester.department_id:
        head_id = await db.scalar(
            select(Department.head_id).where(Department.id == requester.department_id)
        )
        ids = [head_id] if head_id else []
    elif kind is AssigneeType.FORM_FIELD and step["assignee_field"]:
        value = (await _form_data(db, request)).get(step["assignee_field"])
        values = value if isinstance(value, list) else [value]
        ids = [v if isinstance(v, uuid.UUID) else uuid.UUID(str(v)) for v in values if v]

    if ids:  # only active users
        ids = list(await db.scalars(
            select(User.id).where(User.id.in_(ids), User.is_active).order_by(User.full_name)
        ))
    if step["skip_if_requester"]:
        ids = [i for i in ids if i != request.requester_id]
    return ids


def _step(request: Request, step_no: int) -> dict[str, Any]:
    return steps_of(request)[step_no - 1]


def _plain(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _close_task(task: ApprovalTask, status: TaskStatus, comment: str | None) -> None:
    task.status = status
    task.comment = comment
    task.acted_at = datetime.now(UTC)


async def _close_open_tasks(db: AsyncSession, request: Request,
                            step_no: int | None = None) -> None:
    stmt = (
        update(ApprovalTask)
        .where(ApprovalTask.request_id == request.id, ApprovalTask.status == TaskStatus.PENDING)
        .values(status=TaskStatus.CLOSED, acted_at=datetime.now(UTC))
        .execution_options(synchronize_session=False)
    )
    if step_no is not None:
        stmt = stmt.where(ApprovalTask.step_no == step_no)
    await db.flush()
    await db.execute(stmt)


async def _has_open_tasks(db: AsyncSession, request: Request, step_no: int) -> bool:
    await db.flush()
    found = await db.scalar(
        select(ApprovalTask.id).where(
            ApprovalTask.request_id == request.id,
            ApprovalTask.step_no == step_no,
            ApprovalTask.status == TaskStatus.PENDING,
        ).limit(1)
    )
    return found is not None


async def _finish(db: AsyncSession, request: Request, status: RequestStatus,
                  *, stage: str) -> None:
    request.status = status
    request.stage = stage
    request.current_step = None
    request.completed_at = datetime.now(UTC)


async def _form_data(db: AsyncSession, request: Request) -> dict[str, Any]:
    definition, row = await load_form_row(db, request)
    return definition.read_schema.model_validate(row).model_dump()


async def _log(db: AsyncSession, request: Request, action: HistoryAction, actor: User | None,
               step_no: int | None, comment: str | None) -> None:
    db.add(RequestHistory(
        request_id=request.id,
        action=action,
        actor_id=actor.id if actor else None,
        step_no=step_no,
        comment=comment,
    ))
    await db.flush()


def _check(step: dict[str, Any], action: str, comment: str | None) -> None:
    if action == "reject" and not step["allow_reject"]:
        raise ActionNotAllowedError(action, step["name"])
    if action == "return" and not step["allow_return"]:
        raise ActionNotAllowedError(action, step["name"])
    if action in step["require_comment_on"] and not (comment or "").strip():
        raise CommentRequiredError(action)


async def _return_target(db: AsyncSession, request: Request,
                         step: dict[str, Any]) -> int | None:
    """Step number to reopen, or None for the requester."""
    if step["return_to"] == "requester":
        return None
    if step["return_to"] == "previous":
        # last earlier step someone approved in this round (skipped steps don't count)
        return await db.scalar(
            select(ApprovalTask.step_no)
            .where(
                ApprovalTask.request_id == request.id,
                ApprovalTask.step_no < step["step_no"],
                ApprovalTask.status == TaskStatus.APPROVED,
                ApprovalTask.acted_at >= request.submitted_at,  # this round only
            )
            .order_by(ApprovalTask.step_no.desc())
            .limit(1)
        )  # None -> nothing approved before: back to the requester
    return int(step["return_to"])


def _action(key: str, label: str, task_id: uuid.UUID | None = None,
            require_comment: bool = False) -> dict[str, Any]:
    return {"key": key, "label": label, "task_id": task_id, "require_comment": require_comment}
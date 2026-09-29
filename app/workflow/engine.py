"""Workflow runtime. Every status change of an in-progress request happens here."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.modules.approvals.models import ApprovalTask, TaskStatus
from app.modules.forms.plugin import FormContext, FormDataMixin, FormDefinition
from app.modules.forms.registry import get_definition
from app.modules.requests.models import (
    HistoryAction,
    Request,
    RequestHistory,
    RequestStatus,
)
from app.modules.users.models import Department, User, user_roles
from app.workflow.conditions import matches
from app.workflow.models import AssigneeType, Workflow


class NoActiveWorkflowError(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = "NO_ACTIVE_WORKFLOW"

    def __init__(self, form_code: str):
        super().__init__(f"Form '{form_code}' has no active workflow")


# --- entry points -------------------------------------------------------------


async def start(db: AsyncSession, request: Request, actor: User) -> None:
    """Submit / resubmit: snapshot the active workflow and open step 1."""
    workflow = await db.scalar(
        select(Workflow).where(Workflow.form_code == request.form_code, Workflow.is_active)
    )
    if not workflow:
        raise NoActiveWorkflowError(request.form_code)

    request.workflow_id = workflow.id
    request.workflow_snapshot = [
        {
            "step_no": s.step_no,
            "name": s.name,
            "assignee_type": s.assignee_type.value,
            "assignee_user_id": str(s.assignee_user_id) if s.assignee_user_id else None,
            "assignee_role_id": str(s.assignee_role_id) if s.assignee_role_id else None,
            "mode": s.mode.value,
            "conditions": s.conditions,
            "skip_if_requester": s.skip_if_requester,
        }
        for s in workflow.steps
    ]
    await _open_step(db, request, 1, actor)


async def approve(db: AsyncSession, request: Request, task: ApprovalTask, actor: User,
                  comment: str | None) -> None:
    step = _step(request, task.step_no)
    _close_task(task, TaskStatus.APPROVED, comment)
    await _log(db, request, HistoryAction.APPROVED, actor, task.step_no, comment)

    if step["mode"] == "any":
        await _close_open_tasks(db, request, step_no=task.step_no)
    elif await _has_open_tasks(db, request, step_no=task.step_no):
        return  # "all" mode: wait for the others
    await _open_step(db, request, task.step_no + 1, actor)


async def reject(db: AsyncSession, request: Request, task: ApprovalTask, actor: User,
                 comment: str | None) -> None:
    _close_task(task, TaskStatus.REJECTED, comment)
    await _close_open_tasks(db, request)
    await _finish(db, request, RequestStatus.REJECTED)
    await _log(db, request, HistoryAction.REJECTED, actor, task.step_no, comment)
    await _run_hook(db, request, actor, "on_rejected")


async def return_to_requester(db: AsyncSession, request: Request, task: ApprovalTask,
                              actor: User, comment: str | None) -> None:
    _close_task(task, TaskStatus.RETURNED, comment)
    await _close_open_tasks(db, request)
    request.status = RequestStatus.RETURNED
    request.current_step = None  # resubmit restarts from step 1
    await _log(db, request, HistoryAction.RETURNED, actor, task.step_no, comment)
    await _run_hook(db, request, actor, "on_returned")


async def cancel(db: AsyncSession, request: Request) -> None:
    """Requester cancelled: close whatever is still open."""
    await _close_open_tasks(db, request)
    request.current_step = None


# --- internals ----------------------------------------------------------------


async def _open_step(db: AsyncSession, request: Request, step_no: int, actor: User) -> None:
    """Open `step_no`, skipping steps whose condition fails or that have no approver."""
    steps = request.workflow_snapshot or []
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

        request.current_step = step_no
        db.add_all(
            ApprovalTask(request_id=request.id, step_no=step_no, assignee_id=uid)
            for uid in approvers
        )
        await db.flush()
        return

    # Past the last step: done
    await _finish(db, request, RequestStatus.APPROVED)
    await _log(db, request, HistoryAction.COMPLETED, None, None, None)
    await _run_hook(db, request, actor, "on_approved")


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

    if ids:  # only active users
        ids = list(await db.scalars(
            select(User.id).where(User.id.in_(ids), User.is_active).order_by(User.full_name)
        ))
    if step["skip_if_requester"]:
        ids = [i for i in ids if i != request.requester_id]
    return ids


def _step(request: Request, step_no: int) -> dict[str, Any]:
    return (request.workflow_snapshot or [])[step_no - 1]


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


async def _finish(db: AsyncSession, request: Request, status: RequestStatus) -> None:
    request.status = status
    request.current_step = None
    request.completed_at = datetime.now(UTC)


async def _form_row(db: AsyncSession, request: Request) -> tuple[FormDefinition, FormDataMixin]:
    from app.modules.requests.repository import RequestRepository  # avoid import cycle

    definition = get_definition(request.form_code)
    row = await RequestRepository(db).get_data(definition.model, request.id)
    return definition, row


async def _form_data(db: AsyncSession, request: Request) -> dict[str, Any]:
    definition, row = await _form_row(db, request)
    return definition.read_schema.model_validate(row).model_dump()


async def _run_hook(db: AsyncSession, request: Request, actor: User, name: str) -> None:
    definition, row = await _form_row(db, request)
    ctx = FormContext(db=db, request=request, user=actor, definition=definition)
    await getattr(definition.hooks, name)(ctx, row)


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
import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.models import ApprovalTask, TaskStatus
from app.modules.requests.models import HistoryAction, Request, RequestHistory
from app.modules.users.models import User
from app.workflow import engine
from app.workflow.enums import EscalationAction, WorkflowEvent
from app.workflow.events import dispatch

logger = logging.getLogger(__name__)
BATCH_SIZE = 200


def _is_due(now: datetime):
    """Pending, and a reminder or escalation is due that hasn't happened yet."""
    return and_(
        ApprovalTask.status == TaskStatus.PENDING,
        or_(
            and_(ApprovalTask.remind_at <= now, ApprovalTask.reminded_at.is_(None)),
            and_(ApprovalTask.escalate_at <= now, ApprovalTask.escalated_at.is_(None)),
        ),
    )


async def find_due_task_ids(db: AsyncSession, now: datetime) -> list[uuid.UUID]:
    rows = await db.scalars(
        select(ApprovalTask.id).where(_is_due(now)).limit(BATCH_SIZE)
    )
    return list(rows)


async def process_task(db: AsyncSession, task_id: uuid.UUID, now: datetime) -> str | None:
    """Remind or escalate one task. Returns what was done, or None if nothing."""
    task = await db.scalar(
        select(ApprovalTask)
        .where(ApprovalTask.id == task_id, _is_due(now))
        .with_for_update(skip_locked=True)
    )
    if task is None:
        return None  # already handled, approved meanwhile, or locked by another worker

    if task.escalate_at and task.escalate_at <= now and task.escalated_at is None:
        await escalate(db, task, now)
        task.escalated_at = now
        task.reminded_at = task.reminded_at or now  # no late reminder after escalating
        return "escalated"

    await remind(db, task, now)
    task.reminded_at = now
    return "reminded"


# ---------- Actions ----------

async def remind(db: AsyncSession, task: ApprovalTask, now: datetime) -> None:
    request, step = await _load(db, task)
    _history(db, request, HistoryAction.REMINDED, step, "Reminder sent to approver")
    user_ids = [task.assignee_id, *await engine.proxy_ids_for(db, task.assignee_id, request)]
    await dispatch(db, WorkflowEvent.TASK_REMINDER, request, None, step=step, user_ids=user_ids)


async def escalate(db: AsyncSession, task: ApprovalTask, now: datetime) -> None:
    request, step = await _load(db, task)
    approver = await db.get(User, task.assignee_id)
    approver_name = approver.full_name if approver else "the approver"
    manager_id = approver.manager_id if approver else None  # adjust to your manager field
    extra = {"approver": approver_name, "hours": str(step["escalate_after_hours"])}

    if manager_id is None:
        _history(db, request, HistoryAction.ESCALATED, step,
                 f"Overdue with {approver_name}; no manager to escalate to")
        return

    if (
        step["escalation_action"] == EscalationAction.REASSIGN_MANAGER
        and await _can_reassign(db, task, request, manager_id)
    ):
        await _reassign(db, task, request, step, manager_id, now)
        _history(db, request, HistoryAction.REASSIGNED, step,
                 f"Reassigned from {approver_name} to their manager after {extra['hours']}h")
        await dispatch(
            db, WorkflowEvent.TASK_REASSIGNED, request, None,
            step=step, user_ids=[task.assignee_id, manager_id], extra=extra,
        )
        return

    _history(db, request, HistoryAction.ESCALATED, step,
             f"Overdue with {approver_name} for {extra['hours']}h; manager notified")
    await dispatch(
        db, WorkflowEvent.TASK_ESCALATED, request, None,
        step=step, user_ids=[manager_id], extra=extra,
    )


# ---------- Helpers ----------

async def _reassign(
    db: AsyncSession, task: ApprovalTask, request: Request,
    step: dict[str, Any], manager_id: uuid.UUID, now: datetime,
) -> None:
    """Close the overdue task and give the step to the manager, with a fresh SLA clock."""
    task.status = TaskStatus.REASSIGNED
    task.acted_at = now
    remind_at, escalate_at = engine.sla_deadlines(step, now)
    db.add(ApprovalTask(
        request_id=request.id,
        step_no=task.step_no,
        assignee_id=manager_id,
        status=TaskStatus.PENDING,
        remind_at=remind_at,
        escalate_at=escalate_at,
    ))


async def _can_reassign(
    db: AsyncSession, task: ApprovalTask, request: Request, manager_id: uuid.UUID
) -> bool:
    if manager_id == request.requester_id:
        return False  # nobody approves their own request: notify instead
    already_assigned = await db.scalar(
        select(ApprovalTask.id).where(
            ApprovalTask.request_id == request.id,
            ApprovalTask.step_no == task.step_no,
            ApprovalTask.assignee_id == manager_id,
            ApprovalTask.status == TaskStatus.PENDING,
        )
    )
    return already_assigned is None  # manager already on this step: notify instead


async def _load(db: AsyncSession, task: ApprovalTask) -> tuple[Request, dict[str, Any]]:
    request = await db.get(Request, task.request_id)
    return request, engine.steps_of(request)[task.step_no - 1]


def _history(
    db: AsyncSession, request: Request, action: HistoryAction,
    step: dict[str, Any], comment: str,
) -> None:
    db.add(RequestHistory(
        request_id=request.id,
        action=action,
        actor_id=None,  # system
        step_no=step["step_no"],
        comment=comment,
    ))
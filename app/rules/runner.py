import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.requests.models import Request
from app.rules.context import ActionContext
from app.rules.enums import ExecutionStatus
from app.rules.models import RuleExecution
from app.rules.registry import get_action

logger = get_logger(__name__)


async def claim_batch(sessions) -> list[uuid.UUID]:
    """Lock due rows, push their next_attempt_at forward (the lease), and count the attempt."""
    s = get_settings()
    now = datetime.now(UTC)
    async with sessions() as db, db.begin():
        ids = list(await db.scalars(
            select(RuleExecution.id)
            .where(RuleExecution.status == ExecutionStatus.PENDING,
                   RuleExecution.is_async,
                   RuleExecution.next_attempt_at <= now)
            .order_by(RuleExecution.next_attempt_at)
            .limit(s.RULE_ACTIONS_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        ))
        if ids:
            await db.execute(
                update(RuleExecution).where(RuleExecution.id.in_(ids)).values(
                    next_attempt_at=now + timedelta(seconds=s.RULE_ACTION_LEASE_SECONDS),
                    attempts=RuleExecution.attempts + 1,
                )
            )
    return ids


async def run_one(sessions, exe_id: uuid.UUID) -> ExecutionStatus:
    s = get_settings()
    async with sessions() as db, db.begin():
        exe = await db.get(RuleExecution, exe_id, with_for_update=True)
        if exe is None or exe.status != ExecutionStatus.PENDING:
            return exe.status if exe else ExecutionStatus.SKIPPED

        now = datetime.now(UTC)
        spec = get_action(exe.action_type)
        if spec is None:
            exe.status, exe.finished_at = ExecutionStatus.SKIPPED, now
            exe.last_error = "Action type no longer exists"
            return exe.status

        try:
            async with db.begin_nested():   # the action's own DB changes roll back on error
                request = await db.get(Request, exe.request_id)
                ctx = ActionContext(db=db, request=request)
                await spec.handler(ctx, spec.params.model_validate(exe.params))
        except Exception as e:
            exe.last_error = f"{type(e).__name__}: {e}"[:2000]
            if exe.attempts >= s.RULE_ACTION_MAX_ATTEMPTS:
                exe.status, exe.finished_at = ExecutionStatus.FAILED, now
                logger.error("Rule action %s failed for good: %s", exe.id, exe.last_error)
            else:
                exe.next_attempt_at = now + timedelta(minutes=2 ** (exe.attempts - 1))
                logger.warning("Rule action %s failed (attempt %s), retrying", exe.id, exe.attempts)
            return exe.status

        exe.status, exe.finished_at, exe.last_error = ExecutionStatus.SUCCEEDED, now, None
        return exe.status


async def run_pending(sessions) -> dict[str, int]:
    counts = {"succeeded": 0, "retrying": 0, "failed": 0, "skipped": 0}
    for exe_id in await claim_batch(sessions):
        status = await run_one(sessions, exe_id)
        key = {"pending": "retrying"}.get(status.value, status.value)
        counts[key] = counts.get(key, 0) + 1
    return counts
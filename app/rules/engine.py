import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnprocessableError        # your 422 error
from app.modules.users.models import User
from app.rules.context import ActionContext, render
from app.rules.enums import ExecutionStatus
from app.rules.models import RuleExecution
from app.rules.registry import ActionError, get_action
from app.workflow.conditions import matches              # your existing evaluator

logger = logging.getLogger(__name__)


def _matches(rule: dict, event: str, step_no: int | None) -> bool:
    return rule["event"] == event and rule.get("step_no") in (None, step_no)


async def run_rules(
    db: AsyncSession, event: str, request: Any, *,
    event_id: uuid.UUID, step_no: int | None, actor: User | None, data: dict[str, Any],
) -> None:
    rules = [r for r in (request.workflow_snapshot or {}).get("rules", [])
             if _matches(r, event, step_no)]
    if not rules:
        return

    ctx = ActionContext(
        db=db, request=request, requester=await db.get(User, request.requester_id),
        data=data, event=event, step_no=step_no, actor=actor,
    )
    variables = ctx.template_vars

    for rule in rules:
        if rule.get("conditions") and not matches(rule["conditions"], data):
            continue

        for i, action in enumerate(rule["actions"]):
            spec = get_action(action["type"])
            exe = RuleExecution(
                event_id=event_id, request_id=request.id,
                rule_id=uuid.UUID(rule["id"]), rule_name=rule["name"],
                action_index=i, action_type=action["type"],
                params={}, is_async=bool(spec and spec.is_async),
                status=ExecutionStatus.PENDING,
            )
            db.add(exe)

            if spec is None:
                exe.status = ExecutionStatus.SKIPPED
                exe.last_error = "Action type no longer exists"
                logger.warning("Rule %s: unknown action %s", rule["name"], action["type"])
                continue

            try:
                exe.params = render(action.get("params", {}), variables)
                params = spec.params.model_validate(exe.params)
            except Exception as e:
                raise UnprocessableError(f"Rule '{rule['name']}' is misconfigured: {e}") from e

            if spec.is_async:
                continue                     # stays PENDING; the worker runs it (Step 4)

            try:
                await spec.handler(ctx, params)
            except ActionError as e:
                raise UnprocessableError(f"{rule['name']}: {e}") from e

            exe.status = ExecutionStatus.SUCCEEDED
            exe.attempts = 1
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, UnprocessableError
from app.modules.forms.data import load_form_data
from app.modules.requests.models import Request
from app.rules.context import ActionContext, render
from app.rules.models import WorkflowRule
from app.rules.registry import get_action, validate_actions
from app.rules.schemas import (
    ActionPreview,
    RuleCreate,
    RuleTestIn,
    RuleTestOut,
    RuleUpdate,
)
from app.workflow.conditions import matches
from app.workflow.models import Workflow


def _conditions_json(c) -> Any:
    if c is None:
        return {}
    if isinstance(c, list):
        return [i.model_dump(by_alias=True, exclude_none=True) for i in c]
    return c.model_dump(by_alias=True, exclude_none=True)


class RuleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _workflow(self, workflow_id: uuid.UUID) -> Workflow:
        wf = await self.db.scalar(
            select(Workflow).where(Workflow.id == workflow_id)
            .options(selectinload(Workflow.steps), selectinload(Workflow.form))
        )
        if not wf:
            raise NotFoundError("Workflow not found")
        return wf

    async def _rule(self, workflow_id: uuid.UUID, rule_id: uuid.UUID) -> WorkflowRule:
        rule = await self.db.get(WorkflowRule, rule_id)
        if not rule or rule.workflow_id != workflow_id:
            raise NotFoundError("Rule not found")
        return rule

    def _check(self, wf: Workflow, step_no: int | None, actions: list[dict]) -> None:
        if step_no is not None and step_no not in {s.step_no for s in wf.steps}:
            raise UnprocessableError(f"Step {step_no} doesn't exist in this workflow")
        if errors := validate_actions(actions, wf.form.code):
            raise UnprocessableError("; ".join(errors))

    async def list(self, workflow_id: uuid.UUID) -> list[WorkflowRule]:
        await self._workflow(workflow_id)
        rows = await self.db.scalars(
            select(WorkflowRule).where(WorkflowRule.workflow_id == workflow_id)
            .order_by(WorkflowRule.priority, WorkflowRule.created_at)
        )
        return list(rows)

    async def create(self, workflow_id: uuid.UUID, data: RuleCreate) -> WorkflowRule:
        wf = await self._workflow(workflow_id)
        actions = [a.model_dump() for a in data.actions]
        self._check(wf, data.step_no, actions)
        rule = WorkflowRule(
            workflow_id=wf.id, name=data.name, event=data.event, step_no=data.step_no,
            conditions=_conditions_json(data.conditions), actions=actions,
            priority=data.priority, is_active=data.is_active,
        )
        self.db.add(rule)
        await self.db.flush()
        return rule

    async def update(self, workflow_id: uuid.UUID, rule_id: uuid.UUID,
                     data: RuleUpdate) -> WorkflowRule:
        wf = await self._workflow(workflow_id)
        rule = await self._rule(workflow_id, rule_id)
        changes = data.model_dump(exclude_unset=True)
        if "conditions" in changes:
            changes["conditions"] = _conditions_json(data.conditions)
        if "actions" in changes:
            changes["actions"] = [a.model_dump() for a in data.actions]
        for k, v in changes.items():
            setattr(rule, k, v)
        self._check(wf, rule.step_no, rule.actions)
        await self.db.flush()
        return rule

    async def delete(self, workflow_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        await self.db.delete(await self._rule(workflow_id, rule_id))

    async def test(self, workflow_id: uuid.UUID, body: RuleTestIn) -> RuleTestOut:
        wf = await self._workflow(workflow_id)
        rule = body.rule
        self._check(wf, rule.step_no, [a.model_dump() for a in rule.actions])

        request = await self.db.get(Request, body.request_id)
        if not request:
            raise NotFoundError("Request not found")
        data = await load_form_data(self.db, request)  # same helper dispatch() uses

        if not matches(_conditions_json(rule.conditions), data):
            return RuleTestOut(matched=False)

        ctx = ActionContext(
            db=self.db, request=request,
            data=data, event=rule.event, step_no=rule.step_no, actor=None,
        )
        previews = []
        for a in rule.actions:
            params = render(a.params, ctx.template_vars)
            try:
                get_action(a.type).params.model_validate(params)
                previews.append(ActionPreview(type=a.type, params=params, valid=True))
            except ValidationError as e:
                previews.append(ActionPreview(type=a.type, params=params, valid=False,
                                              error=e.errors()[0]["msg"]))
        return RuleTestOut(matched=True, actions=previews)
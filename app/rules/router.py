import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, require_permission
from app.modules.users.models import User
from app.rules.registry import list_actions
from app.rules.schemas import (ActionTypeOut, RuleCreate, RuleOut, RuleTestIn,
                               RuleTestOut, RuleUpdate)
from app.rules.service import RuleService
from app.shared.schemas import APIResponse, ok

router = APIRouter()
Manager = Annotated[User, Depends(require_permission("workflow:manage"))]


def get_service(db: DbSession) -> RuleService:
    return RuleService(db)


Svc = Annotated[RuleService, Depends(get_service)]


@router.get("/rules/actions", response_model=APIResponse[list[ActionTypeOut]])
async def action_types(_: Manager, form_code: str | None = None):
    return ok([ActionTypeOut(type=s.type, description=s.description, is_async=s.is_async,
                             params_schema=s.params.model_json_schema())
               for s in list_actions(form_code)])


@router.get("/workflows/{workflow_id}/rules", response_model=APIResponse[list[RuleOut]])
async def list_rules(workflow_id: uuid.UUID, _: Manager, svc: Svc):
    return ok(await svc.list(workflow_id))


@router.post("/workflows/{workflow_id}/rules", response_model=APIResponse[RuleOut],
             status_code=status.HTTP_201_CREATED)
async def create_rule(workflow_id: uuid.UUID, data: RuleCreate, _: Manager, svc: Svc):
    return APIResponse.success(await svc.create(workflow_id, data), status_code=201)


@router.post("/workflows/{workflow_id}/rules/test", response_model=APIResponse[RuleTestOut])
async def test_rule(workflow_id: uuid.UUID, body: RuleTestIn, _: Manager, svc: Svc):
    return ok(await svc.test(workflow_id, body))


@router.patch("/workflows/{workflow_id}/rules/{rule_id}", response_model=APIResponse[RuleOut])
async def update_rule(workflow_id: uuid.UUID, rule_id: uuid.UUID, data: RuleUpdate,
                      _: Manager, svc: Svc):
    return ok(await svc.update(workflow_id, rule_id, data))


@router.delete("/workflows/{workflow_id}/rules/{rule_id}", response_model=APIResponse[None])
async def delete_rule(workflow_id: uuid.UUID, rule_id: uuid.UUID, _: Manager, svc: Svc):
    await svc.delete(workflow_id, rule_id)
    return ok(None)
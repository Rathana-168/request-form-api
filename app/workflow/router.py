import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import DbSession, require_permission
from app.modules.users.models import User
from app.shared.schemas import APIResponse, ok
from app.workflow.schemas import AssigneeTypeOut, WorkflowCreate, WorkflowOut, WorkflowUpdate
from app.workflow.service import WorkflowService

router = APIRouter()


def get_workflow_service(db: DbSession) -> WorkflowService:
    return WorkflowService(db)


WorkflowSvc = Annotated[WorkflowService, Depends(get_workflow_service)]
Manager = Annotated[User, Depends(require_permission("workflow:manage"))]


@router.get("", response_model=list[WorkflowOut])
async def list_workflows(
    _: Manager, svc: WorkflowSvc, form_code: Annotated[str | None, Query(max_length=50)] = None
):
    return await svc.list_all(form_code)


@router.get("/{workflow_id}", response_model=WorkflowOut)
async def get_workflow(workflow_id: uuid.UUID, _: Manager, svc: WorkflowSvc):
    return await svc.get(workflow_id)


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
async def create_workflow(data: WorkflowCreate, _: Manager, svc: WorkflowSvc):
    return await svc.create(data)


@router.put("/{workflow_id}", response_model=WorkflowOut)
async def update_workflow(
    workflow_id: uuid.UUID, data: WorkflowUpdate, _: Manager, svc: WorkflowSvc
):
    return await svc.update(workflow_id, data)


@router.post("/{workflow_id}/activate", response_model=WorkflowOut)
async def activate_workflow(workflow_id: uuid.UUID, _: Manager, svc: WorkflowSvc):
    return await svc.activate(workflow_id)


@router.post("/{workflow_id}/deactivate", response_model=WorkflowOut)
async def deactivate_workflow(workflow_id: uuid.UUID, _: Manager, svc: WorkflowSvc):
    return await svc.deactivate(workflow_id)


@router.get("/remote/assignee-types", response_model=APIResponse[list[AssigneeTypeOut]])
async def assignee_types():
    return ok(WorkflowService.remote_assignee_types())

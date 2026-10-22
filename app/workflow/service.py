import uuid

from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.modules.forms.exceptions import FormNotFoundError
from app.modules.forms.registry import get_definition
from app.modules.forms.repository import FormRepository
from app.workflow.conditions import rule_fields
from app.workflow.models import AssigneeType, Workflow, WorkflowStep
from app.workflow.schemas import AssigneeTypeOut, StepIn, WorkflowCreate, WorkflowUpdate


class WorkflowNotFoundError(NotFoundError):
    code = "WORKFLOW_NOT_FOUND"

    def __init__(self):
        super().__init__("Workflow not found")


class WorkflowService:
    """Admin side. Editing is safe for in-flight requests: they run on a snapshot."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_all(self, form_code: str | None) -> list[Workflow]:
        stmt = select(Workflow).order_by(Workflow.form_code, Workflow.created_at)
        if form_code:
            stmt = stmt.where(Workflow.form_code == form_code)
        return list(await self.db.scalars(stmt))

    async def get(self, workflow_id: uuid.UUID) -> Workflow:
        workflow = await self.db.get(Workflow, workflow_id)
        if not workflow:
            raise WorkflowNotFoundError()
        return workflow

    async def create(self, data: WorkflowCreate) -> Workflow:
        if not await FormRepository(self.db).get_by_code(data.form_code):
            raise FormNotFoundError()
        await self._validate_steps(data.form_code, data.steps)
        workflow = Workflow(
            form_code=data.form_code,
            name=data.name,
            description=data.description,
            steps=self._build_steps(data.steps),
            completed_status=data.completed_status,
        )
        self.db.add(workflow)
        await self.db.flush()
        return await self._reload(workflow)

    async def update(self, workflow_id: uuid.UUID, data: WorkflowUpdate) -> Workflow:
        workflow = await self.get(workflow_id)
        await self._validate_steps(workflow.form_code, data.steps)

        workflow.name = data.name
        workflow.description = data.description
        workflow.completed_status = data.completed_status
        workflow.steps = []  # delete-orphan removes the old steps first
        await self.db.flush()

        workflow.steps = self._build_steps(data.steps)
        await self.db.flush()
        return await self._reload(workflow)

    async def activate(self, workflow_id: uuid.UUID) -> Workflow:
        """Make this the form's workflow; any other active one for the form is switched off."""
        workflow = await self.get(workflow_id)
        await self.db.execute(
            update(Workflow)
            .where(Workflow.form_code == workflow.form_code, Workflow.id != workflow.id)
            .values(is_active=False)
        )
        await self.db.flush()
        workflow.is_active = True
        await self.db.flush()
        return await self._reload(workflow)

    async def deactivate(self, workflow_id: uuid.UUID) -> Workflow:
        workflow = await self.get(workflow_id)
        workflow.is_active = False
        await self.db.flush()
        return await self._reload(workflow)
    
    @staticmethod
    def remote_assignee_types() -> list[AssigneeTypeOut]:
        ASSIGNEE_TYPE_INFO = {
            AssigneeType.USER: ("Specific user", "One named person.", "user", True),
            AssigneeType.ROLE: ("Everyone with a role", "All active users who have the chosen role.", "role", True),
            AssigneeType.REQUESTER_MANAGER: ("Requester's manager", "The requester's manager.", None, False),
            AssigneeType.DEPARTMENT_HEAD: ("Department head", "The head of the requester's department.", None, False),
            AssigneeType.FORM_FIELD: ("User from a form field", "A user ID taken from the request's form data.", "field", True),
        }
        return [
            AssigneeTypeOut(value=t, label=label, description=desc, needs=needs, supported=supported)
            for t, (label, desc, needs, supported) in ASSIGNEE_TYPE_INFO.items()
        ]

    # --- helpers ---

    @staticmethod
    def _build_steps(steps: list[StepIn]) -> list[WorkflowStep]:
        return [
            WorkflowStep(
                step_no=i,
                **s.model_dump(exclude={"conditions"}),
                conditions=s.conditions_json(),
            )
            for i, s in enumerate(steps, start=1)
        ]

    async def _validate_steps(self, form_code: str, steps: list[StepIn]) -> None:
        fields = set(get_definition(form_code).read_schema.model_fields)
        errors = []
        available = ", ".join(sorted(fields))
        for i, step in enumerate(steps):
            loc = ("body", "steps", i)
            for name in rule_fields(step.conditions_json()):          # fields inside any/all too
                if name not in fields:
                    errors.append(self._err(
                        (*loc, "conditions"), f"Unknown field '{name}'. Available: {available}"
                    ))
            if step.assignee_field and step.assignee_field not in fields:
                errors.append(self._err(
                    (*loc, "assignee_field"),
                    f"Unknown field '{step.assignee_field}'. Available: {available}",
                ))
            if step.return_to.isdigit() and int(step.return_to) >= i + 1:  # only backwards
                errors.append(self._err(
                    (*loc, "return_to"), "Can only return to an earlier step number"
                ))
            # (keep the existing user / role existence checks here)
            
        if errors:
            raise RequestValidationError(errors)

    @staticmethod
    def _err(loc: tuple, msg: str) -> dict:
        return {"type": "value_error", "loc": loc, "msg": msg, "input": None}

    async def _reload(self, workflow: Workflow) -> Workflow:
        await self.db.refresh(workflow, attribute_names=["steps", "updated_at", "created_at"])
        return workflow
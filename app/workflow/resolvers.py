import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from app.modules.forms.data import load_form_row
from app.modules.requests.models import Request
from app.modules.users.models import User, user_roles
from app.shared.utils import get_by_path
from app.workflow.models import AssigneeType


async def resolve_step_users(
    db: AsyncSession, request: Request, step: dict[str, Any]
) -> list[uuid.UUID]:
    requester = await db.get(User, request.requester_id)
    kind = AssigneeType(step["assignee_type"])
    ids: list[uuid.UUID] = []

    if kind == AssigneeType.USER and step["assignee_user_id"]:
        ids = _user(step)

    elif kind == AssigneeType.ROLE and step["assignee_role_id"]:
        ids = await _role(db, step)

    elif kind is AssigneeType.FORM_FIELD and step["assignee_field"]:
        ids = await _form_field(db, request, step)

    # elif kind is AssigneeType.REQUESTER_MANAGER and requester.manager_id:
    #         ids = [requester.manager_id]

    # elif kind is AssigneeType.DEPARTMENT_HEAD and requester.department_id:
    #     head_id = await db.scalar(
    #         select(Department.head_id).where(Department.id == requester.department_id)
    #     )
    #     ids = [head_id] if head_id else []

    if ids:  # only active users
        ids = list(await db.scalars(
            select(User.id).where(User.id.in_(ids), User.is_active)
        ))
    if step["skip_if_requester"]:
        ids = [i for i in ids if i != request.requester_id]

    return ids


def _user(step: dict[str, Any]) -> list[uuid.UUID]:
    user_id = step.get("assignee_user_id")
    return [uuid.UUID(user_id)]


async def _role(db: AsyncSession, step: dict[str, Any]) -> list[uuid.UUID]:
    role_id = step.get("assignee_role_id")
    return list(
        await db.scalars(
            select(user_roles.c.user_id).where(
                user_roles.c.role_id == uuid.UUID(role_id)
            )
        )
    )


async def _form_field(
    db: AsyncSession, request: Request, step: dict[str, Any]
) -> list[uuid.UUID]:
    field_name = step.get("assignee_field")
    form_data_json = await _form_data(db, request)
    value = get_by_path(form_data_json, field_name)
    values = value if isinstance(value, list) else [value]
    return [v if isinstance(v, uuid.UUID) else uuid.UUID(str(v)) for v in values if v]


async def _form_data(db: AsyncSession, request: Request) -> dict[str, Any]:
    definition, row = await load_form_row(db, request)
    return definition.read_schema.model_validate(row).model_dump()

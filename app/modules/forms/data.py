from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.forms.plugin import FormDataMixin, FormDefinition
from app.modules.forms.registry import get_definition

if TYPE_CHECKING:
    from app.modules.requests.models import Request


async def load_form_row(
    db: AsyncSession, request: "Request"
) -> tuple[FormDefinition, FormDataMixin | None]:
    """The form's definition and its data row for this request."""
    definition = get_definition(request.form_code)
    row = await db.scalar(
        select(definition.model).where(definition.model.request_id == request.id)
    )
    return definition, row


async def load_form_data(db: AsyncSession, request: Request) -> dict[str, Any]:
    definition, row = await load_form_row(db, request)
    return definition.read_schema.model_validate(row).model_dump()
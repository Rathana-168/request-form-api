"""Contract every form plugin implements.

A plugin lives in app/modules/forms/definitions/<name>/ and exports `definition`.
The requests/workflow modules only talk to forms through FormDefinition.
"""

import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import ForeignKey, inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.modules.requests.models import Request
    from app.modules.users.models import User


class FormDataMixin(UUIDMixin, TimestampMixin):
    """Base for every form's own table: one row per request."""

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"), unique=True
    )


def build_instance(model: type, data: dict[str, Any]) -> Any:
    """Create a model instance; list fields that are relationships become child rows.

    Works at any depth (items -> sub-items). A child with a `line_no` column gets its
    position in the list when the payload doesn't set it.
    """
    rels = sa_inspect(model).relationships
    values: dict[str, Any] = {}
    for key, value in data.items():
        rel = rels.get(key)
        if rel is not None and rel.uselist:
            values[key] = _build_children(rel.mapper.class_, value or [])
        else:
            values[key] = value
    return model(**values)


def apply_values(row: Any, data: dict[str, Any]) -> None:
    """Set fields on a row. A child list is replaced as a whole (delete-orphan drops old rows)."""
    rels = sa_inspect(type(row)).relationships
    for key, value in data.items():
        rel = rels.get(key)
        if rel is not None and rel.uselist:
            setattr(row, key, _build_children(rel.mapper.class_, value or []))
        else:
            setattr(row, key, value)


def _build_children(model: type, items: list[dict[str, Any]]) -> list[Any]:
    has_line_no = "line_no" in sa_inspect(model).columns
    children = []
    for i, item in enumerate(items, start=1):
        if has_line_no and item.get("line_no") is None:
            item = {**item, "line_no": i}
        children.append(build_instance(model, item))
    return children


@dataclass
class FormContext:
    """What a hook receives. Hooks run inside the caller's transaction."""

    db: AsyncSession
    request: "Request"
    user: "User"
    definition: "FormDefinition"


class FormHooks:
    """Override only what the form needs. All hooks are optional.

    Raise an AppException subclass to block the action.
    """

    # --- building the form row (drafts: create and edit) ---
    async def build(self, ctx: FormContext, data: BaseModel) -> FormDataMixin:
        """Create the form row from validated create_schema data. The core sets request_id."""
        return build_instance(ctx.definition.model, data.model_dump())

    async def apply_update(
        self, ctx: FormContext, row: FormDataMixin, data: BaseModel, fields: set[str]
    ) -> None:
        """Apply an edit. `data` is the full, re-validated form; `fields` are the ones sent."""
        apply_values(row, data.model_dump(include=fields))

    # --- lifecycle ---
    async def validate(self, ctx: FormContext, data: Any) -> None:
        """Business rules beyond the schema (overlaps, balances...). Runs on submit."""

    async def on_submit(self, ctx: FormContext, data: Any) -> None:
        """After validate, on first submit and on resubmit."""

    async def on_approved(self, ctx: FormContext, data: Any) -> None:
        """All workflow steps approved."""

    async def on_rejected(self, ctx: FormContext, data: Any) -> None: ...

    async def on_returned(self, ctx: FormContext, data: Any) -> None: ...

    async def on_cancelled(self, ctx: FormContext, data: Any) -> None: ...

    async def on_step_approved(self, ctx: FormContext, data: Any, step: dict) -> None:
        """One step completed with approval. step["step_no"], step["name"] tell which."""

    async def on_step_rejected(self, ctx: FormContext, data: Any, step: dict) -> None: ...


@dataclass(frozen=True)
class FormDefinition:
    code: str  # matches forms.code, e.g. "LEAVE_REQUEST"
    prefix: str  # request number prefix, e.g. "LEAVE" -> LEAVE-2026-00001
    model: type[FormDataMixin]  # the form's own table
    create_schema: type[BaseModel]  # full payload (submit / create draft)
    update_schema: type[BaseModel]  # partial payload (edit draft / returned)
    read_schema: type[BaseModel]  # response + history snapshot
    hooks: FormHooks = field(default_factory=FormHooks)
    router: APIRouter | None = None  # custom endpoints, mounted at /forms/<slug>

    @property
    def slug(self) -> str:
        return self.code.lower().replace("_", "-")
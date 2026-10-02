import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments.repository import CommentRepository
from app.modules.forms.exceptions import FormInactiveError, FormNotFoundError
from app.modules.forms.plugin import FormContext, FormDataMixin, FormDefinition
from app.modules.forms.registry import get_definition
from app.modules.forms.repository import FormRepository
from app.modules.requests.access import can_view_request
from app.modules.requests.exceptions import (
    InvalidRequestStatusError,
    NotRequesterError,
    RequestNotFoundError,
)
from app.modules.requests.models import (
    EDITABLE_STATUSES,
    HistoryAction,
    Request,
    RequestHistory,
    RequestStatus,
)
from app.modules.requests.repository import RequestRepository
from app.modules.requests.schemas import RequestCreate, RequestUpdate
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams
from app.workflow import engine
from app.modules.approvals.repository import ApprovalProxyRepository, ApprovalRepository

CANCELLABLE = {RequestStatus.IN_PROGRESS, RequestStatus.RETURNED}


def _validate[S: BaseModel](schema: type[S], data: dict[str, Any]) -> S:
    """Run a plugin schema; report errors as a normal 422 under body.data."""
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        errors = [{**err, "loc": ("body", "data", *err["loc"])} for err in e.errors()]
        raise RequestValidationError(errors) from None


class RequestService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = RequestRepository(db)
        self.forms = FormRepository(db)
        self.approvals = ApprovalRepository(db)
        self.proxies = ApprovalProxyRepository(db)

    # --- queries ---

    async def get_detail(self, request_id: uuid.UUID, user: User) -> dict[str, Any]:
        request = await self._get(request_id)
        if not await can_view_request(self.db, request, user):
            raise RequestNotFoundError()  # don't reveal other people's requests
        return await self._detail(request, user=user)

    async def detail_for(self, request: Request, user: User) -> dict[str, Any]:
        """Response body for a request the caller already has access to."""
        return await self._detail(request, user=user)

    async def list_mine(
        self,
        user: User,
        params: PageParams,
        *,
        status: RequestStatus | None,
        form_code: str | None,
    ) -> Page:
        items, total = await self.repo.list_for_requester(
            user.id, offset=params.offset, limit=params.size, status=status, form_code=form_code
        )
        return Page(items=items, total=total, page=params.page, size=params.size)

    # --- requester actions ---

    async def create_draft(self, payload: RequestCreate, user: User) -> dict[str, Any]:
        form = await self.forms.get_by_code(payload.form_code)
        if not form:
            raise FormNotFoundError()
        if not form.is_active:
            raise FormInactiveError()
        definition = get_definition(form.code)
        data = _validate(definition.create_schema, payload.data)

        request = await self.repo.add(Request(form_code=form.code, requester_id=user.id))
        row = await definition.hooks.build(self._ctx(request, user, definition), data)
        row.request_id = request.id
        await self.repo.add_data(row)

        await self._log(request, HistoryAction.CREATED, user)
        return await self._detail(request, definition, user)

    async def update(
        self, request_id: uuid.UUID, payload: RequestUpdate, user: User
    ) -> dict[str, Any]:
        request = await self._get_own(request_id, user, for_update=True)
        self._require(request, EDITABLE_STATUSES, "edit")
        definition = get_definition(request.form_code)
        row = await self._data(definition, request)

        changes = _validate(definition.update_schema, payload.data).model_dump(exclude_unset=True)
        merged = {**definition.read_schema.model_validate(row).model_dump(), **changes}
        # Re-check the full payload so cross-field rules (e.g. date ranges) still hold
        full = _validate(definition.create_schema, merged)
        ctx = self._ctx(request, user, definition)
        await definition.hooks.apply_update(ctx, row, full, set(changes))
        await self.db.flush()
        return await self._detail(request, definition, user)

    async def submit(self, request_id: uuid.UUID, user: User) -> dict[str, Any]:
        request = await self._get_own(request_id, user, for_update=True)
        self._require(request, EDITABLE_STATUSES, "submit")
        definition = get_definition(request.form_code)
        row = await self._data(definition, request)

        ctx = self._ctx(request, user, definition)
        await definition.hooks.validate(ctx, row)
        await definition.hooks.on_submit(ctx, row)

        is_resubmit = request.status == RequestStatus.RETURNED
        request.status = RequestStatus.IN_PROGRESS
        request.submitted_at = datetime.now(UTC)
        await engine.start(self.db, request, user)

        # take the ticket no after process done
        if not request.request_no:
            request.request_no = await self.repo.next_request_no(definition.prefix)

        await self._log(
            request,
            HistoryAction.RESUBMITTED if is_resubmit else HistoryAction.SUBMITTED,
            user,
            snapshot=definition.read_schema.model_validate(row).model_dump(mode="json"),
        )
        return await self._detail(request, definition, user)

    async def cancel(
        self, request_id: uuid.UUID, user: User, comment: str | None
    ) -> dict[str, Any]:
        request = await self._get_own(request_id, user, for_update=True)
        self._require(request, CANCELLABLE, "cancel")
        definition = get_definition(request.form_code)
        row = await self._data(definition, request)

        await definition.hooks.on_cancelled(self._ctx(request, user, definition), row)
        await engine.cancel(self.db, request)
        request.status = RequestStatus.CANCELLED
        request.completed_at = datetime.now(UTC)
        await self._log(request, HistoryAction.CANCELLED, user, comment=comment)
        return await self._detail(request, definition, user)

    async def delete_draft(self, request_id: uuid.UUID, user: User) -> None:
        request = await self._get_own(request_id, user, for_update=True)
        self._require(request, {RequestStatus.DRAFT}, "delete")
        await self.repo.delete(request)

    # --- helpers ---
    def _ctx(self, request: Request, user: User, definition: FormDefinition) -> FormContext:
        return FormContext(db=self.db, request=request, user=user, definition=definition)

    async def _get(self, request_id: uuid.UUID, *, for_update: bool = False) -> Request:
        request = await self.repo.get(request_id, for_update=for_update)
        if not request:
            raise RequestNotFoundError()
        return request

    async def _get_own(
        self, request_id: uuid.UUID, user: User, *, for_update: bool = False
    ) -> Request:
        request = await self._get(request_id, for_update=for_update)
        if request.requester_id != user.id:
            raise NotRequesterError()
        return request

    @staticmethod
    def _require(request: Request, allowed: set[RequestStatus], action: str) -> None:
        if request.status not in allowed:
            raise InvalidRequestStatusError(action, request.status)

    async def _data(self, definition: FormDefinition, request: Request) -> FormDataMixin:
        row = await self.repo.get_data(definition.model, request.id)
        if row is None:  # should never happen: created together with the request
            raise RuntimeError(f"Form data missing for request {request.id}")
        return row

    async def _log(
        self,
        request: Request,
        action: HistoryAction,
        user: User,
        *,
        comment: str | None = None,
        snapshot: dict[str, Any] | None = None,
    ) -> None:
        await self.repo.add_history(
            RequestHistory(
                request_id=request.id,
                action=action,
                actor_id=user.id,
                step_no=request.current_step,
                comment=comment,
                data_snapshot=snapshot,
            )
        )

    async def _detail(
        self, request: Request, definition: FormDefinition | None = None, user: User | None = None
    ) -> dict[str, Any]:
        definition = definition or get_definition(request.form_code)
        await self.db.refresh(request)  # pick up server-side updated_at
        row = await self._data(definition, request)
        return {
            **{c: getattr(request, c) for c in (
                "id", "request_no", "form_code", "status", "requester", "current_step",
                "submitted_at", "completed_at", "created_at", "updated_at", "stage"
            )},
            "data": definition.read_schema.model_validate(row).model_dump(mode="json"),
            "history": await self.repo.list_history(request.id),\
            "approvals": await self.approvals.for_request(request.id),
            "available_actions": await engine.available_actions(self.db, request, user) if user else [],
            "approval_steps": [{"order": s["step_no"], "label": s["name"]} for s in engine.steps_of(request)],
            "comment_count": await CommentRepository(self.db).count_for_request(request.id),
        }

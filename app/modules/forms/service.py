import uuid

from app.modules.forms.exceptions import (
    FormCodeExistsError,
    FormInactiveError,
    FormNotFoundError,
    UnknownFormError,
)
from app.modules.forms.models import Form
from app.modules.forms.repository import FormRepository
from app.modules.forms.schemas import FormCreate, FormUpdate
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams


class FormService:
    def __init__(self, repo: FormRepository):
        self.repo = repo

    async def get(self, form_id: uuid.UUID) -> Form:
        form = await self.repo.get(form_id)
        if not form:
            raise FormNotFoundError()
        return form

    async def get_active_by_code(self, code: str) -> Form:
        """Used by the requests module before accepting a submission."""
        form = await self.repo.get_by_code(code)
        if not form:
            raise FormNotFoundError()
        if not form.is_active:
            raise FormInactiveError()
        return form

    async def list(
        self,
        params: PageParams,
        *,
        active_only: bool,
        search: str | None,
        category: str | None,
    ) -> Page:
        items, total = await self.repo.list(
            offset=params.offset,
            limit=params.size,
            active_only=active_only,
            search=search,
            category=category,
        )
        return Page(items=items, total=total, page=params.page, size=params.size)

    async def available_codes(self) -> list[str]:
        """Codes with a schema in code but no row in the DB yet."""
        return sorted(set(FORM_SCHEMAS) - await self.repo.list_codes())

    async def create(self, data: FormCreate, created_by: User) -> Form:
        if data.code not in FORM_SCHEMAS:
            raise UnknownFormError(f"No schema registered for form '{data.code}'")
        if await self.repo.get_by_code(data.code):
            raise FormCodeExistsError()
        form = Form(**data.model_dump(), created_by_id=created_by.id)
        return await self.repo.add(form)

    async def update(self, form_id: uuid.UUID, data: FormUpdate) -> Form:
        form = await self.get(form_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(form, field, value)
        return form

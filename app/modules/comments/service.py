import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.comments.exceptions import (
    CommentNotFoundError, CommentsClosedError, NotCommentAuthorError,
)
from app.modules.comments.models import RequestComment
from app.modules.comments.repository import CommentRepository
from app.modules.comments.schemas import CommentOut
from app.modules.requests.access import acting_for, can_view_request
from app.modules.requests.exceptions import RequestNotFoundError
from app.modules.requests.models import Request, RequestStatus
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams

OPEN_STATUSES = {RequestStatus.DRAFT, RequestStatus.IN_PROGRESS, RequestStatus.RETURNED}


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommentRepository(db)

    async def list(self, request_id: uuid.UUID, user: User, params: PageParams) -> Page[CommentOut]:
        request = await self._visible_request(request_id, user)
        items, total = await self.repo.list_for_request(
            request.id, offset=params.offset, limit=params.size
        )
        return Page.of([self._out(c, request, user) for c in items], total, params)

    async def add(self, request_id: uuid.UUID, user: User, body: str) -> CommentOut:
        request = await self._visible_request(request_id, user)
        self._ensure_open(request)
        comment = RequestComment(
            request_id=request.id,
            author_id=user.id,
            on_behalf_of_id=await acting_for(self.db, request, user),
            body=self._clean(body),
        )
        self.repo.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)  # load created_at and relationships
        # Step 3: notify participants
        return self._out(comment, request, user)

    async def edit(
        self, request_id: uuid.UUID, comment_id: uuid.UUID, user: User, body: str
    ) -> CommentOut:
        request, comment = await self._own_comment(request_id, comment_id, user)
        comment.body = self._clean(body)
        comment.edited_at = datetime.now(UTC)
        await self.db.flush()
        return self._out(comment, request, user)

    async def delete(self, request_id: uuid.UUID, comment_id: uuid.UUID, user: User) -> None:
        _, comment = await self._own_comment(request_id, comment_id, user)
        comment.deleted_at = datetime.now(UTC)
        await self.db.flush()

    # ---------- helpers ----------

    async def _visible_request(self, request_id: uuid.UUID, user: User) -> Request:
        request = await self.db.get(Request, request_id)
        if request is None or not await can_view_request(self.db, request, user):
            raise RequestNotFoundError()  # don't reveal other people's requests
        return request

    async def _own_comment(
        self, request_id: uuid.UUID, comment_id: uuid.UUID, user: User
    ) -> tuple[Request, RequestComment]:
        request = await self._visible_request(request_id, user)
        comment = await self.repo.get(comment_id)
        if comment is None or comment.request_id != request.id or comment.deleted_at:
            raise CommentNotFoundError()
        if comment.author_id != user.id:
            raise NotCommentAuthorError()
        self._ensure_open(request)
        return request, comment

    @staticmethod
    def _ensure_open(request: Request) -> None:
        if request.status not in OPEN_STATUSES:
            raise CommentsClosedError()

    @staticmethod
    def _clean(body: str) -> str:
        text = body.strip()
        if not text:
            raise RequestValidationError(
                [{"loc": ("body", "body"), "msg": "Comment can't be empty", "type": "value_error"}]
            )
        return text

    @staticmethod
    def _out(comment: RequestComment, request: Request, user: User) -> CommentOut:
        deleted = comment.deleted_at is not None
        return CommentOut(
            id=comment.id,
            body=None if deleted else comment.body,
            author=comment.author,
            on_behalf_of=comment.on_behalf_of,
            created_at=comment.created_at,
            edited_at=comment.edited_at,
            is_deleted=deleted,
            can_edit=(
                not deleted
                and comment.author_id == user.id
                and request.status in OPEN_STATUSES
            ),
        )
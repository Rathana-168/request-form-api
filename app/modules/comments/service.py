import uuid
from datetime import UTC, datetime

from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.repository import ApprovalRepository
from app.modules.attachments.service import AttachmentService
from app.modules.comments.exceptions import (
    CommentNotFoundError, CommentsClosedError, NotCommentAuthorError,
)
from app.modules.comments.models import RequestComment
from app.modules.comments.repository import CommentRepository
from app.modules.comments.schemas import CommentCreate, CommentOut
from app.modules.requests.access import acting_for, can_view_request
from app.modules.requests.exceptions import RequestNotFoundError
from app.modules.requests.models import Request, RequestStatus
from app.modules.users.models import User
from app.shared.schemas import Page
from app.workflow import engine
from app.workflow.enums import WorkflowEvent
from app.workflow.events import dispatch

OPEN_STATUSES = {RequestStatus.DRAFT, RequestStatus.IN_PROGRESS, RequestStatus.RETURNED}


class CommentService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = CommentRepository(db)
        self.approvals = ApprovalRepository(db)

    async def list(self, request_id, user, params) -> Page[CommentOut]:
        request = await self._visible_request(request_id, user)
        rows, total = await self.repo.list_for_request(
            request.id, offset=params.offset, limit=params.size
        )
        return Page.of(
            [self._out(c, request, user, reply_count=n, last_reply_at=last) for c, n, last in rows],
            total, params,
        )

    async def list_replies(self, request_id, comment_id, user, params) -> Page[CommentOut]:
        request = await self._visible_request(request_id, user)
        parent = await self._thread_parent(request, comment_id)
        items, total = await self.repo.list_replies(parent.id, offset=params.offset, limit=params.size)
        return Page.of([self._out(c, request, user) for c in items], total, params)

    async def add(self, request_id: uuid.UUID, user: User, comment: CommentCreate) -> CommentOut:
        request = await self._visible_request(request_id, user)
        return await self._create(request, user, comment, parent_id=None)

    async def reply(self, request_id, comment_id, user, body) -> CommentOut:
        request = await self._visible_request(request_id, user)
        parent = await self._thread_parent(request, comment_id)
        return await self._create(request, user, body, parent_id=parent.id)

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
    
    async def _create(self, request: Request, user: User, body: CommentCreate, *, parent_id: uuid.UUID | None = None) -> CommentOut:
        self._ensure_open(request)
        attachments = await AttachmentService(self.db).load(set(body.attachments), user)
        comment = RequestComment(
            request_id=request.id,
            parent_id=parent_id,
            author_id=user.id,
            on_behalf_of_id=await acting_for(self.db, request, user),
            body=self._clean(body.body),
            attachments=attachments
        )
        self.repo.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        await self._notify(request, comment, user)
        return self._out(comment, request, user)

    async def _thread_parent(self, request: Request, comment_id: uuid.UUID) -> RequestComment:
        parent = await self.repo.get(comment_id)
        if parent is None or parent.request_id != request.id or parent.parent_id is not None:
            raise CommentNotFoundError()  # missing, wrong request, or a reply (no nesting)
        return parent
    
    async def _notify(self, request: Request, comment: RequestComment, user: User) -> None:
        if comment.parent_id:
            event = WorkflowEvent.COMMENT_REPLIED
            user_ids = await self.repo.thread_participant_ids(comment.parent_id)
        else:
            event = WorkflowEvent.COMMENT_ADDED
            user_ids = [
                request.requester_id,
                *await self._pending_approver_ids(request),
                *await self.repo.commenter_ids(request.id),
            ]
        await dispatch(
            self.db, event, request, user,
            user_ids=list(set(user_ids)),
            extra={"actor": self._actor_label(comment, user), "excerpt": self._excerpt(comment.body)},
        )

    async def _pending_approver_ids(self, request: Request) -> list[uuid.UUID]:
        tasks = await self.approvals.pending_approval_tasks(request.id)
        assignees = [i.assignee_id for i in tasks]
        ids = list(assignees)
        for a in assignees:
            ids += await engine.proxy_ids_for(self.db, a, request)
        return ids

    async def _load_attachment(self, file_ids: list[uuid.UUID]):
        return await AttachmentService(self.db).load(set(body.attachments), user)

    @staticmethod
    def _actor_label(comment: RequestComment, user: User) -> str:
        if comment.on_behalf_of:
            return f"{user.full_name} (on behalf of {comment.on_behalf_of.full_name})"
        return user.full_name

    @staticmethod
    def _excerpt(body: str, limit: int = 100) -> str:
        return body if len(body) <= limit else body[:limit].rstrip() + "…"

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
    def _out(comment: RequestComment, request: Request, user: User, 
             *, reply_count: int = 0, last_reply_at: datetime | None = None
        ) -> CommentOut:
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
            parent_id=comment.parent_id,
            reply_count=reply_count,
            last_reply_at=last_reply_at
        )
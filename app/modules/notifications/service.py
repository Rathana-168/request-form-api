import uuid

from app.modules.notifications.messages import MESSAGES
from app.modules.notifications.models import Notification
from app.modules.notifications.repository import NotificationRepository
from app.modules.requests.models import Request
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams
from app.workflow.enums import WorkflowEvent


class NotificationService:
    def __init__(self, repo: NotificationRepository):
        self.repo = repo

    async def list_mine(
        self, user: User, params: PageParams, unread_only: bool = False
    ) -> Page[Notification]:
        items, total = await self.repo.list_for_user(
            user.id, offset=params.offset, limit=params.size, unread_only=unread_only
        )
        return Page.of(items, total, params)

    async def unread_count(self, user: User) -> int:
        return await self.repo.unread_count(user.id)

    async def mark_read(self, user: User, ids: list[uuid.UUID] | None) -> None:
        await self.repo.mark_read(user.id, ids)

    def create_for_event(
        self, event: WorkflowEvent, request: Request, actor: User, user_ids: list[uuid.UUID],
        *, step: dict | None = None, comment: str | None = None,
    ) -> None:
        template = MESSAGES.get(event)
        recipients = {uid for uid in user_ids if uid != actor.id}  # don't notify yourself
        if not template or not recipients:
            return

        ntype, title, body = template
        values = {
            "no": request.request_no,
            "form": request.form.name,
            "requester": request.requester.full_name,
            "actor": actor.full_name,
            "step": step["name"] if step else "",
            "comment": comment or "",
        }
        self.repo.add_many([
            Notification(
                user_id=uid, type=ntype, request_id=request.id,
                title=title.format(**values),
                body=body.format(**values).strip() if body else None,
            )
            for uid in recipients
        ])
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.exceptions import TaskNotActionableError, TaskNotFoundError
from app.modules.approvals.models import ApprovalTask, TaskStatus
from app.modules.approvals.repository import ApprovalRepository
from app.modules.requests.models import Request, RequestStatus
from app.modules.requests.repository import RequestRepository
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams
from app.workflow import engine

Action = Callable[[AsyncSession, Request, ApprovalTask, User, str | None], Awaitable[None]]


class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ApprovalRepository(db)
        self.requests = RequestRepository(db)

    async def inbox(self, user: User, params: PageParams, form_code: str | None) -> Page:
        rows, total = await self.repo.inbox(
            user.id, offset=params.offset, limit=params.size, form_code=form_code
        )
        items: list[dict[str, Any]] = [
            {
                "id": task.id,
                "step_no": task.step_no,
                "step_name": request.workflow_snapshot[task.step_no - 1]["name"],
                "created_at": task.created_at,
                "request": request,
            }
            for task, request in rows
        ]
        return Page(items=items, total=total, page=params.page, size=params.size)

    async def approve(self, task_id: uuid.UUID, user: User, comment: str | None) -> Request:
        return await self._act(task_id, user, comment, engine.approve)

    async def reject(self, task_id: uuid.UUID, user: User, comment: str | None) -> Request:
        return await self._act(task_id, user, comment, engine.reject)

    async def return_(self, task_id: uuid.UUID, user: User, comment: str | None) -> Request:
        return await self._act(task_id, user, comment, engine.return_to_requester)

    async def _act(
        self, task_id: uuid.UUID, user: User, comment: str | None, action: Action
    ) -> Request:
        task = await self.repo.get(task_id)
        if not task or task.assignee_id != user.id:
            raise TaskNotFoundError()  # don't reveal other people's tasks

        # Lock the request first: two approvers acting at once are serialised here
        request = await self.requests.get(task.request_id, for_update=True)
        await self.db.refresh(task)  # re-read after the lock
        
        if task.status != TaskStatus.PENDING:
            raise TaskNotActionableError(f"This task is already {task.status}")
        if request.status != RequestStatus.IN_PROGRESS or request.current_step != task.step_no:
            raise TaskNotActionableError("The request is no longer waiting on this step")

        await action(self.db, request, task, user, comment)
        await self.db.flush()
        return request
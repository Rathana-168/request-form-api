import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.exceptions import TaskNotActionableError, TaskNotFoundError
from app.modules.approvals.models import ApprovalTask, TaskStatus
from app.modules.approvals.repository import ApprovalProxyRepository, ApprovalRepository
from app.modules.requests.exceptions import RequestNotFoundError
from app.modules.requests.models import Request, RequestStatus
from app.modules.requests.repository import RequestRepository
from app.modules.users.models import User
from app.shared.schemas import Page, PageParams
from app.workflow import engine
from app.workflow.dispatcher import dispatch
from app.workflow.enums import WorkflowEvent

Action = Callable[[AsyncSession, Request, ApprovalTask, User, str | None], Awaitable[None]]
VERBS = {"approve": "approved", "reject": "rejected", "return": "returned"}

class ApprovalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ApprovalRepository(db)
        self.requests = RequestRepository(db)
        self.proxies = ApprovalProxyRepository(db)
        

    async def inbox(self, user: User, params: PageParams, form_code: str | None) -> Page:
        acting_ids = [user.id, *(await self.proxies.principals_of(user.id, datetime.now(UTC)))]
        rows, total = await self.repo.inbox(
            user.id, 
            offset=params.offset, 
            limit=params.size, 
            form_code=form_code, 
            acting_ids=acting_ids
        )
        items: list[dict[str, Any]] = [
            {
                "id": task.id,
                "step_no": task.step_no,
                "step_name": engine.steps_of(request)[task.step_no - 1]["name"],
                "created_at": task.created_at,
                "request": request,
            }
            for task, request in rows
        ]
        return Page(items=items, total=total, page=params.page, size=params.size)

    async def approve(self, task_id: uuid.UUID, user: User, comment: str | None) -> Request:
        return await self._act(task_id, user, comment, engine.approve, "approve")

    async def reject(self, task_id: uuid.UUID, user: User, comment: str | None) -> Request:
        return await self._act(task_id, user, comment, engine.reject, "reject")

    async def return_(self, task_id: uuid.UUID, user: User, comment: str | None) -> Request:
        return await self._act(task_id, user, comment, engine.return_back, "return")

    async def _act(
        self, task_id: uuid.UUID, user: User, comment: str | None, action: Action, action_name: str
    ) -> Request:
        task = await self.repo.get(task_id)
        if not task:
            raise TaskNotFoundError()  # don't reveal other people's tasks

        # Lock the request first: two approvers acting at once are serialised here
        request = await self.requests.get(task.request_id, for_update=True)
        if not request:
            raise RequestNotFoundError()
        await self.db.refresh(task)  # re-read after the lock

        if not await self._can_act(task, request, user):
            raise TaskNotFoundError()  # don't reveal other people's tasks

        if task.status != TaskStatus.PENDING:
            raise TaskNotActionableError(f"This task is already {task.status}")
        if request.status != RequestStatus.IN_PROGRESS or request.current_step != task.step_no:
            raise TaskNotActionableError("The request is no longer waiting on this step")

        task.acted_by_id = user.id
        await action(self.db, request, task, user, comment)

        # Acted as a proxy: let the assignee know, only after the action succeeded
        if task.assignee_id != user.id:
            step = engine.steps_of(request)[task.step_no - 1]
            await dispatch(
                self.db, WorkflowEvent.ACTED_BY_PROXY, request, user,
                step=step, user_ids=[task.assignee_id],
                extra={"proxy": user.full_name, "verb": VERBS[action_name]},
            )

        await self.db.flush()
        return request

    async def _can_act(self, task: ApprovalTask, request: Request, user: User) -> bool:
        if task.assignee_id == user.id:
            return True
        if request.requester_id == user.id:
            return False  # nobody acts on their own request, even as a proxy
        return await self.proxies.can_act_for(user.id, task.assignee_id, datetime.now(UTC))
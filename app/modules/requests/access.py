import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.approvals.models import ApprovalTask
from app.modules.approvals.repository import ApprovalProxyRepository, ApprovalRepository
from app.modules.requests.models import Request
from app.modules.users.models import User


def _is_admin(user: User) -> bool:
    return user.is_superuser or "request:read_all" in user.permission_codes


async def can_view_request(db: AsyncSession, request: Request, user: User) -> bool:
    if request.requester_id == user.id or _is_admin(user):
        return True
    principals = await ApprovalProxyRepository(db).principals_of(user.id, datetime.now(UTC))
    return await ApprovalRepository(db).can_view(request.id, [user.id, *principals])


async def acting_for(db: AsyncSession, request: Request, user: User) -> uuid.UUID | None:
    """The principal this user represents on this request, or None if they're
    here in their own right (requester, own task, or admin)."""
    if request.requester_id == user.id:
        return None
    own_task = await db.scalar(select(ApprovalTask.id).where(
        ApprovalTask.request_id == request.id, ApprovalTask.assignee_id == user.id
    ).limit(1))
    if own_task:
        return None
    principals = await ApprovalProxyRepository(db).principals_of(user.id, datetime.now(UTC))
    if not principals:
        return None
    return await db.scalar(select(ApprovalTask.assignee_id).where(
        ApprovalTask.request_id == request.id, ApprovalTask.assignee_id.in_(principals)
    ).limit(1))
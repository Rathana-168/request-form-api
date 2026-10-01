import uuid
from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.modules.approvals.repository import ApprovalProxyRepository
from app.modules.forms.definitions.proxy_request.schemas import ProxyOut
from app.shared.schemas import APIResponse, ok

router = APIRouter()


@router.get("/mine", response_model=APIResponse[list[ProxyOut]])
async def my_proxies(user: CurrentUser, db: DbSession):
    """Proxies I've given and proxies I hold, running or scheduled."""
    return ok(await ApprovalProxyRepository(db).current_for(user.id, datetime.now(UTC)))


@router.post("/{request_id}/end", response_model=APIResponse[ProxyOut])
async def end_proxy(request_id: uuid.UUID, user: CurrentUser, db: DbSession):
    proxy = await ApprovalProxyRepository(db).open_by_source(request_id)
    if proxy is None:
        raise NotFoundError("No running proxy for this request")
    if proxy.principal_id != user.id:
        raise PermissionDeniedError("Only the person who requested the proxy can end it")
    proxy.ended_at = datetime.now(UTC)
    return ok(proxy)
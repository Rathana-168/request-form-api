from typing import Any, Literal
from urllib.parse import urlparse
import uuid

import httpx
from pydantic import BaseModel, HttpUrl, model_validator

from app.core.config import get_settings
from app.rules.context import ActionContext
from app.rules.registry import ActionError, register_action


# ---------- notify (sync): in-app notification ----------
class NotifyParams(BaseModel):
    to: Literal["requester", "manager", "role", "users"]
    role_code: str | None = None
    user_ids: list[uuid.UUID] = []
    title: str
    message: str

    @model_validator(mode="after")
    def _check_target(self):
        if self.to == "role" and not self.role_code:
            raise ValueError("role_code is required when to = 'role'")
        if self.to == "users" and not self.user_ids:
            raise ValueError("user_ids is required when to = 'users'")
        return self


@register_action("notify", params=NotifyParams, is_async=False,
                 description="Send an in-app notification")
async def notify(ctx: ActionContext, p: NotifyParams) -> None:
    from app.modules.notifications.service import NotificationService
    from app.modules.users.repository import UserRepository

    users = UserRepository(ctx.db)
    match p.to:
        case "requester":
            ids = [ctx.request.requester_id]
        case "manager":
            requester = await users.get(ctx.request.requester_id)
            ids = [requester.manager_id] if requester.manager_id else []
        case "role":
            ids = await users.ids_by_role(p.role_code)
        case "users":
            ids = p.user_ids
    if ids:
        await NotificationService(ctx.db).create_many(
            user_ids=ids, title=p.title, body=p.message, request_id=ctx.request.id,
        )


# ---------- http_call (async): call an external system ----------
class HttpCallParams(BaseModel):
    url: HttpUrl
    method: Literal["POST", "PUT", "PATCH"] = "POST"
    headers: dict[str, str] = {}
    body: dict[str, Any] = {}

    @model_validator(mode="after")
    def _allowed_host(self):
        allowed = get_settings().RULE_HTTP_ALLOWED_HOSTS
        if urlparse(str(self.url)).hostname not in allowed:
            raise ValueError(f"host is not in RULE_HTTP_ALLOWED_HOSTS")
        return self


@register_action("http_call", params=HttpCallParams, is_async=True,
                 description="Call an external API")
async def http_call(ctx: ActionContext, p: HttpCallParams) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.request(p.method, str(p.url), headers=p.headers, json=p.body)
    if resp.status_code >= 400:
        raise ActionError(f"HTTP {resp.status_code}: {resp.text[:500]}")
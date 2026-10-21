from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import status
from sqlalchemy import select

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.modules.approvals.models import ApprovalProxy
from app.modules.approvals.repository import ApprovalProxyRepository
from app.modules.forms.definitions.proxy_request.models import ProxyRequestData
from app.modules.forms.plugin import FormContext, FormHooks
from app.modules.requests.models import Request, RequestStatus
from app.modules.users.models import User


class ProxyRequestError(AppException):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "PROXY_REQUEST_INVALID"


def period_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive dates -> [start of start_date, start of the day after end_date) in company time."""
    tz = ZoneInfo(get_settings().APP_TIMEZONE)
    return (
        datetime.combine(start, time.min, tz),
        datetime.combine(end + timedelta(days=1), time.min, tz),
    )


class ProxyRequestHooks(FormHooks):
    async def validate(self, ctx: FormContext, data: ProxyRequestData) -> None:
        requester_id = ctx.request.requester_id
        today = datetime.now(ZoneInfo(get_settings().APP_TIMEZONE)).date()

        if data.proxy_user_id == requester_id:
            raise ProxyRequestError("You can't be your own proxy")
        if data.end_date < data.start_date:
            raise ProxyRequestError("End date must be on or after start date")
        if data.end_date < today:
            raise ProxyRequestError("The proxy period has already ended")

        proxy_user = await ctx.db.get(User, data.proxy_user_id)
        if proxy_user is None or not proxy_user.is_active:
            raise ProxyRequestError("The selected proxy is not an active user")

        if await self._overlaps(ctx, data):
            raise ProxyRequestError("You already have a proxy for part of this period")

    async def on_approved(self, ctx: FormContext, data: ProxyRequestData) -> None:
        start_at, end_at = period_bounds(data.start_date, data.end_date)
        ApprovalProxyRepository(ctx.db).add(ApprovalProxy(
            principal_id=ctx.request.requester_id,
            proxy_id=data.proxy_user_id,
            start_at=start_at,
            end_at=end_at,
            source_request_id=ctx.request.id,
        ))

    async def _overlaps(self, ctx: FormContext, data: ProxyRequestData) -> bool:
        requester_id = ctx.request.requester_id
        start_at, end_at = period_bounds(data.start_date, data.end_date)

        # an approved proxy that is still running or scheduled
        active = await ctx.db.scalar(select(ApprovalProxy.id).where(
            ApprovalProxy.principal_id == requester_id,
            ApprovalProxy.ended_at.is_(None),
            ApprovalProxy.start_at < end_at,
            ApprovalProxy.end_at > start_at,
        ).limit(1))

        # another proxy request still waiting for acknowledgement
        pending = await ctx.db.scalar(
            select(ProxyRequestData.id)
            .join(Request, Request.id == ProxyRequestData.request_id)
            .where(
                Request.requester_id == requester_id,
                Request.status == RequestStatus.IN_PROGRESS,
                Request.id != ctx.request.id,
                ProxyRequestData.start_date <= data.end_date,
                ProxyRequestData.end_date >= data.start_date,
            ).limit(1)
        )
        return active is not None or pending is not None
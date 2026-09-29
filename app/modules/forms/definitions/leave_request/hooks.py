from sqlalchemy import exists, select

from app.core.exceptions import ConflictError
from app.modules.forms.definitions.leave_request.models import LeaveRequestData
from app.modules.forms.plugin import FormContext, FormHooks
from app.modules.requests.models import Request, RequestStatus

ACTIVE = (RequestStatus.IN_PROGRESS, RequestStatus.APPROVED)


class LeaveHooks(FormHooks):
    async def validate(self, ctx: FormContext, data: LeaveRequestData) -> None:
        overlap = await ctx.db.scalar(
            select(
                exists()
                .where(LeaveRequestData.request_id == Request.id)
                .where(Request.requester_id == ctx.request.requester_id)
                .where(Request.status.in_(ACTIVE))
                .where(Request.id != ctx.request.id)
                .where(LeaveRequestData.start_date <= data.end_date)
                .where(LeaveRequestData.end_date >= data.start_date)
            )
        )
        if overlap:
            raise ConflictError("You already have leave in this date range")

    async def build(self, ctx, data):
        row = await super().build(ctx, data)
        row.days = 1  # computed, not typed by user
        row.contact = row.contact or ctx.user.email                     # default from the requester
        return row
"""Workflow runtime. Only `start` exists for now; approvals come with the workflow models."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.requests.models import Request


async def start(db: AsyncSession, request: Request) -> None:
    """Called on submit and resubmit.

    TODO: pick the form's workflow, snapshot its steps into request.workflow_snapshot,
    set current_step to the first step and assign approvers.
    """
    request.current_step = 1
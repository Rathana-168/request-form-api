from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.modules.forms.definitions.leave_request.constants import LeaveType

router = APIRouter()


@router.get("/types", response_model=list[str])
async def leave_types(_: CurrentUser):
    return [t.value for t in LeaveType]
from app.modules.forms.definitions.leave_request.hooks import LeaveHooks
from app.modules.forms.definitions.leave_request.models import LeaveRequestData
from app.modules.forms.definitions.leave_request.router import router
from app.modules.forms.definitions.leave_request.schemas import (
    LeaveCreate,
    LeaveOut,
    LeaveUpdate,
)
from app.modules.forms.plugin import FormDefinition

definition = FormDefinition(
    code="LEAVE_REQUEST",
    prefix="LEAVE",
    model=LeaveRequestData,
    create_schema=LeaveCreate,
    update_schema=LeaveUpdate,
    read_schema=LeaveOut,
    hooks=LeaveHooks(),
    router=router,
)
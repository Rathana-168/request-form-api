from fastapi import APIRouter

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.requests.router import router as requests_router
from app.modules.approvals.router import router as approvals_router
from app.modules.notifications.router import router as notifications_router
from app.modules.comments.router import router as comments_router
from app.modules.attachments.router import router as attachments_router
from app.workflow.router import router as workflows_router
from app.rules.router import router as rules_router


api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(requests_router, prefix="/requests", tags=["requests"])
api_router.include_router(comments_router, prefix="/requests", tags=["comment"])
api_router.include_router(approvals_router, prefix="/approvals", tags=["approvals"])
api_router.include_router(workflows_router, prefix="/workflows", tags=["workflows"])
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(attachments_router, prefix="/attachments", tags=["attachments"])
api_router.include_router(rules_router, tags=["rules"])


# Register form router will scallable as form increase
from app.modules.forms.registry import load_plugins
from app.modules.forms.router import router as forms_router

for _definition in load_plugins().values():
    if _definition.router:
        api_router.include_router(
            _definition.router,
            prefix=f"/forms/{_definition.slug}",
            tags=[f"form: {_definition.code}"],
        )

api_router.include_router(forms_router, prefix="/forms", tags=["forms"])

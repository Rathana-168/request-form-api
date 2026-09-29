from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.requests.router import router as requests_router


api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(requests_router, prefix="/requests", tags=["requests"])


@api_router.get("/health", tags=["health"])
async def health(db: DbSession):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}

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

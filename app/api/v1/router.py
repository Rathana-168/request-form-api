from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.forms.router import router as form_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users", tags=["users"])
api_router.include_router(form_router, prefix="/form", tags=["form"])


@api_router.get("/health", tags=["health"])
async def health(db: DbSession):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


# Module routers are added here later, e.g.:
# api_router.include_router(forms_router, prefix="/forms", tags=["forms"])

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, DbSession, TokenPayload
from app.modules.auth.providers import build_auth_provider
from app.modules.auth.schemas import RefreshRequest, TokenPair
from app.modules.auth.service import AuthService
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserOut
from app.api.deps import oauth2_scheme


router = APIRouter()


def get_auth_service(db: DbSession) -> AuthService:
    users = UserRepository(db)
    return AuthService(users, build_auth_provider(users))


AuthSvc = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/login", response_model=TokenPair)
async def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], svc: AuthSvc):
    return await svc.login(form.username, form.password)  # username = email


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, svc: AuthSvc):
    return await svc.refresh(body.refresh_token)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user


@router.post("/logout", status_code=204)
async def logout(payload: TokenPayload, svc: AuthSvc):
    await svc.logout(payload["sid"])
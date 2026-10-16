from app.core.config import get_settings
from app.modules.auth.providers.ldap import LdapAuthProvider
from app.modules.users.repository import UserRepository
from .base import AuthProvider
from .local import LocalAuthProvider


def build_auth_provider(users: UserRepository) -> AuthProvider:
    settings = get_settings()
    if settings.AUTH_PROVIDER == "local":
        if settings.ENV == "production":
            raise RuntimeError("Local default-password login is disabled in production")
        return LocalAuthProvider(users)
    
    if settings.AUTH_PROVIDER == "ldap":
        return LdapAuthProvider(users)
    
    raise RuntimeError(f"Unknown AUTH_PROVIDER: {settings.AUTH_PROVIDER}")
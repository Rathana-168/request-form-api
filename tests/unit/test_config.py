import pytest
from pydantic import ValidationError

from app.core.config import Settings

BASE = dict(
    _env_file=None,
    SECRET_KEY="x",
    DATABASE_URL="postgresql+asyncpg://u:p@h/db",
    REDIS_URL="redis://h:6379/0",
    CELERY_BROKER_URL="redis://h:6379/1",
    CELERY_RESULT_BACKEND="redis://h:6379/2",
)
SAFE_PROD = dict(
    ENV="production",
    JWT_SECRET="s" * 40,
    AUTH_PROVIDER="ldap",
    CORS_ORIGINS=["https://workflow.example.com"],
    DEBUG=False,
)


def test_safe_production_settings_load():
    Settings(**BASE, **SAFE_PROD)


@pytest.mark.parametrize("override, message", [
    ({"JWT_SECRET": "short"}, "JWT_SECRET"),
    ({"AUTH_PROVIDER": "local"}, "AUTH_PROVIDER"),
    ({"CORS_ORIGINS": ["*"]}, "CORS_ORIGINS"),
    ({"CORS_ORIGINS": []}, "CORS_ORIGINS"),
    ({"DEBUG": True}, "DEBUG"),
])
def test_unsafe_production_settings_fail(override, message):
    with pytest.raises(ValidationError, match=message):
        Settings(**BASE, **(SAFE_PROD | override))


def test_local_env_is_not_checked():
    Settings(**BASE, ENV="local", JWT_SECRET="short", AUTH_PROVIDER="local")
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", ".env.local"), extra="ignore")

    # App
    APP_NAME: str = "Workflow Service"
    ENV: str = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str
    CORS_ORIGINS: list[str] = []
    CIF_LOOKUP_FIELD: str = 'staff_id'
    APP_TIMEZONE: str = "Asia/Phnom_Penh"
    # End App

    # Database
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "public"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    # End Database

    # Reis & Worker
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    # End Database

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # End JWT

    # Worker & CRON 
    SLA_CHECK_CRON: str = "*/10 * * * *"
    # End Worker & CRON 


@lru_cache
def get_settings() -> Settings:
    return Settings()

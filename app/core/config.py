from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServiceConfig(BaseModel):
    url: str
    api_key: str = ""
    timeout: float = 5.0
    retries: int = 2
    

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"), 
        extra="ignore",
        env_nested_delimiter="__",   # FILE_SERVICE__URL -> settings.FILE_SERVICE.url
    )

    # App
    APP_NAME: str = "Workflow Service"
    ENV: str = "local"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str
    CORS_ORIGINS: list[str] = []
    CIF_LOOKUP_FIELD: str = 'staff_id'
    APP_TIMEZONE: str = "Asia/Phnom_Penh"
    MAX_UPLOAD_MB: int = 10

    # Database
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "public"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Reis & Worker
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Kafka
    KAFKA_WORKFLOW_TOPIC: str = "nexgen.workflow.events"
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    OUTBOX_RELAY_SECONDS: int = 5
    OUTBOX_BATCH_SIZE: int = 100

    # Intergration Service
    FILE_SERVICE: ServiceConfig = ServiceConfig(url="http://localhost:8001")

    # Task & CRONTab
    SLA_CHECK_CRON: str = "*/10 * * * *"
    
    OUTBOX_RETENTION_DAYS: int = 7
    OUTBOX_CLEANUP_CRON: str = "30 2 * * *"   # daily at 02:30
    OUTBOX_STUCK_MINUTES: int = 15
        
    ATTACHMENT_CLEANUP_CRON: str = "0 3 * * *"   # daily 03:00
    ATTACHMENT_UNUSED_HOURS: int = 24
    ATTACHMENT_USE_REQUEST_ID: bool = True 


@lru_cache
def get_settings() -> Settings:
    return Settings()

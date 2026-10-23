from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, model_validator
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

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: Literal["text", "json"] = "text"

    # Login
    AUTH_PROVIDER: str = "local"          # later: "ldap"
    DEFAULT_PASSWORD: str = "admin"       # temporary, until LDAP

    # Rule Engine
    RULE_HTTP_ALLOWED_HOSTS: list[str] = []
    RULE_ACTIONS_POLL_SECONDS: int = 10
    RULE_ACTIONS_BATCH_SIZE: int = 20
    RULE_ACTION_MAX_ATTEMPTS: int = 5
    RULE_ACTION_LEASE_SECONDS: int = 300   # how long a claimed row is hidden from other runs

    # Database
    DATABASE_URL: str
    DATABASE_SCHEMA: str = "public"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Redis & Worker
    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
    REDIS_CONNECT_TIMEOUT: float = 1.0
    REDIS_SOCKET_TIMEOUT: float = 1.0
    REDIS_RETRIES: int = 1
    REDIS_MAX_CONNECTIONS: int = 50
    REVOCATION_FAIL_OPEN: bool = False

    # JWT
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LDAP
    LDAP_URL: str = "ldaps://ldap.company.local:636"
    LDAP_BIND_DN: str = ""            # service account DN
    LDAP_BIND_PASSWORD: str = ""
    LDAP_BASE_DN: str = "dc=company,dc=local"
    LDAP_STAFF_ID_ATTR: str = "sAMAccountName"   # or employeeID, depending on your directory
    LDAP_TIMEOUT: int = 5

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
    
    @model_validator(mode="after")
    def _check_production(self):
        if self.ENV != "production":
            return self

        problems = []
        if len(self.JWT_SECRET) < 32:
            problems.append("JWT_SECRET must be at least 32 characters")
        if self.AUTH_PROVIDER != "ldap":
            problems.append("AUTH_PROVIDER must be 'ldap' (local login is for testing only)")
        if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
            problems.append("CORS_ORIGINS must list the allowed frontend URLs (no '*')")
        if self.DEBUG:
            problems.append("DEBUG must be false")

        if problems:
            raise ValueError("Unsafe production settings: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
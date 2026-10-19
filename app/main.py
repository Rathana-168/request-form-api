from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.rules.actions  # noqa: F401

from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.api.v1.router import api_router
from app.api.health import router as health_router
from app.db import query_counter
from app.db.session import engine
from app.integrations.registry import close_all_client_services
from app.integrations.redis import close_redis


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield
    await close_all_client_services()
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    if settings.DB_ECHO: # dev only: SQL count per request
        query_counter.install(app, engine)
        
    return app


app = create_app()

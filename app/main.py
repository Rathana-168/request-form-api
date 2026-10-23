from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.context import TRACE_HEADER
import app.rules.actions
from app.api.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import TraceIdMiddleware
from app.db import query_counter
from app.db.session import engine
from app.integrations.redis import close_redis
from app.integrations.registry import close_all_client_services


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    yield
    await close_all_client_services()
    await close_redis()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    is_prod = settings.ENV == "production"

    app = FastAPI(
        title=settings.APP_NAME, 
        debug=settings.DEBUG, 
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"], 
        expose_headers=[TRACE_HEADER]
    )
    app.add_middleware(TraceIdMiddleware)
    
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    
    if settings.DB_ECHO: # dev only: SQL count per request
        query_counter.install(app, engine)
        
    return app


app = create_app()

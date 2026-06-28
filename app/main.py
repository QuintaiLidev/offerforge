from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging

from fastapi import Depends, FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.api.auth import require_basic_auth
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.seed import seed_knowledge_cards_if_empty
from app.web.app_page import router as app_page_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    init_db()
    run_auto_seed(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    application.include_router(api_router, prefix=settings.api_v1_prefix)
    application.include_router(
        app_page_router,
        dependencies=[Depends(require_basic_auth)],
    )
    register_root_redirect(application)
    register_documentation_routes(application)
    return application


def run_auto_seed(settings: Settings) -> int:
    if not settings.auto_seed_on_startup:
        logger.info("Auto seed disabled.")
        return 0

    with SessionLocal() as db:
        return seed_knowledge_cards_if_empty(db, settings.auto_seed_path)


def register_root_redirect(application: FastAPI) -> None:
    @application.get("/", include_in_schema=False)
    def redirect_to_app() -> RedirectResponse:
        return RedirectResponse(url="/app", status_code=307)


def register_documentation_routes(application: FastAPI) -> None:
    @application.get(
        "/docs",
        include_in_schema=False,
        dependencies=[Depends(require_basic_auth)],
    )
    def swagger_ui_html() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=f"{application.title} - Swagger UI",
        )

    @application.get(
        "/openapi.json",
        include_in_schema=False,
        dependencies=[Depends(require_basic_auth)],
    )
    def openapi_json() -> JSONResponse:
        return JSONResponse(application.openapi())


app: FastAPI = create_app()

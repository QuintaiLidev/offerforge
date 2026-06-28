from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
from threading import Thread

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
    try:
        application.state.auto_seed_thread = start_auto_seed_background(get_settings())
    except Exception:
        logger.exception("Auto seed failed during startup; continue without seed.")
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

    db = SessionLocal()
    try:
        return seed_knowledge_cards_if_empty(db, settings.auto_seed_path)
    except Exception:
        logger.exception("Auto seed failed during startup; continue without seed.")
        return 0
    finally:
        db.close()


def start_auto_seed_background(settings: Settings) -> Thread | None:
    if not settings.auto_seed_on_startup:
        logger.info("Auto seed disabled.")
        return None

    thread = Thread(
        target=_run_auto_seed_background,
        args=(settings,),
        name="offerforge-auto-seed",
        daemon=True,
    )
    thread.start()
    return thread


def _run_auto_seed_background(settings: Settings) -> None:
    try:
        run_auto_seed(settings)
    except Exception:
        logger.exception("Auto seed failed during startup; continue without seed.")


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

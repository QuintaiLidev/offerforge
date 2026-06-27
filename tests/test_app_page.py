from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import create_app

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def make_client() -> AsyncIterator[httpx.AsyncClient]:
    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            yield client


async def test_app_page_auth_disabled_returns_mobile_review_page(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.delenv("OFFERFORGE_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()

    async for client in make_client():
        response = await client.get("/app")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "OfferForge" in response.text
    assert "今日复习" in response.text
    assert "/api/v1/reviews/today" in response.text
    assert "/api/v1/practice-attempts" in response.text
    assert "answer_text" in response.text


async def test_app_page_auth_enabled_protects_app_but_not_health(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    async for client in make_client():
        health = await client.get("/api/v1/health")
        app_without_auth = await client.get("/app")
        app_with_auth = await client.get(
            "/app",
            auth=("offerforge", "test-secret"),
        )

    assert health.status_code == 200
    assert app_without_auth.status_code == 401
    assert app_without_auth.headers["www-authenticate"] == "Basic"
    assert app_with_auth.status_code == 200
    assert "OfferForge" in app_with_auth.text


async def test_app_page_does_not_break_docs_and_openapi_auth(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    async for client in make_client():
        docs_without_auth = await client.get("/docs")
        openapi_without_auth = await client.get("/openapi.json")
        docs_with_auth = await client.get(
            "/docs",
            auth=("offerforge", "test-secret"),
        )
        openapi_with_auth = await client.get(
            "/openapi.json",
            auth=("offerforge", "test-secret"),
        )

    assert docs_without_auth.status_code == 401
    assert openapi_without_auth.status_code == 401
    assert docs_without_auth.headers["www-authenticate"] == "Basic"
    assert openapi_without_auth.headers["www-authenticate"] == "Basic"
    assert docs_with_auth.status_code == 200
    assert openapi_with_auth.status_code == 200

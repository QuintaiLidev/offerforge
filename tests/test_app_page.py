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
    assert "练习历史" in response.text
    assert "review-section-title" in response.text
    assert "historyList" in response.text
    assert "展开历史" in response.text
    assert "我的回答" in response.text
    assert "编辑卡片" in response.text
    assert "edit-card-button" in response.text
    assert "card-edit-form" in response.text
    assert "createCardEditForm" in response.text
    assert "parseTagsInput" in response.text
    assert "reference_answer" in response.text
    assert "今日复习" in response.text
    assert "今天已练习" in response.text
    assert "查看答案" in response.text
    assert "答案内容" in response.text
    assert "调度信息" in response.text
    assert "掌握状态" in response.text
    assert "连续正确" in response.text
    assert "错误次数" in response.text
    assert "上次练习" in response.text
    assert "下次复习" in response.text
    assert "本次评价" in response.text
    assert "mastery_level" in response.text
    assert "next_review_at" in response.text
    assert "consecutive_correct_count" in response.text
    assert "total_error_count" in response.text
    assert "last_practiced_at" in response.text
    assert "/api/v1/reviews/today" in response.text
    assert "/api/v1/reviews/done-today" in response.text
    assert "/api/v1/reviews/history?limit=50" in response.text
    assert "/api/v1/cards/${card.id}" in response.text
    assert 'method: "PATCH"' in response.text
    assert "/api/v1/practice-attempts" in response.text
    assert "request failed" in response.text
    assert "setButtonsDisabled(true, rating)" in response.text
    assert "dataset.originalText" in response.text
    assert "state.submitting" in response.text
    assert "loadHistory()" in response.text
    assert "Promise.all([loadToday(), loadDoneToday(), loadHistory()])" in response.text
    assert "answer_text" in response.text
    assert "dont_know" in response.text
    assert "with_hint" in response.text
    assert "correct_slow" in response.text
    assert "correct_explain" in response.text
    assert "transfer" in response.text


async def test_root_redirects_to_app(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.delenv("OFFERFORGE_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()

    async for client in make_client():
        response = await client.get("/")

    assert response.status_code == 307
    assert response.headers["location"] == "/app"


async def test_app_page_auth_enabled_protects_app_but_not_health(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    async for client in make_client():
        root = await client.get("/")
        health = await client.get("/api/v1/health")
        app_without_auth = await client.get("/app")
        app_with_auth = await client.get(
            "/app",
            auth=("offerforge", "test-secret"),
        )

    assert root.status_code == 307
    assert root.headers["location"] == "/app"
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

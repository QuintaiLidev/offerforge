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


async def test_auth_disabled_allows_health_docs_openapi_and_cards(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.delenv("OFFERFORGE_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("OFFERFORGE_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()

    async for client in make_client():
        health = await client.get("/api/v1/health")
        docs = await client.get("/docs")
        openapi = await client.get("/openapi.json")
        cards = await client.get("/api/v1/cards")

    assert health.status_code == 200
    assert docs.status_code == 200
    assert openapi.status_code == 200
    assert cards.status_code == 200


async def test_auth_enabled_protects_docs_openapi_and_business_api(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    async for client in make_client():
        health = await client.get("/api/v1/health")
        docs_without_auth = await client.get("/docs")
        openapi_without_auth = await client.get("/openapi.json")
        cards_without_auth = await client.get("/api/v1/cards")
        cards_wrong_password = await client.get(
            "/api/v1/cards",
            auth=("offerforge", "wrong-secret"),
        )
        cards_with_auth = await client.get(
            "/api/v1/cards",
            auth=("offerforge", "test-secret"),
        )
        docs_with_auth = await client.get(
            "/docs",
            auth=("offerforge", "test-secret"),
        )
        openapi_with_auth = await client.get(
            "/openapi.json",
            auth=("offerforge", "test-secret"),
        )

    assert health.status_code == 200
    assert docs_without_auth.status_code == 401
    assert openapi_without_auth.status_code == 401
    assert cards_without_auth.status_code == 401
    assert cards_wrong_password.status_code == 401
    assert cards_with_auth.status_code == 200
    assert docs_with_auth.status_code == 200
    assert openapi_with_auth.status_code == 200
    assert docs_without_auth.headers["www-authenticate"] == "Basic"
    assert openapi_without_auth.headers["www-authenticate"] == "Basic"
    assert cards_without_auth.headers["www-authenticate"] == "Basic"
    assert cards_wrong_password.headers["www-authenticate"] == "Basic"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (None, "test-secret"),
        ("offerforge", None),
        ("", "test-secret"),
        ("offerforge", ""),
    ],
)
def test_auth_enabled_requires_username_and_password(
    monkeypatch: pytest.MonkeyPatch,
    username: str | None,
    password: str | None,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "on")
    if username is None:
        monkeypatch.delenv("OFFERFORGE_AUTH_USERNAME", raising=False)
    else:
        monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", username)

    if password is None:
        monkeypatch.delenv("OFFERFORGE_AUTH_PASSWORD", raising=False)
    else:
        monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", password)
    get_settings.cache_clear()

    with pytest.raises(ValueError, match="Auth is enabled but"):
        create_app()


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("FALSE", False),
        ("0", False),
        ("no", False),
        ("off", False),
    ],
)
def test_auth_enabled_boolean_parsing(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: bool,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", raw_value)
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    assert get_settings().auth_enabled is expected

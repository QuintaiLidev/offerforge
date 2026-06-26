from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_knowledge_card_service
from app.main import app
from app.models import KnowledgeCard
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)

pytestmark = pytest.mark.anyio


@pytest.fixture()
async def client(db_session: Session) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as async_client:
            yield async_client
    app.dependency_overrides.clear()


def card_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Python list comprehension",
        "category": "python",
        "core_knowledge": "List comprehension creates lists from iterables.",
        "question": "Explain a Python list comprehension.",
        "reference_answer": "It builds a list by applying an expression.",
        "scoring_rules": {"must_include": ["expression", "iterable"]},
        "tags": ["python", "list"],
    }
    payload.update(overrides)
    return payload


async def create_card(
    client: httpx.AsyncClient,
    **overrides: Any,
) -> dict[str, Any]:
    response = await client.post("/api/v1/cards", json=card_payload(**overrides))
    assert response.status_code == 201, response.text
    return response.json()


def service_card_response() -> SimpleNamespace:
    now = datetime(2026, 6, 26, 12, 0, 0)
    return SimpleNamespace(
        id=1,
        title="Mocked service card",
        category=KnowledgeCategory.PYTHON,
        difficulty=DifficultyLevel.MEDIUM,
        question_type=QuestionType.KNOWLEDGE,
        core_knowledge="Mocked core knowledge.",
        question="Mocked question.",
        reference_answer="Mocked answer.",
        scoring_rules={},
        tags=[],
        source_reference=None,
        mastery_level=MasteryLevel.NEW,
        last_practiced_at=None,
        next_review_at=None,
        consecutive_correct_count=0,
        total_error_count=0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def test_post_creates_card_and_persists_to_test_database(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    response = await client.post("/api/v1/cards", json=card_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["id"] > 0
    assert data["title"] == "Python list comprehension"
    assert data["difficulty"] == "medium"
    assert data["question_type"] == "knowledge"
    assert data["mastery_level"] == "new"
    assert data["scoring_rules"] == {"must_include": ["expression", "iterable"]}
    assert data["tags"] == ["python", "list"]
    assert {"created_at", "updated_at"} <= set(data)

    count = db_session.scalar(select(func.count()).select_from(KnowledgeCard))
    assert count == 1


async def test_post_duplicate_same_category_returns_409(
    client: httpx.AsyncClient,
) -> None:
    await create_card(client, title="Duplicate title")

    response = await client.post(
        "/api/v1/cards",
        json=card_payload(title="Duplicate title"),
    )

    assert response.status_code == 409
    assert "already exists in category 'python'" in response.json()["detail"]


async def test_post_same_title_different_category_is_allowed(
    client: httpx.AsyncClient,
) -> None:
    first = await create_card(client, title="Same title", category="python")
    second = await create_card(client, title="Same title", category="sql")

    assert first["id"] != second["id"]
    assert second["category"] == "sql"


@pytest.mark.parametrize(
    "payload",
    [
        card_payload(category="not_a_category"),
        card_payload(title="   "),
    ],
)
async def test_post_invalid_payload_returns_422(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
) -> None:
    response = await client.post("/api/v1/cards", json=payload)

    assert response.status_code == 422


async def test_get_detail_returns_existing_card(client: httpx.AsyncClient) -> None:
    created = await create_card(client, title="Detail card")

    response = await client.get(f"/api/v1/cards/{created['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created["id"]
    assert data["title"] == "Detail card"


async def test_get_detail_missing_or_invalid_id(
    client: httpx.AsyncClient,
) -> None:
    missing = await client.get("/api/v1/cards/999999")
    zero = await client.get("/api/v1/cards/0")
    negative = await client.get("/api/v1/cards/-1")

    assert missing.status_code == 404
    assert zero.status_code == 422
    assert negative.status_code == 422


async def test_get_list_default_pagination_and_limit_offset(
    client: httpx.AsyncClient,
) -> None:
    created = [
        await create_card(client, title=f"List card {index}")
        for index in range(5)
    ]

    default_response = await client.get("/api/v1/cards")
    paged_response = await client.get("/api/v1/cards", params={"limit": 2, "offset": 2})

    assert default_response.status_code == 200
    default_data = default_response.json()
    assert default_data["total"] == 5
    assert default_data["limit"] == 20
    assert default_data["offset"] == 0
    assert len(default_data["items"]) == 5
    assert default_data["items"][0]["id"] == created[-1]["id"]

    assert paged_response.status_code == 200
    paged_data = paged_response.json()
    assert paged_data["total"] == 5
    assert paged_data["limit"] == 2
    assert paged_data["offset"] == 2
    assert len(paged_data["items"]) == 2


async def test_get_list_filters_and_keyword_search(
    client: httpx.AsyncClient,
) -> None:
    target = await create_card(
        client,
        title="SQL target card",
        category="sql",
        difficulty="hard",
        question_type="sql",
        core_knowledge="Window function knowledge.",
        question="How do you test SQL rank results?",
    )
    await client.patch(
        f"/api/v1/cards/{target['id']}",
        json={"mastery_level": "familiar", "is_active": False},
    )
    await create_card(
        client,
        title="Python active card",
        category="python",
        difficulty="medium",
        question_type="python_code",
        core_knowledge="Comprehension knowledge.",
        question="Write a list comprehension.",
    )
    await create_card(
        client,
        title="HTTP auth card",
        category="http_api_testing",
        difficulty="easy",
        question_type="knowledge",
        core_knowledge="Cookie session behavior.",
        question="How do you test login token refresh?",
    )

    filtered = await client.get(
        "/api/v1/cards",
        params={
            "category": "sql",
            "difficulty": "hard",
            "mastery_level": "familiar",
            "question_type": "sql",
            "is_active": "false",
        },
    )
    title_match = await client.get("/api/v1/cards", params={"keyword": " target "})
    core_match = await client.get("/api/v1/cards", params={"keyword": "COOKIE"})
    question_match = await client.get("/api/v1/cards", params={"keyword": "rank"})
    invalid_enum = await client.get("/api/v1/cards", params={"category": "bad"})

    assert filtered.status_code == 200
    filtered_data = filtered.json()
    assert filtered_data["total"] == 1
    assert filtered_data["items"][0]["id"] == target["id"]
    assert title_match.json()["total"] == 1
    assert title_match.json()["items"][0]["id"] == target["id"]
    assert core_match.json()["total"] == 1
    assert core_match.json()["items"][0]["title"] == "HTTP auth card"
    assert question_match.json()["total"] == 1
    assert question_match.json()["items"][0]["id"] == target["id"]
    assert invalid_enum.status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"offset": -1},
        {"limit": 0},
        {"limit": 101},
    ],
)
async def test_get_list_invalid_pagination_returns_422(
    client: httpx.AsyncClient,
    params: dict[str, int],
) -> None:
    response = await client.get("/api/v1/cards", params=params)

    assert response.status_code == 422


async def test_patch_updates_single_and_multiple_fields(
    client: httpx.AsyncClient,
) -> None:
    created = await create_card(client, title="Patch target")

    single = await client.patch(
        f"/api/v1/cards/{created['id']}",
        json={"title": "Patched title"},
    )
    multiple = await client.patch(
        f"/api/v1/cards/{created['id']}",
        json={
            "difficulty": "hard",
            "tags": ["updated"],
            "scoring_rules": {"must_include": ["updated"]},
        },
    )
    detail = await client.get(f"/api/v1/cards/{created['id']}")

    assert single.status_code == 200
    assert single.json()["title"] == "Patched title"
    assert single.json()["category"] == created["category"]
    assert multiple.status_code == 200
    assert multiple.json()["difficulty"] == "hard"
    assert multiple.json()["tags"] == ["updated"]
    assert detail.json()["title"] == "Patched title"
    assert detail.json()["difficulty"] == "hard"


async def test_patch_validation_not_found_and_conflict(
    client: httpx.AsyncClient,
) -> None:
    first = await create_card(client, title="First card")
    second = await create_card(client, title="Second card")

    empty_update = await client.patch(f"/api/v1/cards/{first['id']}", json={})
    missing = await client.patch("/api/v1/cards/999999", json={"title": "Missing"})
    conflict = await client.patch(
        f"/api/v1/cards/{first['id']}",
        json={"title": "Second card"},
    )
    self_title = await client.patch(
        f"/api/v1/cards/{first['id']}",
        json={"title": "First card", "category": "python"},
    )

    assert second["category"] == "python"
    assert empty_update.status_code == 422
    assert missing.status_code == 404
    assert conflict.status_code == 409
    assert self_title.status_code == 200
    assert self_title.json()["title"] == "First card"


async def test_delete_card_returns_204_and_removes_card(
    client: httpx.AsyncClient,
) -> None:
    created = await create_card(client, title="Delete target")

    response = await client.delete(f"/api/v1/cards/{created['id']}")
    detail_after_delete = await client.get(f"/api/v1/cards/{created['id']}")
    missing_delete = await client.delete("/api/v1/cards/999999")

    assert response.status_code == 204
    assert response.content == b""
    assert detail_after_delete.status_code == 404
    assert missing_delete.status_code == 404


async def test_health_endpoint_still_works(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "OfferForge"}


async def test_router_uses_service_dependency(client: httpx.AsyncClient) -> None:
    service = Mock()
    service.create_card.return_value = service_card_response()
    app.dependency_overrides[get_knowledge_card_service] = lambda: service

    response = await client.post(
        "/api/v1/cards",
        json=card_payload(title="Mocked service card"),
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Mocked service card"
    service.create_card.assert_called_once()

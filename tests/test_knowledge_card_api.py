from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_knowledge_card_service
from app.core.config import get_settings
from app.main import app, create_app
from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    PracticeRating,
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


def bulk_card_payloads() -> list[dict[str, Any]]:
    return [
        card_payload(
            title="Bulk pytest fixture",
            category="pytest",
            difficulty="easy",
            question_type="knowledge",
            core_knowledge="fixture prepares reusable test state.",
            question="What problem does a pytest fixture solve?",
            reference_answer=(
                "It prepares test preconditions, reusable data, and resource "
                "lifecycles."
            ),
            tags=["pytest", "fixture"],
            source_reference="manual-week1",
        ),
        card_payload(
            title="Bulk SQL join",
            category="sql",
            difficulty="medium",
            question_type="sql",
            core_knowledge="JOIN combines rows from related tables.",
            question="What does an INNER JOIN return?",
            reference_answer="It returns rows that match in both joined tables.",
            tags=["sql", "join"],
            source_reference="manual-week1",
        ),
    ]


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


async def test_post_bulk_creates_cards_and_reviews_can_return_them(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post("/api/v1/cards/bulk", json=bulk_card_payloads())

    assert response.status_code == 201
    data = response.json()
    assert data["created_count"] == 2
    assert len(data["items"]) == 2
    assert [item["title"] for item in data["items"]] == [
        "Bulk pytest fixture",
        "Bulk SQL join",
    ]

    first_id = data["items"][0]["id"]
    second_id = data["items"][1]["id"]
    first_detail = await client.get(f"/api/v1/cards/{first_id}")
    second_detail = await client.get(f"/api/v1/cards/{second_id}")
    today = await client.get("/api/v1/reviews/today")

    assert first_detail.status_code == 200
    assert second_detail.status_code == 200
    assert first_detail.json()["title"] == "Bulk pytest fixture"
    assert second_detail.json()["title"] == "Bulk SQL join"
    assert today.status_code == 200
    today_data = today.json()
    assert today_data["mode"] == "new"
    assert {item["id"] for item in today_data["items"]} == {first_id, second_id}


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [
            card_payload(title=f"Bulk card {index}", category="python")
            for index in range(101)
        ],
        [
            card_payload(title="Valid bulk card"),
            card_payload(title="Invalid bulk card", category="not_a_category"),
        ],
    ],
)
async def test_post_bulk_invalid_payload_returns_422(
    client: httpx.AsyncClient,
    payload: list[dict[str, Any]],
) -> None:
    response = await client.post("/api/v1/cards/bulk", json=payload)

    assert response.status_code == 422


async def test_post_bulk_auth_enabled_protects_business_api_but_not_health(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as auth_client:
            health = await auth_client.get("/api/v1/health")
            without_auth = await auth_client.post(
                "/api/v1/cards/bulk",
                json=bulk_card_payloads(),
            )
            with_auth = await auth_client.post(
                "/api/v1/cards/bulk",
                json=bulk_card_payloads(),
                auth=("offerforge", "test-secret"),
            )

    assert health.status_code == 200
    assert without_auth.status_code == 401
    assert without_auth.headers["www-authenticate"] == "Basic"
    assert with_auth.status_code == 201
    assert with_auth.json()["created_count"] == 2
    get_settings.cache_clear()


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


async def test_post_allows_same_title_category_across_source_references(
    client: httpx.AsyncClient,
) -> None:
    title = "Java 多线程有哪几种实现方式？"
    first = await create_card(
        client,
        title=title,
        category="real_business_case",
        source_reference="interview-week1-v3",
    )
    second = await create_card(
        client,
        title=title,
        category="real_business_case",
        source_reference="interview-week1-v4",
    )

    assert first["id"] != second["id"]
    assert first["source_reference"] == "interview-week1-v3"
    assert second["source_reference"] == "interview-week1-v4"


async def test_post_duplicate_same_source_returns_409(
    client: httpx.AsyncClient,
) -> None:
    title = "Java 多线程有哪几种实现方式？"
    await create_card(
        client,
        title=title,
        category="real_business_case",
        source_reference="interview-week1-v3",
    )

    response = await client.post(
        "/api/v1/cards",
        json=card_payload(
            title=title,
            category="real_business_case",
            source_reference="interview-week1-v3",
        ),
    )

    assert response.status_code == 409
    assert "source_reference 'interview-week1-v3'" in response.json()["detail"]


async def test_post_same_title_different_category_is_allowed(
    client: httpx.AsyncClient,
) -> None:
    first = await create_card(client, title="Same title", category="python")
    second = await create_card(client, title="Same title", category="sql")

    assert first["id"] != second["id"]
    assert second["category"] == "sql"


async def test_post_bulk_allows_v4_when_v3_has_same_title_category(
    client: httpx.AsyncClient,
) -> None:
    title = "Java 多线程有哪几种实现方式？"
    await create_card(
        client,
        title=title,
        category="real_business_case",
        source_reference="interview-week1-v3",
    )

    response = await client.post(
        "/api/v1/cards/bulk",
        json=[
            card_payload(
                title=title,
                category="real_business_case",
                source_reference="interview-week1-v4",
            ),
            card_payload(
                title="Java 多线程题，测试开发岗位需要答到什么深度？",
                category="real_business_case",
                source_reference="interview-week1-v4",
            ),
        ],
    )
    sources = await client.get("/api/v1/cards/sources")
    summaries = {
        item["source_reference"]: item
        for item in sources.json()["items"]
    }

    assert response.status_code == 201
    assert response.json()["created_count"] == 2
    assert summaries["interview-week1-v3"]["total_count"] == 1
    assert summaries["interview-week1-v4"]["total_count"] == 2


async def test_post_bulk_duplicate_same_source_returns_409(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    response = await client.post(
        "/api/v1/cards/bulk",
        json=[
            card_payload(
                title="Bulk duplicate same source",
                source_reference="interview-week1-v4",
            ),
            card_payload(
                title="Bulk duplicate same source",
                source_reference="interview-week1-v4",
            ),
        ],
    )
    count = db_session.scalar(select(func.count()).select_from(KnowledgeCard))

    assert response.status_code == 409
    assert "source_reference 'interview-week1-v4'" in response.json()["detail"]
    assert count == 0


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
    db_session: Session,
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
    target_model = db_session.get(KnowledgeCard, target["id"])
    assert target_model is not None
    target_model.mastery_level = MasteryLevel.FAMILIAR
    target_model.is_active = False
    db_session.commit()
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
            "question": "Updated question?",
            "core_knowledge": "Updated core knowledge.",
            "reference_answer": "Updated reference answer.",
            "tags": ["updated"],
        },
    )
    detail = await client.get(f"/api/v1/cards/{created['id']}")

    assert single.status_code == 200
    assert single.json()["title"] == "Patched title"
    assert single.json()["category"] == created["category"]
    assert multiple.status_code == 200
    assert multiple.json()["question"] == "Updated question?"
    assert multiple.json()["core_knowledge"] == "Updated core knowledge."
    assert multiple.json()["reference_answer"] == "Updated reference answer."
    assert multiple.json()["tags"] == ["updated"]
    assert detail.json()["title"] == "Patched title"
    assert detail.json()["reference_answer"] == "Updated reference answer."


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
        json={"title": "First card"},
    )

    assert second["category"] == "python"
    assert empty_update.status_code == 422
    assert missing.status_code == 404
    assert conflict.status_code == 409
    assert self_title.status_code == 200
    assert self_title.json()["title"] == "First card"


@pytest.mark.parametrize(
    "field_name",
    [
        "id",
        "source_reference",
        "mastery_level",
        "next_review_at",
        "last_practiced_at",
        "consecutive_correct_count",
        "total_error_count",
    ],
)
async def test_patch_rejects_read_only_fields(
    client: httpx.AsyncClient,
    field_name: str,
) -> None:
    created = await create_card(client, title="Read-only patch target")

    response = await client.patch(
        f"/api/v1/cards/{created['id']}",
        json={field_name: "not editable"},
    )

    assert response.status_code == 422


async def test_patch_duplicate_title_is_source_aware(
    client: httpx.AsyncClient,
) -> None:
    await create_card(
        client,
        title="V3 shared title",
        category="real_business_case",
        source_reference="interview-week1-v3",
    )
    v4_first = await create_card(
        client,
        title="V4 first title",
        category="real_business_case",
        source_reference="interview-week1-v4",
    )
    await create_card(
        client,
        title="V4 existing title",
        category="real_business_case",
        source_reference="interview-week1-v4",
    )

    cross_source = await client.patch(
        f"/api/v1/cards/{v4_first['id']}",
        json={"title": "V3 shared title"},
    )
    same_source_conflict = await client.patch(
        f"/api/v1/cards/{v4_first['id']}",
        json={"title": "V4 existing title"},
    )

    assert cross_source.status_code == 200
    assert cross_source.json()["title"] == "V3 shared title"
    assert same_source_conflict.status_code == 409


async def test_patch_auth_enabled_protects_card_update(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    card = KnowledgeCard(
        title="Auth patch card",
        category=KnowledgeCategory.PYTHON,
        core_knowledge="Auth patch core.",
        question="Auth patch question.",
        reference_answer="Auth patch answer.",
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    get_settings.cache_clear()

    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as auth_client:
            health = await auth_client.get("/api/v1/health")
            without_auth = await auth_client.patch(
                f"/api/v1/cards/{card.id}",
                json={"reference_answer": "Updated"},
            )
            with_auth = await auth_client.patch(
                f"/api/v1/cards/{card.id}",
                json={"reference_answer": "Updated"},
                auth=("offerforge", "test-secret"),
            )

    assert health.status_code == 200
    assert without_auth.status_code == 401
    assert without_auth.headers["www-authenticate"] == "Basic"
    assert with_auth.status_code == 200
    assert with_auth.json()["reference_answer"] == "Updated"
    get_settings.cache_clear()


async def test_patch_does_not_modify_practice_attempt_or_schedule_fields(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    created = await create_card(client, title="Attempt safe patch")
    card = db_session.get(KnowledgeCard, created["id"])
    assert card is not None
    card.mastery_level = MasteryLevel.FAMILIAR
    card.last_practiced_at = datetime(2026, 6, 29, 9, 0, 0)
    card.next_review_at = datetime(2026, 7, 3, 9, 0, 0)
    card.consecutive_correct_count = 2
    card.total_error_count = 1
    attempt = PracticeAttempt(
        knowledge_card_id=card.id,
        rating=PracticeRating.CORRECT_EXPLAIN,
        is_correct=True,
        used_hint=False,
        user_answer="Original user answer",
        elapsed_seconds=42,
        scheduled_next_review_at=datetime(2026, 7, 3, 9, 0, 0),
        created_at=datetime(2026, 6, 29, 9, 1, 0),
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(card)
    db_session.refresh(attempt)
    before_card = {
        "mastery_level": card.mastery_level,
        "last_practiced_at": card.last_practiced_at,
        "next_review_at": card.next_review_at,
        "consecutive_correct_count": card.consecutive_correct_count,
        "total_error_count": card.total_error_count,
    }
    before_attempt = {
        "user_answer": attempt.user_answer,
        "rating": attempt.rating,
        "created_at": attempt.created_at,
        "scheduled_next_review_at": attempt.scheduled_next_review_at,
    }

    response = await client.patch(
        f"/api/v1/cards/{card.id}",
        json={
            "reference_answer": "Updated reference answer.",
            "tags": ["edited", "reference"],
        },
    )

    assert response.status_code == 200
    db_session.expire_all()
    refreshed_card = db_session.get(KnowledgeCard, card.id)
    refreshed_attempt = db_session.get(PracticeAttempt, attempt.id)
    assert refreshed_card is not None
    assert refreshed_attempt is not None
    assert refreshed_card.reference_answer == "Updated reference answer."
    assert refreshed_card.tags == ["edited", "reference"]
    assert {
        "mastery_level": refreshed_card.mastery_level,
        "last_practiced_at": refreshed_card.last_practiced_at,
        "next_review_at": refreshed_card.next_review_at,
        "consecutive_correct_count": refreshed_card.consecutive_correct_count,
        "total_error_count": refreshed_card.total_error_count,
    } == before_card
    assert {
        "user_answer": refreshed_attempt.user_answer,
        "rating": refreshed_attempt.rating,
        "created_at": refreshed_attempt.created_at,
        "scheduled_next_review_at": refreshed_attempt.scheduled_next_review_at,
    } == before_attempt


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

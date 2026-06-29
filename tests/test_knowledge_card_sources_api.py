from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app, create_app
from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import KnowledgeCategory, MasteryLevel, PracticeRating
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate

pytestmark = pytest.mark.anyio

FIXED_NOW = datetime(2026, 6, 29, 12, 0, 0)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
    app.dependency_overrides.clear()


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


def make_card_create(
    *,
    title: str,
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    source_reference: str | None = "interview-week1-v3",
) -> KnowledgeCardCreate:
    return KnowledgeCardCreate(
        title=title,
        category=category,
        core_knowledge=f"Core knowledge for {title}",
        question=f"Question about {title}",
        reference_answer=f"Reference answer for {title}",
        source_reference=source_reference,
    )


def create_card(
    db_session: Session,
    *,
    title: str,
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    source_reference: str | None = "interview-week1-v3",
    **overrides: Any,
) -> KnowledgeCard:
    repository = KnowledgeCardRepository(db_session)
    card = repository.create(
        make_card_create(
            title=title,
            category=category,
            source_reference=source_reference,
        )
    )
    for field_name, value in overrides.items():
        setattr(card, field_name, value)
    if overrides:
        db_session.commit()
        db_session.refresh(card)
    return card


def create_attempt(
    db_session: Session,
    *,
    card_id: int,
    created_at: datetime,
) -> PracticeAttempt:
    attempt = PracticeAttempt(
        knowledge_card_id=card_id,
        rating=PracticeRating.CORRECT_EXPLAIN,
        is_correct=True,
        used_hint=False,
        user_answer="Historical answer",
        elapsed_seconds=60,
        created_at=created_at,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    return attempt


def summaries_by_source(data: dict[str, Any]) -> dict[str | None, dict[str, Any]]:
    return {item["source_reference"]: item for item in data["items"]}


def bulk_payload(title: str, source_reference: str) -> dict[str, Any]:
    return {
        "title": title,
        "category": "python",
        "core_knowledge": f"Core knowledge for {title}",
        "question": f"Question about {title}",
        "reference_answer": f"Reference answer for {title}",
        "source_reference": source_reference,
        "scoring_rules": {},
        "tags": ["seed"],
    }


async def test_get_sources_returns_source_reference_summary(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    create_card(db_session, title="V3 active", source_reference="interview-week1-v3")
    create_card(
        db_session,
        title="V3 inactive",
        source_reference="interview-week1-v3",
        is_active=False,
    )
    create_card(db_session, title="V4 active", source_reference="interview-week1-v4")
    create_card(db_session, title="No source", source_reference=None)

    response = await client.get("/api/v1/cards/sources")

    assert response.status_code == 200
    summaries = summaries_by_source(response.json())
    assert summaries["interview-week1-v3"] == {
        "source_reference": "interview-week1-v3",
        "total_count": 2,
        "active_count": 1,
        "inactive_count": 1,
    }
    assert summaries["interview-week1-v4"] == {
        "source_reference": "interview-week1-v4",
        "total_count": 1,
        "active_count": 1,
        "inactive_count": 0,
    }
    assert summaries[None] == {
        "source_reference": None,
        "total_count": 1,
        "active_count": 1,
        "inactive_count": 0,
    }


async def test_patch_source_active_can_disable_and_reenable_source(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    create_card(db_session, title="V3 card one", source_reference="interview-week1-v3")
    create_card(db_session, title="V3 card two", source_reference="interview-week1-v3")
    v4_card = create_card(
        db_session,
        title="V4 untouched",
        source_reference="interview-week1-v4",
    )

    disabled = await client.patch(
        "/api/v1/cards/sources/interview-week1-v3/active",
        json={"is_active": False},
    )
    db_session.expire_all()
    inactive_count = db_session.scalar(
        select(func.count())
        .select_from(KnowledgeCard)
        .where(
            KnowledgeCard.source_reference == "interview-week1-v3",
            KnowledgeCard.is_active.is_(False),
        )
    )
    refreshed_v4 = db_session.get(KnowledgeCard, v4_card.id)

    enabled = await client.patch(
        "/api/v1/cards/sources/interview-week1-v3/active",
        json={"is_active": True},
    )

    assert disabled.status_code == 200
    assert disabled.json() == {
        "source_reference": "interview-week1-v3",
        "updated_count": 2,
        "is_active": False,
    }
    assert inactive_count == 2
    assert refreshed_v4 is not None
    assert refreshed_v4.is_active is True
    assert enabled.status_code == 200
    assert enabled.json() == {
        "source_reference": "interview-week1-v3",
        "updated_count": 2,
        "is_active": True,
    }


async def test_patch_source_active_missing_source_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.patch(
        "/api/v1/cards/sources/not-found/active",
        json={"is_active": False},
    )

    assert response.status_code == 404
    assert "not-found" in response.json()["detail"]


async def test_delete_source_removes_existing_source_cards(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    create_card(db_session, title="Bad v4 one", source_reference="interview-week1-v4")
    create_card(db_session, title="Bad v4 two", source_reference="interview-week1-v4")
    v3_card = create_card(
        db_session,
        title="Bad v4 one",
        source_reference="interview-week1-v3",
    )

    deleted = await client.delete("/api/v1/cards/sources/interview-week1-v4")
    sources = await client.get("/api/v1/cards/sources")
    db_session.expire_all()
    v4_count = db_session.scalar(
        select(func.count())
        .select_from(KnowledgeCard)
        .where(KnowledgeCard.source_reference == "interview-week1-v4")
    )
    refreshed_v3 = db_session.get(KnowledgeCard, v3_card.id)

    assert deleted.status_code == 200
    assert deleted.json() == {
        "source_reference": "interview-week1-v4",
        "deleted_count": 2,
    }
    assert v4_count == 0
    assert refreshed_v3 is not None
    assert refreshed_v3.source_reference == "interview-week1-v3"
    assert "interview-week1-v4" not in summaries_by_source(sources.json())
    assert summaries_by_source(sources.json())["interview-week1-v3"]["total_count"] == 1


async def test_delete_source_missing_source_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.delete("/api/v1/cards/sources/not-found")

    assert response.status_code == 404
    assert "not-found" in response.json()["detail"]


async def test_delete_source_with_practice_attempt_returns_409_and_deletes_nothing(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    attempted_card = create_card(
        db_session,
        title="Practiced v4 card",
        source_reference="interview-week1-v4",
    )
    untouched_card = create_card(
        db_session,
        title="Unpracticed v4 card",
        source_reference="interview-week1-v4",
    )
    attempt = create_attempt(
        db_session,
        card_id=attempted_card.id,
        created_at=FIXED_NOW - timedelta(minutes=5),
    )

    response = await client.delete("/api/v1/cards/sources/interview-week1-v4")
    db_session.expire_all()
    remaining_cards = list(
        db_session.scalars(
            select(KnowledgeCard).where(
                KnowledgeCard.source_reference == "interview-week1-v4"
            )
        ).all()
    )
    refreshed_attempt = db_session.get(PracticeAttempt, attempt.id)

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Cannot delete source_reference because practice attempts exist "
            "for these cards."
        )
    }
    assert {card.id for card in remaining_cards} == {
        attempted_card.id,
        untouched_card.id,
    }
    assert refreshed_attempt is not None


async def test_today_reviews_exclude_inactive_source_but_keep_active_v4(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v3_card = create_card(
        db_session,
        title="Shared source question",
        source_reference="interview-week1-v3",
    )
    v4_card = create_card(
        db_session,
        title="Shared source question",
        source_reference="interview-week1-v4",
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    disabled = await client.patch(
        "/api/v1/cards/sources/interview-week1-v3/active",
        json={"is_active": False},
    )
    today = await client.get("/api/v1/reviews/today")

    assert disabled.status_code == 200
    assert today.status_code == 200
    returned_ids = [item["id"] for item in today.json()["items"]]
    assert v4_card.id in returned_ids
    assert v3_card.id not in returned_ids


async def test_today_reviews_do_not_return_deleted_source(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    v3_card = create_card(
        db_session,
        title="V3 to delete",
        source_reference="interview-week1-v3",
    )
    v4_card = create_card(
        db_session,
        title="V4 remains active",
        category=KnowledgeCategory.SQL,
        source_reference="interview-week1-v4",
    )
    v3_card_id = v3_card.id
    v4_card_id = v4_card.id
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    deleted = await client.delete("/api/v1/cards/sources/interview-week1-v3")
    today = await client.get("/api/v1/reviews/today")

    assert deleted.status_code == 200
    returned_ids = [item["id"] for item in today.json()["items"]]
    assert v4_card_id in returned_ids
    assert v3_card_id not in returned_ids


async def test_done_today_keeps_inactive_source_history_and_attempts(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(
        db_session,
        title="Practiced v3 card",
        source_reference="interview-week1-v3",
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=FIXED_NOW + timedelta(days=1),
    )
    attempt = create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW - timedelta(minutes=10),
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    disabled = await client.patch(
        "/api/v1/cards/sources/interview-week1-v3/active",
        json={"is_active": False},
    )
    done_today = await client.get("/api/v1/reviews/done-today")
    db_session.expire_all()
    attempts_count = db_session.scalar(
        select(func.count()).select_from(PracticeAttempt)
    )
    refreshed_card = db_session.get(KnowledgeCard, card.id)
    refreshed_attempt = db_session.get(PracticeAttempt, attempt.id)

    assert disabled.status_code == 200
    assert done_today.status_code == 200
    data = done_today.json()
    assert [item["card"]["id"] for item in data["items"]] == [card.id]
    assert data["items"][0]["card"]["is_active"] is False
    assert data["items"][0]["latest_attempt"]["id"] == attempt.id
    assert attempts_count == 1
    assert refreshed_card is not None
    assert refreshed_card.is_active is False
    assert refreshed_attempt is not None


async def test_done_today_is_not_affected_when_deleting_unpracticed_source(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    practiced_card = create_card(
        db_session,
        title="Practiced v3 card",
        source_reference="interview-week1-v3",
    )
    attempt = create_attempt(
        db_session,
        card_id=practiced_card.id,
        created_at=FIXED_NOW - timedelta(minutes=10),
    )
    create_card(
        db_session,
        title="Unpracticed v4 card",
        source_reference="interview-week1-v4",
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    deleted = await client.delete("/api/v1/cards/sources/interview-week1-v4")
    done_today = await client.get("/api/v1/reviews/done-today")

    assert deleted.status_code == 200
    assert done_today.status_code == 200
    data = done_today.json()
    assert [item["card"]["id"] for item in data["items"]] == [practiced_card.id]
    assert data["items"][0]["latest_attempt"]["id"] == attempt.id


async def test_source_management_does_not_break_bulk_import(
    client: httpx.AsyncClient,
) -> None:
    bulk = await client.post(
        "/api/v1/cards/bulk",
        json=[
            bulk_payload("Bulk v4 one", "interview-week1-v4"),
            bulk_payload("Bulk v4 two", "interview-week1-v4"),
        ],
    )
    sources = await client.get("/api/v1/cards/sources")

    assert bulk.status_code == 201
    assert bulk.json()["created_count"] == 2
    assert sources.status_code == 200
    assert summaries_by_source(sources.json())["interview-week1-v4"] == {
        "source_reference": "interview-week1-v4",
        "total_count": 2,
        "active_count": 2,
        "inactive_count": 0,
    }


async def test_source_management_auth_and_health_behavior_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    create_card(db_session, title="Auth source", source_reference="interview-week1-v3")
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
            get_without_auth = await auth_client.get("/api/v1/cards/sources")
            patch_without_auth = await auth_client.patch(
                "/api/v1/cards/sources/interview-week1-v3/active",
                json={"is_active": False},
            )
            delete_without_auth = await auth_client.delete(
                "/api/v1/cards/sources/interview-week1-v3"
            )
            get_with_auth = await auth_client.get(
                "/api/v1/cards/sources",
                auth=("offerforge", "test-secret"),
            )
            patch_with_auth = await auth_client.patch(
                "/api/v1/cards/sources/interview-week1-v3/active",
                json={"is_active": False},
                auth=("offerforge", "test-secret"),
            )
            delete_with_auth = await auth_client.delete(
                "/api/v1/cards/sources/interview-week1-v3",
                auth=("offerforge", "test-secret"),
            )

    assert health.status_code == 200
    assert get_without_auth.status_code == 401
    assert get_without_auth.headers["www-authenticate"] == "Basic"
    assert patch_without_auth.status_code == 401
    assert patch_without_auth.headers["www-authenticate"] == "Basic"
    assert delete_without_auth.status_code == 401
    assert delete_without_auth.headers["www-authenticate"] == "Basic"
    assert get_with_auth.status_code == 200
    assert patch_with_auth.status_code == 200
    assert delete_with_auth.status_code == 200
    get_settings.cache_clear()

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.main import app, create_app
from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import KnowledgeCategory, MasteryLevel, PracticeRating
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate

pytestmark = pytest.mark.anyio

FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0)


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


def create_card(
    db_session: Session,
    *,
    title: str,
    **overrides: Any,
) -> KnowledgeCard:
    repository = KnowledgeCardRepository(db_session)
    card = repository.create(
        KnowledgeCardCreate(
            title=title,
            category=KnowledgeCategory.PYTHON,
            core_knowledge=f"Core knowledge for {title}",
            question=f"Question about {title}",
            reference_answer=f"Reference answer for {title}",
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
    rating: PracticeRating = PracticeRating.WITH_HINT,
    user_answer: str | None = "My answer",
) -> PracticeAttempt:
    attempt = PracticeAttempt(
        knowledge_card_id=card_id,
        rating=rating,
        is_correct=rating
        in {
            PracticeRating.CORRECT_SLOW,
            PracticeRating.CORRECT_EXPLAIN,
            PracticeRating.TRANSFER,
        },
        used_hint=rating is PracticeRating.WITH_HINT,
        user_answer=user_answer,
        elapsed_seconds=80,
        scheduled_next_review_at=created_at + timedelta(days=2),
        created_at=created_at,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    return attempt


def item_card_ids(data: dict[str, Any]) -> list[int]:
    return [item["card"]["id"] for item in data["items"]]


async def test_done_today_returns_empty_items_when_no_attempts(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today")

    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_done_today_returns_card_after_practice_attempt(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session, title="Done today card")
    create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW - timedelta(minutes=5),
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today")

    assert response.status_code == 200
    data = response.json()
    assert item_card_ids(data) == [card.id]
    assert data["items"][0]["card"]["title"] == "Done today card"
    assert data["items"][0]["card"]["question"] == "Question about Done today card"
    assert data["items"][0]["card"]["reference_answer"] == (
        "Reference answer for Done today card"
    )


async def test_done_today_returns_latest_attempt_information(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session, title="Latest attempt card")
    attempt = create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW - timedelta(minutes=3),
        rating=PracticeRating.CORRECT_EXPLAIN,
        user_answer="Latest answer text",
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today")

    assert response.status_code == 200
    latest_attempt = response.json()["items"][0]["latest_attempt"]
    assert latest_attempt["id"] == attempt.id
    assert latest_attempt["knowledge_card_id"] == card.id
    assert latest_attempt["rating"] == "correct_explain"
    assert latest_attempt["user_answer"] == "Latest answer text"
    assert latest_attempt["elapsed_seconds"] == 80


async def test_done_today_deduplicates_card_and_uses_latest_attempt(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session, title="Repeated today card")
    older = create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW - timedelta(hours=3),
        rating=PracticeRating.DONT_KNOW,
        user_answer="Older answer",
    )
    newer = create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW - timedelta(minutes=1),
        rating=PracticeRating.TRANSFER,
        user_answer="Newer answer",
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today")

    assert response.status_code == 200
    data = response.json()
    assert item_card_ids(data) == [card.id]
    assert len(data["items"]) == 1
    assert data["items"][0]["latest_attempt"]["id"] == newer.id
    assert data["items"][0]["latest_attempt"]["id"] != older.id
    assert data["items"][0]["latest_attempt"]["rating"] == "transfer"


async def test_done_today_orders_cards_by_latest_attempt_desc(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    oldest = create_card(db_session, title="Oldest attempt card")
    newest = create_card(db_session, title="Newest attempt card")
    middle = create_card(db_session, title="Middle attempt card")
    create_attempt(
        db_session,
        card_id=oldest.id,
        created_at=FIXED_NOW - timedelta(hours=3),
    )
    create_attempt(
        db_session,
        card_id=newest.id,
        created_at=FIXED_NOW - timedelta(minutes=1),
    )
    create_attempt(
        db_session,
        card_id=middle.id,
        created_at=FIXED_NOW - timedelta(hours=1),
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today")

    assert response.status_code == 200
    assert item_card_ids(response.json()) == [newest.id, middle.id, oldest.id]


async def test_done_today_limit_is_applied(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cards = [
        create_card(db_session, title=f"Limited card {index}")
        for index in range(3)
    ]
    for index, card in enumerate(cards):
        create_attempt(
            db_session,
            card_id=card.id,
            created_at=FIXED_NOW - timedelta(minutes=index),
        )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


async def test_done_today_excludes_yesterday_attempts(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session, title="Yesterday card")
    create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW.replace(hour=0) - timedelta(seconds=1),
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = await client.get("/api/v1/reviews/done-today")

    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_done_today_does_not_change_today_review_logic(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(
        db_session,
        title="Future scheduled practiced card",
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=FIXED_NOW + timedelta(days=1),
    )
    create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW - timedelta(minutes=10),
    )
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    today = await client.get("/api/v1/reviews/today")
    done_today = await client.get("/api/v1/reviews/done-today")

    assert today.status_code == 200
    assert card.id not in [item["id"] for item in today.json()["items"]]
    assert item_card_ids(done_today.json()) == [card.id]


@pytest.mark.parametrize("limit", [0, 51])
async def test_done_today_rejects_invalid_limit(
    client: httpx.AsyncClient,
    limit: int,
) -> None:
    response = await client.get("/api/v1/reviews/done-today", params={"limit": limit})

    assert response.status_code == 422


async def test_done_today_auth_and_health_behavior_when_auth_enabled(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)
    get_settings.cache_clear()

    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as auth_client:
            health = await auth_client.get("/api/v1/health")
            without_auth = await auth_client.get("/api/v1/reviews/done-today")
            with_auth = await auth_client.get(
                "/api/v1/reviews/done-today",
                auth=("offerforge", "test-secret"),
            )

    assert health.status_code == 200
    assert without_auth.status_code == 401
    assert without_auth.headers["www-authenticate"] == "Basic"
    assert with_auth.status_code == 200

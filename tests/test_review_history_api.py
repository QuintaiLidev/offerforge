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
            difficulty="medium",
            core_knowledge=f"Core knowledge for {title}",
            question=f"Question about {title}",
            reference_answer=f"Reference answer for {title}",
            source_reference="interview-week1-v4",
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
    rating: PracticeRating = PracticeRating.CORRECT_EXPLAIN,
    user_answer: str | None = "My answer",
) -> PracticeAttempt:
    attempt = PracticeAttempt(
        knowledge_card_id=card_id,
        rating=rating,
        is_correct=True,
        used_hint=False,
        user_answer=user_answer,
        elapsed_seconds=90,
        scheduled_next_review_at=created_at + timedelta(days=4),
        created_at=created_at,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(attempt)
    return attempt


async def test_history_returns_empty_items_when_no_attempts(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/v1/reviews/history")

    assert response.status_code == 200
    assert response.json() == {"items": []}


async def test_history_returns_attempt_with_card_information(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    card = create_card(
        db_session,
        title="History card",
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=FIXED_NOW + timedelta(days=4),
        last_practiced_at=FIXED_NOW,
        consecutive_correct_count=2,
        total_error_count=1,
    )
    attempt = create_attempt(
        db_session,
        card_id=card.id,
        created_at=FIXED_NOW,
        rating=PracticeRating.CORRECT_EXPLAIN,
        user_answer="Detailed answer",
    )

    response = await client.get("/api/v1/reviews/history")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["attempt_id"] == attempt.id
    assert item["created_at"] == FIXED_NOW.isoformat()
    assert item["rating"] == "correct_explain"
    assert item["user_answer"] == "Detailed answer"
    assert item["scheduled_next_review_at"] == (
        FIXED_NOW + timedelta(days=4)
    ).isoformat()
    assert item["card"]["id"] == card.id
    assert item["card"]["title"] == "History card"
    assert item["card"]["question"] == "Question about History card"
    assert item["card"]["reference_answer"] == "Reference answer for History card"
    assert item["card"]["mastery_level"] == "learning"
    assert item["card"]["source_reference"] == "interview-week1-v4"


async def test_history_orders_attempts_by_created_at_desc(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    oldest = create_card(db_session, title="Oldest history")
    newest = create_card(db_session, title="Newest history")
    middle = create_card(db_session, title="Middle history")
    old_attempt = create_attempt(
        db_session,
        card_id=oldest.id,
        created_at=FIXED_NOW - timedelta(hours=3),
    )
    new_attempt = create_attempt(
        db_session,
        card_id=newest.id,
        created_at=FIXED_NOW,
    )
    middle_attempt = create_attempt(
        db_session,
        card_id=middle.id,
        created_at=FIXED_NOW - timedelta(hours=1),
    )

    response = await client.get("/api/v1/reviews/history")

    assert response.status_code == 200
    assert [item["attempt_id"] for item in response.json()["items"]] == [
        new_attempt.id,
        middle_attempt.id,
        old_attempt.id,
    ]


async def test_history_limit_is_applied(
    client: httpx.AsyncClient,
    db_session: Session,
) -> None:
    cards = [
        create_card(db_session, title=f"Limited history {index}")
        for index in range(3)
    ]
    for index, card in enumerate(cards):
        create_attempt(
            db_session,
            card_id=card.id,
            created_at=FIXED_NOW - timedelta(minutes=index),
        )

    response = await client.get("/api/v1/reviews/history", params={"limit": 2})

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


@pytest.mark.parametrize("limit", [0, 101])
async def test_history_rejects_invalid_limit(
    client: httpx.AsyncClient,
    limit: int,
) -> None:
    response = await client.get("/api/v1/reviews/history", params={"limit": limit})

    assert response.status_code == 422


async def test_history_auth_and_health_behavior_when_auth_enabled(
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
            without_auth = await auth_client.get("/api/v1/reviews/history")
            with_auth = await auth_client.get(
                "/api/v1/reviews/history",
                auth=("offerforge", "test-secret"),
            )

    assert health.status_code == 200
    assert without_auth.status_code == 401
    assert without_auth.headers["www-authenticate"] == "Basic"
    assert with_auth.status_code == 200

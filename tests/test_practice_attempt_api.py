from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_practice_attempt_service
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


def make_card_create(
    *,
    title: str = "Practice attempt API card",
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    **overrides: Any,
) -> KnowledgeCardCreate:
    payload: dict[str, Any] = {
        "title": title,
        "category": category,
        "core_knowledge": f"Core knowledge for {title}",
        "question": f"Question about {title}",
        "reference_answer": f"Reference answer for {title}",
    }
    payload.update(overrides)
    return KnowledgeCardCreate(**payload)


def create_card(
    db_session: Session,
    *,
    title: str = "Practice attempt API card",
) -> KnowledgeCard:
    repository = KnowledgeCardRepository(db_session)
    return repository.create(make_card_create(title=title))


def attempt_payload(
    *,
    card_id: int,
    rating: str = "correct_slow",
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "knowledge_card_id": card_id,
        "rating": rating,
        "user_answer": "API answer",
        "elapsed_seconds": 12,
    }
    payload.update(overrides)
    return payload


def iso_at(delta: timedelta = timedelta()) -> str:
    return (FIXED_NOW + delta).isoformat()


def service_attempt_response() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        knowledge_card_id=1,
        rating=PracticeRating.CORRECT_SLOW,
        is_correct=True,
        used_hint=False,
        user_answer="Mocked answer",
        elapsed_seconds=12,
        error_summary=None,
        feedback="Mocked feedback",
        scheduled_next_review_at=FIXED_NOW + timedelta(days=4),
        created_at=FIXED_NOW,
    )


def service_card_response() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        title="Mocked practice card",
        category=KnowledgeCategory.PYTHON,
        difficulty=DifficultyLevel.MEDIUM,
        question_type=QuestionType.KNOWLEDGE,
        core_knowledge="Mocked core knowledge.",
        question="Mocked question.",
        reference_answer="Mocked answer.",
        scoring_rules={},
        tags=[],
        source_reference=None,
        mastery_level=MasteryLevel.FAMILIAR,
        last_practiced_at=FIXED_NOW,
        next_review_at=FIXED_NOW + timedelta(days=4),
        consecutive_correct_count=1,
        total_error_count=0,
        is_active=True,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


async def test_post_practice_attempt_returns_attempt_and_card(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    response = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(card_id=card.id, feedback="Well explained."),
    )

    assert response.status_code == 201
    data = response.json()
    assert set(data) == {"attempt", "card"}
    assert data["attempt"]["id"] > 0
    assert data["attempt"]["knowledge_card_id"] == card.id
    assert data["attempt"]["rating"] == "correct_slow"
    assert data["attempt"]["is_correct"] is True
    assert data["attempt"]["feedback"] == "Well explained."
    assert data["attempt"]["scheduled_next_review_at"] == iso_at(timedelta(days=4))
    assert data["card"]["id"] == card.id
    assert data["card"]["mastery_level"] == "familiar"
    assert data["card"]["last_practiced_at"] == iso_at()
    assert data["card"]["next_review_at"] == iso_at(timedelta(days=4))


@pytest.mark.parametrize(
    (
        "rating",
        "expected_is_correct",
        "expected_used_hint",
        "expected_mastery",
        "expected_delta",
        "expected_consecutive",
        "expected_errors",
    ),
    [
        ("dont_know", False, False, "learning", timedelta(days=1), 0, 1),
        ("with_hint", False, True, "learning", timedelta(days=2), 0, 1),
        ("correct_slow", True, False, "familiar", timedelta(days=4), 1, 0),
        (
            "correct_explain",
            True,
            False,
            "proficient",
            timedelta(days=7),
            1,
            0,
        ),
        ("transfer", True, False, "proficient", timedelta(days=14), 1, 0),
    ],
)
async def test_post_practice_attempt_applies_rating_rules(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    rating: str,
    expected_is_correct: bool,
    expected_used_hint: bool,
    expected_mastery: str,
    expected_delta: timedelta,
    expected_consecutive: int,
    expected_errors: int,
) -> None:
    card = create_card(db_session, title=f"Rating {rating}")
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    response = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(card_id=card.id, rating=rating, used_hint=False),
    )

    assert response.status_code == 201
    data = response.json()
    assert data["attempt"]["rating"] == rating
    assert data["attempt"]["is_correct"] is expected_is_correct
    assert data["attempt"]["used_hint"] is expected_used_hint
    assert data["attempt"]["scheduled_next_review_at"] == iso_at(expected_delta)
    assert data["card"]["mastery_level"] == expected_mastery
    assert data["card"]["next_review_at"] == iso_at(expected_delta)
    assert data["card"]["consecutive_correct_count"] == expected_consecutive
    assert data["card"]["total_error_count"] == expected_errors


async def test_second_transfer_schedules_thirty_day_review(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session, title="Second transfer card")
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    first = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(card_id=card.id, rating="transfer"),
    )
    second = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(card_id=card.id, rating="transfer"),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    second_data = second.json()
    assert second_data["card"]["consecutive_correct_count"] == 2
    assert second_data["card"]["mastery_level"] == "mastered"
    assert second_data["card"]["next_review_at"] == iso_at(timedelta(days=30))


async def test_post_practice_attempt_missing_card_returns_404(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(card_id=999_999, rating="dont_know"),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Knowledge card 999999 was not found."


@pytest.mark.parametrize(
    "payload",
    [
        attempt_payload(card_id=0),
        attempt_payload(card_id=1, rating="not_a_rating"),
        attempt_payload(card_id=1, elapsed_seconds=-1),
    ],
)
async def test_post_practice_attempt_invalid_payload_returns_422(
    client: httpx.AsyncClient,
    payload: dict[str, Any],
) -> None:
    response = await client.post("/api/v1/practice-attempts", json=payload)

    assert response.status_code == 422


async def test_auth_enabled_protects_practice_attempt_api(
    monkeypatch: pytest.MonkeyPatch,
    db_session: Session,
) -> None:
    card = create_card(db_session, title="Auth practice attempt card")
    monkeypatch.setenv("OFFERFORGE_AUTH_ENABLED", "true")
    monkeypatch.setenv("OFFERFORGE_AUTH_USERNAME", "offerforge")
    monkeypatch.setenv("OFFERFORGE_AUTH_PASSWORD", "test-secret")
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)
    get_settings.cache_clear()

    application = create_app()
    transport = httpx.ASGITransport(app=application)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as auth_client:
            without_auth = await auth_client.post(
                "/api/v1/practice-attempts",
                json=attempt_payload(card_id=card.id),
            )
            with_auth = await auth_client.post(
                "/api/v1/practice-attempts",
                json=attempt_payload(card_id=card.id),
                auth=("offerforge", "test-secret"),
            )

    assert without_auth.status_code == 401
    assert without_auth.headers["www-authenticate"] == "Basic"
    assert with_auth.status_code == 201


async def test_post_practice_attempt_persists_attempt_and_updates_card(
    client: httpx.AsyncClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    card = create_card(db_session, title="Persistence practice attempt card")
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    response = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(
            card_id=card.id,
            rating="with_hint",
            user_answer="Persisted answer",
            elapsed_seconds=21,
        ),
    )

    assert response.status_code == 201
    attempt_id = response.json()["attempt"]["id"]
    db_session.expire_all()
    attempt = db_session.scalar(
        select(PracticeAttempt).where(PracticeAttempt.id == attempt_id)
    )
    updated_card = db_session.get(KnowledgeCard, card.id)

    assert attempt is not None
    assert attempt.knowledge_card_id == card.id
    assert attempt.rating is PracticeRating.WITH_HINT
    assert attempt.is_correct is False
    assert attempt.used_hint is True
    assert attempt.user_answer == "Persisted answer"
    assert attempt.elapsed_seconds == 21
    assert attempt.scheduled_next_review_at == FIXED_NOW + timedelta(days=2)
    assert updated_card is not None
    assert updated_card.last_practiced_at == FIXED_NOW
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=2)
    assert updated_card.mastery_level is MasteryLevel.LEARNING
    assert updated_card.total_error_count == 1


async def test_router_uses_practice_attempt_service_dependency(
    client: httpx.AsyncClient,
) -> None:
    service = Mock()
    service.complete_practice.return_value = (
        service_attempt_response(),
        service_card_response(),
    )
    app.dependency_overrides[get_practice_attempt_service] = lambda: service

    response = await client.post(
        "/api/v1/practice-attempts",
        json=attempt_payload(card_id=1, rating="correct_slow"),
    )

    assert response.status_code == 201
    assert response.json()["attempt"]["rating"] == "correct_slow"
    service.complete_practice.assert_called_once()
    called_data = service.complete_practice.call_args.args[0]
    assert called_data.knowledge_card_id == 1
    assert called_data.rating is PracticeRating.CORRECT_SLOW

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models.enums import KnowledgeCategory, MasteryLevel, PracticeRating
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.schemas.practice_attempt import PracticeAttemptCreate
from app.services import KnowledgeCardNotFoundError, PracticeAttemptService


FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0)


def make_card_create(
    *,
    title: str = "Practice service card",
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


def make_attempt_create(
    *,
    card_id: int,
    rating: PracticeRating,
    **overrides: Any,
) -> PracticeAttemptCreate:
    payload: dict[str, Any] = {
        "knowledge_card_id": card_id,
        "rating": rating,
        "user_answer": "service answer",
    }
    payload.update(overrides)
    return PracticeAttemptCreate(**payload)


def make_service(
    db_session: Session,
) -> tuple[PracticeAttemptService, KnowledgeCardRepository, PracticeAttemptRepository]:
    card_repository = KnowledgeCardRepository(db_session)
    attempt_repository = PracticeAttemptRepository(db_session)
    return (
        PracticeAttemptService(attempt_repository, card_repository),
        card_repository,
        attempt_repository,
    )


def create_card(
    card_repository: KnowledgeCardRepository,
    *,
    title: str = "Practice service card",
):
    return card_repository.create(make_card_create(title=title))


def test_complete_practice_raises_when_card_missing(db_session: Session) -> None:
    service, _, _ = make_service(db_session)

    with pytest.raises(KnowledgeCardNotFoundError) as exc_info:
        service.complete_practice(
            make_attempt_create(card_id=999_999, rating=PracticeRating.DONT_KNOW)
        )

    assert exc_info.value.card_id == 999_999


def test_complete_practice_dont_know_updates_attempt_and_card(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, attempt_repository = make_service(db_session)
    card = create_card(card_repository)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    attempt, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.DONT_KNOW)
    )

    assert attempt.is_correct is False
    assert attempt.used_hint is False
    assert attempt.scheduled_next_review_at == FIXED_NOW + timedelta(days=1)
    assert updated_card.last_practiced_at == FIXED_NOW
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=1)
    assert updated_card.consecutive_correct_count == 0
    assert updated_card.total_error_count == 1
    assert updated_card.mastery_level is MasteryLevel.LEARNING
    assert attempt_repository.get_latest_by_card_id(card.id) is not None
    persisted_card = card_repository.get_by_id(card.id)
    assert persisted_card is not None
    assert persisted_card.total_error_count == 1


def test_complete_practice_with_hint_forces_used_hint_and_error_count(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    attempt, updated_card = service.complete_practice(
        make_attempt_create(
            card_id=card.id,
            rating=PracticeRating.WITH_HINT,
            used_hint=False,
        )
    )

    assert attempt.is_correct is False
    assert attempt.used_hint is True
    assert attempt.scheduled_next_review_at == FIXED_NOW + timedelta(days=1)
    assert updated_card.total_error_count == 1
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=1)
    assert updated_card.mastery_level is MasteryLevel.LEARNING


def test_complete_practice_correct_slow_updates_success_stats(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    card.total_error_count = 2
    card_repository.save(card)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    attempt, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.CORRECT_SLOW)
    )

    assert attempt.is_correct is True
    assert attempt.scheduled_next_review_at == FIXED_NOW + timedelta(days=2)
    assert updated_card.consecutive_correct_count == 1
    assert updated_card.total_error_count == 2
    assert updated_card.mastery_level is MasteryLevel.LEARNING
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=2)


def test_complete_practice_correct_slow_second_success_sets_familiar(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    card.consecutive_correct_count = 1
    card_repository.save(card)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    _, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.CORRECT_SLOW)
    )

    assert updated_card.consecutive_correct_count == 2
    assert updated_card.mastery_level is MasteryLevel.FAMILIAR
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=2)


def test_complete_practice_correct_explain_sets_familiar(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    _, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.CORRECT_EXPLAIN)
    )

    assert updated_card.consecutive_correct_count == 1
    assert updated_card.mastery_level is MasteryLevel.FAMILIAR
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=4)


def test_complete_practice_transfer_first_time_sets_seven_days(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    _, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.TRANSFER)
    )

    assert updated_card.consecutive_correct_count == 1
    assert updated_card.mastery_level is MasteryLevel.FAMILIAR
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=7)


def test_complete_practice_transfer_second_time_sets_fourteen_days(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    card.consecutive_correct_count = 1
    card_repository.save(card)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    _, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.TRANSFER)
    )

    assert updated_card.consecutive_correct_count == 2
    assert updated_card.mastery_level is MasteryLevel.FAMILIAR
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=14)


def test_complete_practice_transfer_third_time_sets_mastered_and_thirty_days(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    card.consecutive_correct_count = 2
    card_repository.save(card)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    _, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.TRANSFER)
    )

    assert updated_card.consecutive_correct_count == 3
    assert updated_card.mastery_level is MasteryLevel.MASTERED
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=30)


def test_complete_practice_transfer_fourth_time_sets_sixty_days(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    card.consecutive_correct_count = 3
    card.mastery_level = MasteryLevel.MASTERED
    card_repository.save(card)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    _, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.TRANSFER)
    )

    assert updated_card.consecutive_correct_count == 4
    assert updated_card.mastery_level is MasteryLevel.MASTERED
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=60)


def test_complete_practice_mastered_card_dont_know_downgrades_to_learning(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    card.consecutive_correct_count = 4
    card.total_error_count = 2
    card.mastery_level = MasteryLevel.MASTERED
    card_repository.save(card)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    attempt, updated_card = service.complete_practice(
        make_attempt_create(card_id=card.id, rating=PracticeRating.DONT_KNOW)
    )

    assert attempt.scheduled_next_review_at == FIXED_NOW + timedelta(days=1)
    assert updated_card.next_review_at == attempt.scheduled_next_review_at
    assert updated_card.mastery_level is MasteryLevel.LEARNING
    assert updated_card.consecutive_correct_count == 0
    assert updated_card.total_error_count == 3


def test_complete_practice_preserves_user_is_correct_but_stats_follow_rating(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, _ = make_service(db_session)
    card = create_card(card_repository)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    attempt, updated_card = service.complete_practice(
        make_attempt_create(
            card_id=card.id,
            rating=PracticeRating.TRANSFER,
            is_correct=False,
        )
    )

    assert attempt.is_correct is False
    assert updated_card.consecutive_correct_count == 1
    assert updated_card.total_error_count == 0
    assert updated_card.next_review_at == FIXED_NOW + timedelta(days=7)


def test_complete_practice_returns_attempt_and_updated_card(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, card_repository, attempt_repository = make_service(db_session)
    card = create_card(card_repository)
    monkeypatch.setattr("app.services.practice_attempt.utc_now", lambda: FIXED_NOW)

    attempt, updated_card = service.complete_practice(
        make_attempt_create(
            card_id=card.id,
            rating=PracticeRating.CORRECT_EXPLAIN,
            elapsed_seconds=33,
            feedback="Good explanation.",
        )
    )

    assert attempt.id is not None
    assert updated_card.id == card.id
    latest_attempt = attempt_repository.get_latest_by_card_id(card.id)
    persisted_card = card_repository.get_by_id(card.id)
    assert latest_attempt is not None
    assert latest_attempt.elapsed_seconds == 33
    assert latest_attempt.feedback == "Good explanation."
    assert persisted_card is not None
    assert persisted_card.last_practiced_at == FIXED_NOW

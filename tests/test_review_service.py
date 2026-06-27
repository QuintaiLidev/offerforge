from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.services import ReviewService

FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0)


def card_response(
    *,
    card_id: int,
    title: str,
    mastery_level: MasteryLevel = MasteryLevel.NEW,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=card_id,
        title=title,
        category=KnowledgeCategory.PYTHON,
        difficulty=DifficultyLevel.MEDIUM,
        question_type=QuestionType.KNOWLEDGE,
        mastery_level=mastery_level,
        next_review_at=None,
        consecutive_correct_count=0,
        total_error_count=0,
        is_active=True,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def test_get_today_reviews_returns_due_cards_without_new_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Mock()
    due_card = card_response(
        card_id=1,
        title="Due card",
        mastery_level=MasteryLevel.LEARNING,
    )
    repository.list_due_for_review.return_value = ([due_card], 1)
    service = ReviewService(repository)
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = service.get_today_reviews(limit=10)

    assert response.mode == "due"
    assert response.items[0].id == due_card.id
    assert response.total == 1
    assert response.limit == 10
    assert response.generated_at == FIXED_NOW
    repository.list_due_for_review.assert_called_once_with(FIXED_NOW, limit=10)
    repository.list_new_for_review.assert_not_called()


def test_get_today_reviews_falls_back_to_new_cards_when_no_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Mock()
    new_card = card_response(card_id=2, title="New card")
    repository.list_due_for_review.return_value = ([], 0)
    repository.list_new_for_review.return_value = ([new_card], 1)
    service = ReviewService(repository)
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = service.get_today_reviews(limit=5)

    assert response.mode == "new"
    assert response.items[0].id == new_card.id
    assert response.total == 1
    assert response.limit == 5
    assert response.generated_at == FIXED_NOW
    repository.list_due_for_review.assert_called_once_with(FIXED_NOW, limit=5)
    repository.list_new_for_review.assert_called_once_with(limit=5)


@pytest.mark.parametrize("limit", [0, 51])
def test_get_today_reviews_rejects_invalid_limit(limit: int) -> None:
    service = ReviewService(Mock())

    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        service.get_today_reviews(limit=limit)

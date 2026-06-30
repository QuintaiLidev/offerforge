from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    PracticeRating,
    QuestionType,
)
from app.services.review import ReviewService, balance_cards_by_category

FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0)


def card_response(
    *,
    card_id: int,
    title: str,
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    mastery_level: MasteryLevel = MasteryLevel.NEW,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=card_id,
        title=title,
        category=category,
        difficulty=DifficultyLevel.MEDIUM,
        question_type=QuestionType.KNOWLEDGE,
        core_knowledge=f"Core knowledge for {title}",
        question=f"Question about {title}",
        reference_answer=f"Reference answer for {title}",
        scoring_rules={},
        tags=[],
        source_reference="interview-week1-v4",
        mastery_level=mastery_level,
        last_practiced_at=None,
        next_review_at=None,
        consecutive_correct_count=0,
        total_error_count=0,
        is_active=True,
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def item_ids(items: list[SimpleNamespace]) -> list[int]:
    return [item.id for item in items]


def make_attempt_repository_mock(
    practiced_categories: list[str] | None = None,
) -> Mock:
    attempt_repository = Mock()
    attempt_repository.list_practiced_categories_for_period.return_value = (
        practiced_categories or []
    )
    return attempt_repository


def attempt_response(
    *,
    attempt_id: int,
    card_id: int,
    created_at: datetime = FIXED_NOW,
    rating: PracticeRating = PracticeRating.CORRECT_EXPLAIN,
    user_answer: str | None = "My answer",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=attempt_id,
        knowledge_card_id=card_id,
        rating=rating,
        is_correct=True,
        used_hint=False,
        user_answer=user_answer,
        elapsed_seconds=30,
        error_summary=None,
        feedback=None,
        scheduled_next_review_at=created_at,
        created_at=created_at,
    )


def test_balance_cards_by_category_round_robins_multiple_categories() -> None:
    cards = [
        card_response(card_id=1, title="Python 1"),
        card_response(card_id=2, title="Python 2"),
        card_response(card_id=3, title="Python 3"),
        card_response(card_id=4, title="SQL 1", category=KnowledgeCategory.SQL),
        card_response(card_id=5, title="SQL 2", category=KnowledgeCategory.SQL),
        card_response(card_id=6, title="SQL 3", category=KnowledgeCategory.SQL),
        card_response(
            card_id=7,
            title="Selenium 1",
            category=KnowledgeCategory.SELENIUM,
        ),
        card_response(
            card_id=8,
            title="Selenium 2",
            category=KnowledgeCategory.SELENIUM,
        ),
    ]

    balanced = balance_cards_by_category(
        cards,
        limit=6,
        today=date(2026, 6, 27),
    )

    assert item_ids(balanced) != [1, 2, 3, 4, 5, 6]
    assert len({card.category for card in balanced[:3]}) == 3


def test_balance_cards_by_category_is_stable_for_same_day() -> None:
    cards = [
        card_response(card_id=1, title="Python 1"),
        card_response(card_id=2, title="SQL 1", category=KnowledgeCategory.SQL),
        card_response(
            card_id=3,
            title="Selenium 1",
            category=KnowledgeCategory.SELENIUM,
        ),
        card_response(
            card_id=4,
            title="API 1",
            category=KnowledgeCategory.HTTP_API_TESTING,
        ),
        card_response(card_id=5, title="Python 2"),
        card_response(card_id=6, title="SQL 2", category=KnowledgeCategory.SQL),
        card_response(
            card_id=7,
            title="Selenium 2",
            category=KnowledgeCategory.SELENIUM,
        ),
        card_response(
            card_id=8,
            title="API 2",
            category=KnowledgeCategory.HTTP_API_TESTING,
        ),
    ]

    first = balance_cards_by_category(cards, limit=8, today=date(2026, 6, 27))
    second = balance_cards_by_category(cards, limit=8, today=date(2026, 6, 27))

    assert item_ids(first) == item_ids(second)


def test_balance_cards_by_category_can_change_across_days() -> None:
    cards = [
        card_response(card_id=1, title="Python 1"),
        card_response(card_id=2, title="SQL 1", category=KnowledgeCategory.SQL),
        card_response(
            card_id=3,
            title="Selenium 1",
            category=KnowledgeCategory.SELENIUM,
        ),
        card_response(
            card_id=4,
            title="API 1",
            category=KnowledgeCategory.HTTP_API_TESTING,
        ),
        card_response(card_id=5, title="Python 2"),
        card_response(card_id=6, title="SQL 2", category=KnowledgeCategory.SQL),
        card_response(
            card_id=7,
            title="Selenium 2",
            category=KnowledgeCategory.SELENIUM,
        ),
        card_response(
            card_id=8,
            title="API 2",
            category=KnowledgeCategory.HTTP_API_TESTING,
        ),
    ]

    first = balance_cards_by_category(cards, limit=8, today=date(2026, 6, 27))
    next_day = balance_cards_by_category(cards, limit=8, today=date(2026, 6, 28))

    assert item_ids(first) != item_ids(next_day)


def test_balance_cards_by_category_handles_single_category_and_short_candidates() -> None:
    cards = [
        card_response(card_id=1, title="Python 1"),
        card_response(card_id=2, title="Python 2"),
        card_response(card_id=3, title="Python 3"),
    ]

    balanced = balance_cards_by_category(
        cards,
        limit=10,
        today=date(2026, 6, 27),
    )

    assert len(balanced) == 3
    assert {card.category for card in balanced} == {KnowledgeCategory.PYTHON}


def test_balance_cards_by_category_prefers_less_practiced_categories() -> None:
    cards = [
        card_response(card_id=1, title="SQL 1", category=KnowledgeCategory.SQL),
        card_response(card_id=2, title="SQL 2", category=KnowledgeCategory.SQL),
        card_response(card_id=3, title="HR 1", category=KnowledgeCategory.HR_INTERVIEW),
        card_response(card_id=4, title="Python 1"),
    ]

    balanced = balance_cards_by_category(
        cards,
        limit=4,
        today=date(2026, 6, 27),
        practiced_category_counts={"sql": 3},
        recent_practiced_categories=["sql", "sql"],
    )

    assert balanced[0].category is not KnowledgeCategory.SQL
    assert KnowledgeCategory.SQL in {card.category for card in balanced}


def test_balance_cards_by_category_avoids_more_than_two_repeats_when_possible() -> None:
    cards = [
        *[
            card_response(
                card_id=index,
                title=f"SQL {index}",
                category=KnowledgeCategory.SQL,
            )
            for index in range(1, 6)
        ],
        card_response(card_id=6, title="Python 1"),
        card_response(card_id=7, title="Python 2"),
        card_response(
            card_id=8,
            title="HR 1",
            category=KnowledgeCategory.HR_INTERVIEW,
        ),
    ]

    balanced = balance_cards_by_category(
        cards,
        limit=8,
        today=date(2026, 6, 27),
        recent_practiced_categories=["sql", "sql"],
    )
    categories = [card.category for card in balanced]

    assert all(
        not (
            categories[index]
            == categories[index + 1]
            == categories[index + 2]
            and len(set(categories[index:])) > 1
        )
        for index in range(len(categories) - 2)
    )


def test_get_today_reviews_returns_only_due_cards_when_due_reaches_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Mock()
    due_cards = [
        card_response(
            card_id=index,
            title=f"Due card {index}",
            category=KnowledgeCategory.PYTHON
            if index % 2
            else KnowledgeCategory.SQL,
            mastery_level=MasteryLevel.LEARNING,
        )
        for index in range(1, 9)
    ]
    repository.list_due_for_review.return_value = (due_cards, len(due_cards))
    attempt_repository = make_attempt_repository_mock()
    service = ReviewService(repository, attempt_repository)
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = service.get_today_reviews(limit=5)

    assert response.mode == "due"
    assert len(response.items) == 5
    assert {item.id for item in response.items} <= {card.id for card in due_cards}
    assert response.total == 8
    assert response.limit == 5
    assert response.generated_at == FIXED_NOW
    repository.list_due_for_review.assert_called_once_with(FIXED_NOW, limit=5)
    repository.list_new_for_review.assert_not_called()
    attempt_repository.list_practiced_categories_for_period.assert_called_once()


def test_get_today_reviews_keeps_due_before_new_when_due_is_short(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Mock()
    due_cards = [
        card_response(
            card_id=1,
            title="Due Python",
            category=KnowledgeCategory.PYTHON,
            mastery_level=MasteryLevel.LEARNING,
        ),
        card_response(
            card_id=2,
            title="Due SQL",
            category=KnowledgeCategory.SQL,
            mastery_level=MasteryLevel.LEARNING,
        ),
        card_response(
            card_id=3,
            title="Due Selenium",
            category=KnowledgeCategory.SELENIUM,
            mastery_level=MasteryLevel.LEARNING,
        ),
    ]
    new_cards = [
        card_response(
            card_id=4,
            title="New Python",
            category=KnowledgeCategory.PYTHON,
        ),
        card_response(card_id=5, title="New SQL", category=KnowledgeCategory.SQL),
        card_response(
            card_id=6,
            title="New API",
            category=KnowledgeCategory.HTTP_API_TESTING,
        ),
    ]
    repository.list_due_for_review.return_value = (due_cards, len(due_cards))
    repository.list_new_for_review.return_value = (new_cards, len(new_cards))
    service = ReviewService(repository, make_attempt_repository_mock())
    monkeypatch.setattr("app.services.review.utc_now", lambda: FIXED_NOW)

    response = service.get_today_reviews(limit=6)

    returned_ids = item_ids(response.items)
    assert response.mode == "due"
    assert {1, 2, 3} <= set(returned_ids)
    assert set(returned_ids) == {1, 2, 3, 4, 5, 6}
    assert response.total == 6
    repository.list_due_for_review.assert_called_once_with(FIXED_NOW, limit=6)
    repository.list_new_for_review.assert_called_once_with(limit=3)


def test_get_today_reviews_returns_new_cards_when_no_due(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Mock()
    new_card = card_response(card_id=2, title="New card")
    repository.list_due_for_review.return_value = ([], 0)
    repository.list_new_for_review.return_value = ([new_card], 1)
    service = ReviewService(repository, make_attempt_repository_mock())
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
    with pytest.raises(ValueError, match="limit must be between 1 and 50"):
        service = ReviewService(Mock(), make_attempt_repository_mock())
        service.get_today_reviews(limit=limit)


def test_get_today_reviews_prioritizes_less_practiced_categories() -> None:
    repository = Mock()
    due_cards = [
        card_response(card_id=1, title="SQL 1", category=KnowledgeCategory.SQL),
        card_response(card_id=2, title="SQL 2", category=KnowledgeCategory.SQL),
        card_response(card_id=3, title="SQL 3", category=KnowledgeCategory.SQL),
        card_response(
            card_id=4,
            title="HR interview",
            category=KnowledgeCategory.HR_INTERVIEW,
        ),
        card_response(card_id=5, title="Python interview"),
    ]
    repository.list_due_for_review.return_value = (due_cards, len(due_cards))
    attempt_repository = make_attempt_repository_mock(
        practiced_categories=["sql", "sql", "sql"]
    )
    service = ReviewService(repository, attempt_repository)

    response = service.get_today_reviews(limit=5)

    assert response.items[0].category is not KnowledgeCategory.SQL
    assert {item.id for item in response.items} == {1, 2, 3, 4, 5}


def test_get_practice_history_returns_recent_attempts_with_cards() -> None:
    card = card_response(card_id=1, title="History card")
    attempt = attempt_response(
        attempt_id=10,
        card_id=card.id,
        user_answer="History answer",
    )
    attempt_repository = Mock()
    attempt_repository.list_recent_with_cards.return_value = [(card, attempt)]
    service = ReviewService(Mock(), attempt_repository)

    response = service.get_practice_history(limit=25)

    assert len(response.items) == 1
    item = response.items[0]
    assert item.attempt_id == attempt.id
    assert item.rating is PracticeRating.CORRECT_EXPLAIN
    assert item.user_answer == "History answer"
    assert item.card.id == card.id
    assert item.card.title == "History card"
    attempt_repository.list_recent_with_cards.assert_called_once_with(limit=25)


@pytest.mark.parametrize("limit", [0, 101])
def test_get_practice_history_rejects_invalid_limit(limit: int) -> None:
    service = ReviewService(Mock(), Mock())

    with pytest.raises(ValueError, match="limit must be between 1 and 100"):
        service.get_practice_history(limit=limit)

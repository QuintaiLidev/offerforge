from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import DEFAULT_DATABASE_PATH
from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    PracticeRating,
    QuestionType,
)
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate, KnowledgeCardUpdate


def make_card_create(
    *,
    title: str = "Python list comprehension",
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    **overrides: Any,
) -> KnowledgeCardCreate:
    payload: dict[str, Any] = {
        "title": title,
        "category": category,
        "core_knowledge": f"Core knowledge for {title}",
        "question": f"Question about {title}",
        "reference_answer": f"Reference answer for {title}",
        "scoring_rules": {"must_include": ["key point"]},
        "tags": ["python", "practice"],
    }
    payload.update(overrides)
    return KnowledgeCardCreate(**payload)


def make_repository(db_session: Session) -> KnowledgeCardRepository:
    return KnowledgeCardRepository(db_session)


def test_create_persists_knowledge_card_with_defaults(db_session: Session) -> None:
    repository = make_repository(db_session)

    card = repository.create(make_card_create())

    assert card.id is not None
    assert card.difficulty is DifficultyLevel.MEDIUM
    assert card.question_type is QuestionType.KNOWLEDGE
    assert card.mastery_level is MasteryLevel.NEW
    assert card.scoring_rules == {"must_include": ["key point"]}
    assert card.tags == ["python", "practice"]

    persisted = db_session.get(KnowledgeCard, card.id)
    assert persisted is not None
    assert persisted.title == "Python list comprehension"


def test_get_by_id_returns_card_or_none(db_session: Session) -> None:
    repository = make_repository(db_session)
    card = repository.create(make_card_create())

    assert repository.get_by_id(card.id) == card
    assert repository.get_by_id(999_999) is None


def test_get_by_source_category_and_title_uses_exact_source_category_and_title(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    python_card = repository.create(
        make_card_create(
            title="JOIN basics",
            category=KnowledgeCategory.PYTHON,
            source_reference="interview-week1-v3",
        )
    )
    repository.create(
        make_card_create(
            title="JOIN basics",
            category=KnowledgeCategory.PYTHON,
            source_reference="interview-week1-v4",
        )
    )
    repository.create(
        make_card_create(
            title="JOIN basics",
            category=KnowledgeCategory.SQL,
            source_reference="interview-week1-v3",
        )
    )

    found = repository.get_by_source_category_and_title(
        "interview-week1-v3",
        KnowledgeCategory.PYTHON,
        "JOIN basics",
    )

    assert found == python_card
    assert (
        repository.get_by_source_category_and_title(
            "interview-week1-v5",
            KnowledgeCategory.PYTHON,
            "JOIN basics",
        )
        is None
    )


def test_list_paginates_total_and_uses_stable_order(db_session: Session) -> None:
    repository = make_repository(db_session)
    cards = [
        repository.create(make_card_create(title=f"Card {index}"))
        for index in range(5)
    ]
    shared_created_at = cards[-1].created_at
    for card in cards:
        card.created_at = shared_created_at
    db_session.commit()

    first_page, first_total = repository.list(offset=0, limit=2)
    second_page, second_total = repository.list(offset=2, limit=2)

    assert first_total == 5
    assert second_total == 5
    assert len(first_page) == 2
    assert len(second_page) == 2
    assert [card.id for card in first_page] == [cards[4].id, cards[3].id]
    assert [card.id for card in second_page] == [cards[2].id, cards[1].id]


def test_list_supports_combined_filters(db_session: Session) -> None:
    repository = make_repository(db_session)
    target = repository.create(
        make_card_create(
            title="SQL window function",
            category=KnowledgeCategory.SQL,
            difficulty=DifficultyLevel.HARD,
            question_type=QuestionType.SQL,
        )
    )
    target.mastery_level = MasteryLevel.FAMILIAR
    target.is_active = False
    db_session.commit()
    db_session.refresh(target)
    repository.create(
        make_card_create(
            title="SQL easy question",
            category=KnowledgeCategory.SQL,
            difficulty=DifficultyLevel.EASY,
            question_type=QuestionType.SQL,
        )
    )
    repository.create(
        make_card_create(
            title="Python hard question",
            category=KnowledgeCategory.PYTHON,
            difficulty=DifficultyLevel.HARD,
            question_type=QuestionType.PYTHON_CODE,
        )
    )

    items, total = repository.list(
        category=KnowledgeCategory.SQL,
        difficulty=DifficultyLevel.HARD,
        mastery_level=MasteryLevel.FAMILIAR,
        question_type=QuestionType.SQL,
        is_active=False,
    )

    assert total == 1
    assert items == [target]


def test_list_due_for_review_filters_active_due_cards_and_orders_stably(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    now = datetime(2026, 6, 27, 12, 0, 0)
    due_later = repository.create(make_card_create(title="Due later"))
    due_earlier = repository.create(make_card_create(title="Due earlier"))
    due_exact = repository.create(make_card_create(title="Due exact"))
    future = repository.create(make_card_create(title="Future review"))
    inactive_due = repository.create(make_card_create(title="Inactive due"))
    unscheduled = repository.create(make_card_create(title="Unscheduled"))

    due_later.next_review_at = now - timedelta(hours=1)
    due_earlier.next_review_at = now - timedelta(days=1)
    due_exact.next_review_at = now
    future.next_review_at = now + timedelta(seconds=1)
    inactive_due.next_review_at = now - timedelta(days=2)
    inactive_due.is_active = False
    unscheduled.next_review_at = None
    db_session.commit()

    items, total = repository.list_due_for_review(now, limit=2)

    assert total == 3
    assert [card.id for card in items] == [due_earlier.id, due_later.id]


def test_list_new_for_review_filters_active_new_cards_and_orders_stably(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    older_new = repository.create(make_card_create(title="Older new"))
    newer_new = repository.create(make_card_create(title="Newer new"))
    familiar = repository.create(make_card_create(title="Familiar card"))
    inactive_new = repository.create(make_card_create(title="Inactive new"))

    older_new.created_at = datetime(2026, 6, 20, 9, 0, 0)
    newer_new.created_at = datetime(2026, 6, 21, 9, 0, 0)
    familiar.mastery_level = MasteryLevel.FAMILIAR
    familiar.created_at = datetime(2026, 6, 19, 9, 0, 0)
    inactive_new.is_active = False
    inactive_new.created_at = datetime(2026, 6, 18, 9, 0, 0)
    db_session.commit()

    items, total = repository.list_new_for_review(limit=1)

    assert total == 2
    assert items == [older_new]


@pytest.mark.parametrize("method_name", ["list_due_for_review", "list_new_for_review"])
def test_review_query_methods_reject_negative_limit(
    db_session: Session,
    method_name: str,
) -> None:
    repository = make_repository(db_session)

    with pytest.raises(ValueError):
        if method_name == "list_due_for_review":
            repository.list_due_for_review(datetime(2026, 6, 27, 12, 0, 0), limit=-1)
        else:
            repository.list_new_for_review(limit=-1)


def test_keyword_search_matches_title_core_knowledge_and_question(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    title_match = repository.create(make_card_create(title="HTTP token testing"))
    core_match = repository.create(
        make_card_create(
            title="Core match",
            core_knowledge="Learn how cookies behave in browser sessions.",
            question="A neutral prompt.",
        )
    )
    question_match = repository.create(
        make_card_create(
            title="Question match",
            core_knowledge="A neutral core.",
            question="How do you test Selenium iframe switching?",
        )
    )
    repository.create(
        make_card_create(
            title="Unrelated card",
            core_knowledge="No shared term.",
            question="No shared term here either.",
        )
    )

    title_items, title_total = repository.list(keyword=" token ")
    core_items, core_total = repository.list(keyword="COOKIES")
    question_items, question_total = repository.list(keyword="iframe")
    blank_items, blank_total = repository.list(keyword="   ")
    unrelated_items, unrelated_total = repository.list(keyword="does-not-exist")

    assert title_items == [title_match]
    assert title_total == 1
    assert core_items == [core_match]
    assert core_total == 1
    assert question_items == [question_match]
    assert question_total == 1
    assert blank_total == 4
    assert len(blank_items) == 4
    assert unrelated_items == []
    assert unrelated_total == 0


def test_update_changes_only_provided_fields_and_persists(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    card = repository.create(make_card_create())
    original_category = card.category
    original_question = card.question
    original_updated_at = card.updated_at

    updated = repository.update(
        card,
        KnowledgeCardUpdate(
            title="Updated Python list comprehension",
            reference_answer="Updated reference answer.",
            tags=["python", "updated"],
        ),
    )

    assert updated.title == "Updated Python list comprehension"
    assert updated.reference_answer == "Updated reference answer."
    assert updated.tags == ["python", "updated"]
    assert updated.category is original_category
    assert updated.question == original_question
    assert updated.updated_at >= original_updated_at

    persisted = repository.get_by_id(card.id)
    assert persisted is not None
    assert persisted.title == "Updated Python list comprehension"
    assert persisted.reference_answer == "Updated reference answer."


def test_save_persists_direct_card_changes(db_session: Session) -> None:
    repository = make_repository(db_session)
    card = repository.create(make_card_create())

    card.consecutive_correct_count = 2
    card.mastery_level = MasteryLevel.MASTERED
    saved = repository.save(card)

    assert saved.consecutive_correct_count == 2
    assert saved.mastery_level is MasteryLevel.MASTERED
    persisted = repository.get_by_id(card.id)
    assert persisted is not None
    assert persisted.consecutive_correct_count == 2
    assert persisted.mastery_level is MasteryLevel.MASTERED


def test_delete_removes_card_and_cascades_attempts(db_session: Session) -> None:
    repository = make_repository(db_session)
    card = repository.create(make_card_create())
    attempt = PracticeAttempt(
        knowledge_card_id=card.id,
        rating=PracticeRating.DONT_KNOW,
    )
    db_session.add(attempt)
    db_session.commit()

    repository.delete(card)

    assert repository.get_by_id(card.id) is None
    attempts_count = db_session.scalar(select(func.count()).select_from(PracticeAttempt))
    assert attempts_count == 0


def test_create_unique_constraint_failure_rolls_back_session(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    repository.create(
        make_card_create(
            title="Duplicate title",
            category=KnowledgeCategory.PYTHON,
            source_reference="interview-week1-v3",
        )
    )
    cross_source_card = repository.create(
        make_card_create(
            title="Duplicate title",
            category=KnowledgeCategory.PYTHON,
            source_reference="interview-week1-v4",
        )
    )

    with pytest.raises(IntegrityError):
        repository.create(
            make_card_create(
                title="Duplicate title",
                category=KnowledgeCategory.PYTHON,
                source_reference="interview-week1-v3",
            )
        )

    valid_card = repository.create(
        make_card_create(title="Valid after rollback", category=KnowledgeCategory.PYTHON)
    )

    assert cross_source_card.id is not None
    assert valid_card.id is not None
    assert repository.get_by_id(valid_card.id) == valid_card


def test_exists_by_source_category_and_title_supports_excluding_current_card(
    db_session: Session,
) -> None:
    repository = make_repository(db_session)
    current = repository.create(
        make_card_create(
            title="Same title",
            category=KnowledgeCategory.SQL,
            source_reference="interview-week1-v3",
        )
    )
    other = repository.create(
        make_card_create(
            title="Existing SQL title",
            category=KnowledgeCategory.SQL,
            source_reference="interview-week1-v3",
        )
    )
    repository.create(
        make_card_create(
            title="Same title",
            category=KnowledgeCategory.SQL,
            source_reference="interview-week1-v4",
        )
    )

    assert repository.exists_by_source_category_and_title(
        "interview-week1-v3",
        KnowledgeCategory.SQL,
        "Same title",
    )
    assert not repository.exists_by_source_category_and_title(
        "interview-week1-v3",
        KnowledgeCategory.SQL,
        "Same title",
        exclude_id=current.id,
    )

    assert repository.exists_by_source_category_and_title(
        "interview-week1-v3",
        KnowledgeCategory.SQL,
        other.title,
        exclude_id=current.id,
    )
    assert not repository.exists_by_source_category_and_title(
        "interview-week1-v5",
        KnowledgeCategory.SQL,
        "Same title",
    )


@pytest.mark.parametrize(
    ("offset", "limit"),
    [(-1, 20), (0, -1)],
)
def test_list_rejects_negative_pagination_values(
    db_session: Session,
    offset: int,
    limit: int,
) -> None:
    repository = make_repository(db_session)

    with pytest.raises(ValueError):
        repository.list(offset=offset, limit=limit)


def test_repository_tests_do_not_touch_default_database(
    db_session: Session,
    test_db_path: Path,
) -> None:
    default_db_exists_before = DEFAULT_DATABASE_PATH.exists()
    default_db_stat_before = (
        DEFAULT_DATABASE_PATH.stat() if default_db_exists_before else None
    )
    repository = make_repository(db_session)

    card = repository.create(make_card_create(title="Isolation check"))

    assert card.id is not None
    assert test_db_path.exists()
    assert DEFAULT_DATABASE_PATH.exists() is default_db_exists_before
    if default_db_stat_before is not None:
        default_db_stat_after = DEFAULT_DATABASE_PATH.stat()
        assert default_db_stat_after.st_size == default_db_stat_before.st_size
        assert default_db_stat_after.st_mtime_ns == default_db_stat_before.st_mtime_ns

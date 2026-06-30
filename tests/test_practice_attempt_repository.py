from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models.enums import KnowledgeCategory, PracticeRating
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.schemas.practice_attempt import PracticeAttemptCreate


def make_card_create(
    *,
    title: str = "Practice repository card",
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
    title: str = "Practice repository card",
    *,
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
) -> int:
    card = KnowledgeCardRepository(db_session).create(
        make_card_create(title=title, category=category)
    )
    return card.id


def make_attempt_create(
    *,
    card_id: int,
    rating: PracticeRating = PracticeRating.DONT_KNOW,
    **overrides: Any,
) -> PracticeAttemptCreate:
    payload: dict[str, Any] = {
        "knowledge_card_id": card_id,
        "rating": rating,
        "user_answer": "attempt answer",
    }
    payload.update(overrides)
    return PracticeAttemptCreate(**payload)


def test_create_persists_attempt_and_relationship(db_session: Session) -> None:
    card_id = create_card(db_session)
    repository = PracticeAttemptRepository(db_session)

    attempt = repository.create(
        make_attempt_create(
            card_id=card_id,
            rating=PracticeRating.CORRECT_EXPLAIN,
            used_hint=True,
        )
    )

    assert attempt.id is not None
    assert attempt.knowledge_card_id == card_id
    assert attempt.rating is PracticeRating.CORRECT_EXPLAIN
    assert attempt.used_hint is True
    assert attempt.knowledge_card.id == card_id


def test_get_latest_by_card_id_returns_most_recent_attempt(
    db_session: Session,
) -> None:
    card_id = create_card(db_session)
    repository = PracticeAttemptRepository(db_session)
    first = repository.create(make_attempt_create(card_id=card_id))
    second = repository.create(
        make_attempt_create(card_id=card_id, rating=PracticeRating.TRANSFER)
    )
    shared_created_at = datetime(2026, 6, 27, 12, 0, 0)
    first.created_at = shared_created_at
    second.created_at = shared_created_at
    db_session.commit()

    latest = repository.get_latest_by_card_id(card_id)

    assert latest == second
    assert repository.get_latest_by_card_id(999_999) is None


def test_list_by_card_id_paginates_total_and_uses_stable_order(
    db_session: Session,
) -> None:
    card_id = create_card(db_session)
    other_card_id = create_card(db_session, title="Other card")
    repository = PracticeAttemptRepository(db_session)
    attempts = [
        repository.create(make_attempt_create(card_id=card_id))
        for _ in range(5)
    ]
    repository.create(make_attempt_create(card_id=other_card_id))
    shared_created_at = datetime(2026, 6, 27, 12, 0, 0)
    for attempt in attempts:
        attempt.created_at = shared_created_at
    db_session.commit()

    first_page, first_total = repository.list_by_card_id(card_id, limit=2, offset=0)
    second_page, second_total = repository.list_by_card_id(card_id, limit=2, offset=2)

    assert first_total == 5
    assert second_total == 5
    assert [attempt.id for attempt in first_page] == [attempts[4].id, attempts[3].id]
    assert [attempt.id for attempt in second_page] == [attempts[2].id, attempts[1].id]


def test_list_by_card_id_returns_empty_for_missing_card_id(
    db_session: Session,
) -> None:
    repository = PracticeAttemptRepository(db_session)

    items, total = repository.list_by_card_id(999_999)

    assert items == []
    assert total == 0


def test_list_practiced_categories_for_period_orders_recent_first(
    db_session: Session,
) -> None:
    python_card_id = create_card(db_session, title="Python category")
    sql_card_id = create_card(
        db_session,
        title="SQL category",
        category=KnowledgeCategory.SQL,
    )
    repository = PracticeAttemptRepository(db_session)
    older = repository.create(
        make_attempt_create(card_id=python_card_id, rating=PracticeRating.TRANSFER)
    )
    newer = repository.create(
        make_attempt_create(card_id=sql_card_id, rating=PracticeRating.DONT_KNOW)
    )
    outside = repository.create(
        make_attempt_create(card_id=python_card_id, rating=PracticeRating.WITH_HINT)
    )
    older.created_at = datetime(2026, 6, 27, 9, 0, 0)
    newer.created_at = datetime(2026, 6, 27, 11, 0, 0)
    outside.created_at = datetime(2026, 6, 26, 23, 0, 0)
    db_session.commit()

    categories = repository.list_practiced_categories_for_period(
        start_at=datetime(2026, 6, 27, 0, 0, 0),
        end_at=datetime(2026, 6, 28, 0, 0, 0),
    )

    assert categories == ["sql", "python"]


@pytest.mark.parametrize(
    ("limit", "offset"),
    [(-1, 0), (20, -1)],
)
def test_list_by_card_id_rejects_negative_pagination(
    db_session: Session,
    limit: int,
    offset: int,
) -> None:
    repository = PracticeAttemptRepository(db_session)

    with pytest.raises(ValueError):
        repository.list_by_card_id(1, limit=limit, offset=offset)

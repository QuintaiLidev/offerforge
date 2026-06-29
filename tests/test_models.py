from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import KnowledgeCard, PracticeAttempt
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    PracticeRating,
    QuestionType,
)


def build_knowledge_card(
    *,
    title: str = "Explain Python list and tuple differences",
    category: KnowledgeCategory = KnowledgeCategory.PYTHON,
    source_reference: str | None = None,
) -> KnowledgeCard:
    return KnowledgeCard(
        title=title,
        category=category,
        core_knowledge="Python sequence types and mutability.",
        question="Explain the difference between list and tuple.",
        reference_answer="A list is mutable; a tuple is immutable.",
        source_reference=source_reference,
    )


def test_knowledge_card_can_be_created_with_expected_defaults(
    db_session: Session,
) -> None:
    first_card = build_knowledge_card()
    second_card = build_knowledge_card(title="Explain Python dict and set usage")
    db_session.add_all([first_card, second_card])
    db_session.commit()
    db_session.refresh(first_card)
    db_session.refresh(second_card)

    assert first_card.id is not None
    assert first_card.difficulty is DifficultyLevel.MEDIUM
    assert first_card.question_type is QuestionType.KNOWLEDGE
    assert first_card.mastery_level is MasteryLevel.NEW
    assert first_card.consecutive_correct_count == 0
    assert first_card.total_error_count == 0
    assert first_card.is_active is True
    assert first_card.scoring_rules == {}
    assert first_card.tags == []

    assert first_card.scoring_rules is not second_card.scoring_rules
    assert first_card.tags is not second_card.tags

    first_card.scoring_rules["must_include"] = "mutability"
    first_card.tags.append("python")

    assert second_card.scoring_rules == {}
    assert second_card.tags == []


def test_practice_attempt_can_be_created_and_read_through_relationship(
    db_session: Session,
) -> None:
    card = build_knowledge_card()
    db_session.add(card)
    db_session.flush()

    attempt = PracticeAttempt(
        knowledge_card_id=card.id,
        rating=PracticeRating.CORRECT_EXPLAIN,
        user_answer="Lists are mutable and tuples are immutable.",
        elapsed_seconds=42,
    )
    db_session.add(attempt)
    db_session.commit()
    db_session.refresh(card)
    db_session.refresh(attempt)

    assert attempt.rating is PracticeRating.CORRECT_EXPLAIN
    assert attempt.used_hint is False
    assert attempt.knowledge_card == card
    assert card.practice_attempts == [attempt]


def test_knowledge_card_title_is_unique_within_source_and_category(
    db_session: Session,
) -> None:
    db_session.add_all(
        [
            build_knowledge_card(
                title="JOIN basics",
                category=KnowledgeCategory.SQL,
                source_reference="interview-week1-v3",
            ),
            build_knowledge_card(
                title="JOIN basics",
                category=KnowledgeCategory.SQL,
                source_reference="interview-week1-v3",
            ),
        ]
    )

    try:
        db_session.commit()
    except IntegrityError:
        db_session.rollback()
    else:
        raise AssertionError("Expected duplicate title/category to fail.")

    db_session.add_all(
        [
            build_knowledge_card(
                title="JOIN basics",
                category=KnowledgeCategory.SQL,
                source_reference="interview-week1-v3",
            ),
            build_knowledge_card(
                title="JOIN basics",
                category=KnowledgeCategory.SQL,
                source_reference="interview-week1-v4",
            ),
            build_knowledge_card(
                title="JOIN basics",
                category=KnowledgeCategory.PROJECT_EXPLANATION,
                source_reference="interview-week1-v3",
            ),
        ]
    )
    db_session.commit()

    card_count = db_session.scalar(select(func.count()).select_from(KnowledgeCard))
    assert card_count == 3


def test_database_cascade_deletes_attempts_when_card_is_deleted(
    db_session: Session,
) -> None:
    foreign_keys_enabled = db_session.scalar(text("PRAGMA foreign_keys"))
    assert foreign_keys_enabled == 1

    card = build_knowledge_card(title="HTTP status codes")
    db_session.add(card)
    db_session.flush()
    attempt = PracticeAttempt(
        knowledge_card_id=card.id,
        rating=PracticeRating.WITH_HINT,
    )
    db_session.add(attempt)
    db_session.commit()

    card_id = card.id
    db_session.execute(
        text("DELETE FROM knowledge_cards WHERE id = :card_id"),
        {"card_id": card_id},
    )
    db_session.commit()

    remaining_attempts = db_session.scalar(
        select(func.count())
        .select_from(PracticeAttempt)
        .where(PracticeAttempt.knowledge_card_id == card_id)
    )
    assert remaining_attempts == 0


def test_enum_values_are_stored_as_public_string_values(
    db_session: Session,
) -> None:
    card = build_knowledge_card()
    db_session.add(card)
    db_session.flush()
    attempt = PracticeAttempt(
        knowledge_card_id=card.id,
        rating=PracticeRating.DONT_KNOW,
    )
    db_session.add(attempt)
    db_session.commit()

    card_row = db_session.execute(
        text(
            """
            SELECT category, difficulty, question_type, mastery_level
            FROM knowledge_cards
            WHERE id = :card_id
            """
        ),
        {"card_id": card.id},
    ).mappings().one()
    attempt_row = db_session.execute(
        text("SELECT rating FROM practice_attempts WHERE id = :attempt_id"),
        {"attempt_id": attempt.id},
    ).mappings().one()

    assert card_row["category"] == "python"
    assert card_row["difficulty"] == "medium"
    assert card_row["question_type"] == "knowledge"
    assert card_row["mastery_level"] == "new"
    assert attempt_row["rating"] == "dont_know"

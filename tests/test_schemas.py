from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    PracticeRating,
    QuestionType,
)
from app.schemas.knowledge_card import (
    KnowledgeCardCreate,
    KnowledgeCardListItem,
    KnowledgeCardListResponse,
    KnowledgeCardRead,
    KnowledgeCardUpdate,
)
from app.schemas.practice_attempt import PracticeAttemptCreate, PracticeAttemptRead


def valid_knowledge_card_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "  Python list vs tuple  ",
        "category": KnowledgeCategory.PYTHON,
        "core_knowledge": "Sequence mutability.",
        "question": "Explain list and tuple differences.",
        "reference_answer": "List is mutable; tuple is immutable.",
    }
    payload.update(overrides)
    return payload


def test_knowledge_card_create_valid_payload_and_defaults() -> None:
    schema = KnowledgeCardCreate(**valid_knowledge_card_payload())

    assert schema.title == "Python list vs tuple"
    assert schema.difficulty is DifficultyLevel.MEDIUM
    assert schema.question_type is QuestionType.KNOWLEDGE
    assert schema.scoring_rules == {}
    assert schema.tags == []


def test_knowledge_card_create_default_containers_are_independent() -> None:
    first = KnowledgeCardCreate(**valid_knowledge_card_payload())
    second = KnowledgeCardCreate(
        **valid_knowledge_card_payload(title="Python dict vs set")
    )

    first.scoring_rules["must_include"] = "mutability"
    first.tags.append("python")

    assert second.scoring_rules == {}
    assert second.tags == []
    assert first.scoring_rules is not second.scoring_rules
    assert first.tags is not second.tags


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("title", "   "),
        ("core_knowledge", ""),
        ("question", " "),
        ("reference_answer", ""),
    ],
)
def test_knowledge_card_create_rejects_empty_required_text(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardCreate(**valid_knowledge_card_payload(**{field_name: value}))


def test_knowledge_card_create_rejects_invalid_tags() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardCreate(**valid_knowledge_card_payload(tags=["python", 123]))


def test_knowledge_card_create_rejects_non_dict_scoring_rules() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardCreate(**valid_knowledge_card_payload(scoring_rules=[]))


def test_knowledge_card_create_rejects_invalid_category() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardCreate(**valid_knowledge_card_payload(category="not_a_category"))


def test_knowledge_card_update_accepts_single_and_multiple_fields() -> None:
    single = KnowledgeCardUpdate(title="  Updated title  ")
    multiple = KnowledgeCardUpdate(
        question="  Updated question  ",
        core_knowledge="Updated core knowledge.",
        reference_answer="Updated reference answer.",
        tags=["sql", "join"],
    )

    assert single.title == "Updated title"
    assert multiple.question == "Updated question"
    assert multiple.core_knowledge == "Updated core knowledge."
    assert multiple.reference_answer == "Updated reference answer."
    assert multiple.tags == ["sql", "join"]


def test_knowledge_card_update_rejects_empty_update() -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardUpdate()


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("title", ""),
        ("core_knowledge", " "),
        ("question", ""),
        ("reference_answer", "   "),
    ],
)
def test_knowledge_card_update_rejects_empty_string_fields(
    field_name: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardUpdate(**{field_name: value})


@pytest.mark.parametrize(
    "field_name",
    [
        "id",
        "category",
        "difficulty",
        "question_type",
        "scoring_rules",
        "source_reference",
        "mastery_level",
        "last_practiced_at",
        "next_review_at",
        "consecutive_correct_count",
        "total_error_count",
        "is_active",
    ],
)
def test_knowledge_card_update_rejects_read_only_fields(field_name: str) -> None:
    with pytest.raises(ValidationError):
        KnowledgeCardUpdate(**{field_name: "not editable"})


def test_knowledge_card_read_can_validate_from_attributes() -> None:
    now = datetime(2026, 6, 26, 12, 0, 0)
    orm_like = SimpleNamespace(
        id=1,
        title="Python list vs tuple",
        category=KnowledgeCategory.PYTHON,
        difficulty=DifficultyLevel.MEDIUM,
        question_type=QuestionType.KNOWLEDGE,
        core_knowledge="Sequence mutability.",
        question="Explain list and tuple differences.",
        reference_answer="List is mutable; tuple is immutable.",
        scoring_rules={"must_include": ["mutable", "immutable"]},
        tags=["python"],
        source_reference="Week 1 / Python data types",
        mastery_level=MasteryLevel.NEW,
        last_practiced_at=None,
        next_review_at=None,
        consecutive_correct_count=0,
        total_error_count=0,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    schema = KnowledgeCardRead.model_validate(orm_like)
    dumped = schema.model_dump(mode="json")

    assert schema.id == 1
    assert schema.category is KnowledgeCategory.PYTHON
    assert dumped["category"] == "python"
    assert dumped["difficulty"] == "medium"
    assert dumped["question_type"] == "knowledge"
    assert dumped["mastery_level"] == "new"


def test_knowledge_card_list_response_validates_pagination() -> None:
    now = datetime(2026, 6, 26, 12, 0, 0)
    item = KnowledgeCardListItem(
        id=1,
        title="JOIN basics",
        category=KnowledgeCategory.SQL,
        difficulty=DifficultyLevel.MEDIUM,
        question_type=QuestionType.SQL,
        mastery_level=MasteryLevel.LEARNING,
        next_review_at=None,
        consecutive_correct_count=0,
        total_error_count=1,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    response = KnowledgeCardListResponse(
        items=[item],
        total=1,
        limit=20,
        offset=0,
    )

    assert response.items == [item]
    assert response.total == 1
    assert response.limit == 20
    assert response.offset == 0


@pytest.mark.parametrize(
    "field_name",
    ["total", "limit", "offset"],
)
def test_knowledge_card_list_response_rejects_negative_pagination(
    field_name: str,
) -> None:
    values = {"items": [], "total": 0, "limit": 20, "offset": 0}
    values[field_name] = -1

    with pytest.raises(ValidationError):
        KnowledgeCardListResponse(**values)


def test_practice_attempt_create_valid_payload_and_defaults() -> None:
    schema = PracticeAttemptCreate(
        knowledge_card_id=1,
        rating=PracticeRating.CORRECT_EXPLAIN,
        user_answer="List is mutable; tuple is immutable.",
        elapsed_seconds=30,
    )

    assert schema.knowledge_card_id == 1
    assert schema.rating is PracticeRating.CORRECT_EXPLAIN
    assert schema.used_hint is False
    assert schema.is_correct is None


@pytest.mark.parametrize("knowledge_card_id", [0, -1])
def test_practice_attempt_create_rejects_invalid_knowledge_card_id(
    knowledge_card_id: int,
) -> None:
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(
            knowledge_card_id=knowledge_card_id,
            rating=PracticeRating.DONT_KNOW,
        )


def test_practice_attempt_create_rejects_negative_elapsed_seconds() -> None:
    with pytest.raises(ValidationError):
        PracticeAttemptCreate(
            knowledge_card_id=1,
            rating=PracticeRating.WITH_HINT,
            elapsed_seconds=-1,
        )


def test_practice_attempt_create_allows_null_is_correct() -> None:
    schema = PracticeAttemptCreate(
        knowledge_card_id=1,
        rating=PracticeRating.TRANSFER,
        is_correct=None,
    )

    assert schema.is_correct is None


def test_practice_attempt_read_can_validate_from_attributes() -> None:
    now = datetime(2026, 6, 26, 12, 0, 0)
    orm_like = SimpleNamespace(
        id=1,
        knowledge_card_id=2,
        rating=PracticeRating.DONT_KNOW,
        is_correct=False,
        used_hint=True,
        user_answer="I am not sure.",
        elapsed_seconds=5,
        error_summary="Could not recall JOIN null behavior.",
        feedback="Review LEFT JOIN examples.",
        scheduled_next_review_at=None,
        created_at=now,
    )

    schema = PracticeAttemptRead.model_validate(orm_like)
    dumped = schema.model_dump(mode="json")

    assert schema.id == 1
    assert schema.knowledge_card_id == 2
    assert schema.rating is PracticeRating.DONT_KNOW
    assert dumped["rating"] == "dont_know"

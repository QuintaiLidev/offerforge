from __future__ import annotations

from datetime import datetime
from typing import Any, Self

from pydantic import Field, StrictStr, field_validator, model_validator

from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.schemas.common import (
    SchemaModel,
    strip_non_empty_string,
    strip_optional_string,
)


class KnowledgeCardBase(SchemaModel):
    title: str
    category: KnowledgeCategory
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM
    question_type: QuestionType = QuestionType.KNOWLEDGE
    core_knowledge: str
    question: str
    reference_answer: str
    scoring_rules: dict[str, Any] = Field(default_factory=dict)
    tags: list[StrictStr] = Field(default_factory=list)
    source_reference: str | None = None

    @field_validator(
        "title",
        "core_knowledge",
        "question",
        "reference_answer",
        mode="before",
    )
    @classmethod
    def validate_required_text(cls, value: Any) -> Any:
        return strip_non_empty_string(value)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: Any) -> Any:
        return strip_optional_string(value)


class KnowledgeCardCreate(KnowledgeCardBase):
    pass


class KnowledgeCardUpdate(SchemaModel):
    title: str | None = None
    category: KnowledgeCategory | None = None
    difficulty: DifficultyLevel | None = None
    question_type: QuestionType | None = None
    core_knowledge: str | None = None
    question: str | None = None
    reference_answer: str | None = None
    scoring_rules: dict[str, Any] | None = None
    tags: list[StrictStr] | None = None
    source_reference: str | None = None
    mastery_level: MasteryLevel | None = None
    last_practiced_at: datetime | None = None
    next_review_at: datetime | None = None
    consecutive_correct_count: int | None = Field(default=None, ge=0)
    total_error_count: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator(
        "title",
        "core_knowledge",
        "question",
        "reference_answer",
        mode="before",
    )
    @classmethod
    def validate_required_text(cls, value: Any) -> Any:
        if value is None:
            return value
        return strip_non_empty_string(value)

    @field_validator("source_reference", mode="before")
    @classmethod
    def validate_source_reference(cls, value: Any) -> Any:
        return strip_optional_string(value)

    @model_validator(mode="after")
    def validate_non_empty_update(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        non_nullable_fields = {
            "title",
            "category",
            "difficulty",
            "question_type",
            "core_knowledge",
            "question",
            "reference_answer",
            "scoring_rules",
            "tags",
            "mastery_level",
            "consecutive_correct_count",
            "total_error_count",
            "is_active",
        }
        for field_name in non_nullable_fields & self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")

        return self


class KnowledgeCardRead(KnowledgeCardBase):
    id: int
    mastery_level: MasteryLevel
    last_practiced_at: datetime | None
    next_review_at: datetime | None
    consecutive_correct_count: int
    total_error_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeCardListItem(SchemaModel):
    id: int
    title: str
    category: KnowledgeCategory
    difficulty: DifficultyLevel
    question_type: QuestionType
    mastery_level: MasteryLevel
    next_review_at: datetime | None
    consecutive_correct_count: int
    total_error_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnowledgeCardListResponse(SchemaModel):
    items: list[KnowledgeCardListItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=0)
    offset: int = Field(ge=0)


class KnowledgeCardBulkCreateResponse(SchemaModel):
    created_count: int = Field(ge=0)
    items: list[KnowledgeCardRead]

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import SchemaModel, strip_non_empty_string

ANSWER_SCORE_DIMENSIONS = (
    "direct_answer",
    "structure",
    "real_example",
    "job_match",
    "boundary",
    "professional_expression",
    "risk_control",
)


class AnswerScoreRequest(SchemaModel):
    card_id: int = Field(gt=0)
    user_answer: str = Field(min_length=30)
    mode: Literal["rule", "ai"] = "rule"

    @field_validator("user_answer", mode="before")
    @classmethod
    def validate_user_answer(cls, value: object) -> object:
        return strip_non_empty_string(value)


class AnswerScoreResponse(SchemaModel):
    provider: str
    total_score: int = Field(ge=0, le=100)
    dimension_scores: dict[str, int]
    strengths: list[str]
    problems: list[str]
    risk_expressions: list[str]
    suggestions: list[str]
    optimized_answer_30s: str
    memory_labels: list[str]
    missing_points: list[str] = Field(default_factory=list)
    complete_answer: str | None = None
    concrete_examples: list[str] = Field(default_factory=list)
    interview_answer_60s: str | None = None
    interview_answer_30s: str | None = None
    follow_up_questions: list[str] = Field(default_factory=list)
    follow_up_qas: list[str] = Field(default_factory=list)
    next_practice_step: str | None = None

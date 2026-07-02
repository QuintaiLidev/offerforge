from __future__ import annotations

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

    @field_validator("user_answer", mode="before")
    @classmethod
    def validate_user_answer(cls, value: object) -> object:
        return strip_non_empty_string(value)


class AnswerScoreResponse(SchemaModel):
    total_score: int = Field(ge=0, le=100)
    dimension_scores: dict[str, int]
    strengths: list[str]
    problems: list[str]
    risk_expressions: list[str]
    suggestions: list[str]
    optimized_answer_30s: str
    memory_labels: list[str]

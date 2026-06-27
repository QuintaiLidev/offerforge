from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.models.enums import PracticeRating
from app.schemas.common import SchemaModel
from app.schemas.knowledge_card import KnowledgeCardRead


class PracticeAttemptBase(SchemaModel):
    knowledge_card_id: int = Field(gt=0)
    rating: PracticeRating
    is_correct: bool | None = None
    used_hint: bool = False
    user_answer: str | None = None
    elapsed_seconds: int | None = Field(default=None, ge=0)
    error_summary: str | None = None
    feedback: str | None = None
    scheduled_next_review_at: datetime | None = None


class PracticeAttemptCreate(PracticeAttemptBase):
    pass


class PracticeAttemptRead(PracticeAttemptBase):
    id: int
    created_at: datetime


class PracticeAttemptCompleteResponse(SchemaModel):
    attempt: PracticeAttemptRead
    card: KnowledgeCardRead

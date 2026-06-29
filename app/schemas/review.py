from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.models.enums import PracticeRating
from app.schemas.common import SchemaModel
from app.schemas.knowledge_card import KnowledgeCardListItem, KnowledgeCardRead
from app.schemas.practice_attempt import PracticeAttemptRead

ReviewMode = Literal["due", "new"]


class ReviewTodayResponse(SchemaModel):
    mode: ReviewMode
    items: list[KnowledgeCardListItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50)
    generated_at: datetime


class DoneTodayReviewItem(SchemaModel):
    card: KnowledgeCardRead
    latest_attempt: PracticeAttemptRead


class DoneTodayReviewResponse(SchemaModel):
    items: list[DoneTodayReviewItem]


class PracticeHistoryItem(SchemaModel):
    attempt_id: int
    created_at: datetime
    rating: PracticeRating
    user_answer: str | None
    scheduled_next_review_at: datetime | None
    card: KnowledgeCardRead


class PracticeHistoryResponse(SchemaModel):
    items: list[PracticeHistoryItem]

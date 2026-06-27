from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import SchemaModel
from app.schemas.knowledge_card import KnowledgeCardListItem

ReviewMode = Literal["due", "new"]


class ReviewTodayResponse(SchemaModel):
    mode: ReviewMode
    items: list[KnowledgeCardListItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=50)
    generated_at: datetime

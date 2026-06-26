from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PracticeRating, mapped_enum
from app.models.time import utc_now


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    knowledge_card_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating: Mapped[PracticeRating] = mapped_column(
        mapped_enum(PracticeRating, "practice_rating"),
        nullable=False,
    )
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    used_hint: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    user_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
    )

    knowledge_card: Mapped["KnowledgeCard"] = relationship(
        "KnowledgeCard",
        back_populates="practice_attempts",
    )

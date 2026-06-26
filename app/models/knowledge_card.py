from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
    mapped_enum,
)
from app.models.time import utc_now


class KnowledgeCard(Base):
    __tablename__ = "knowledge_cards"
    __table_args__ = (
        UniqueConstraint(
            "category",
            "title",
            name="uq_knowledge_cards_category_title",
        ),
        Index("ix_knowledge_cards_category", "category"),
        Index("ix_knowledge_cards_difficulty", "difficulty"),
        Index("ix_knowledge_cards_mastery_level", "mastery_level"),
        Index("ix_knowledge_cards_next_review_at", "next_review_at"),
        Index("ix_knowledge_cards_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[KnowledgeCategory] = mapped_column(
        mapped_enum(KnowledgeCategory, "knowledge_category"),
        nullable=False,
    )
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        mapped_enum(DifficultyLevel, "difficulty_level"),
        nullable=False,
        default=DifficultyLevel.MEDIUM,
    )
    question_type: Mapped[QuestionType] = mapped_column(
        mapped_enum(QuestionType, "question_type"),
        nullable=False,
        default=QuestionType.KNOWLEDGE,
    )
    core_knowledge: Mapped[str] = mapped_column(Text, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_rules: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mastery_level: Mapped[MasteryLevel] = mapped_column(
        mapped_enum(MasteryLevel, "mastery_level"),
        nullable=False,
        default=MasteryLevel.NEW,
    )
    last_practiced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    consecutive_correct_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_error_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    practice_attempts: Mapped[list["PracticeAttempt"]] = relationship(
        "PracticeAttempt",
        back_populates="knowledge_card",
        cascade="all, delete-orphan",
    )

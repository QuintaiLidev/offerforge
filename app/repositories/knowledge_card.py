from __future__ import annotations

from datetime import datetime

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import KnowledgeCard
from app.models.enums import (
    DifficultyLevel,
    KnowledgeCategory,
    MasteryLevel,
    QuestionType,
)
from app.schemas.knowledge_card import KnowledgeCardCreate, KnowledgeCardUpdate


class KnowledgeCardRepository:
    """Persistence operations for knowledge cards.

    Transaction strategy: write methods add/update/delete, commit, and refresh
    the ORM object when applicable. If a SQLAlchemy write fails, the session is
    rolled back and the original exception is re-raised for the service/API layer.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: KnowledgeCardCreate) -> KnowledgeCard:
        card = KnowledgeCard(**data.model_dump())
        self.session.add(card)

        try:
            self.session.commit()
            self.session.refresh(card)
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return card

    def get_by_id(self, card_id: int) -> KnowledgeCard | None:
        return self.session.get(KnowledgeCard, card_id)

    def get_by_category_and_title(
        self,
        category: KnowledgeCategory,
        title: str,
    ) -> KnowledgeCard | None:
        statement = select(KnowledgeCard).where(
            KnowledgeCard.category == category,
            KnowledgeCard.title == title,
        )
        return self.session.scalar(statement)

    def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        category: KnowledgeCategory | None = None,
        difficulty: DifficultyLevel | None = None,
        mastery_level: MasteryLevel | None = None,
        question_type: QuestionType | None = None,
        is_active: bool | None = None,
        keyword: str | None = None,
    ) -> tuple[list[KnowledgeCard], int]:
        if offset < 0:
            raise ValueError("offset must be non-negative.")
        if limit < 0:
            raise ValueError("limit must be non-negative.")

        filters = self._build_filters(
            category=category,
            difficulty=difficulty,
            mastery_level=mastery_level,
            question_type=question_type,
            is_active=is_active,
            keyword=keyword,
        )

        total_statement = select(func.count()).select_from(KnowledgeCard).where(*filters)
        total = self.session.scalar(total_statement) or 0

        items_statement = (
            select(KnowledgeCard)
            .where(*filters)
            .order_by(KnowledgeCard.created_at.desc(), KnowledgeCard.id.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.session.scalars(items_statement).all())
        return items, total

    def list_due_for_review(
        self,
        now: datetime,
        *,
        limit: int = 10,
    ) -> tuple[list[KnowledgeCard], int]:
        if limit < 0:
            raise ValueError("limit must be non-negative.")

        filters = [
            KnowledgeCard.is_active.is_(True),
            KnowledgeCard.next_review_at <= now,
        ]
        total_statement = select(func.count()).select_from(KnowledgeCard).where(*filters)
        total = self.session.scalar(total_statement) or 0

        items_statement = (
            select(KnowledgeCard)
            .where(*filters)
            .order_by(KnowledgeCard.next_review_at.asc(), KnowledgeCard.id.asc())
            .limit(limit)
        )
        items = list(self.session.scalars(items_statement).all())
        return items, total

    def list_new_for_review(
        self,
        *,
        limit: int = 10,
    ) -> tuple[list[KnowledgeCard], int]:
        if limit < 0:
            raise ValueError("limit must be non-negative.")

        filters = [
            KnowledgeCard.is_active.is_(True),
            KnowledgeCard.mastery_level == MasteryLevel.NEW,
        ]
        total_statement = select(func.count()).select_from(KnowledgeCard).where(*filters)
        total = self.session.scalar(total_statement) or 0

        items_statement = (
            select(KnowledgeCard)
            .where(*filters)
            .order_by(KnowledgeCard.created_at.asc(), KnowledgeCard.id.asc())
            .limit(limit)
        )
        items = list(self.session.scalars(items_statement).all())
        return items, total

    def update(
        self,
        card: KnowledgeCard,
        data: KnowledgeCardUpdate,
    ) -> KnowledgeCard:
        values = data.model_dump(exclude_unset=True)
        for field_name, value in values.items():
            setattr(card, field_name, value)

        try:
            self.session.commit()
            self.session.refresh(card)
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return card

    def save(self, card: KnowledgeCard) -> KnowledgeCard:
        try:
            self.session.commit()
            self.session.refresh(card)
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return card

    def delete(self, card: KnowledgeCard) -> None:
        self.session.delete(card)

        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def exists_by_category_and_title(
        self,
        category: KnowledgeCategory,
        title: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        filters = [
            KnowledgeCard.category == category,
            KnowledgeCard.title == title,
        ]
        if exclude_id is not None:
            filters.append(KnowledgeCard.id != exclude_id)

        statement = select(exists().where(*filters))
        return bool(self.session.scalar(statement))

    def _build_filters(
        self,
        *,
        category: KnowledgeCategory | None,
        difficulty: DifficultyLevel | None,
        mastery_level: MasteryLevel | None,
        question_type: QuestionType | None,
        is_active: bool | None,
        keyword: str | None,
    ) -> list[object]:
        filters: list[object] = []

        if category is not None:
            filters.append(KnowledgeCard.category == category)
        if difficulty is not None:
            filters.append(KnowledgeCard.difficulty == difficulty)
        if mastery_level is not None:
            filters.append(KnowledgeCard.mastery_level == mastery_level)
        if question_type is not None:
            filters.append(KnowledgeCard.question_type == question_type)
        if is_active is not None:
            filters.append(KnowledgeCard.is_active == is_active)

        normalized_keyword = keyword.strip() if keyword is not None else ""
        if normalized_keyword:
            pattern = f"%{normalized_keyword}%"
            filters.append(
                or_(
                    KnowledgeCard.title.ilike(pattern),
                    KnowledgeCard.core_knowledge.ilike(pattern),
                    KnowledgeCard.question.ilike(pattern),
                )
            )

        return filters

from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, exists, func, or_, select
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


def _source_reference_filter(source_reference: str | None) -> object:
    if source_reference is None:
        return KnowledgeCard.source_reference.is_(None)
    return KnowledgeCard.source_reference == source_reference


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

    def get_by_source_category_and_title(
        self,
        source_reference: str | None,
        category: KnowledgeCategory,
        title: str,
    ) -> KnowledgeCard | None:
        statement = select(KnowledgeCard).where(
            _source_reference_filter(source_reference),
            KnowledgeCard.category == category,
            KnowledgeCard.title == title,
        )
        return self.session.scalar(statement)

    def count(self) -> int:
        statement = select(func.count()).select_from(KnowledgeCard)
        return self.session.scalar(statement) or 0

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

    def list_source_summaries(self) -> list[tuple[str | None, int, int, int]]:
        active_count = func.sum(
            case((KnowledgeCard.is_active.is_(True), 1), else_=0)
        )
        statement = (
            select(
                KnowledgeCard.source_reference,
                func.count(KnowledgeCard.id),
                active_count,
            )
            .group_by(KnowledgeCard.source_reference)
            .order_by(KnowledgeCard.source_reference.asc())
        )
        rows = self.session.execute(statement).all()

        summaries: list[tuple[str | None, int, int, int]] = []
        for source_reference, total_count, active_total in rows:
            total = int(total_count or 0)
            active = int(active_total or 0)
            summaries.append((source_reference, total, active, total - active))
        return summaries

    def list_ids_by_source_reference(self, source_reference: str) -> list[int]:
        statement = (
            select(KnowledgeCard.id)
            .where(KnowledgeCard.source_reference == source_reference)
            .order_by(KnowledgeCard.id.asc())
        )
        return list(self.session.scalars(statement).all())

    def count_by_source_reference(self, source_reference: str) -> int:
        statement = (
            select(func.count())
            .select_from(KnowledgeCard)
            .where(KnowledgeCard.source_reference == source_reference)
        )
        return self.session.scalar(statement) or 0

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

    def set_active_by_source_reference(
        self,
        source_reference: str,
        *,
        is_active: bool,
    ) -> int:
        statement = select(KnowledgeCard).where(
            KnowledgeCard.source_reference == source_reference
        )
        cards = list(self.session.scalars(statement).all())
        for card in cards:
            card.is_active = is_active

        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return len(cards)

    def delete_by_source_reference(self, source_reference: str) -> int:
        statement = select(KnowledgeCard).where(
            KnowledgeCard.source_reference == source_reference
        )
        cards = list(self.session.scalars(statement).all())
        for card in cards:
            self.session.delete(card)

        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return len(cards)

    def delete(self, card: KnowledgeCard) -> None:
        self.session.delete(card)

        try:
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def exists_by_source_category_and_title(
        self,
        source_reference: str | None,
        category: KnowledgeCategory,
        title: str,
        *,
        exclude_id: int | None = None,
    ) -> bool:
        filters = [
            _source_reference_filter(source_reference),
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

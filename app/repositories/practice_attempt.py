from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import PracticeAttempt
from app.schemas.practice_attempt import PracticeAttemptCreate


class PracticeAttemptRepository:
    """Persistence operations for practice attempts.

    Write methods follow the current repository strategy: commit internally,
    refresh on success, rollback on SQLAlchemy errors, and re-raise the original
    exception for the service layer.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, data: PracticeAttemptCreate) -> PracticeAttempt:
        attempt = PracticeAttempt(**data.model_dump())
        self.session.add(attempt)

        try:
            self.session.commit()
            self.session.refresh(attempt)
        except SQLAlchemyError:
            self.session.rollback()
            raise

        return attempt

    def list_by_card_id(
        self,
        card_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[PracticeAttempt], int]:
        if offset < 0:
            raise ValueError("offset must be non-negative.")
        if limit < 0:
            raise ValueError("limit must be non-negative.")

        filters = [PracticeAttempt.knowledge_card_id == card_id]
        total_statement = select(func.count()).select_from(PracticeAttempt).where(*filters)
        total = self.session.scalar(total_statement) or 0

        items_statement = (
            select(PracticeAttempt)
            .where(*filters)
            .order_by(PracticeAttempt.created_at.desc(), PracticeAttempt.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(items_statement).all()), total

    def get_latest_by_card_id(self, card_id: int) -> PracticeAttempt | None:
        statement = (
            select(PracticeAttempt)
            .where(PracticeAttempt.knowledge_card_id == card_id)
            .order_by(PracticeAttempt.created_at.desc(), PracticeAttempt.id.desc())
            .limit(1)
        )
        return self.session.scalar(statement)

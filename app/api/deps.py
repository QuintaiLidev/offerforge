from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.services import KnowledgeCardService, PracticeAttemptService, ReviewService


def get_knowledge_card_service(
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeCardService:
    repository = KnowledgeCardRepository(db)
    return KnowledgeCardService(repository)


def get_practice_attempt_service(
    db: Annotated[Session, Depends(get_db)],
) -> PracticeAttemptService:
    attempt_repository = PracticeAttemptRepository(db)
    card_repository = KnowledgeCardRepository(db)
    return PracticeAttemptService(attempt_repository, card_repository)


def get_review_service(
    db: Annotated[Session, Depends(get_db)],
) -> ReviewService:
    card_repository = KnowledgeCardRepository(db)
    return ReviewService(card_repository)

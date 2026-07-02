from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.services import KnowledgeCardService, PracticeAttemptService, ReviewService
from app.services.answer_arena import AnswerArenaService


def get_knowledge_card_service(
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeCardService:
    card_repository = KnowledgeCardRepository(db)
    attempt_repository = PracticeAttemptRepository(db)
    return KnowledgeCardService(card_repository, attempt_repository)


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
    attempt_repository = PracticeAttemptRepository(db)
    return ReviewService(card_repository, attempt_repository)


def get_answer_arena_service(
    db: Annotated[Session, Depends(get_db)],
) -> AnswerArenaService:
    card_repository = KnowledgeCardRepository(db)
    return AnswerArenaService(card_repository)

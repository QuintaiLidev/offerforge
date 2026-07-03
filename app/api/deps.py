from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from app.core.config import get_settings
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import KnowledgeCardRepository, PracticeAttemptRepository
from app.services import KnowledgeCardService, PracticeAttemptService, ReviewService
from app.services.answer_arena import AnswerArenaService, OpenAIAnswerScoringProvider


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
    settings = get_settings()
    ai_provider = OpenAIAnswerScoringProvider(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        timeout_seconds=settings.ai_score_timeout_seconds,
    )
    return AnswerArenaService(card_repository, ai_provider=ai_provider)

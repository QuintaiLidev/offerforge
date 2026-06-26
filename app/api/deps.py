from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories import KnowledgeCardRepository
from app.services import KnowledgeCardService


def get_knowledge_card_service(
    db: Annotated[Session, Depends(get_db)],
) -> KnowledgeCardService:
    repository = KnowledgeCardRepository(db)
    return KnowledgeCardService(repository)

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate
from app.services.knowledge_card import KnowledgeCardService

logger = logging.getLogger(__name__)


def seed_knowledge_cards_if_empty(db: Session, seed_path: Path) -> int:
    try:
        return _seed_knowledge_cards_if_empty(db, seed_path)
    except Exception:
        logger.exception("Auto seed failed; continue without seed.")
        return 0


def _seed_knowledge_cards_if_empty(db: Session, seed_path: Path) -> int:
    repository = KnowledgeCardRepository(db)
    existing_count = repository.count()
    if existing_count > 0:
        logger.info("Existing knowledge cards found, skip auto seed.")
        return 0

    logger.info("Knowledge card table is empty, start auto seed.")
    items = _load_seed_items(seed_path)
    if items is None:
        return 0

    service = KnowledgeCardService(repository)
    try:
        created = service.create_cards(items)
    except Exception:
        logger.exception("Auto seed failed while inserting knowledge cards.")
        return 0

    logger.info("Auto seed created %s knowledge cards.", len(created))
    return len(created)


def _load_seed_items(seed_path: Path) -> list[KnowledgeCardCreate] | None:
    if not seed_path.exists():
        logger.warning("Auto seed file missing: %s", seed_path)
        return None

    try:
        raw_items: Any = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        logger.exception("Auto seed file contains invalid JSON: %s", seed_path)
        return None

    if not isinstance(raw_items, list):
        logger.error("Auto seed file must contain a top-level JSON array: %s", seed_path)
        return None

    try:
        return [KnowledgeCardCreate.model_validate(item) for item in raw_items]
    except ValidationError:
        logger.exception("Auto seed file contains invalid knowledge card schema.")
        return None

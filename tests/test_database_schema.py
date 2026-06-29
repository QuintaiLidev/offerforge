from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core.config import DEFAULT_DATABASE_PATH, get_settings
from app.db.base import Base
from app.db.init_db import init_db
from app.db.session import SessionLocal, engine
from app.models.enums import KnowledgeCategory
from app.repositories import KnowledgeCardRepository
from app.schemas.knowledge_card import KnowledgeCardCreate


def test_init_db_creates_model_tables(db_session: object) -> None:
    table_names = set(inspect(engine).get_table_names())

    assert {"knowledge_cards", "practice_attempts"} <= table_names


def test_database_initialization_uses_test_database(test_db_path: Path) -> None:
    default_db_exists_before = DEFAULT_DATABASE_PATH.exists()
    default_db_stat_before = (
        DEFAULT_DATABASE_PATH.stat() if default_db_exists_before else None
    )

    init_db()

    assert get_settings().database_path == test_db_path
    assert test_db_path.exists()
    assert DEFAULT_DATABASE_PATH.exists() is default_db_exists_before
    if default_db_stat_before is not None:
        default_db_stat_after = DEFAULT_DATABASE_PATH.stat()
        assert default_db_stat_after.st_size == default_db_stat_before.st_size
        assert default_db_stat_after.st_mtime_ns == default_db_stat_before.st_mtime_ns


def test_init_db_migrates_legacy_card_uniqueness_to_source_aware() -> None:
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE knowledge_cards (
                    id INTEGER NOT NULL,
                    title VARCHAR(200) NOT NULL,
                    category VARCHAR(255) NOT NULL,
                    difficulty VARCHAR(255) NOT NULL,
                    question_type VARCHAR(255) NOT NULL,
                    core_knowledge TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reference_answer TEXT NOT NULL,
                    scoring_rules JSON NOT NULL,
                    tags JSON NOT NULL,
                    source_reference VARCHAR(255),
                    mastery_level VARCHAR(255) NOT NULL,
                    last_practiced_at DATETIME,
                    next_review_at DATETIME,
                    consecutive_correct_count INTEGER NOT NULL,
                    total_error_count INTEGER NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    PRIMARY KEY (id),
                    CONSTRAINT uq_knowledge_cards_category_title
                        UNIQUE (category, title)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO knowledge_cards (
                    id,
                    title,
                    category,
                    difficulty,
                    question_type,
                    core_knowledge,
                    question,
                    reference_answer,
                    scoring_rules,
                    tags,
                    source_reference,
                    mastery_level,
                    consecutive_correct_count,
                    total_error_count,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (
                    1,
                    'Shared title',
                    'python',
                    'medium',
                    'knowledge',
                    'Core',
                    'Question',
                    'Answer',
                    '{}',
                    '[]',
                    'interview-week1-v3',
                    'new',
                    0,
                    0,
                    1,
                    '2026-06-29 00:00:00',
                    '2026-06-29 00:00:00'
                )
                """
            )
        )

    init_db()

    session = SessionLocal()
    try:
        repository = KnowledgeCardRepository(session)
        v4_card = repository.create(
            KnowledgeCardCreate(
                title="Shared title",
                category=KnowledgeCategory.PYTHON,
                core_knowledge="Core",
                question="Question",
                reference_answer="Answer",
                source_reference="interview-week1-v4",
            )
        )

        assert v4_card.id is not None

        with pytest.raises(IntegrityError):
            repository.create(
                KnowledgeCardCreate(
                    title="Shared title",
                    category=KnowledgeCategory.PYTHON,
                    core_knowledge="Core",
                    question="Question",
                    reference_answer="Answer",
                    source_reference="interview-week1-v4",
                )
            )
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)

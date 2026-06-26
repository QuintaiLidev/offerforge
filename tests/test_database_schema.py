from __future__ import annotations

from pathlib import Path

from sqlalchemy import inspect

from app.core.config import DEFAULT_DATABASE_PATH, get_settings
from app.db.init_db import init_db
from app.db.session import engine


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

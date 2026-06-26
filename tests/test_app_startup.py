from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
import pytest

from app.core.config import DEFAULT_DATABASE_PATH
from app.main import app, create_app


def test_app_can_be_imported() -> None:
    application = create_app()

    assert isinstance(application, FastAPI)
    assert application.title == "OfferForge"


@pytest.mark.anyio
async def test_startup_initializes_test_database_without_touching_default_db(
    test_db_path: Path,
) -> None:
    default_db_exists_before = DEFAULT_DATABASE_PATH.exists()
    default_db_stat_before = (
        DEFAULT_DATABASE_PATH.stat() if default_db_exists_before else None
    )

    async with app.router.lifespan_context(app):
        pass

    assert test_db_path.exists()
    assert DEFAULT_DATABASE_PATH.exists() is default_db_exists_before
    if default_db_stat_before is not None:
        default_db_stat_after = DEFAULT_DATABASE_PATH.stat()
        assert default_db_stat_after.st_size == default_db_stat_before.st_size
        assert default_db_stat_after.st_mtime_ns == default_db_stat_before.st_mtime_ns

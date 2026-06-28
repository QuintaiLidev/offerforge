from __future__ import annotations

from collections.abc import Generator
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

_TEST_DB_DIR: Path | None = None
_TEST_DB_PATH: Path | None = None
_PREVIOUS_ENV: dict[str, str | None] = {}


def pytest_configure(config: pytest.Config) -> None:
    global _TEST_DB_DIR, _TEST_DB_PATH, _PREVIOUS_ENV

    _PREVIOUS_ENV = {
        "OFFERFORGE_TESTING": os.environ.get("OFFERFORGE_TESTING"),
        "OFFERFORGE_DATABASE_PATH": os.environ.get("OFFERFORGE_DATABASE_PATH"),
        "OFFERFORGE_AUTO_SEED_ON_STARTUP": os.environ.get(
            "OFFERFORGE_AUTO_SEED_ON_STARTUP"
        ),
    }

    _TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="offerforge_pytest_"))
    _TEST_DB_PATH = _TEST_DB_DIR / "offerforge_test.db"
    os.environ["OFFERFORGE_TESTING"] = "1"
    os.environ["OFFERFORGE_DATABASE_PATH"] = str(_TEST_DB_PATH)
    os.environ["OFFERFORGE_AUTO_SEED_ON_STARTUP"] = "false"


def pytest_sessionfinish(
    session: pytest.Session,
    exitstatus: pytest.ExitCode | int,
) -> None:
    for key, previous_value in _PREVIOUS_ENV.items():
        if previous_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous_value

    if _TEST_DB_DIR is not None:
        shutil.rmtree(_TEST_DB_DIR, ignore_errors=True)


@pytest.fixture()
def test_db_path() -> Path:
    if _TEST_DB_PATH is None:
        raise RuntimeError("Test database path was not configured.")
    return _TEST_DB_PATH


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    from app.db.base import Base
    from app.db.init_db import init_db
    from app.db.session import SessionLocal, engine

    Base.metadata.drop_all(bind=engine)
    init_db()

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"

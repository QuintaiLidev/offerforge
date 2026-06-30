from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def is_sqlite_database_url(database_url: str) -> bool:
    return make_url(database_url).get_backend_name() == "sqlite"


def build_engine_options(database_url: str) -> dict[str, Any]:
    options: dict[str, Any] = {"future": True}
    if is_sqlite_database_url(database_url):
        options["connect_args"] = {"check_same_thread": False}
    else:
        options["pool_pre_ping"] = True
        options["pool_recycle"] = 1800
    return options


def create_database_engine(database_url: str) -> Engine:
    return create_engine(database_url, **build_engine_options(database_url))


engine: Engine = create_database_engine(get_settings().database_url)
SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(
    dbapi_connection: Any,
    connection_record: Any,
) -> None:
    if engine.dialect.name != "sqlite":
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

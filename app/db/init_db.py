from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine


def init_db() -> None:
    settings = get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(bind=connection)

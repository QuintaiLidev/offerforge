from __future__ import annotations

from pathlib import Path

from sqlalchemy import MetaData, text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.schema import CreateTable

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine, is_sqlite_database_url
from app.models import KnowledgeCard, PracticeAttempt


def init_db() -> None:
    _ = (KnowledgeCard, PracticeAttempt)
    settings = get_settings()
    if not is_sqlite_database_url(settings.database_url):
        Base.metadata.create_all(bind=engine)
        return

    _ensure_sqlite_database_parent(settings.database_url)

    with engine.connect() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        Base.metadata.create_all(bind=connection)
        connection.commit()
        _migrate_legacy_knowledge_card_uniqueness(connection)


def _ensure_sqlite_database_parent(database_url: str) -> None:
    database_path = make_url(database_url).database
    if not database_path or database_path == ":memory:":
        return
    Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)


def _migrate_legacy_knowledge_card_uniqueness(connection: Connection) -> None:
    if connection.dialect.name != "sqlite":
        return
    if not _sqlite_table_exists(connection, "knowledge_cards"):
        return

    unique_columns = _sqlite_unique_index_columns(connection, "knowledge_cards")
    has_legacy_unique = ("category", "title") in unique_columns
    has_source_unique = (
        "source_reference",
        "category",
        "title",
    ) in unique_columns
    if not has_legacy_unique or has_source_unique:
        return

    metadata = MetaData()
    migrated_table = KnowledgeCard.__table__.to_metadata(
        metadata,
        name="knowledge_cards_new",
    )
    column_names = [column.name for column in KnowledgeCard.__table__.columns]
    columns_sql = ", ".join(_sqlite_quote_identifier(name) for name in column_names)

    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    connection.commit()
    try:
        with connection.begin():
            connection.execute(CreateTable(migrated_table))
            connection.exec_driver_sql(
                "INSERT INTO knowledge_cards_new "
                f"({columns_sql}) SELECT {columns_sql} FROM knowledge_cards"
            )
            connection.exec_driver_sql("DROP TABLE knowledge_cards")
            connection.exec_driver_sql(
                "ALTER TABLE knowledge_cards_new RENAME TO knowledge_cards"
            )
    finally:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.commit()

    for index in KnowledgeCard.__table__.indexes:
        index.create(bind=connection, checkfirst=True)
    connection.commit()


def _sqlite_table_exists(connection: Connection, table_name: str) -> bool:
    row = connection.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).first()
    return row is not None


def _sqlite_unique_index_columns(
    connection: Connection,
    table_name: str,
) -> set[tuple[str, ...]]:
    indexes = connection.exec_driver_sql(
        f"PRAGMA index_list({_sqlite_quote_identifier(table_name)})"
    ).all()
    unique_columns: set[tuple[str, ...]] = set()

    for index in indexes:
        index_name = index[1]
        is_unique = bool(index[2])
        if not is_unique:
            continue
        columns = connection.exec_driver_sql(
            f"PRAGMA index_info({_sqlite_quote_identifier(index_name)})"
        ).all()
        unique_columns.add(tuple(column[2] for column in columns))

    return unique_columns


def _sqlite_quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'

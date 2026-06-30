from __future__ import annotations

from typing import Any

from app.db import session as db_session_module


def test_sqlite_engine_options_include_check_same_thread() -> None:
    options = db_session_module.build_engine_options("sqlite:///data/offerforge.db")

    assert options["future"] is True
    assert options["connect_args"] == {"check_same_thread": False}


def test_postgresql_engine_options_do_not_include_sqlite_connect_args() -> None:
    options = db_session_module.build_engine_options(
        "postgresql://user:pass@db.example.com/offerforge"
    )

    assert options["future"] is True
    assert options["pool_pre_ping"] is True
    assert options["pool_recycle"] == 1800
    assert "connect_args" not in options


def test_create_database_engine_passes_postgresql_url_without_sqlite_options(
    monkeypatch,
) -> None:
    captured: dict[str, Any] = {}
    sentinel_engine = object()

    def fake_create_engine(database_url: str, **kwargs: Any) -> object:
        captured["database_url"] = database_url
        captured["kwargs"] = kwargs
        return sentinel_engine

    monkeypatch.setattr(db_session_module, "create_engine", fake_create_engine)

    engine = db_session_module.create_database_engine(
        "postgresql://user:pass@db.example.com/offerforge"
    )

    assert engine is sentinel_engine
    assert captured["database_url"] == (
        "postgresql://user:pass@db.example.com/offerforge"
    )
    assert captured["kwargs"] == {
        "future": True,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }

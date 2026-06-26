from __future__ import annotations

from pathlib import Path

from app.core.config import DEFAULT_DATABASE_PATH, load_settings


def test_default_host_and_port_are_local_only() -> None:
    settings = load_settings({})

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.database_path == DEFAULT_DATABASE_PATH


def test_test_environment_can_override_database_path(tmp_path: Path) -> None:
    database_path = tmp_path / "offerforge_test.db"

    settings = load_settings(
        {
            "OFFERFORGE_TESTING": "true",
            "OFFERFORGE_DATABASE_PATH": str(database_path),
        }
    )

    assert settings.testing is True
    assert settings.database_path == database_path
    assert settings.database_url == f"sqlite:///{database_path.as_posix()}"

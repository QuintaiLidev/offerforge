from __future__ import annotations

from pathlib import Path

from app.core.config import DEFAULT_AUTO_SEED_PATH, DEFAULT_DATABASE_PATH, load_settings


def test_default_host_and_port_are_local_only() -> None:
    settings = load_settings({})

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.database_path == DEFAULT_DATABASE_PATH
    assert settings.database_url == f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
    assert settings.auto_seed_on_startup is True
    assert settings.auto_seed_path == DEFAULT_AUTO_SEED_PATH


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
    assert settings.auto_seed_on_startup is False


def test_database_url_can_be_loaded_from_database_url() -> None:
    settings = load_settings(
        {
            "DATABASE_URL": "postgresql://user:pass@db.example.com/offerforge",
        }
    )

    assert settings.database_url == "postgresql://user:pass@db.example.com/offerforge"


def test_offerforge_database_url_takes_priority_over_database_url() -> None:
    settings = load_settings(
        {
            "OFFERFORGE_DATABASE_URL": (
                "postgresql://offerforge:secret@primary.example.com/offerforge"
            ),
            "DATABASE_URL": "postgresql://other:secret@fallback.example.com/other",
        }
    )

    assert (
        settings.database_url
        == "postgresql://offerforge:secret@primary.example.com/offerforge"
    )


def test_postgres_scheme_is_normalized_for_sqlalchemy() -> None:
    settings = load_settings(
        {
            "DATABASE_URL": "postgres://user:pass@db.example.com/offerforge",
        }
    )

    assert settings.database_url == "postgresql://user:pass@db.example.com/offerforge"


def test_auto_seed_settings_can_be_overridden(tmp_path: Path) -> None:
    seed_path = tmp_path / "seed.json"

    settings = load_settings(
        {
            "OFFERFORGE_TESTING": "true",
            "OFFERFORGE_AUTO_SEED_ON_STARTUP": "true",
            "OFFERFORGE_AUTO_SEED_PATH": str(seed_path),
        }
    )

    assert settings.auto_seed_on_startup is True
    assert settings.auto_seed_path == seed_path

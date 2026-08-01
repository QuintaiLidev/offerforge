from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import DEFAULT_AUTO_SEED_PATH, DEFAULT_DATABASE_PATH, load_settings


def test_default_host_and_port_are_local_only() -> None:
    settings = load_settings({})

    assert settings.host == "127.0.0.1"
    assert settings.port == 8000
    assert settings.app_name == "SkillLoop"
    assert settings.database_path == DEFAULT_DATABASE_PATH
    assert settings.database_url == f"sqlite:///{DEFAULT_DATABASE_PATH.as_posix()}"
    assert settings.auto_seed_on_startup is True
    assert settings.auto_seed_path == DEFAULT_AUTO_SEED_PATH
    assert settings.ai_score_provider == "rule"
    assert settings.ai_score_backend == "openai"
    assert settings.openai_api_key is None
    assert settings.openai_model == "gpt-4o-mini"
    assert settings.openrouter_api_key is None
    assert settings.openrouter_model == "openai/gpt-4o-mini"
    assert settings.openrouter_site_url is None
    assert settings.openrouter_app_title == "SkillLoop"
    assert settings.ai_score_timeout_seconds == 20


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


def test_ai_score_settings_can_be_loaded_from_environment() -> None:
    settings = load_settings(
        {
            "OFFERFORGE_AI_SCORE_PROVIDER": "ai",
            "OFFERFORGE_AI_SCORE_BACKEND": "openrouter",
            "OPENAI_API_KEY": "test-openai-key",
            "OFFERFORGE_OPENAI_MODEL": "gpt-4o-mini-2026",
            "OPENROUTER_API_KEY": "test-openrouter-key",
            "OFFERFORGE_OPENROUTER_MODEL": "anthropic/claude-3.5-sonnet",
            "OFFERFORGE_OPENROUTER_SITE_URL": "https://offerforge.example",
            "OFFERFORGE_OPENROUTER_APP_TITLE": "OfferForge Test",
            "OFFERFORGE_AI_SCORE_TIMEOUT_SECONDS": "12",
        }
    )

    assert settings.ai_score_provider == "ai"
    assert settings.ai_score_backend == "openrouter"
    assert settings.openai_api_key == "test-openai-key"
    assert settings.openai_model == "gpt-4o-mini-2026"
    assert settings.openrouter_api_key == "test-openrouter-key"
    assert settings.openrouter_model == "anthropic/claude-3.5-sonnet"
    assert settings.openrouter_site_url == "https://offerforge.example"
    assert settings.openrouter_app_title == "OfferForge Test"
    assert settings.ai_score_timeout_seconds == 12


def test_skillloop_environment_variables_take_priority_over_legacy_names(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "skillloop_test.db"

    settings = load_settings(
        {
            "SKILLLOOP_APP_NAME": "SkillLoop Test",
            "OFFERFORGE_APP_NAME": "Legacy Name",
            "SKILLLOOP_TESTING": "true",
            "SKILLLOOP_DATABASE_PATH": str(database_path),
            "OFFERFORGE_DATABASE_PATH": str(tmp_path / "legacy.db"),
        }
    )

    assert settings.app_name == "SkillLoop Test"
    assert settings.testing is True
    assert settings.database_path == database_path


def test_non_empty_skillloop_value_takes_priority_over_legacy_value() -> None:
    settings = load_settings(
        {
            "SKILLLOOP_DATABASE_URL": " postgresql://new.example/skillloop ",
            "OFFERFORGE_DATABASE_URL": "postgresql://legacy.example/offerforge",
            "DATABASE_URL": "postgresql://generic.example/fallback",
        }
    )

    assert settings.database_url == "postgresql://new.example/skillloop"


@pytest.mark.parametrize("blank_value", ["", "   ", "\t"])
def test_blank_skillloop_value_falls_back_to_non_empty_legacy_value(
    blank_value: str,
) -> None:
    settings = load_settings(
        {
            "SKILLLOOP_DATABASE_URL": blank_value,
            "OFFERFORGE_DATABASE_URL": " postgresql://legacy.example/offerforge ",
            "DATABASE_URL": "postgresql://generic.example/fallback",
        }
    )

    assert settings.database_url == "postgresql://legacy.example/offerforge"


def test_blank_product_database_urls_fall_back_to_database_url() -> None:
    settings = load_settings(
        {
            "SKILLLOOP_DATABASE_URL": " ",
            "OFFERFORGE_DATABASE_URL": "\t",
            "DATABASE_URL": "postgresql://generic.example/fallback",
        }
    )

    assert settings.database_url == "postgresql://generic.example/fallback"


def test_blank_product_values_fall_back_to_original_defaults() -> None:
    settings = load_settings(
        {
            "SKILLLOOP_APP_NAME": " ",
            "OFFERFORGE_APP_NAME": "\t",
            "SKILLLOOP_DATABASE_PATH": "",
            "OFFERFORGE_DATABASE_PATH": "   ",
        }
    )

    assert settings.app_name == "SkillLoop"
    assert settings.database_path == DEFAULT_DATABASE_PATH


def test_blank_skillloop_auth_enabled_preserves_enabled_legacy_auth() -> None:
    settings = load_settings(
        {
            "SKILLLOOP_AUTH_ENABLED": "   ",
            "OFFERFORGE_AUTH_ENABLED": "true",
            "OFFERFORGE_AUTH_USERNAME": "legacy-user",
            "OFFERFORGE_AUTH_PASSWORD": "test-password",
        }
    )

    assert settings.auth_enabled is True
    assert settings.auth_username == "legacy-user"
    assert settings.auth_password == "test-password"

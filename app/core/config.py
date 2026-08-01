from __future__ import annotations

import os
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
# Keep the legacy filename so existing local and hosted deployments continue to
# use the same database after the product rename.
DEFAULT_DATABASE_PATH: Path = PROJECT_ROOT / "data" / "offerforge.db"
DEFAULT_AUTO_SEED_PATH: Path = (
    PROJECT_ROOT / "data_seed" / "cards_seed_week1_interview_v3.json"
)
PRODUCT_NAME = "SkillLoop"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = PRODUCT_NAME
    api_v1_prefix: str = "/api/v1"
    database_path: Path = DEFAULT_DATABASE_PATH
    database_url_override: str | None = None
    testing: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    auth_enabled: bool = False
    auth_username: str | None = None
    auth_password: str | None = None
    auto_seed_on_startup: bool = True
    auto_seed_path: Path = DEFAULT_AUTO_SEED_PATH
    ai_score_provider: str = "rule"
    ai_score_backend: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_site_url: str | None = None
    openrouter_app_title: str = PRODUCT_NAME
    ai_score_timeout_seconds: int = 20

    @field_validator("database_path", mode="after")
    @classmethod
    def make_database_path_absolute(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (PROJECT_ROOT / value).resolve()

    @field_validator("database_url_override", mode="before")
    @classmethod
    def normalize_database_url_override(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value

        stripped = value.strip()
        if not stripped:
            return None
        if stripped.startswith("postgres://"):
            return "postgresql://" + stripped[len("postgres://") :]
        return stripped

    @field_validator("auto_seed_path", mode="after")
    @classmethod
    def make_auto_seed_path_absolute(cls, value: Path) -> Path:
        if value.is_absolute():
            return value
        return (PROJECT_ROOT / value).resolve()

    @field_validator("ai_score_provider", mode="before")
    @classmethod
    def normalize_ai_score_provider(cls, value: object) -> object:
        if value is None:
            return "rule"
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        if normalized not in {"rule", "ai"}:
            raise ValueError("SKILLLOOP_AI_SCORE_PROVIDER must be rule or ai.")
        return normalized

    @field_validator("ai_score_backend", mode="before")
    @classmethod
    def normalize_ai_score_backend(cls, value: object) -> object:
        if value is None:
            return "openai"
        if not isinstance(value, str):
            return value

        normalized = value.strip().lower()
        if normalized not in {"openai", "openrouter"}:
            raise ValueError("SKILLLOOP_AI_SCORE_BACKEND must be openai or openrouter.")
        return normalized

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def normalize_openai_api_key(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("openrouter_api_key", "openrouter_site_url", mode="before")
    @classmethod
    def normalize_optional_openrouter_string(cls, value: object) -> object:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("openai_model", mode="before")
    @classmethod
    def normalize_openai_model(cls, value: object) -> object:
        if value is None:
            return "gpt-4o-mini"
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or "gpt-4o-mini"

    @field_validator("openrouter_model", mode="before")
    @classmethod
    def normalize_openrouter_model(cls, value: object) -> object:
        if value is None:
            return "openai/gpt-4o-mini"
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or "openai/gpt-4o-mini"

    @field_validator("openrouter_app_title", mode="before")
    @classmethod
    def normalize_openrouter_app_title(cls, value: object) -> object:
        if value is None:
            return PRODUCT_NAME
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped

    @field_validator("ai_score_timeout_seconds")
    @classmethod
    def validate_ai_score_timeout_seconds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("SKILLLOOP_AI_SCORE_TIMEOUT_SECONDS must be positive.")
        return value

    @model_validator(mode="after")
    def validate_auth_credentials(self) -> Settings:
        if self.auth_enabled and (
            not self.auth_username or not self.auth_password
        ):
            raise ValueError(
                "Auth is enabled but SKILLLOOP_AUTH_USERNAME or "
                "SKILLLOOP_AUTH_PASSWORD is missing."
            )
        return self

    @property
    def database_url(self) -> str:
        if self.database_url_override is not None:
            return self.database_url_override
        return f"sqlite:///{self.database_path.as_posix()}"


def _read_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _read_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    return int(value)


def _read_product_env(
    environ: Mapping[str, str],
    suffix: str,
    default: str | None = None,
) -> str | None:
    """Read a SkillLoop setting with an OfferForge compatibility fallback."""
    for prefix in ("SKILLLOOP", "OFFERFORGE"):
        value = environ.get(f"{prefix}_{suffix}")
        if value is not None and value.strip():
            return value
    return default


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    testing = _read_bool(_read_product_env(env, "TESTING"), False)
    database_url_override = _read_product_env(env, "DATABASE_URL") or env.get(
        "DATABASE_URL"
    )

    return Settings(
        app_name=_read_product_env(env, "APP_NAME", PRODUCT_NAME) or PRODUCT_NAME,
        api_v1_prefix=_read_product_env(env, "API_V1_PREFIX", "/api/v1")
        or "/api/v1",
        database_path=Path(
            _read_product_env(env, "DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
            or str(DEFAULT_DATABASE_PATH)
        ),
        database_url_override=database_url_override,
        testing=testing,
        host=_read_product_env(env, "HOST", "127.0.0.1") or "127.0.0.1",
        port=_read_int(_read_product_env(env, "PORT"), 8000),
        auth_enabled=_read_bool(_read_product_env(env, "AUTH_ENABLED"), False),
        auth_username=_read_product_env(env, "AUTH_USERNAME") or None,
        auth_password=_read_product_env(env, "AUTH_PASSWORD") or None,
        auto_seed_on_startup=_read_bool(
            _read_product_env(env, "AUTO_SEED_ON_STARTUP"),
            not testing,
        ),
        auto_seed_path=Path(
            _read_product_env(env, "AUTO_SEED_PATH", str(DEFAULT_AUTO_SEED_PATH))
            or str(DEFAULT_AUTO_SEED_PATH)
        ),
        ai_score_provider=_read_product_env(env, "AI_SCORE_PROVIDER", "rule"),
        ai_score_backend=_read_product_env(env, "AI_SCORE_BACKEND", "openai"),
        openai_api_key=env.get("OPENAI_API_KEY") or None,
        openai_model=_read_product_env(env, "OPENAI_MODEL", "gpt-4o-mini"),
        openrouter_api_key=env.get("OPENROUTER_API_KEY") or None,
        openrouter_model=_read_product_env(
            env,
            "OPENROUTER_MODEL",
            "openai/gpt-4o-mini",
        ),
        openrouter_site_url=_read_product_env(env, "OPENROUTER_SITE_URL") or None,
        openrouter_app_title=_read_product_env(
            env,
            "OPENROUTER_APP_TITLE",
            PRODUCT_NAME,
        ),
        ai_score_timeout_seconds=_read_int(
            _read_product_env(env, "AI_SCORE_TIMEOUT_SECONDS"),
            20,
        ),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH: Path = PROJECT_ROOT / "data" / "offerforge.db"
DEFAULT_AUTO_SEED_PATH: Path = (
    PROJECT_ROOT / "data_seed" / "cards_seed_week1_interview_v3.json"
)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "OfferForge"
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

    @model_validator(mode="after")
    def validate_auth_credentials(self) -> "Settings":
        if self.auth_enabled and (
            not self.auth_username or not self.auth_password
        ):
            raise ValueError(
                "Auth is enabled but OFFERFORGE_AUTH_USERNAME or "
                "OFFERFORGE_AUTH_PASSWORD is missing."
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


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if environ is None else environ
    testing = _read_bool(env.get("OFFERFORGE_TESTING"), False)
    database_url_override = env.get("OFFERFORGE_DATABASE_URL") or env.get(
        "DATABASE_URL"
    )

    return Settings(
        app_name=env.get("OFFERFORGE_APP_NAME", "OfferForge"),
        api_v1_prefix=env.get("OFFERFORGE_API_V1_PREFIX", "/api/v1"),
        database_path=Path(
            env.get("OFFERFORGE_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
        ),
        database_url_override=database_url_override,
        testing=testing,
        host=env.get("OFFERFORGE_HOST", "127.0.0.1"),
        port=_read_int(env.get("OFFERFORGE_PORT"), 8000),
        auth_enabled=_read_bool(env.get("OFFERFORGE_AUTH_ENABLED"), False),
        auth_username=env.get("OFFERFORGE_AUTH_USERNAME") or None,
        auth_password=env.get("OFFERFORGE_AUTH_PASSWORD") or None,
        auto_seed_on_startup=_read_bool(
            env.get("OFFERFORGE_AUTO_SEED_ON_STARTUP"),
            not testing,
        ),
        auto_seed_path=Path(
            env.get("OFFERFORGE_AUTO_SEED_PATH", str(DEFAULT_AUTO_SEED_PATH))
        ),
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()

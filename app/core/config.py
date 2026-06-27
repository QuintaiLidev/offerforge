from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_PATH: Path = PROJECT_ROOT / "data" / "offerforge.db"


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_name: str = "OfferForge"
    api_v1_prefix: str = "/api/v1"
    database_path: Path = DEFAULT_DATABASE_PATH
    testing: bool = False
    host: str = "127.0.0.1"
    port: int = 8000
    auth_enabled: bool = False
    auth_username: str | None = None
    auth_password: str | None = None

    @field_validator("database_path", mode="after")
    @classmethod
    def make_database_path_absolute(cls, value: Path) -> Path:
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

    return Settings(
        app_name=env.get("OFFERFORGE_APP_NAME", "OfferForge"),
        api_v1_prefix=env.get("OFFERFORGE_API_V1_PREFIX", "/api/v1"),
        database_path=Path(
            env.get("OFFERFORGE_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
        ),
        testing=_read_bool(env.get("OFFERFORGE_TESTING"), False),
        host=env.get("OFFERFORGE_HOST", "127.0.0.1"),
        port=_read_int(env.get("OFFERFORGE_PORT"), 8000),
        auth_enabled=_read_bool(env.get("OFFERFORGE_AUTH_ENABLED"), False),
        auth_username=env.get("OFFERFORGE_AUTH_USERNAME") or None,
        auth_password=env.get("OFFERFORGE_AUTH_PASSWORD") or None,
    )


@lru_cache
def get_settings() -> Settings:
    return load_settings()

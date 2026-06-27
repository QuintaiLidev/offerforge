from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import get_settings

security = HTTPBasic(auto_error=False)


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> None:
    settings = get_settings()
    if not settings.auth_enabled:
        return

    if credentials is None:
        raise_auth_error()

    expected_username = settings.auth_username or ""
    expected_password = settings.auth_password or ""
    username_matches = secrets.compare_digest(
        credentials.username,
        expected_username,
    )
    password_matches = secrets.compare_digest(
        credentials.password,
        expected_password,
    )
    if not (username_matches and password_matches):
        raise_auth_error()


def raise_auth_error() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required.",
        headers={"WWW-Authenticate": "Basic"},
    )

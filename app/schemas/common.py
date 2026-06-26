from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def strip_non_empty_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        raise ValueError("Field cannot be empty.")
    return stripped


def strip_optional_string(value: Any) -> Any:
    if value is None or not isinstance(value, str):
        return value

    stripped = value.strip()
    return stripped or None

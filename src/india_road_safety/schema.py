"""JSON schema validation utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError

from .config import load_settings


class SchemaValidationError(Exception):
    """Raised when a record fails schema validation."""


def _schemas_dir() -> Path:
    return load_settings().schemas_dir


def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON schema by name (e.g., 'accident_record')."""
    path = _schemas_dir() / f"{name}.json"
    if not path.is_file():
        raise FileNotFoundError(f"schema not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def validate(name: str, obj: Any) -> None:
    """Validate ``obj`` against schema ``name``. Raises :class:`SchemaValidationError` on failure."""
    schema = load_schema(name)
    try:
        Draft202012Validator(schema).validate(obj)
    except ValidationError as exc:
        raise SchemaValidationError(f"{name} validation failed: {exc.message}") from exc


def validate_record_like(name: str, obj: Any) -> None:
    """Validate by converting Pydantic models to dicts when needed."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json", exclude_unset=False)
    elif hasattr(obj, "dict"):  # pydantic v1 fallback (not expected)
        obj = obj.dict()
    validate(name, obj)

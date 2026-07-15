"""Internal helpers for immutable, defensive JSON-compatible values."""

import math
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any


def _copy_json_value(value: Any, path: str, ancestors: set[int]) -> Any:
    if isinstance(value, Mapping):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"{path} must not contain circular references.")

        ancestors.add(identity)
        try:
            copied = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{path} object keys must be strings.")
                copied[key] = _copy_json_value(
                    child,
                    f"{path}.{key}",
                    ancestors,
                )
            return copied
        finally:
            ancestors.remove(identity)

    if isinstance(value, (list, tuple)):
        identity = id(value)
        if identity in ancestors:
            raise ValueError(f"{path} must not contain circular references.")

        ancestors.add(identity)
        try:
            return [
                _copy_json_value(child, f"{path}[{index}]", ancestors)
                for index, child in enumerate(value)
            ]
        finally:
            ancestors.remove(identity)

    if value is None or isinstance(value, (bool, int, str)):
        return value

    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} numbers must be finite.")
        return value

    raise ValueError(f"{path} must contain only JSON-compatible values.")


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {
                key: _freeze_json_value(child)
                for key, child in value.items()
            }
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(child) for child in value)
    return value


def freeze_json_value(value: Any, path: str) -> Any:
    """Return an immutable defensive copy of one JSON-compatible value."""

    return _freeze_json_value(_copy_json_value(value, path, set()))


def thaw_json_value(value: Any) -> Any:
    """Return an independent mutable JSON-compatible representation."""

    if isinstance(value, Mapping):
        return {
            key: thaw_json_value(child)
            for key, child in value.items()
        }
    if isinstance(value, tuple):
        return [thaw_json_value(child) for child in value]
    return value


def validate_trimmed_identifier(value: Any, label: str) -> str:
    """Validate a stable identifier without imposing a future ID format."""

    if (
        not isinstance(value, str)
        or not value.strip()
        or value != value.strip()
    ):
        raise ValueError(f"{label} must be a non-empty trimmed string.")
    return value


def validate_optional_identifier(value: Any, label: str) -> None:
    if value is not None:
        validate_trimmed_identifier(value, label)

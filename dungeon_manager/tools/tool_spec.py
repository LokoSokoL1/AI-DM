"""Provider-neutral metadata for registered tools."""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Dict


_JSON_SCHEMA_TYPES = {
    "array",
    "boolean",
    "integer",
    "null",
    "number",
    "object",
    "string",
}


def _copy_json_value(value: Any, path: str = "input_schema") -> Any:
    if isinstance(value, Mapping):
        copied = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} object keys must be strings.")
            copied[key] = _copy_json_value(child, f"{path}.{key}")
        return copied

    if isinstance(value, (list, tuple)):
        return [
            _copy_json_value(child, f"{path}[{index}]")
            for index, child in enumerate(value)
        ]

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    raise ValueError(f"{path} must contain only JSON-compatible values.")


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze_json_value(child) for key, child in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze_json_value(child) for child in value)
    return value


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            key: _thaw_json_value(child)
            for key, child in value.items()
        }
    if isinstance(value, tuple):
        return [_thaw_json_value(child) for child in value]
    return value


def _validate_input_schema(schema: Dict[str, Any]) -> None:
    if schema.get("type") != "object":
        raise ValueError("Tool input schema type must be 'object'.")

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        raise ValueError("Tool input schema must define a properties object.")

    required = schema.get("required")
    if not isinstance(required, list):
        raise ValueError("Tool input schema must define an explicit required list.")

    if schema.get("additionalProperties") is not False:
        raise ValueError(
            "Tool input schema must set additionalProperties to false."
        )

    for property_name, property_schema in properties.items():
        if not property_name or property_name != property_name.strip():
            raise ValueError("Tool property names must be non-empty strings.")
        if not isinstance(property_schema, dict):
            raise ValueError(
                f"Tool property '{property_name}' must define a schema object."
            )

        property_type = property_schema.get("type")
        if property_type not in _JSON_SCHEMA_TYPES:
            raise ValueError(
                f"Tool property '{property_name}' must define a supported type."
            )

        description = property_schema.get("description")
        if (
            not isinstance(description, str)
            or not description.strip()
        ):
            raise ValueError(
                f"Tool property '{property_name}' must define a description."
            )

    if any(
        not isinstance(name, str)
        or not name.strip()
        or name != name.strip()
        for name in required
    ):
        raise ValueError("Required tool arguments must be non-empty strings.")
    if len(required) != len(set(required)):
        raise ValueError("Required tool arguments must be unique.")

    missing_properties = set(required) - set(properties)
    if missing_properties:
        missing = ", ".join(sorted(missing_properties))
        raise ValueError(
            f"Required tool arguments are missing from properties: {missing}."
        )


@dataclass(frozen=True)
class ToolSpec:
    """Immutable, provider-neutral description of one registered tool."""

    name: str
    description: str
    input_schema: Mapping[str, Any]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.name, str)
            or not self.name.strip()
            or self.name != self.name.strip()
        ):
            raise ValueError("Tool name must be a non-empty trimmed string.")
        if (
            not isinstance(self.description, str)
            or not self.description.strip()
        ):
            raise ValueError("Tool description must be a non-empty string.")
        if not isinstance(self.input_schema, Mapping):
            raise ValueError("Tool input schema must be an object.")

        schema = _copy_json_value(self.input_schema)
        try:
            json.dumps(schema, allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Tool input schema must be JSON-compatible."
            ) from error

        _validate_input_schema(schema)
        object.__setattr__(self, "input_schema", _freeze_json_value(schema))

    def to_dict(self) -> Dict[str, Any]:
        """Return an independent JSON-compatible catalog entry."""

        return {
            "description": self.description,
            "input_schema": _thaw_json_value(self.input_schema),
            "name": self.name,
        }

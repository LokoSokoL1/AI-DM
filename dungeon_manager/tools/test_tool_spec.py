import inspect
import json

import pytest

from .registry import ToolRegistry
from .tool_spec import ToolSpec


def string_property(description, **keywords):
    return {
        "type": "string",
        "description": description,
        **keywords,
    }


def input_schema(properties, required):
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def test_create_character_specification_is_accurate():
    specs = {spec.name: spec for spec in ToolRegistry().get_tool_specs()}

    create_spec = specs["create_character"].to_dict()

    assert create_spec == {
        "name": "create_character",
        "description": "Create and persist a new player character.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": string_property(
                    "Name of the character to create.",
                    examples=["Arven"],
                ),
                "race": string_property(
                    "Race or ancestry of the character.",
                    default="",
                    examples=["Human"],
                ),
                "character_class": string_property(
                    "Class of the character.",
                    default="",
                    examples=["Fighter"],
                ),
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    }


def test_load_character_specification_is_accurate():
    specs = {spec.name: spec for spec in ToolRegistry().get_tool_specs()}

    load_spec = specs["load_character"].to_dict()

    assert load_spec == {
        "name": "load_character",
        "description": "Load a previously stored character by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": string_property(
                    "Name of the character to load.",
                    examples=["Arven"],
                ),
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    }


def test_character_specs_match_callable_names_defaults_and_required_fields():
    registry = ToolRegistry()
    tools = registry.get_tools()
    specs = {spec.name: spec for spec in registry.get_tool_specs()}

    assert set(specs) == set(tools)

    for name, tool in tools.items():
        signature = inspect.signature(tool)
        schema = specs[name].input_schema
        assert set(schema["properties"]) == set(signature.parameters)
        assert set(schema["required"]) == {
            parameter_name
            for parameter_name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        }
        assert schema["additionalProperties"] is False


def test_specs_are_deterministically_ordered_serialized_and_immutable():
    registry = ToolRegistry()

    specs = registry.get_tool_specs()
    serialized_once = json.dumps(
        [spec.to_dict() for spec in specs],
        separators=(",", ":"),
        sort_keys=True,
    )
    serialized_twice = json.dumps(
        [spec.to_dict() for spec in registry.get_tool_specs()],
        separators=(",", ":"),
        sort_keys=True,
    )

    assert [spec.name for spec in specs] == [
        "create_character",
        "load_character",
    ]
    assert serialized_once == serialized_twice

    with pytest.raises(AttributeError):
        specs.append(specs[0])
    with pytest.raises(TypeError):
        specs[0].input_schema["type"] = "array"
    with pytest.raises(TypeError):
        specs[0].input_schema["properties"]["name"]["type"] = "number"

    copied = specs[0].to_dict()
    copied["input_schema"]["properties"]["name"]["type"] = "number"
    assert specs[0].input_schema["properties"]["name"]["type"] == "string"


@pytest.mark.parametrize(
    "spec_factory",
    [
        lambda: ToolSpec(
            " ",
            "Description",
            input_schema({}, []),
        ),
        lambda: ToolSpec(
            "valid_name",
            " ",
            input_schema({}, []),
        ),
        lambda: ToolSpec(
            "valid_name",
            "Description",
            {
                **input_schema({}, []),
                "type": "array",
            },
        ),
        lambda: ToolSpec(
            "valid_name",
            "Description",
            {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        ),
        lambda: ToolSpec(
            "valid_name",
            "Description",
            input_schema(
                {"name": {"type": "string", "description": ""}},
                ["name"],
            ),
        ),
        lambda: ToolSpec(
            "valid_name",
            "Description",
            {
                **input_schema({}, []),
                "additionalProperties": True,
            },
        ),
        lambda: ToolSpec(
            "valid_name",
            "Description",
            input_schema({}, ["missing"]),
        ),
    ],
    ids=[
        "empty-name",
        "empty-description",
        "non-object-input",
        "missing-required-list",
        "missing-property-description",
        "additional-properties",
        "required-property-missing",
    ],
)
def test_malformed_specifications_are_rejected(spec_factory):
    with pytest.raises(ValueError):
        spec_factory()


def test_duplicate_tool_names_are_rejected():
    registry = ToolRegistry()
    duplicate_spec = next(
        spec
        for spec in registry.get_tool_specs()
        if spec.name == "load_character"
    )

    with pytest.raises(ValueError, match="Duplicate tool name"):
        registry.register(duplicate_spec, lambda name: None)


@pytest.mark.parametrize(
    ("spec", "tool", "message"),
    [
        (
            ToolSpec(
                "missing_property",
                "Missing schema property.",
                input_schema({}, []),
            ),
            lambda name: None,
            "signature mismatch",
        ),
        (
            ToolSpec(
                "unsupported_property",
                "Unsupported schema property.",
                input_schema(
                    {"invented": string_property("Invented argument.")},
                    ["invented"],
                ),
            ),
            lambda: None,
            "signature mismatch",
        ),
        (
            ToolSpec(
                "wrong_required",
                "Wrong required list.",
                input_schema(
                    {"name": string_property("A name.")},
                    [],
                ),
            ),
            lambda name: None,
            "required arguments",
        ),
    ],
    ids=["missing", "unsupported", "required-default-drift"],
)
def test_schema_callable_drift_is_rejected(spec, tool, message):
    registry = ToolRegistry()

    with pytest.raises(ValueError, match=message):
        registry.register(spec, tool)


def test_valid_future_tool_can_be_registered_without_character_changes():
    registry = ToolRegistry()
    spec = ToolSpec(
        "z_roll_die",
        "Roll one die with a requested number of sides.",
        input_schema(
            {
                "sides": {
                    "type": "integer",
                    "description": "Number of sides on the die.",
                    "examples": [20],
                },
                "modifier": {
                    "type": "integer",
                    "description": "Modifier added to the roll.",
                    "default": 0,
                    "examples": [2],
                },
            },
            ["sides"],
        ),
    )

    def roll_die(sides, modifier=0):
        return sides + modifier

    registry.register(spec, roll_die)

    assert registry.get_tools()["z_roll_die"] is roll_die
    assert registry.get_tool_specs()[-1] is spec


def test_tool_group_name_mismatch_and_duplicates_fail_clearly():
    declared = ToolSpec(
        "declared_name",
        "A declared tool.",
        input_schema({}, []),
    )

    class MismatchedGroup:
        def get_tools(self):
            return {"actual_name": lambda: None}

        def get_tool_specs(self):
            return (declared,)

    class DuplicateGroup:
        def get_tools(self):
            return {"declared_name": lambda: None}

        def get_tool_specs(self):
            return (declared, declared)

    with pytest.raises(ValueError, match="exactly match"):
        ToolRegistry(MismatchedGroup())
    with pytest.raises(ValueError, match="Duplicate tool specification"):
        ToolRegistry(DuplicateGroup())


def test_uninspectable_or_variadic_callables_are_rejected():
    empty_spec = ToolSpec(
        "unsupported_callable",
        "A tool with an unsupported callable.",
        input_schema({}, []),
    )

    class UninspectableTool:
        @property
        def __signature__(self):
            raise ValueError("private detail")

        def __call__(self):
            return None

    registry = ToolRegistry()

    with pytest.raises(ValueError, match="Could not inspect"):
        registry.register(empty_spec, UninspectableTool())

    variadic_spec = ToolSpec(
        "variadic_tool",
        "A variadic tool.",
        input_schema({}, []),
    )
    with pytest.raises(ValueError, match="unsupported parameters"):
        registry.register(variadic_spec, lambda **kwargs: kwargs)

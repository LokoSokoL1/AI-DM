import inspect

from dungeon_manager.tools.character_tools import CharacterTools
from dungeon_manager.tools.tool_spec import ToolSpec


class ToolRegistry:
    """
    Central registry for AI accessible tools.
    """

    def __init__(self, character_tools=None):

        self.character_tools = (
            character_tools
            if character_tools is not None
            else CharacterTools()
        )

        self._tools = {}
        self._tool_specs = {}
        self._register_tool_group(self.character_tools)


    def _register_tool_group(self, tool_group):

        tools = tool_group.get_tools()
        specs = tuple(tool_group.get_tool_specs())

        if not isinstance(tools, dict):
            raise ValueError("Tool groups must return a tool-name mapping.")
        if any(not isinstance(spec, ToolSpec) for spec in specs):
            raise ValueError("Tool groups must return ToolSpec instances.")

        spec_names = [spec.name for spec in specs]
        if len(spec_names) != len(set(spec_names)):
            raise ValueError("Duplicate tool specification names are not allowed.")
        if set(tools) != set(spec_names):
            raise ValueError(
                "Tool specification names must exactly match registered tools."
            )

        for spec in specs:
            self.register(spec, tools[spec.name])


    @staticmethod
    def _validate_signature(spec, tool):

        if not callable(tool):
            raise ValueError(f"Registered tool '{spec.name}' must be callable.")

        try:
            signature = inspect.signature(tool)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Could not inspect registered tool '{spec.name}'."
            ) from error

        supported_kinds = {
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        }
        unsupported = [
            parameter.name
            for parameter in signature.parameters.values()
            if parameter.kind not in supported_kinds
        ]
        if unsupported:
            names = ", ".join(unsupported)
            raise ValueError(
                f"Tool '{spec.name}' has unsupported parameters: {names}."
            )

        parameters = signature.parameters
        properties = spec.input_schema["properties"]
        parameter_names = set(parameters)
        property_names = set(properties)

        if parameter_names != property_names:
            missing = sorted(parameter_names - property_names)
            unsupported = sorted(property_names - parameter_names)
            details = []
            if missing:
                details.append(f"missing schema properties: {', '.join(missing)}")
            if unsupported:
                details.append(
                    "unsupported schema properties: "
                    f"{', '.join(unsupported)}"
                )
            raise ValueError(
                f"Tool '{spec.name}' signature mismatch ({'; '.join(details)})."
            )

        callable_required = {
            name
            for name, parameter in parameters.items()
            if parameter.default is inspect.Parameter.empty
        }
        schema_required = set(spec.input_schema["required"])
        if callable_required != schema_required:
            raise ValueError(
                f"Tool '{spec.name}' required arguments do not match "
                "callable defaults."
            )


    def register(self, spec, tool):
        """Register one validated specification/callable pair."""

        if not isinstance(spec, ToolSpec):
            raise ValueError(
                "Registered tool specifications must be ToolSpec instances."
            )
        if spec.name in self._tools:
            raise ValueError(f"Duplicate tool name: {spec.name}")

        self._validate_signature(spec, tool)
        self._tools[spec.name] = tool
        self._tool_specs[spec.name] = spec


    def get_tools(self):

        return dict(self._tools)


    def get_tool_specs(self):
        """Return immutable specifications in deterministic name order."""

        return tuple(
            self._tool_specs[name]
            for name in sorted(self._tool_specs)
        )


    def execute(self, tool_name: str, **kwargs):

        if tool_name not in self._tools:
            return {
                "success": False,
                "message": f"Unknown tool: {tool_name}"
            }

        return self._tools[tool_name](**kwargs)

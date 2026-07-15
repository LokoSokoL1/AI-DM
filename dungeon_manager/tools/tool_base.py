class BaseTool:
    """
    Base class for AI accessible tools.
    """

    name = ""
    description = ""

    def get_tools(self):
        """
        Returns available functions.
        """

        return {}

    def get_tool_specs(self):
        """Returns provider-neutral specifications for available functions."""

        return ()

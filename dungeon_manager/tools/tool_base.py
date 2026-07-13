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
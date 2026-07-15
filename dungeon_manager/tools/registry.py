from dungeon_manager.tools.character_tools import CharacterTools


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


    def get_tools(self):

        return {
            "create_character": self.character_tools.create_character,
            "load_character": self.character_tools.load_character
        }


    def execute(self, tool_name: str, **kwargs):

        tools = self.get_tools()

        if tool_name not in tools:
            return {
                "success": False,
                "message": f"Unknown tool: {tool_name}"
            }

        return tools[tool_name](**kwargs)

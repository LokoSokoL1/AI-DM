from dungeon_manager.tools.registry import ToolRegistry


class ToolAgent:
    """
    Connects the AI provider with available tools.
    """

    def __init__(self, ai_provider):

        self.ai_provider = ai_provider
        self.tool_registry = ToolRegistry()


    def get_available_tools(self):

        return list(
            self.tool_registry.get_tools().keys()
        )


    def ask(self, prompt: str):

        tools = self.get_available_tools()

        enhanced_prompt = f"""
You are Dungeon Manager AI.

Available tools:
{tools}

User request:
{prompt}

Respond normally.
"""

        return self.ai_provider.generate(
            enhanced_prompt
        )
from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("Tool name cannot be empty")
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Tool not found: {name}") from exc

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def llm_definitions(self) -> list[dict[str, object]]:
        return [tool.to_llm_definition() for tool in self._tools.values()]

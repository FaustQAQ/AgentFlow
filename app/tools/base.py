from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from app.schemas.execution import ToolCallResult


class BaseTool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel]

    @abstractmethod
    def execute(self, arguments: BaseModel) -> ToolCallResult:
        """Execute the tool with validated arguments."""

    def validate_arguments(self, raw_arguments: dict[str, Any]) -> BaseModel:
        return self.args_schema.model_validate(raw_arguments)

    def to_llm_definition(self) -> dict[str, Any]:
        schema = self.args_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }

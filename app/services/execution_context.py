from copy import deepcopy
from typing import Any


class ExecutionContext:
    def __init__(self) -> None:
        self._step_outputs: dict[int, Any] = {}

    def save_step_output(self, step_index: int, output: Any) -> None:
        if step_index < 1:
            raise ValueError("step_index must be at least 1")
        self._step_outputs[step_index] = deepcopy(output)

    def get_step_output(self, step_index: int) -> Any:
        if step_index not in self._step_outputs:
            raise KeyError(f"No output found for step {step_index}")
        return deepcopy(self._step_outputs[step_index])

    def get_step_field(self, step_index: int, field_name: str) -> Any:
        output = self.get_step_output(step_index)
        if not isinstance(output, dict):
            raise TypeError(f"Output for step {step_index} has no fields")
        if field_name not in output:
            raise KeyError(f"Field '{field_name}' not found in output for step {step_index}")
        return deepcopy(output[field_name])

    def resolve_references(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, dict):
            return {key: self.resolve_references(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.resolve_references(item) for item in value]
        return value

    def _resolve_string(self, value: str) -> Any:
        if not value.startswith("$steps."):
            return value

        parts = value.split(".")
        if len(parts) != 3 or parts[0] != "$steps" or not parts[1].isdigit() or not parts[2]:
            raise ValueError(
                f"Invalid step reference '{value}'; expected $steps.<step_index>.<field>"
            )

        step_index = int(parts[1])
        if step_index < 1:
            raise ValueError(f"Invalid step reference '{value}'; step_index must be at least 1")
        return self.get_step_field(step_index, parts[2])

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


class DummyArguments(BaseModel):
    value: int


class OtherArguments(BaseModel):
    text: str


class DummyTool(BaseTool):
    name = "dummy"
    description = "A test-only tool"
    args_schema = DummyArguments

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        return ToolCallResult(success=True, output_data={"value": arguments.value})


class OtherDummyTool(BaseTool):
    name = "other_dummy"
    description = "Another test-only tool"
    args_schema = OtherArguments

    def execute(self, arguments: OtherArguments) -> ToolCallResult:
        return ToolCallResult(success=True, output_data=arguments.text)


class EmptyNameTool(DummyTool):
    name = ""


def test_can_register_tool() -> None:
    registry = ToolRegistry()
    tool = DummyTool()

    registry.register(tool)

    assert registry.get_tool("dummy") is tool


def test_can_find_registered_tool_by_name() -> None:
    registry = ToolRegistry()
    tool = DummyTool()
    registry.register(tool)

    assert registry.get_tool("dummy") is tool


def test_can_list_all_registered_tools() -> None:
    registry = ToolRegistry()
    first = DummyTool()
    second = OtherDummyTool()
    registry.register(first)
    registry.register(second)

    assert registry.list_tools() == [first, second]


def test_duplicate_tool_name_raises_value_error() -> None:
    registry = ToolRegistry()
    registry.register(DummyTool())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(DummyTool())


def test_empty_tool_name_raises_value_error() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        ToolRegistry().register(EmptyNameTool())


def test_missing_tool_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Tool not found: missing"):
        ToolRegistry().get_tool("missing")


def test_tool_arguments_validate_successfully() -> None:
    arguments = DummyTool().validate_arguments({"value": 3})

    assert isinstance(arguments, DummyArguments)
    assert arguments.value == 3


def test_tool_arguments_with_wrong_type_fail_validation() -> None:
    with pytest.raises(ValidationError):
        DummyTool().validate_arguments({"value": "not-an-integer"})


def test_missing_required_tool_argument_fails_validation() -> None:
    with pytest.raises(ValidationError):
        DummyTool().validate_arguments({})


def test_different_tools_can_use_different_argument_models() -> None:
    dummy_arguments = DummyTool().validate_arguments({"value": 7})
    other_arguments = OtherDummyTool().validate_arguments({"text": "hello"})

    assert isinstance(dummy_arguments, DummyArguments)
    assert isinstance(other_arguments, OtherArguments)


def test_execute_returns_tool_call_result() -> None:
    result = DummyTool().execute(DummyArguments(value=5))

    assert isinstance(result, ToolCallResult)
    assert result.success is True
    assert result.output_data == {"value": 5}


def test_list_tools_returns_copy_of_internal_collection() -> None:
    registry = ToolRegistry()
    registry.register(DummyTool())
    listed_tools = registry.list_tools()

    listed_tools.clear()

    assert registry.get_tool("dummy").name == "dummy"

from datetime import timezone
import logging
import math

import pytest
from pydantic import BaseModel

from app.schemas.execution import (
    AgentExecution,
    ExecutionStatus,
    StepStatus,
    ToolCallRequest,
    ToolCallResult,
)
from app.services.agent_executor import AgentExecutor
from app.services.exceptions import ToolRetryableError, ToolTimeoutError
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry
from app.tools.markdown_report import MarkdownReportGeneratorTool
from app.tools.sales_data import SalesDataQueryTool
from app.tools.sales_metrics import SalesMetricsCalculatorTool


class DummyArguments(BaseModel):
    value: int


class DummyTool(BaseTool):
    name = "dummy"
    description = "Executor test tool"
    args_schema = DummyArguments

    def __init__(self, calls: list[str] | None = None) -> None:
        self.calls = calls

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        if self.calls is not None:
            self.calls.append(f"dummy:{arguments.value}")
        return ToolCallResult(success=True, output_data={"value": arguments.value})


class SecondDummyTool(BaseTool):
    name = "second"
    description = "Second executor test tool"
    args_schema = DummyArguments

    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        self.calls.append(f"second:{arguments.value}")
        return ToolCallResult(success=True, output_data={"value": arguments.value})


class FailingTool(BaseTool):
    name = "failing"
    description = "Business-failure test tool"
    args_schema = DummyArguments

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        return ToolCallResult(success=False, error_message="Business operation failed")


class ExplodingTool(BaseTool):
    name = "exploding"
    description = "Unexpected-error test tool"
    args_schema = DummyArguments

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        raise RuntimeError("Unexpected tool error")


class TimeoutTool(BaseTool):
    name = "timeout"
    description = "Timeout test tool"
    args_schema = DummyArguments

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        raise ToolTimeoutError("external operation timed out")


class RetryableTool(BaseTool):
    name = "retryable"
    description = "Retryable failure test tool"
    args_schema = DummyArguments

    def __init__(self, failures_before_success: int) -> None:
        self.failures_before_success = failures_before_success
        self.calls = 0

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        self.calls += 1
        if self.calls <= self.failures_before_success:
            raise ToolRetryableError("temporary retryable failure")
        return ToolCallResult(success=True, output_data={"value": arguments.value})


class BusinessFailureCountingTool(BaseTool):
    name = "business_failure_counting"
    description = "Business failure counting test tool"
    args_schema = DummyArguments

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, arguments: DummyArguments) -> ToolCallResult:
        self.calls += 1
        return ToolCallResult(success=False, error_message="Business failure")


class DictArguments(BaseModel):
    payload: dict[str, int]


class DictTool(BaseTool):
    name = "dict_tool"
    description = "Dictionary reference test tool"
    args_schema = DictArguments

    def execute(self, arguments: DictArguments) -> ToolCallResult:
        return ToolCallResult(success=True, output_data={"amount": arguments.payload["amount"]})


class ListArguments(BaseModel):
    values: list[int]


class ListTool(BaseTool):
    name = "list_tool"
    description = "List reference test tool"
    args_schema = ListArguments

    def execute(self, arguments: ListArguments) -> ToolCallResult:
        return ToolCallResult(success=True, output_data={"total": sum(arguments.values)})


class TextArguments(BaseModel):
    text: str


class TextTool(BaseTool):
    name = "text_tool"
    description = "Plain string test tool"
    args_schema = TextArguments

    def execute(self, arguments: TextArguments) -> ToolCallResult:
        return ToolCallResult(success=True, output_data={"text": arguments.text})


def _executor(
    *tools: BaseTool,
    max_steps: int = 10,
    max_retries: int = 2,
    retry_delay_seconds: float = 0.5,
) -> AgentExecutor:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return AgentExecutor(
        registry,
        max_steps=max_steps,
        max_retries=max_retries,
        retry_delay_seconds=retry_delay_seconds,
    )


def _call(tool_name: str, value: int = 1) -> ToolCallRequest:
    return ToolCallRequest(tool_name=tool_name, arguments={"value": value})


def test_can_execute_one_tool_successfully() -> None:
    execution = _executor(DummyTool()).run("Run one tool", [_call("dummy", 3)])

    assert isinstance(execution, AgentExecution)
    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.success is True


def test_tools_execute_in_requested_order() -> None:
    calls: list[str] = []
    execution = _executor(DummyTool(calls), SecondDummyTool(calls)).run(
        "Run two tools", [_call("dummy", 1), _call("second", 2)]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert calls == ["dummy:1", "second:2"]


def test_all_successful_steps_make_execution_succeeded() -> None:
    execution = _executor(DummyTool()).run(
        "Run tools", [_call("dummy", 1), _call("dummy", 2)]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.error_message is None
    assert execution.completed_at is not None


def test_step_indexes_start_at_one_and_increment() -> None:
    execution = _executor(DummyTool()).run(
        "Run tools", [_call("dummy", 1), _call("dummy", 2)]
    )

    assert [step.step_index for step in execution.steps] == [1, 2]


def test_each_step_references_parent_execution() -> None:
    execution = _executor(DummyTool()).run(
        "Run tools", [_call("dummy", 1), _call("dummy", 2)]
    )

    assert all(step.execution_id == execution.execution_id for step in execution.steps)


def test_each_step_preserves_tool_call_result() -> None:
    execution = _executor(DummyTool()).run("Run tool", [_call("dummy", 4)])

    result = execution.steps[0].tool_result
    assert result is not None
    assert result.output_data == {"value": 4}


def test_business_failure_fails_execution_and_records_error() -> None:
    execution = _executor(FailingTool()).run("Run failing tool", [_call("failing")])

    assert execution.status is ExecutionStatus.FAILED
    assert execution.steps[0].status is StepStatus.FAILED
    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_message == "Business operation failed"
    assert execution.error_message == "Business operation failed"


def test_missing_tool_fails_execution() -> None:
    execution = _executor().run("Run missing tool", [_call("missing")])

    assert execution.status is ExecutionStatus.FAILED
    assert execution.steps[0].status is StepStatus.FAILED
    assert execution.steps[0].tool_result is not None
    assert "KeyError" in (execution.error_message or "")
    assert "Tool not found: missing" in (execution.error_message or "")


def test_invalid_arguments_fail_execution() -> None:
    execution = _executor(DummyTool()).run(
        "Run invalid tool", [ToolCallRequest(tool_name="dummy", arguments={})]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert execution.steps[0].status is StepStatus.FAILED
    assert execution.steps[0].tool_result is not None
    assert "ValidationError" in (execution.error_message or "")


def test_unexpected_tool_exception_fails_execution() -> None:
    execution = _executor(ExplodingTool()).run("Run exploding tool", [_call("exploding")])

    assert execution.status is ExecutionStatus.FAILED
    assert execution.steps[0].status is StepStatus.FAILED
    assert execution.steps[0].tool_result is not None
    assert "RuntimeError: Unexpected tool error" == execution.error_message


def test_execution_stops_after_first_failed_tool() -> None:
    calls: list[str] = []
    execution = _executor(FailingTool(), DummyTool(calls)).run(
        "Stop after failure", [_call("failing"), _call("dummy", 2)]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert len(execution.steps) == 1
    assert calls == []


def test_execution_and_steps_have_timezone_aware_timestamps() -> None:
    execution = _executor(DummyTool()).run("Record timestamps", [_call("dummy")])
    step = execution.steps[0]

    assert execution.started_at is not None
    assert execution.completed_at is not None
    assert step.started_at is not None
    assert step.completed_at is not None
    assert execution.started_at.tzinfo is not None
    assert execution.completed_at.tzinfo is not None
    assert step.started_at.tzinfo is not None
    assert step.completed_at.tzinfo is not None
    assert execution.started_at.utcoffset() == timezone.utc.utcoffset(execution.started_at)
    assert step.started_at.utcoffset() == timezone.utc.utcoffset(step.started_at)


def test_successful_step_has_succeeded_status() -> None:
    execution = _executor(DummyTool()).run("Check step status", [_call("dummy")])

    assert execution.steps[0].status is StepStatus.SUCCEEDED


@pytest.mark.parametrize("tool_name", ["missing"])
def test_failed_step_has_error_message(tool_name: str) -> None:
    execution = _executor().run("Check failure message", [_call(tool_name)])

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.success is False
    assert execution.steps[0].tool_result.error_message is not None
    assert execution.error_message == execution.steps[0].tool_result.error_message


def test_second_step_can_reference_first_step_output() -> None:
    execution = _executor(DummyTool()).run(
        "Pass output forward",
        [
            _call("dummy", 7),
            ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.1.value"}),
        ],
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[1].tool_result is not None
    assert execution.steps[1].tool_result.output_data == {"value": 7}


def test_third_step_can_reference_second_step_output() -> None:
    execution = _executor(DummyTool()).run(
        "Chain outputs",
        [
            _call("dummy", 3),
            ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.1.value"}),
            ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.2.value"}),
        ],
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert [step.tool_result.output_data for step in execution.steps] == [
        {"value": 3},
        {"value": 3},
        {"value": 3},
    ]


def test_dictionary_reference_is_resolved_before_validation() -> None:
    execution = _executor(DummyTool(), DictTool()).run(
        "Resolve dictionary reference",
        [
            _call("dummy", 8),
            ToolCallRequest(
                tool_name="dict_tool",
                arguments={"payload": {"amount": "$steps.1.value"}},
            ),
        ],
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[1].tool_result.output_data == {"amount": 8}


def test_list_reference_is_resolved_before_validation() -> None:
    execution = _executor(DummyTool(), ListTool()).run(
        "Resolve list reference",
        [
            _call("dummy", 8),
            ToolCallRequest(
                tool_name="list_tool",
                arguments={"values": ["$steps.1.value", 2]},
            ),
        ],
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[1].tool_result.output_data == {"total": 10}


def test_plain_string_is_not_treated_as_reference() -> None:
    execution = _executor(TextTool()).run(
        "Keep ordinary string",
        [ToolCallRequest(tool_name="text_tool", arguments={"text": "hello $steps.1.value"})],
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[0].tool_result.output_data == {"text": "hello $steps.1.value"}


def test_missing_reference_fails_current_step() -> None:
    execution = _executor(DummyTool()).run(
        "Missing reference",
        [ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.99.value"})],
    )

    assert execution.status is ExecutionStatus.FAILED
    assert execution.steps[0].status is StepStatus.FAILED
    assert execution.steps[0].tool_result is not None
    assert "No output found for step 99" in (execution.error_message or "")


def test_reference_failure_stops_following_tools() -> None:
    calls: list[str] = []
    execution = _executor(DummyTool(calls)).run(
        "Stop after reference failure",
        [
            ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.99.value"}),
            _call("dummy", 2),
        ],
    )

    assert execution.status is ExecutionStatus.FAILED
    assert len(execution.steps) == 1
    assert calls == []


def test_runs_have_isolated_execution_contexts() -> None:
    executor = _executor(DummyTool())
    first = executor.run("First run", [_call("dummy", 7)])
    second = executor.run(
        "Second run",
        [ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.1.value"})],
    )

    assert first.status is ExecutionStatus.SUCCEEDED
    assert second.status is ExecutionStatus.FAILED
    assert "No output found for step 1" in (second.error_message or "")


def test_sales_tools_pass_data_through_complete_pipeline() -> None:
    executor = _executor(
        SalesDataQueryTool(),
        SalesMetricsCalculatorTool(),
        MarkdownReportGeneratorTool(),
    )
    execution = executor.run(
        "Generate January sales report",
        [
            ToolCallRequest(
                tool_name="sales_data_query",
                arguments={"dataset_id": 1, "start_date": "2024-01-01", "end_date": "2024-01-03"},
            ),
            ToolCallRequest(
                tool_name="sales_metrics_calculator",
                arguments={
                    "current_sales": "$steps.1.current_sales",
                    "previous_sales": "$steps.1.previous_sales",
                },
            ),
            ToolCallRequest(
                tool_name="markdown_report_generator",
                arguments={
                    "title": "January Sales Report",
                    "current_sales": "$steps.1.current_sales",
                    "previous_sales": "$steps.1.previous_sales",
                    "growth_rate": "$steps.2.growth_rate",
                },
            ),
        ],
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert execution.steps[2].tool_result is not None
    assert isinstance(execution.steps[2].tool_result.output_data, str)
    assert "# January Sales Report" in execution.steps[2].tool_result.output_data
    assert "33,000.00" in execution.steps[2].tool_result.output_data
    assert "11.86%" in execution.steps[2].tool_result.output_data


def test_exceeding_max_steps_fails_execution() -> None:
    execution = _executor(DummyTool(), max_steps=1).run(
        "Too many steps", [_call("dummy"), _call("dummy")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert execution.completed_at is not None


def test_exceeding_max_steps_does_not_execute_any_tool() -> None:
    calls: list[str] = []
    execution = _executor(DummyTool(calls), max_steps=1).run(
        "Do not execute", [_call("dummy"), _call("dummy")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert calls == []


def test_exceeding_max_steps_does_not_create_steps() -> None:
    execution = _executor(DummyTool(), max_steps=1).run(
        "No steps", [_call("dummy"), _call("dummy")]
    )

    assert execution.steps == []


def test_max_steps_error_contains_limit_and_submitted_count() -> None:
    execution = _executor(DummyTool(), max_steps=2).run(
        "Explain limit", [_call("dummy"), _call("dummy"), _call("dummy")]
    )

    assert execution.error_message is not None
    assert "max_steps=2" in execution.error_message
    assert "submitted_steps=3" in execution.error_message


def test_exactly_max_steps_is_allowed() -> None:
    execution = _executor(DummyTool(), max_steps=2).run(
        "At limit", [_call("dummy"), _call("dummy")]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert len(execution.steps) == 2


def test_custom_max_steps_is_used() -> None:
    execution = _executor(DummyTool(), max_steps=3).run(
        "Custom limit", [_call("dummy"), _call("dummy"), _call("dummy")]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert len(execution.steps) == 3


def test_zero_max_steps_raises_value_error() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        AgentExecutor(ToolRegistry(), max_steps=0)


def test_negative_max_steps_raises_value_error() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        AgentExecutor(ToolRegistry(), max_steps=-1)


def test_default_max_steps_is_ten() -> None:
    executor = AgentExecutor(ToolRegistry())

    assert executor.max_steps == 10


def test_timeout_error_fails_current_step() -> None:
    execution = _executor(TimeoutTool()).run(
        "Run timeout tool", [_call("timeout")]
    )

    assert execution.steps[0].status is StepStatus.FAILED


def test_timeout_information_is_saved_in_tool_result() -> None:
    execution = _executor(TimeoutTool()).run(
        "Save timeout", [_call("timeout")]
    )

    result = execution.steps[0].tool_result
    assert result is not None
    assert result.success is False
    assert "timed out" in (result.error_message or "")


def test_timeout_fails_entire_execution() -> None:
    execution = _executor(TimeoutTool()).run(
        "Fail on timeout", [_call("timeout")]
    )

    assert execution.status is ExecutionStatus.FAILED


def test_execution_error_message_contains_timeout_information() -> None:
    execution = _executor(TimeoutTool()).run(
        "Record timeout", [_call("timeout")]
    )

    assert execution.error_message is not None
    assert "timed out" in execution.error_message


def test_timeout_stops_following_tools() -> None:
    calls: list[str] = []
    execution = _executor(TimeoutTool(), DummyTool(calls)).run(
        "Stop after timeout", [_call("timeout"), _call("dummy")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert len(execution.steps) == 1
    assert calls == []


def test_timeout_step_has_started_and_completed_timestamps() -> None:
    execution = _executor(TimeoutTool()).run(
        "Timestamp timeout", [_call("timeout")]
    )
    step = execution.steps[0]

    assert step.started_at is not None
    assert step.completed_at is not None
    assert step.started_at.tzinfo is not None
    assert step.completed_at.tzinfo is not None


def test_regular_exception_handling_is_preserved() -> None:
    execution = _executor(ExplodingTool()).run(
        "Run regular exception", [_call("exploding")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert execution.error_message == "RuntimeError: Unexpected tool error"


def test_timeout_and_regular_exception_are_distinguishable() -> None:
    timeout_execution = _executor(TimeoutTool()).run(
        "Timeout distinction", [_call("timeout")]
    )
    regular_execution = _executor(ExplodingTool()).run(
        "Exception distinction", [_call("exploding")]
    )

    assert timeout_execution.error_message != regular_execution.error_message
    assert "timed out" in (timeout_execution.error_message or "")
    assert "RuntimeError" in (regular_execution.error_message or "")


def test_retryable_error_then_success_retries_once(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.agent_executor.time.sleep", sleep_calls.append)
    tool = RetryableTool(failures_before_success=1)

    execution = _executor(tool, max_retries=2).run(
        "Retry once", [_call("retryable")]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert tool.calls == 2
    assert sleep_calls == [0.5]


def test_two_retryable_failures_then_success_retries_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.agent_executor.time.sleep", sleep_calls.append)
    tool = RetryableTool(failures_before_success=2)

    execution = _executor(tool, max_retries=2).run(
        "Retry twice", [_call("retryable")]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert tool.calls == 3
    assert sleep_calls == [0.5, 1.0]


def test_retryable_error_fails_after_retry_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.agent_executor.time.sleep", sleep_calls.append)
    tool = RetryableTool(failures_before_success=5)

    execution = _executor(tool, max_retries=2).run(
        "Exhaust retries", [_call("retryable")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert tool.calls == 3
    assert len(sleep_calls) == 2
    assert execution.error_message is not None
    assert "after 3 attempts" in execution.error_message


def test_zero_max_retries_does_not_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.agent_executor.time.sleep", sleep_calls.append)
    tool = RetryableTool(failures_before_success=1)

    execution = _executor(tool, max_retries=0).run(
        "No retry", [_call("retryable")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert tool.calls == 1
    assert sleep_calls == []


def test_max_retries_two_allows_at_most_three_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.agent_executor.time.sleep", lambda _: None)
    tool = RetryableTool(failures_before_success=3)

    execution = _executor(tool, max_retries=2).run(
        "Three attempts maximum", [_call("retryable")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert tool.calls == 3


def test_retry_success_creates_only_one_execution_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.agent_executor.time.sleep", lambda _: None)
    tool = RetryableTool(failures_before_success=1)

    execution = _executor(tool, max_retries=1).run(
        "One step with retry", [_call("retryable")]
    )

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert len(execution.steps) == 1
    assert execution.steps[0].status is StepStatus.SUCCEEDED


def test_retry_failure_stops_following_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.agent_executor.time.sleep", lambda _: None)
    retryable = RetryableTool(failures_before_success=5)
    calls: list[str] = []

    execution = _executor(retryable, DummyTool(calls), max_retries=2).run(
        "Stop after retry failure", [_call("retryable"), _call("dummy")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert len(execution.steps) == 1
    assert retryable.calls == 3
    assert calls == []


def test_regular_runtime_error_does_not_trigger_retry() -> None:
    execution = _executor(ExplodingTool(), max_retries=2).run(
        "No retry for runtime error", [_call("exploding")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert execution.error_message == "RuntimeError: Unexpected tool error"


def test_timeout_error_does_not_trigger_retry() -> None:
    execution = _executor(TimeoutTool(), max_retries=2).run(
        "No retry for timeout", [_call("timeout")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert execution.error_message is not None
    assert "timed out" in execution.error_message


def test_business_failure_result_does_not_trigger_retry() -> None:
    tool = BusinessFailureCountingTool()

    execution = _executor(tool, max_retries=2).run(
        "No retry for business failure", [_call("business_failure_counting")]
    )

    assert execution.status is ExecutionStatus.FAILED
    assert tool.calls == 1


def test_negative_max_retries_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        AgentExecutor(ToolRegistry(), max_retries=-1)


def test_boolean_max_retries_raises_value_error() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        AgentExecutor(ToolRegistry(), max_retries=True)


def test_negative_retry_delay_raises_value_error() -> None:
    with pytest.raises(ValueError, match="finite non-negative number"):
        AgentExecutor(ToolRegistry(), retry_delay_seconds=-0.1)


def test_boolean_retry_delay_raises_value_error() -> None:
    with pytest.raises(ValueError, match="finite non-negative number"):
        AgentExecutor(ToolRegistry(), retry_delay_seconds=True)


@pytest.mark.parametrize("retry_delay", [math.nan, math.inf, -math.inf])
def test_non_finite_retry_delay_raises_value_error(retry_delay: float) -> None:
    with pytest.raises(ValueError, match="finite non-negative number"):
        AgentExecutor(ToolRegistry(), retry_delay_seconds=retry_delay)


def test_custom_retry_count_and_delay_are_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr("app.services.agent_executor.time.sleep", sleep_calls.append)
    tool = RetryableTool(failures_before_success=3)
    executor = _executor(
        tool,
        max_retries=3,
        retry_delay_seconds=0.25,
    )

    execution = executor.run("Custom retry policy", [_call("retryable")])

    assert execution.status is ExecutionStatus.SUCCEEDED
    assert executor.max_retries == 3
    assert executor.retry_delay_seconds == 0.25
    assert tool.calls == 4
    assert sleep_calls == [0.25, 0.5, 1.0]


def test_validation_error_has_validation_error_type() -> None:
    execution = _executor(DummyTool()).run(
        "Classify validation error",
        [ToolCallRequest(tool_name="dummy", arguments={})],
    )

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "validation_error"


def test_missing_tool_has_tool_not_found_error_type() -> None:
    execution = _executor().run("Classify missing tool", [_call("missing")])

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "tool_not_found"


def test_timeout_has_timeout_error_type() -> None:
    execution = _executor(TimeoutTool()).run(
        "Classify timeout", [_call("timeout")]
    )

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "timeout"


def test_retry_exhaustion_has_retry_exhausted_error_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.services.agent_executor.time.sleep", lambda _: None)
    execution = _executor(
        RetryableTool(failures_before_success=5), max_retries=2
    ).run("Classify retry exhaustion", [_call("retryable")])

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "retry_exhausted"


def test_business_failure_has_business_error_type() -> None:
    execution = _executor(FailingTool()).run(
        "Classify business failure", [_call("failing")]
    )

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "business_error"


def test_unexpected_exception_has_unexpected_error_type() -> None:
    execution = _executor(ExplodingTool()).run(
        "Classify unexpected error", [_call("exploding")]
    )

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "unexpected_error"


def test_successful_result_has_no_error_type() -> None:
    execution = _executor(DummyTool()).run(
        "Classify success", [_call("dummy")]
    )

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type is None


def test_context_reference_error_is_not_tool_not_found() -> None:
    execution = _executor(DummyTool()).run(
        "Classify context error",
        [ToolCallRequest(tool_name="dummy", arguments={"value": "$steps.99.value"})],
    )

    assert execution.steps[0].tool_result is not None
    assert execution.steps[0].tool_result.error_type == "unexpected_error"
    assert execution.steps[0].tool_result.error_type != "tool_not_found"


def test_execution_and_step_start_logs_include_identifiers(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.agent_executor")

    execution = _executor(DummyTool()).run(
        "Log execution start", [_call("dummy")]
    )
    messages = [record.getMessage() for record in caplog.records]

    assert any("execution_started" in message for message in messages)
    assert any("step_started" in message for message in messages)
    assert any(str(execution.execution_id) in message for message in messages)
    assert any("step_index=1" in message and "tool_name=dummy" in message for message in messages)


def test_retry_logs_warning(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.agent_executor")
    monkeypatch.setattr("app.services.agent_executor.time.sleep", lambda _: None)

    execution = _executor(
        RetryableTool(failures_before_success=1), max_retries=1
    ).run("Log retry", [_call("retryable")])

    retry_records = [
        record for record in caplog.records if "tool_retrying" in record.getMessage()
    ]
    assert retry_records
    assert retry_records[0].levelno == logging.WARNING
    assert str(execution.execution_id) in retry_records[0].getMessage()


def test_step_failure_logs_error_with_classification(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.agent_executor")

    execution = _executor(FailingTool()).run(
        "Log step failure", [_call("failing")]
    )
    failure_records = [
        record for record in caplog.records if "step_failed" in record.getMessage()
    ]

    assert failure_records
    assert failure_records[0].levelno == logging.ERROR
    assert "error_type=business_error" in failure_records[0].getMessage()
    assert str(execution.execution_id) in failure_records[0].getMessage()


def test_execution_success_logs_info(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.agent_executor")

    execution = _executor(DummyTool()).run(
        "Log execution success", [_call("dummy")]
    )

    success_records = [
        record
        for record in caplog.records
        if "execution_succeeded" in record.getMessage()
    ]
    assert success_records
    assert success_records[0].levelno == logging.INFO
    assert str(execution.execution_id) in success_records[0].getMessage()


def test_execution_failure_logs_error(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="app.services.agent_executor")

    execution = _executor(ExplodingTool()).run(
        "Log execution failure", [_call("exploding")]
    )

    failure_records = [
        record
        for record in caplog.records
        if "execution_failed" in record.getMessage()
    ]
    assert failure_records
    assert failure_records[-1].levelno == logging.ERROR
    assert str(execution.execution_id) in failure_records[-1].getMessage()


def test_failure_logs_include_step_and_tool_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.services.agent_executor")

    execution = _executor(TimeoutTool()).run(
        "Log timeout failure", [_call("timeout")]
    )

    failure_records = [
        record for record in caplog.records if "step_failed" in record.getMessage()
    ]
    assert failure_records
    message = failure_records[0].getMessage()
    assert str(execution.execution_id) in message
    assert "step_index=1" in message
    assert "tool_name=timeout" in message
    assert "error_type=timeout" in message

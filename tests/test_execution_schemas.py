from datetime import timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.execution import (
    AgentExecution,
    ExecutionStatus,
    ExecutionStep,
    StepStatus,
    ToolCallRequest,
    ToolCallResult,
)


def test_execution_status_has_expected_values() -> None:
    assert [status.value for status in ExecutionStatus] == [
        "pending",
        "running",
        "succeeded",
        "failed",
    ]


def test_step_status_has_expected_values() -> None:
    assert [status.value for status in StepStatus] == [
        "pending",
        "running",
        "succeeded",
        "failed",
    ]


def test_agent_execution_defaults_to_pending() -> None:
    execution = AgentExecution(user_request="Run a task")

    assert execution.status is ExecutionStatus.PENDING


def test_agent_execution_generates_uuid() -> None:
    execution = AgentExecution(user_request="Run a task")

    assert execution.execution_id is not None


def test_independent_agent_executions_have_different_uuids() -> None:
    first = AgentExecution(user_request="First task")
    second = AgentExecution(user_request="Second task")

    assert first.execution_id != second.execution_id


def test_user_request_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        AgentExecution(user_request="")


def test_execution_step_index_must_be_at_least_one() -> None:
    with pytest.raises(ValidationError):
        ExecutionStep(
            execution_id=uuid4(),
            step_index=0,
            tool_call=ToolCallRequest(tool_name="lookup"),
        )


def test_tool_call_request_defaults_to_empty_arguments() -> None:
    request = ToolCallRequest(tool_name="lookup")

    assert request.arguments == {}


def test_tool_call_result_stores_successful_result() -> None:
    result = ToolCallResult(success=True, output_data={"value": 42})

    assert result.success is True
    assert result.output_data == {"value": 42}


def test_tool_call_result_stores_failure_information() -> None:
    result = ToolCallResult(success=False, error_message="Tool failed")

    assert result.success is False
    assert result.error_message == "Tool failed"


def test_agent_execution_created_at_is_timezone_aware_utc() -> None:
    execution = AgentExecution(user_request="Run a task")

    assert execution.created_at.tzinfo is not None
    assert execution.created_at.utcoffset() == timezone.utc.utcoffset(execution.created_at)


def test_agent_execution_steps_default_is_independent_between_instances() -> None:
    first = AgentExecution(user_request="First task")
    second = AgentExecution(user_request="Second task")
    first.steps.append(
        ExecutionStep(
            execution_id=first.execution_id,
            step_index=1,
            tool_call=ToolCallRequest(tool_name="lookup"),
        )
    )

    assert len(first.steps) == 1
    assert second.steps == []

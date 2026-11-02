from unittest.mock import Mock

import pytest

from app.schemas.execution import AgentExecution, ToolCallRequest
from app.services.agent_execution_service import AgentExecutionService
from app.services.exceptions import ExecutionPersistenceError


def test_execution_service_runs_then_persists_and_closes_session() -> None:
    execution = AgentExecution(user_request="test")
    executor = Mock()
    executor.run.return_value = execution
    persistence = Mock()
    session = Mock()
    service = AgentExecutionService(executor, persistence, lambda: session)

    result = service.run("test", [])

    assert result is execution
    executor.run.assert_called_once_with("test", [])
    persistence.save_execution.assert_called_once_with(session, execution)
    session.close.assert_called_once_with()


def test_execution_service_persists_failed_execution() -> None:
    execution = AgentExecution(user_request="test")
    execution.error_message = "tool failed"
    executor = Mock()
    executor.run.return_value = execution
    persistence = Mock()
    session = Mock()

    result = AgentExecutionService(executor, persistence, lambda: session).run(
        "test", []
    )

    assert result.error_message == "tool failed"
    persistence.save_execution.assert_called_once()


def test_persistence_failure_is_wrapped_and_session_closes() -> None:
    execution = AgentExecution(user_request="test")
    executor = Mock()
    executor.run.return_value = execution
    persistence = Mock()
    persistence.save_execution.side_effect = RuntimeError("database unavailable")
    session = Mock()

    with pytest.raises(ExecutionPersistenceError) as raised:
        AgentExecutionService(executor, persistence, lambda: session).run("test", [])

    assert raised.value.execution is execution
    assert isinstance(raised.value.__cause__, RuntimeError)
    session.close.assert_called_once_with()

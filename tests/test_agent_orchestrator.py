from unittest.mock import Mock

from app.schemas.execution import ToolCallResult
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.llm.client import LLMResponse, LLMToolCall
from app.tools.registry import ToolRegistry


class FakePersistence:
    def __init__(self) -> None:
        self.saved = []

    def save_execution(self, db, execution):
        self.saved.append(execution)
        return str(execution.execution_id)


def test_orchestrator_supports_direct_llm_answer() -> None:
    llm = Mock()
    llm.chat.return_value = LLMResponse("直接回答", [], {"role": "assistant", "content": "直接回答"})
    persistence = FakePersistence()
    orchestrator = AgentOrchestrator(
        llm, ToolRegistry(), Mock(), persistence, lambda: Mock()
    )

    result = orchestrator.run("你好")

    assert result.final_output == "直接回答"
    assert result.status.value == "succeeded"
    assert len(persistence.saved) == 1


def test_orchestrator_rejects_unknown_tool_before_executor() -> None:
    llm = Mock()
    llm.chat.return_value = LLMResponse(
        None,
        [LLMToolCall("call-1", "unknown", {})],
        {"role": "assistant", "tool_calls": []},
    )
    executor = Mock()
    executor.run.return_value = Mock(steps=[], status=Mock(value="failed"), error_message="unknown")
    persistence = FakePersistence()
    result = AgentOrchestrator(llm, ToolRegistry(), executor, persistence, lambda: Mock()).run("x")
    assert result.status.value == "failed"

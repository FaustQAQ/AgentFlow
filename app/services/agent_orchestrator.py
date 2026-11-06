import json
import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.schemas.execution import AgentExecution, ExecutionStatus, ToolCallRequest
from app.services.agent_executor import AgentExecutor
from app.services.execution_persistence import ExecutionPersistenceService
from app.services.exceptions import ExecutionPersistenceError
from app.services.llm.client import LLMError, LLMResponse
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是 AgentFlow 销售分析助手。只能使用系统提供的已注册工具。
不要编造销售数据；必须以工具实际返回的数据为准。缺失数据或工具失败时如实说明。
需要工具时调用工具，完成分析后给出简洁、清晰的中文回答。"""


class AgentOrchestrator:
    """Drive bounded LLM tool-calling rounds while Python owns tool execution."""

    def __init__(
        self,
        llm: object,
        registry: ToolRegistry,
        executor: AgentExecutor,
        persistence: ExecutionPersistenceService | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
        max_rounds: int = 6,
        max_tool_calls: int = 10,
    ) -> None:
        if max_rounds <= 0 or max_tool_calls <= 0:
            raise ValueError("max_rounds and max_tool_calls must be positive")
        self.llm = llm
        self.registry = registry
        self.executor = executor
        self.persistence = persistence or ExecutionPersistenceService()
        self.session_factory = session_factory
        self.max_rounds = max_rounds
        self.max_tool_calls = max_tool_calls

    def run(self, user_request: str, dataset_id: int | None = None) -> AgentExecution:
        execution = AgentExecution(user_request=user_request, dataset_id=dataset_id)
        execution.status = ExecutionStatus.RUNNING
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"当前数据集 ID: {dataset_id}\n{user_request}" if dataset_id else user_request},
        ]
        tool_call_count = 0

        try:
            for _ in range(self.max_rounds):
                response: LLMResponse = self.llm.chat(
                    messages, self.registry.llm_definitions()
                )
                if not response.tool_calls:
                    execution.final_output = response.content or ""
                    execution.status = ExecutionStatus.SUCCEEDED
                    break

                if tool_call_count + len(response.tool_calls) > self.max_tool_calls:
                    raise LLMError("Maximum tool call limit exceeded")
                tool_call_count += len(response.tool_calls)
                messages.append(response.assistant_message)

                round_result = self.executor.run(
                    user_request,
                    [
                        ToolCallRequest(
                            tool_name=call.name,
                            arguments=call.arguments,
                        )
                        for call in response.tool_calls
                    ], dataset_id=dataset_id,
                )
                for step in round_result.steps:
                    step.execution_id = execution.execution_id
                    step.step_index = len(execution.steps) + 1
                    execution.steps.append(step)
                if round_result.status is ExecutionStatus.FAILED:
                    execution.status = ExecutionStatus.FAILED
                    execution.error_message = round_result.error_message
                    break
                for call, step in zip(response.tool_calls, round_result.steps):
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(
                                step.tool_result.output_data
                                if step.tool_result is not None
                                else None,
                                ensure_ascii=False,
                            ),
                        }
                    )
            else:
                execution.status = ExecutionStatus.FAILED
                execution.error_message = "Maximum LLM rounds exceeded"
        except Exception as error:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = str(error) or type(error).__name__

        execution.completed_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )
        self._persist(execution)
        return execution

    def _persist(self, execution: AgentExecution) -> None:
        db = self.session_factory()
        try:
            self.persistence.save_execution(db, execution)
        except Exception as error:
            raise ExecutionPersistenceError(
                str(execution.execution_id), execution, error
            ) from error
        finally:
            db.close()

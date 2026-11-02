from datetime import datetime, timezone
import logging
import math
import time
from uuid import UUID

from pydantic import BaseModel, ValidationError

from app.schemas.execution import (
    AgentExecution,
    ExecutionStatus,
    ExecutionStep,
    StepStatus,
    ToolCallRequest,
    ToolCallResult,
)
from app.services.execution_context import ExecutionContext
from app.services.exceptions import ToolRetryableError, ToolTimeoutError
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _exception_message(error: Exception) -> str:
    message = str(error)
    if message:
        return f"{type(error).__name__}: {message}"
    return type(error).__name__


class AgentExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        max_steps: int = 10,
        max_retries: int = 2,
        retry_delay_seconds: float = 0.5,
    ) -> None:
        if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        if (
            isinstance(max_retries, bool)
            or not isinstance(max_retries, int)
            or max_retries < 0
        ):
            raise ValueError("max_retries must be a non-negative integer")
        if (
            isinstance(retry_delay_seconds, bool)
            or not isinstance(retry_delay_seconds, (int, float))
            or not math.isfinite(float(retry_delay_seconds))
            or retry_delay_seconds < 0
        ):
            raise ValueError("retry_delay_seconds must be a finite non-negative number")

        self.registry = registry
        self.max_steps = max_steps
        self.max_retries = max_retries
        self.retry_delay_seconds = float(retry_delay_seconds)

    def _execute_with_retries(
        self,
        tool: BaseTool,
        arguments: BaseModel,
        execution_id: UUID,
        step_index: int,
    ) -> ToolCallResult:
        for retry_index in range(self.max_retries + 1):
            try:
                return tool.execute(arguments)
            except ToolRetryableError as error:
                if retry_index >= self.max_retries:
                    return ToolCallResult(
                        success=False,
                        error_message=(
                            f"Retryable tool failure after {retry_index + 1} attempts: "
                            f"{_exception_message(error)}"
                        ),
                        error_type="retry_exhausted",
                    )
                delay = self.retry_delay_seconds * (2**retry_index)
                logger.warning(
                    "tool_retrying execution_id=%s step_index=%s tool_name=%s "
                    "retry_index=%s max_retries=%s delay_seconds=%s "
                    "error_message=%s",
                    execution_id,
                    step_index,
                    tool.name,
                    retry_index + 1,
                    self.max_retries,
                    delay,
                    _exception_message(error),
                )
                time.sleep(delay)

        raise RuntimeError("Retry execution did not produce a result")

    def _execute_tool(
        self,
        execution_id: UUID,
        step_index: int,
        tool_call: ToolCallRequest,
        context: ExecutionContext,
    ) -> ToolCallResult:
        try:
            resolved_arguments = context.resolve_references(tool_call.arguments)
        except Exception as error:
            return ToolCallResult(
                success=False,
                error_message=_exception_message(error),
                error_type="unexpected_error",
            )

        try:
            tool = self.registry.get_tool(tool_call.tool_name)
        except KeyError as error:
            return ToolCallResult(
                success=False,
                error_message=_exception_message(error),
                error_type="tool_not_found",
            )

        try:
            arguments = tool.validate_arguments(resolved_arguments)
        except ValidationError as error:
            return ToolCallResult(
                success=False,
                error_message=_exception_message(error),
                error_type="validation_error",
            )

        try:
            return self._execute_with_retries(
                tool,
                arguments,
                execution_id,
                step_index,
            )
        except ToolTimeoutError as error:
            timeout_message = str(error)
            return ToolCallResult(
                success=False,
                error_message=(
                    f"Tool timed out: {timeout_message}"
                    if timeout_message
                    else "Tool timed out"
                ),
                error_type="timeout",
            )
        except Exception as error:
            return ToolCallResult(
                success=False,
                error_message=_exception_message(error),
                error_type="unexpected_error",
            )

    def run(
        self,
        user_request: str,
        tool_calls: list[ToolCallRequest],
    ) -> AgentExecution:
        execution = AgentExecution(user_request=user_request)
        context = ExecutionContext()
        execution.started_at = _utc_now()
        logger.info(
            "execution_started execution_id=%s tool_count=%s",
            execution.execution_id,
            len(tool_calls),
        )

        if len(tool_calls) > self.max_steps:
            execution.status = ExecutionStatus.FAILED
            execution.error_message = (
                f"Maximum execution steps exceeded: max_steps={self.max_steps}, "
                f"submitted_steps={len(tool_calls)}"
            )
            execution.completed_at = _utc_now()
            logger.error(
                "execution_failed execution_id=%s error_type=%s error_message=%s",
                execution.execution_id,
                "max_steps_exceeded",
                execution.error_message,
            )
            return execution

        execution.status = ExecutionStatus.RUNNING

        for step_index, tool_call in enumerate(tool_calls, start=1):
            step = ExecutionStep(
                execution_id=execution.execution_id,
                step_index=step_index,
                tool_call=tool_call,
            )
            execution.steps.append(step)
            step.started_at = _utc_now()
            step.status = StepStatus.RUNNING
            logger.info(
                "step_started execution_id=%s step_index=%s tool_name=%s",
                execution.execution_id,
                step_index,
                tool_call.tool_name,
            )

            result = self._execute_tool(
                execution.execution_id,
                step_index,
                tool_call,
                context,
            )

            step.tool_result = result
            step.completed_at = _utc_now()

            if not result.success:
                if result.error_type is None:
                    result = result.model_copy(update={"error_type": "business_error"})
                    step.tool_result = result
                step.status = StepStatus.FAILED
                execution.status = ExecutionStatus.FAILED
                execution.error_message = result.error_message or "Tool execution failed"
                execution.completed_at = _utc_now()
                logger.error(
                    "step_failed execution_id=%s step_index=%s tool_name=%s "
                    "error_type=%s error_message=%s",
                    execution.execution_id,
                    step_index,
                    tool_call.tool_name,
                    result.error_type,
                    result.error_message,
                )
                logger.error(
                    "execution_failed execution_id=%s error_type=%s error_message=%s",
                    execution.execution_id,
                    result.error_type,
                    execution.error_message,
                )
                return execution

            if result.error_type is not None:
                result = result.model_copy(update={"error_type": None})
                step.tool_result = result
            step.status = StepStatus.SUCCEEDED
            context.save_step_output(step_index, result.output_data)
            logger.info(
                "step_succeeded execution_id=%s step_index=%s tool_name=%s",
                execution.execution_id,
                step_index,
                tool_call.tool_name,
            )

        execution.status = ExecutionStatus.SUCCEEDED
        execution.completed_at = _utc_now()
        logger.info(
            "execution_succeeded execution_id=%s steps=%s",
            execution.execution_id,
            len(execution.steps),
        )
        return execution

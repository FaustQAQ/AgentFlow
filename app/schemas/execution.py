from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ToolCallRequest(BaseModel):
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    success: bool
    output_data: dict[str, Any] | str | None = None
    error_message: str | None = None
    error_type: str | None = None


class ExecutionStep(BaseModel):
    step_id: UUID = Field(default_factory=uuid4)
    execution_id: UUID
    step_index: int = Field(ge=1)
    status: StepStatus = StepStatus.PENDING
    tool_call: ToolCallRequest
    tool_result: ToolCallResult | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentExecution(BaseModel):
    execution_id: UUID = Field(default_factory=uuid4)
    user_request: str = Field(min_length=1)
    dataset_id: int | None = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    steps: list[ExecutionStep] = Field(default_factory=list)
    final_output: str | None = None
    error_message: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None

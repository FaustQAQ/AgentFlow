from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic import Field


class ExecutionStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_id: str
    execution_id: str
    step_index: int
    tool_name: str
    arguments: dict[str, Any]
    status: str
    output_data: dict[str, Any] | str | None = None
    error_type: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExecutionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    execution_id: str
    user_request: str
    dataset_id: int | None = None
    status: str
    final_output: str | None = None
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    steps: list[ExecutionStepResponse] = Field(default_factory=list)


class ExecutionListResponse(BaseModel):
    items: list[ExecutionResponse]
    page: int
    page_size: int
    total: int

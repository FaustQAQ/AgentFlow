from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.history import ExecutionListResponse, ExecutionResponse
from app.services.agent_orchestrator import AgentOrchestrator
from app.services.execution_query import ExecutionNotFoundError, ExecutionQueryService

router = APIRouter(prefix="/api/v1/executions", tags=["executions"])


class ExecutionCreateRequest(BaseModel):
    user_request: str = Field(min_length=1, max_length=10000)


def get_orchestrator() -> AgentOrchestrator:
    from app.main import orchestrator

    return orchestrator


@router.post("", response_model=ExecutionResponse, status_code=status.HTTP_201_CREATED)
def create_execution(
    request: ExecutionCreateRequest,
    db: Session = Depends(get_db),
    agent: AgentOrchestrator = Depends(get_orchestrator),
) -> ExecutionResponse:
    try:
        execution = agent.run(request.user_request)
        return ExecutionQueryService().get_execution(db, str(execution.execution_id))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error) or type(error).__name__,
        ) from error


@router.get("", response_model=ExecutionListResponse)
def list_executions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    execution_status: str | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
) -> ExecutionListResponse:
    return ExecutionQueryService().list_executions(
        db, page=page, page_size=page_size, status=execution_status
    )


@router.get("/{execution_id}", response_model=ExecutionResponse)
def get_execution(
    execution_id: str,
    db: Session = Depends(get_db),
) -> ExecutionResponse:
    try:
        return ExecutionQueryService().get_execution(db, execution_id)
    except ExecutionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/{execution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_execution(execution_id: str, db: Session = Depends(get_db)) -> None:
    try:
        ExecutionQueryService().delete_execution(db, execution_id)
    except ExecutionNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

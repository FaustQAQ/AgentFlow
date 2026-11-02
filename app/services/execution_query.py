from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.execution import AgentExecutionModel
from app.schemas.history import ExecutionListResponse, ExecutionResponse


class ExecutionNotFoundError(LookupError):
    """Raised when an execution id does not exist."""


class ExecutionQueryService:
    """Read execution history without exposing SQLAlchemy model instances."""

    def get_execution(self, db: Session, execution_id: str) -> ExecutionResponse:
        statement = (
            select(AgentExecutionModel)
            .options(selectinload(AgentExecutionModel.steps))
            .where(AgentExecutionModel.execution_id == execution_id)
        )
        execution = db.scalar(statement)
        if execution is None:
            raise ExecutionNotFoundError(f"Execution not found: {execution_id}")
        return ExecutionResponse.model_validate(execution)

    def list_executions(
        self,
        db: Session,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> ExecutionListResponse:
        if page < 1 or page_size < 1 or page_size > 100:
            raise ValueError("page must be >= 1 and page_size must be between 1 and 100")

        base = select(AgentExecutionModel)
        count = select(func.count()).select_from(AgentExecutionModel)
        if status is not None:
            base = base.where(AgentExecutionModel.status == status)
            count = count.where(AgentExecutionModel.status == status)

        total = db.scalar(count) or 0
        executions = db.scalars(
            base.options(selectinload(AgentExecutionModel.steps))
            .order_by(AgentExecutionModel.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return ExecutionListResponse(
            items=[ExecutionResponse.model_validate(item) for item in executions],
            page=page,
            page_size=page_size,
            total=total,
        )

    def delete_execution(self, db: Session, execution_id: str) -> None:
        execution = db.scalar(
            select(AgentExecutionModel).where(
                AgentExecutionModel.execution_id == execution_id
            )
        )
        if execution is None:
            raise ExecutionNotFoundError(f"Execution not found: {execution_id}")
        try:
            db.delete(execution)
            db.commit()
        except Exception:
            db.rollback()
            raise

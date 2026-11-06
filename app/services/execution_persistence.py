from sqlalchemy.orm import Session

from app.models.execution import AgentExecutionModel, ExecutionStepModel
from app.schemas.execution import AgentExecution


class ExecutionPersistenceService:
    """Persist a complete AgentExecution in one database transaction."""

    def save_execution(self, db: Session, execution: AgentExecution) -> str:
        execution_id = str(execution.execution_id)
        execution_model = AgentExecutionModel(
            execution_id=execution_id,
            user_request=execution.user_request,
            dataset_id=execution.dataset_id,
            status=execution.status.value,
            final_output=execution.final_output,
            error_message=execution.error_message,
            created_at=execution.created_at,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
        )

        step_models = [
            ExecutionStepModel(
                step_id=str(step.step_id),
                execution_id=execution_id,
                step_index=step.step_index,
                tool_name=step.tool_call.tool_name,
                arguments=step.tool_call.model_dump(mode="json")["arguments"],
                status=step.status.value,
                output_data=(
                    step.tool_result.model_dump(mode="json")["output_data"]
                    if step.tool_result is not None
                    else None
                ),
                error_type=(
                    step.tool_result.error_type
                    if step.tool_result is not None
                    else None
                ),
                error_message=(
                    step.tool_result.error_message
                    if step.tool_result is not None
                    else None
                ),
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            for step in execution.steps
        ]

        try:
            db.add(execution_model)
            db.add_all(step_models)
            db.commit()
        except Exception:
            db.rollback()
            raise

        return execution_id

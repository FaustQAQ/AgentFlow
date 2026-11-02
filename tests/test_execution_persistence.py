from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.execution import AgentExecutionModel, ExecutionStepModel
from app.schemas.execution import (
    AgentExecution,
    ExecutionStatus,
    ExecutionStep,
    StepStatus,
    ToolCallRequest,
    ToolCallResult,
)
from app.services.execution_persistence import ExecutionPersistenceService


@pytest.fixture
def persistence_session(tmp_path: Path):
    database_path = tmp_path / "test_execution_persistence.db"
    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine)

    with session_local() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def _execution(
    *,
    status: ExecutionStatus = ExecutionStatus.SUCCEEDED,
    steps: list[ExecutionStep] | None = None,
) -> AgentExecution:
    timestamp = datetime.now(timezone.utc)
    return AgentExecution(
        user_request="Analyze sales",
        status=status,
        steps=steps or [],
        final_output="# Sales report",
        error_message=None,
        created_at=timestamp,
        started_at=timestamp,
        completed_at=timestamp,
    )


def _step(
    execution_id,
    *,
    step_index: int,
    result: ToolCallResult | None = None,
) -> ExecutionStep:
    timestamp = datetime.now(timezone.utc)
    return ExecutionStep(
        execution_id=execution_id,
        step_index=step_index,
        status=StepStatus.SUCCEEDED if result is not None else StepStatus.PENDING,
        tool_call=ToolCallRequest(
            tool_name="sales_data_query",
            arguments={"start_date": "2024-01-01", "limit": 1},
        ),
        tool_result=result,
        started_at=timestamp,
        completed_at=timestamp,
    )


def test_can_save_execution_without_steps(persistence_session: Session) -> None:
    execution = _execution()
    service = ExecutionPersistenceService()

    saved_id = service.save_execution(persistence_session, execution)
    saved = persistence_session.scalar(
        select(AgentExecutionModel).where(
            AgentExecutionModel.execution_id == saved_id
        )
    )

    assert saved is not None
    assert saved.execution_id == str(execution.execution_id)
    assert saved.status == "succeeded"
    assert saved.steps == []


def test_can_save_execution_with_multiple_steps(
    persistence_session: Session,
) -> None:
    execution = _execution()
    execution.steps = [
        _step(
            execution.execution_id,
            step_index=1,
            result=ToolCallResult(
                success=True,
                output_data={"current_sales": 33000.0},
            ),
        ),
        _step(
            execution.execution_id,
            step_index=2,
            result=ToolCallResult(success=True, output_data={"growth_rate": 10.5}),
        ),
    ]

    ExecutionPersistenceService().save_execution(persistence_session, execution)
    saved_steps = persistence_session.scalars(
        select(ExecutionStepModel).order_by(ExecutionStepModel.step_index)
    ).all()

    assert len(saved_steps) == 2
    assert [step.step_index for step in saved_steps] == [1, 2]


def test_execution_id_and_status_are_saved(
    persistence_session: Session,
) -> None:
    execution = _execution(status=ExecutionStatus.FAILED)

    saved_id = ExecutionPersistenceService().save_execution(
        persistence_session,
        execution,
    )
    saved = persistence_session.scalar(
        select(AgentExecutionModel).where(
            AgentExecutionModel.execution_id == saved_id
        )
    )

    assert saved is not None
    assert saved.execution_id == str(execution.execution_id)
    assert saved.status == ExecutionStatus.FAILED.value


def test_tool_name_and_arguments_are_saved(
    persistence_session: Session,
) -> None:
    execution = _execution()
    execution.steps = [_step(execution.execution_id, step_index=1)]

    ExecutionPersistenceService().save_execution(persistence_session, execution)
    saved = persistence_session.scalar(select(ExecutionStepModel))

    assert saved is not None
    assert saved.tool_name == "sales_data_query"
    assert saved.arguments == {"start_date": "2024-01-01", "limit": 1}


def test_tool_output_is_saved(
    persistence_session: Session,
) -> None:
    execution = _execution()
    execution.steps = [
        _step(
            execution.execution_id,
            step_index=1,
            result=ToolCallResult(
                success=True,
                output_data={"current_sales": 33000.0, "items": [1, 2]},
            ),
        )
    ]

    ExecutionPersistenceService().save_execution(persistence_session, execution)
    saved = persistence_session.scalar(select(ExecutionStepModel))

    assert saved is not None
    assert saved.output_data == {"current_sales": 33000.0, "items": [1, 2]}


def test_error_type_and_error_message_are_saved(
    persistence_session: Session,
) -> None:
    execution = _execution(status=ExecutionStatus.FAILED)
    execution.error_message = "Tool failed"
    execution.steps = [
        _step(
            execution.execution_id,
            step_index=1,
            result=ToolCallResult(
                success=False,
                error_type="unexpected_error",
                error_message="RuntimeError: Tool failed",
            ),
        )
    ]

    ExecutionPersistenceService().save_execution(persistence_session, execution)
    saved = persistence_session.scalar(select(ExecutionStepModel))

    assert saved is not None
    assert saved.error_type == "unexpected_error"
    assert saved.error_message == "RuntimeError: Tool failed"


def test_time_fields_are_saved(
    persistence_session: Session,
) -> None:
    execution = _execution()
    execution.steps = [_step(execution.execution_id, step_index=1)]

    ExecutionPersistenceService().save_execution(persistence_session, execution)
    saved_execution = persistence_session.scalar(select(AgentExecutionModel))
    saved_step = persistence_session.scalar(select(ExecutionStepModel))

    assert saved_execution is not None
    assert saved_step is not None
    assert saved_execution.created_at is not None
    assert saved_execution.started_at is not None
    assert saved_execution.completed_at is not None
    assert saved_step.started_at is not None
    assert saved_step.completed_at is not None


def test_tool_result_none_is_saved_as_null(
    persistence_session: Session,
) -> None:
    execution = _execution()
    execution.steps = [_step(execution.execution_id, step_index=1)]

    ExecutionPersistenceService().save_execution(persistence_session, execution)
    saved = persistence_session.scalar(select(ExecutionStepModel))

    assert saved is not None
    assert saved.output_data is None
    assert saved.error_type is None
    assert saved.error_message is None


def test_save_failure_rolls_back_and_does_not_leave_partial_records(
    persistence_session: Session,
) -> None:
    execution_id = uuid4()
    execution = _execution()
    execution.execution_id = execution_id
    execution.steps = [
        _step(execution_id, step_index=1),
        _step(execution_id, step_index=1),
    ]

    with pytest.raises(IntegrityError):
        ExecutionPersistenceService().save_execution(persistence_session, execution)

    assert persistence_session.scalar(
        select(AgentExecutionModel).where(
            AgentExecutionModel.execution_id == str(execution_id)
        )
    ) is None
    assert persistence_session.scalars(select(ExecutionStepModel)).all() == []


def test_multiple_executions_are_saved_separately(
    persistence_session: Session,
) -> None:
    service = ExecutionPersistenceService()
    first = _execution()
    second = _execution()

    first_id = service.save_execution(persistence_session, first)
    second_id = service.save_execution(persistence_session, second)

    saved = persistence_session.scalars(select(AgentExecutionModel)).all()
    assert {record.execution_id for record in saved} == {first_id, second_id}

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.execution import AgentExecutionModel, ExecutionStepModel


@pytest.fixture
def model_session(tmp_path: Path):
    database_path = tmp_path / "test_execution_models.db"
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


def _execution(execution_id: str | None = None) -> AgentExecutionModel:
    return AgentExecutionModel(
        execution_id=execution_id or str(uuid4()),
        user_request="Analyze sales",
        status="pending",
        created_at=datetime.now(timezone.utc),
    )


def _step(
    execution_id: str,
    step_index: int = 1,
    step_id: str | None = None,
) -> ExecutionStepModel:
    return ExecutionStepModel(
        step_id=step_id or str(uuid4()),
        execution_id=execution_id,
        step_index=step_index,
        tool_name="sales_data_query",
        arguments={"start_date": "2024-01-01"},
        status="succeeded",
        output_data={"current_sales": 33000.0},
    )


def test_can_create_execution_record(model_session: Session) -> None:
    execution = _execution()
    model_session.add(execution)
    model_session.commit()

    saved = model_session.get(AgentExecutionModel, execution.id)

    assert saved is not None
    assert saved.execution_id == execution.execution_id
    assert saved.status == "pending"


def test_can_create_step_record(model_session: Session) -> None:
    execution = _execution()
    step = _step(execution.execution_id)
    model_session.add_all([execution, step])
    model_session.commit()

    saved = model_session.get(ExecutionStepModel, step.id)

    assert saved is not None
    assert saved.tool_name == "sales_data_query"


def test_one_execution_can_have_multiple_steps(model_session: Session) -> None:
    execution = _execution()
    first = _step(execution.execution_id, step_index=1)
    second = _step(execution.execution_id, step_index=2)
    model_session.add_all([execution, first, second])
    model_session.commit()
    model_session.refresh(execution)

    assert len(execution.steps) == 2
    assert {step.step_index for step in execution.steps} == {1, 2}


def test_execution_id_must_be_unique(model_session: Session) -> None:
    execution_id = str(uuid4())
    model_session.add_all([_execution(execution_id), _execution(execution_id)])

    with pytest.raises(IntegrityError):
        model_session.commit()


def test_step_id_must_be_unique(model_session: Session) -> None:
    execution = _execution()
    step_id = str(uuid4())
    model_session.add_all(
        [
            execution,
            _step(execution.execution_id, step_index=1, step_id=step_id),
            _step(execution.execution_id, step_index=2, step_id=step_id),
        ]
    )

    with pytest.raises(IntegrityError):
        model_session.commit()


def test_step_index_must_be_unique_within_execution(
    model_session: Session,
) -> None:
    execution = _execution()
    model_session.add_all(
        [
            execution,
            _step(execution.execution_id, step_index=1),
            _step(execution.execution_id, step_index=1),
        ]
    )

    with pytest.raises(IntegrityError):
        model_session.commit()


def test_foreign_key_relationship_is_correct(model_session: Session) -> None:
    execution = _execution()
    step = _step(execution.execution_id)
    model_session.add_all([execution, step])
    model_session.commit()
    model_session.refresh(step)

    assert step.execution is execution
    assert step.execution.execution_id == execution.execution_id


def test_deleting_execution_cascades_to_steps(model_session: Session) -> None:
    execution = _execution()
    step = _step(execution.execution_id)
    model_session.add_all([execution, step])
    model_session.commit()
    step_id = step.id

    model_session.delete(execution)
    model_session.commit()

    assert model_session.get(ExecutionStepModel, step_id) is None


def test_json_arguments_and_output_are_saved_and_loaded(
    model_session: Session,
) -> None:
    execution = _execution()
    step = _step(execution.execution_id)
    step.arguments = {"filters": ["north", "online"], "limit": 10}
    step.output_data = {"current_sales": 33000.0, "metadata": {"source": "mock"}}
    model_session.add_all([execution, step])
    model_session.commit()
    model_session.expire_all()

    saved = model_session.get(ExecutionStepModel, step.id)

    assert saved is not None
    assert saved.arguments == {"filters": ["north", "online"], "limit": 10}
    assert saved.output_data == {
        "current_sales": 33000.0,
        "metadata": {"source": "mock"},
    }


def test_time_fields_are_saved_and_loaded(model_session: Session) -> None:
    timestamp = datetime.now(timezone.utc)
    execution = _execution()
    execution.started_at = timestamp
    execution.completed_at = timestamp
    step = _step(execution.execution_id)
    step.started_at = timestamp
    step.completed_at = timestamp
    model_session.add_all([execution, step])
    model_session.commit()
    model_session.expire_all()

    saved_execution = model_session.get(AgentExecutionModel, execution.id)
    saved_step = model_session.get(ExecutionStepModel, step.id)

    assert saved_execution is not None
    assert saved_step is not None
    assert saved_execution.started_at is not None
    assert saved_execution.completed_at is not None
    assert saved_step.started_at is not None
    assert saved_step.completed_at is not None


def test_different_executions_can_reuse_step_index(
    model_session: Session,
) -> None:
    first_execution = _execution()
    second_execution = _execution()
    first_step = _step(first_execution.execution_id, step_index=1)
    second_step = _step(second_execution.execution_id, step_index=1)
    model_session.add_all(
        [first_execution, second_execution, first_step, second_step]
    )
    model_session.commit()

    steps = model_session.scalars(
        select(ExecutionStepModel).where(ExecutionStepModel.step_index == 1)
    ).all()

    assert len(steps) == 2

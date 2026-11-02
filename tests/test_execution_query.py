from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models.execution import AgentExecutionModel, ExecutionStepModel
from app.services.execution_query import ExecutionNotFoundError, ExecutionQueryService


@pytest.fixture
def query_session(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'query.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection: object, _: object) -> None:
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()

    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def _record(status: str = "succeeded", days_ago: int = 0) -> AgentExecutionModel:
    execution_id = str(uuid4())
    created = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return AgentExecutionModel(
        execution_id=execution_id,
        user_request=f"request {execution_id}",
        status=status,
        created_at=created,
    )


def test_get_execution_returns_response_with_steps(query_session: Session) -> None:
    record = _record()
    record.steps.append(
        ExecutionStepModel(
            step_id=str(uuid4()),
            execution_id=record.execution_id,
            step_index=1,
            tool_name="demo",
            arguments={"x": 1},
            status="succeeded",
        )
    )
    query_session.add(record)
    query_session.commit()

    result = ExecutionQueryService().get_execution(query_session, record.execution_id)

    assert result.execution_id == record.execution_id
    assert len(result.steps) == 1
    assert result.steps[0].arguments == {"x": 1}


def test_get_missing_execution_raises(query_session: Session) -> None:
    with pytest.raises(ExecutionNotFoundError):
        ExecutionQueryService().get_execution(query_session, str(uuid4()))


def test_list_supports_pagination_and_status(query_session: Session) -> None:
    records = [_record("succeeded", 2), _record("failed", 1), _record("succeeded")]
    query_session.add_all(records)
    query_session.commit()

    result = ExecutionQueryService().list_executions(
        query_session, page=1, page_size=1, status="succeeded"
    )

    assert result.total == 2
    assert len(result.items) == 1
    assert result.items[0].status == "succeeded"


def test_delete_execution_cascades_steps(query_session: Session) -> None:
    record = _record()
    step = ExecutionStepModel(
        step_id=str(uuid4()),
        execution_id=record.execution_id,
        step_index=1,
        tool_name="demo",
        arguments={},
        status="succeeded",
    )
    record.steps.append(step)
    query_session.add(record)
    query_session.commit()
    step_id = step.id

    ExecutionQueryService().delete_execution(query_session, record.execution_id)

    assert query_session.get(AgentExecutionModel, record.id) is None
    assert query_session.get(ExecutionStepModel, step_id) is None

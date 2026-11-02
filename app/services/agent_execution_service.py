import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.schemas.execution import AgentExecution, ToolCallRequest
from app.services.agent_executor import AgentExecutor
from app.services.exceptions import ExecutionPersistenceError
from app.services.execution_persistence import ExecutionPersistenceService

logger = logging.getLogger(__name__)


class AgentExecutionService:
    """Coordinate execution and short-lived persistence sessions."""

    def __init__(
        self,
        executor: AgentExecutor,
        persistence: ExecutionPersistenceService | None = None,
        session_factory: Callable[[], Session] = SessionLocal,
    ) -> None:
        self.executor = executor
        self.persistence = persistence or ExecutionPersistenceService()
        self.session_factory = session_factory

    def run(
        self,
        user_request: str,
        tool_calls: list[ToolCallRequest],
    ) -> AgentExecution:
        execution = self.executor.run(user_request, tool_calls)
        logger.info("persisting_execution execution_id=%s", execution.execution_id)

        db = self.session_factory()
        try:
            self.persistence.save_execution(db, execution)
        except Exception as error:
            raise ExecutionPersistenceError(
                str(execution.execution_id), execution, error
            ) from error
        finally:
            db.close()

        return execution

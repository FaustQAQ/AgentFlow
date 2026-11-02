class ToolTimeoutError(TimeoutError):
    """Raised when a tool's external operation times out."""


class ToolRetryableError(Exception):
    """Raised for explicitly retryable tool failures."""


class ExecutionPersistenceError(Exception):
    """Raised when an execution cannot be persisted."""

    def __init__(self, execution_id: str, execution: object, cause: Exception) -> None:
        self.execution_id = execution_id
        self.execution = execution
        self.cause = cause
        super().__init__(f"Failed to persist execution {execution_id}: {cause}")

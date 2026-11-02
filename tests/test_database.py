from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import DEFAULT_DATABASE_PATH, DEFAULT_DATABASE_URL, settings
from app.db import database


class TrackingSession(Session):
    close_called = False

    def close(self) -> None:
        self.close_called = True
        super().close()


@pytest.fixture
def temporary_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Path, None, None]:
    database_path = tmp_path / "test_agentflow.db"
    temporary_engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    temporary_session_local = sessionmaker(
        bind=temporary_engine,
        autoflush=False,
        autocommit=False,
    )
    monkeypatch.setattr(database, "engine", temporary_engine)
    monkeypatch.setattr(database, "SessionLocal", temporary_session_local)

    yield database_path

    temporary_engine.dispose()


def test_engine_can_be_created(temporary_database: Path) -> None:
    assert isinstance(database.engine, Engine)


def test_sqlite_database_connection_succeeds(temporary_database: Path) -> None:
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_session_local_creates_session(temporary_database: Path) -> None:
    session = database.SessionLocal()

    try:
        assert isinstance(session, Session)
    finally:
        session.close()


def test_session_can_execute_simple_sql(temporary_database: Path) -> None:
    with database.SessionLocal() as session:
        assert session.execute(text("SELECT 1")).scalar_one() == 1


def test_get_db_provides_session(temporary_database: Path) -> None:
    db_generator = database.get_db()
    session = next(db_generator)

    try:
        assert isinstance(session, Session)
    finally:
        with pytest.raises(StopIteration):
            next(db_generator)


def test_get_db_closes_session_after_use(
    temporary_database: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracking_session_local = sessionmaker(
        bind=database.engine,
        class_=TrackingSession,
        autoflush=False,
        autocommit=False,
    )
    monkeypatch.setattr(database, "SessionLocal", tracking_session_local)

    db_generator = database.get_db()
    session = next(db_generator)

    with pytest.raises(StopIteration):
        next(db_generator)

    assert isinstance(session, TrackingSession)
    assert session.close_called is True


def test_database_path_configuration_is_correct() -> None:
    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.database_url == "sqlite:///D:/Codex/AgentFlow/data/agentflow/.db"
    assert DEFAULT_DATABASE_PATH == Path(
        "D:/Codex/AgentFlow/data/agentflow/.db"
    )


def test_tests_use_temporary_database_not_development_database(
    temporary_database: Path,
) -> None:
    with database.engine.connect():
        pass

    assert temporary_database != DEFAULT_DATABASE_PATH
    assert temporary_database.exists()
    assert database.engine.url.database == temporary_database.as_posix()

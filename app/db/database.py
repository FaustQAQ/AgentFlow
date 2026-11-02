from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _ensure_sqlite_directory(database_url: str) -> None:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        return
    if url.database == ":memory:":
        return
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)

connect_args = (
    # FastAPI's synchronous request handling may use worker threads; this
    # allows a SQLite connection to be used across those request threads.
    {"check_same_thread": False}
    if make_url(settings.database_url).get_backend_name() == "sqlite"
    else {}
)

engine = create_engine(settings.database_url, connect_args=connect_args)


if make_url(settings.database_url).get_backend_name() == "sqlite":

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

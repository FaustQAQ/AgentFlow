from collections.abc import Callable, Generator
import asyncio
import sys
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base
from app.models import execution as _execution_models
from app.models import sales as _sales_models
from app.models.sales import SalesDatasetModel, SalesRecordModel
from app.tools import sales_data
from app.main import app

if sys.platform == "win32":
    # Starlette TestClient otherwise selects ProactorEventLoop, whose socketpair
    # setup is blocked by the managed test environment.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
def sales_test_session_factory(
    tmp_path: Path,
) -> Generator[Callable[[], Session], None, None]:
    """Isolated business fixture; never touches the development SQLite database."""
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'sales_fixture.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = factory()
    dataset = SalesDatasetModel(
        name="测试销售数据（非生产）",
        original_filename="fixture.csv",
        file_type="csv",
        total_rows=10,
        successful_rows=10,
        failed_rows=0,
    )
    db.add(dataset)
    db.flush()
    amounts = {
        date(2023, 1, 1): Decimal("9000"), date(2023, 1, 2): Decimal("10000"),
        date(2023, 1, 3): Decimal("10500"), date(2023, 1, 4): Decimal("9800"),
        date(2023, 1, 5): Decimal("0"), date(2024, 1, 1): Decimal("10000"),
        date(2024, 1, 2): Decimal("12000"), date(2024, 1, 3): Decimal("11000"),
        date(2024, 1, 4): Decimal("12500"), date(2024, 1, 5): Decimal("0"),
    }
    db.add_all(
        [
            SalesRecordModel(
                dataset_id=dataset.id,
                order_id=f"fixture-{index}",
                order_date=record_date,
                product_name="测试产品 A" if index % 2 else "测试产品 B",
                category="测试类别",
                quantity=1,
                unit_price=amount,
                total_amount=amount,
                region="华东" if index % 2 else "华南",
            )
            for index, (record_date, amount) in enumerate(amounts.items(), start=1)
        ]
    )
    db.commit()
    db.close()
    yield factory
    engine.dispose()


@pytest.fixture(autouse=True)
def isolate_sales_tool_database(monkeypatch: pytest.MonkeyPatch, sales_test_session_factory) -> None:
    """Keep every legacy sales-tool test on the fixture database, not production SQLite."""
    monkeypatch.setattr(sales_data, "SessionLocal", sales_test_session_factory)


@pytest.fixture(autouse=True)
def disable_production_lifespan_for_http_unit_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid running production migration hooks in Starlette's in-process client."""
    @asynccontextmanager
    async def noop_lifespan(_app):
        yield

    monkeypatch.setattr(app.router, "lifespan_context", noop_lifespan)

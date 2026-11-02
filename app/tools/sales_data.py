from datetime import date

from pydantic import BaseModel, model_validator

from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool


class SalesDataQueryArguments(BaseModel):
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "SalesDataQueryArguments":
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be earlier than start_date")
        return self


_SALES_DATA: dict[date, float] = {
    date(2023, 1, 1): 9000.0,
    date(2023, 1, 2): 10000.0,
    date(2023, 1, 3): 10500.0,
    date(2023, 1, 4): 9800.0,
    date(2023, 1, 5): 0.0,
    date(2024, 1, 1): 10000.0,
    date(2024, 1, 2): 12000.0,
    date(2024, 1, 3): 11000.0,
    date(2024, 1, 4): 12500.0,
    date(2024, 1, 5): 0.0,
}


def _previous_year_date(value: date) -> date:
    try:
        return value.replace(year=value.year - 1)
    except ValueError:
        return value.replace(year=value.year - 1, day=28)


class SalesDataQueryTool(BaseTool):
    name = "sales_data_query"
    description = "Query fixed simulated sales data for a date range and its prior-year period."
    args_schema = SalesDataQueryArguments

    def execute(self, arguments: SalesDataQueryArguments) -> ToolCallResult:
        current_records = [
            amount
            for record_date, amount in _SALES_DATA.items()
            if arguments.start_date <= record_date <= arguments.end_date
        ]
        if not current_records:
            return ToolCallResult(
                success=False,
                error_message=(
                    "No simulated sales data available for current date range "
                    f"{arguments.start_date.isoformat()} to {arguments.end_date.isoformat()}."
                ),
            )

        current_sales = sum(current_records)
        previous_start = _previous_year_date(arguments.start_date)
        previous_end = _previous_year_date(arguments.end_date)
        previous_records = [
            amount
            for record_date, amount in _SALES_DATA.items()
            if previous_start <= record_date <= previous_end
        ]
        if not previous_records:
            return ToolCallResult(
                success=False,
                error_message=(
                    "No simulated sales data available for previous-year date range "
                    f"{previous_start.isoformat()} to {previous_end.isoformat()}."
                ),
            )

        previous_sales = sum(previous_records)

        return ToolCallResult(
            success=True,
            output_data={
                "current_sales": current_sales,
                "previous_sales": previous_sales,
                "start_date": arguments.start_date.isoformat(),
                "end_date": arguments.end_date.isoformat(),
                "previous_start_date": previous_start.isoformat(),
                "previous_end_date": previous_end.isoformat(),
            },
        )

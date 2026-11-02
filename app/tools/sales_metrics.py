from pydantic import BaseModel, Field

from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool


class SalesMetricsArguments(BaseModel):
    current_sales: float = Field(ge=0)
    previous_sales: float = Field(ge=0)


class SalesMetricsCalculatorTool(BaseTool):
    name = "sales_metrics_calculator"
    description = "Calculate year-over-year sales growth from current and previous sales."
    args_schema = SalesMetricsArguments

    def execute(self, arguments: SalesMetricsArguments) -> ToolCallResult:
        if arguments.previous_sales == 0:
            return ToolCallResult(
                success=False,
                error_message="Cannot calculate year-over-year growth rate when previous_sales is zero.",
            )

        growth_rate = round(
            (arguments.current_sales - arguments.previous_sales)
            / arguments.previous_sales
            * 100,
            2,
        )
        return ToolCallResult(
            success=True,
            output_data={
                "current_sales": arguments.current_sales,
                "previous_sales": arguments.previous_sales,
                "growth_rate": growth_rate,
            },
        )

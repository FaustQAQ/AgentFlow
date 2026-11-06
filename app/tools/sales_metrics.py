from pydantic import BaseModel, Field
from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool

class SalesMetricsArguments(BaseModel):
    current_sales: float = Field(ge=0)
    previous_sales: float | None = Field(default=None, ge=0)
    previous_period_sales: float | None = Field(default=None, ge=0)
    metric: str = "yoy"

class SalesMetricsCalculatorTool(BaseTool):
    name = "sales_metrics_calculator"
    description = "用 Python 确定性计算销售总额、同比或环比增长率。上期缺失时明确返回不可计算。"
    args_schema = SalesMetricsArguments
    def execute(self, arguments: SalesMetricsArguments) -> ToolCallResult:
        previous = arguments.previous_period_sales if arguments.metric == "mom" else arguments.previous_sales
        if previous is None: return ToolCallResult(success=False, error_message="上期数据缺失，无法计算增长率")
        if previous == 0: return ToolCallResult(success=False, error_message="上期销售额为零，无法计算增长率")
        rate = round((arguments.current_sales - previous) / previous * 100, 2)
        return ToolCallResult(success=True, output_data={"current_sales": arguments.current_sales, "previous_sales": previous, "growth_rate": rate, "metric": arguments.metric})

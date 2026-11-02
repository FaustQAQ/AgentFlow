from pydantic import BaseModel, Field

from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool


class MarkdownReportArguments(BaseModel):
    title: str = Field(min_length=1)
    current_sales: float = Field(ge=0)
    previous_sales: float = Field(ge=0)
    growth_rate: float


class MarkdownReportGeneratorTool(BaseTool):
    name = "markdown_report_generator"
    description = "Generate a Markdown sales analysis report from calculated metrics."
    args_schema = MarkdownReportArguments

    def execute(self, arguments: MarkdownReportArguments) -> ToolCallResult:
        if arguments.growth_rate > 0:
            conclusion = f"销售额同比增长 {arguments.growth_rate:.2f}%，表现良好。"
        elif arguments.growth_rate < 0:
            conclusion = f"销售额同比下降 {abs(arguments.growth_rate):.2f}%，需要关注销售表现。"
        else:
            conclusion = "销售额同比持平，增长率为 0.00%。"

        report = (
            f"# {arguments.title}\n\n"
            "## 销售概览\n\n"
            f"- 本期销售额：{arguments.current_sales:,.2f}\n"
            f"- 上期销售额：{arguments.previous_sales:,.2f}\n"
            f"- 同比增长率：{arguments.growth_rate:.2f}%\n\n"
            "## 分析结论\n\n"
            f"{conclusion}\n"
        )
        return ToolCallResult(success=True, output_data=report)

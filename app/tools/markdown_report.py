from typing import Any
from pydantic import BaseModel, Field
from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool

class MarkdownReportArguments(BaseModel):
    title: str = Field(min_length=1)
    current_sales: float = Field(ge=0)
    previous_sales: float | None = Field(default=None, ge=0)
    growth_rate: float | None = None
    dataset_name: str = "用户导入数据集"
    start_date: str = ""
    end_date: str = ""
    record_count: int = 0
    products: list[dict[str, Any]] = Field(default_factory=list)
    regions: list[dict[str, Any]] = Field(default_factory=list)

class MarkdownReportGeneratorTool(BaseTool):
    name = "markdown_report_generator"
    description = "基于工具真实输出生成带数据来源、范围、记录数和排名的 Markdown 报告。"
    args_schema = MarkdownReportArguments
    def execute(self, arguments: MarkdownReportArguments) -> ToolCallResult:
        growth = "不可计算（上期数据不足）" if arguments.growth_rate is None else f"{arguments.growth_rate:.2f}%"
        conclusion = "数据不足，未生成虚假的同比结论。" if arguments.growth_rate is None else (f"销售额同比增长 {arguments.growth_rate:.2f}%。" if arguments.growth_rate > 0 else f"销售额同比下降 {abs(arguments.growth_rate):.2f}%。" if arguments.growth_rate < 0 else "销售额同比持平。")
        products = "\n".join(f"{i}. {x.get('product_name', '')}：{float(x.get('sales', 0)):,.2f}" for i, x in enumerate(arguments.products, 1)) or "暂无"
        regions = "\n".join(f"{i}. {x.get('region', '')}：{float(x.get('sales', 0)):,.2f}" for i, x in enumerate(arguments.regions, 1)) or "暂无"
        previous = "不可用" if arguments.previous_sales is None else f"{arguments.previous_sales:,.2f}"
        report = f"# {arguments.title}\n\n## 数据来源\n- 数据集：{arguments.dataset_name}\n- 分析范围：{arguments.start_date} 至 {arguments.end_date}\n- 实际参与记录数：{arguments.record_count}\n\n## 销售概览\n- 销售总额：{arguments.current_sales:,.2f}\n- 上期销售额：{previous}\n- 同比增长率：{growth}\n\n## 产品销售排名\n{products}\n\n## 地区销售排名\n{regions}\n\n## 分析结论\n{conclusion}\n"
        return ToolCallResult(success=True, output_data=report)

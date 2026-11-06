from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool
from app.tools.markdown_report import MarkdownReportArguments, MarkdownReportGeneratorTool
from app.tools.sales_data import SalesDataQueryArguments, SalesDataQueryTool
from app.tools.sales_metrics import SalesMetricsArguments, SalesMetricsCalculatorTool


def test_sales_data_query_returns_current_and_previous_sales() -> None:
    tool = SalesDataQueryTool()
    arguments = tool.validate_arguments(
        {"dataset_id": 1, "start_date": "2024-01-01", "end_date": "2024-01-03"}
    )

    result = tool.execute(arguments)

    assert result.success is True
    assert result.output_data["current_sales"] == 33000.0
    assert result.output_data["previous_sales"] == 29500.0


def test_sales_data_query_rejects_invalid_date_range() -> None:
    with pytest.raises(ValidationError, match="end_date cannot be earlier"):
        SalesDataQueryTool().validate_arguments(
            {"dataset_id": 1, "start_date": "2024-01-03", "end_date": "2024-01-01"}
        )


def test_sales_data_query_is_deterministic() -> None:
    tool = SalesDataQueryTool()
    raw_arguments = {"dataset_id": 1, "start_date": date(2024, 1, 1), "end_date": date(2024, 1, 3)}

    first = tool.execute(tool.validate_arguments(raw_arguments))
    second = tool.execute(tool.validate_arguments(raw_arguments))

    assert first == second


def test_sales_data_query_fails_when_current_range_has_no_records() -> None:
    result = SalesDataQueryTool().execute(
        SalesDataQueryArguments(dataset_id=1, start_date=date(2025, 1, 1), end_date=date(2025, 1, 3))
    )

    assert result.success is False
    assert result.error_message is not None
    assert "没有销售记录" in result.error_message


def test_sales_data_query_fails_when_previous_range_has_no_records() -> None:
    result = SalesDataQueryTool().execute(
        SalesDataQueryArguments(dataset_id=1, start_date=date(2023, 1, 1), end_date=date(2023, 1, 4))
    )

    assert result.success is True
    assert result.output_data["previous_sales"] is None
    assert result.output_data["previous_record_count"] == 0


def test_sales_data_query_preserves_real_zero_sales_records() -> None:
    result = SalesDataQueryTool().execute(
        SalesDataQueryArguments(dataset_id=1, start_date=date(2024, 1, 5), end_date=date(2024, 1, 5))
    )

    assert result.success is True
    assert result.output_data["current_sales"] == 0.0
    assert result.output_data["previous_sales"] == 0.0


def test_sales_metrics_calculates_positive_growth() -> None:
    tool = SalesMetricsCalculatorTool()

    result = tool.execute(tool.validate_arguments({"current_sales": 120.0, "previous_sales": 100.0}))

    assert result.success is True
    assert result.output_data["growth_rate"] == 20.0


def test_sales_metrics_calculates_negative_growth() -> None:
    tool = SalesMetricsCalculatorTool()

    result = tool.execute(tool.validate_arguments({"current_sales": 80.0, "previous_sales": 100.0}))

    assert result.output_data["growth_rate"] == -20.0


def test_sales_metrics_calculates_zero_growth() -> None:
    tool = SalesMetricsCalculatorTool()

    result = tool.execute(tool.validate_arguments({"current_sales": 100.0, "previous_sales": 100.0}))

    assert result.output_data["growth_rate"] == 0.0


def test_sales_metrics_returns_failure_when_previous_sales_is_zero() -> None:
    result = SalesMetricsCalculatorTool().execute(
        SalesMetricsArguments(current_sales=100.0, previous_sales=0.0)
    )

    assert result.success is False
    assert result.error_message is not None
    assert "上期销售额为零" in result.error_message


def test_sales_metrics_rejects_negative_sales() -> None:
    with pytest.raises(ValidationError):
        SalesMetricsCalculatorTool().validate_arguments(
            {"current_sales": -1.0, "previous_sales": 100.0}
        )


def test_markdown_report_contains_title_sales_and_growth_rate() -> None:
    tool = MarkdownReportGeneratorTool()
    arguments = tool.validate_arguments(
        {
            "title": "January Sales Analysis",
            "current_sales": 120.0,
            "previous_sales": 100.0,
            "growth_rate": 20.0,
        }
    )

    result = tool.execute(arguments)

    assert result.success is True
    assert isinstance(result.output_data, str)
    assert "# January Sales Analysis" in result.output_data
    assert "120.00" in result.output_data
    assert "100.00" in result.output_data
    assert "20.00%" in result.output_data


def test_markdown_report_expresses_negative_growth() -> None:
    result = MarkdownReportGeneratorTool().execute(
        MarkdownReportArguments(
            title="Negative Growth",
            current_sales=80.0,
            previous_sales=100.0,
            growth_rate=-20.0,
        )
    )

    assert "同比下降 20.00%" in result.output_data


def test_markdown_report_expresses_zero_growth() -> None:
    result = MarkdownReportGeneratorTool().execute(
        MarkdownReportArguments(
            title="Flat Growth",
            current_sales=100.0,
            previous_sales=100.0,
            growth_rate=0.0,
        )
    )

    assert "同比持平" in result.output_data


@pytest.mark.parametrize(
    ("tool", "raw_arguments"),
    [
        (
            SalesDataQueryTool(),
                {"dataset_id": 1, "start_date": "2024-01-01", "end_date": "2024-01-01"},
        ),
        (SalesMetricsCalculatorTool(), {"current_sales": 10.0, "previous_sales": 5.0}),
        (
            MarkdownReportGeneratorTool(),
            {
                "title": "Test",
                "current_sales": 10.0,
                "previous_sales": 5.0,
                "growth_rate": 100.0,
            },
        ),
    ],
)
def test_all_business_tools_use_base_tool_interface_and_return_result(
    tool: BaseTool, raw_arguments: dict[str, object]
) -> None:
    assert isinstance(tool, BaseTool)
    arguments = tool.validate_arguments(raw_arguments)
    result = tool.execute(arguments)

    assert isinstance(result, ToolCallResult)


def test_business_tool_names_are_expected() -> None:
    assert SalesDataQueryTool().name == "sales_data_query"
    assert SalesMetricsCalculatorTool().name == "sales_metrics_calculator"
    assert MarkdownReportGeneratorTool().name == "markdown_report_generator"

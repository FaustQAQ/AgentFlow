from datetime import date
from collections.abc import Callable
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field, model_validator
from app.db.database import SessionLocal
from app.models.sales import SalesRecordModel
from app.schemas.execution import ToolCallResult
from app.tools.base import BaseTool

class SalesDataQueryArguments(BaseModel):
    dataset_id: int = Field(gt=0)
    start_date: date
    end_date: date
    product_name: str | None = None
    category: str | None = None
    region: str | None = None
    @model_validator(mode="after")
    def validate_date_range(self):
        if self.end_date < self.start_date: raise ValueError("end_date cannot be earlier than start_date")
        return self

def _prior_year(value: date) -> date:
    try: return value.replace(year=value.year - 1)
    except ValueError: return value.replace(year=value.year - 1, day=28)

class SalesDataQueryTool(BaseTool):
    name = "sales_data_query"
    description = "从用户指定的数据集查询真实销售记录、同比区间、产品和地区汇总。必须提供 dataset_id。"
    args_schema = SalesDataQueryArguments
    def __init__(self, session_factory: Callable[[], Session] | None = None) -> None:
        self.session_factory = session_factory or SessionLocal

    def execute(self, arguments: SalesDataQueryArguments) -> ToolCallResult:
        db = self.session_factory()
        try:
            filters = [SalesRecordModel.dataset_id == arguments.dataset_id, SalesRecordModel.order_date.between(arguments.start_date, arguments.end_date)]
            for column, value in ((SalesRecordModel.product_name, arguments.product_name), (SalesRecordModel.category, arguments.category), (SalesRecordModel.region, arguments.region)):
                if value: filters.append(column == value)
            rows = db.scalars(select(SalesRecordModel).where(*filters)).all()
            if not rows: return ToolCallResult(success=False, error_message="指定数据集在当前时间范围内没有销售记录")
            prev_filters = [SalesRecordModel.dataset_id == arguments.dataset_id, SalesRecordModel.order_date.between(_prior_year(arguments.start_date), _prior_year(arguments.end_date))]
            previous = db.scalars(select(SalesRecordModel).where(*prev_filters)).all()
            product, region = {}, {}
            for row in rows:
                product[row.product_name] = product.get(row.product_name, 0) + float(row.total_amount)
                region[row.region] = region.get(row.region, 0) + float(row.total_amount)
            return ToolCallResult(success=True, output_data={"dataset_id": arguments.dataset_id, "current_sales": round(sum(float(r.total_amount) for r in rows), 2), "previous_sales": round(sum(float(r.total_amount) for r in previous), 2) if previous else None, "record_count": len(rows), "previous_record_count": len(previous), "start_date": arguments.start_date.isoformat(), "end_date": arguments.end_date.isoformat(), "previous_start_date": _prior_year(arguments.start_date).isoformat(), "previous_end_date": _prior_year(arguments.end_date).isoformat(), "products": sorted(({"product_name": k, "sales": round(v, 2)} for k, v in product.items()), key=lambda x: x["sales"], reverse=True), "regions": sorted(({"region": k, "sales": round(v, 2)} for k, v in region.items()), key=lambda x: x["sales"], reverse=True)})
        finally: db.close()

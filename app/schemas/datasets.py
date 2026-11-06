from datetime import date, datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class DatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; name: str; original_filename: str; file_type: str
    total_rows: int; successful_rows: int; failed_rows: int
    created_at: datetime; updated_at: datetime

class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]; total: int

class UploadPreviewResponse(BaseModel):
    preview_id: str; filename: str; headers: list[str]; mapping: dict[str, str]
    total_rows: int; successful_rows: int; failed_rows: int
    preview_rows: list[dict[str, Any]]; errors: list[dict[str, Any]]

class DatasetRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int; dataset_id: int; order_id: str; order_date: date; product_name: str
    category: str; quantity: int; unit_price: Decimal; total_amount: Decimal; region: str
    created_at: datetime

class DatasetDetailResponse(DatasetResponse):
    records: list[DatasetRecordResponse] = Field(default_factory=list)

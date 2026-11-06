import csv
import io
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.sales import SalesDatasetModel, SalesRecordModel

REQUIRED_FIELDS = ("order_id", "order_date", "product_name", "category", "quantity", "unit_price", "total_amount", "region")
FIELD_ALIASES = {
    "order_id": {"order_id", "订单编号", "订单号", "订单ID", "orderid"},
    "order_date": {"order_date", "销售日期", "订单日期", "日期", "date"},
    "product_name": {"product_name", "产品名称", "商品名称", "产品", "product"},
    "category": {"category", "产品类别", "类别", "品类"},
    "quantity": {"quantity", "销售数量", "数量", "qty"},
    "unit_price": {"unit_price", "单价", "价格", "price"},
    "total_amount": {"total_amount", "销售金额", "总金额", "金额", "sales"},
    "region": {"region", "销售地区", "地区", "区域"},
}


def _normal(value: Any) -> str:
    return str(value).strip().lower().replace(" ", "") if value is not None else ""


def detect_mapping(headers: list[str]) -> dict[str, str]:
    normalized = {_normal(h): h for h in headers}
    return {field: normalized[alias] for field, aliases in FIELD_ALIASES.items() for alias in aliases if _normal(alias) in normalized}


def _parse_date(value: Any) -> date:
    if isinstance(value, datetime): return value.date()
    if isinstance(value, date): return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y年%m月%d日", "%m/%d/%Y"):
        try: return datetime.strptime(text, fmt).date()
        except ValueError: pass
    raise ValueError("日期格式无效")


def _decimal(value: Any, label: str) -> Decimal:
    try:
        result = Decimal(str(value).replace(",", "").replace("￥", "").replace("$", "").strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{label}格式无效")
    if not result.is_finite() or result < 0: raise ValueError(f"{label}必须为非负金额")
    return result.quantize(Decimal("0.01"))


def _int(value: Any) -> int:
    try: result = int(str(value).replace(",", "").strip())
    except ValueError: raise ValueError("销售数量格式无效")
    if result <= 0: raise ValueError("销售数量必须大于0")
    return result


def parse_bytes(filename: str, content: bytes, mapping: dict[str, str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".csv":
        try: text = content.decode("utf-8-sig")
        except UnicodeDecodeError: text = content.decode("gb18030")
        reader = csv.DictReader(io.StringIO(text))
        headers = [h or "" for h in (reader.fieldnames or [])]
        rows = list(reader)
    elif suffix == ".xlsx":
        try:
            from openpyxl import load_workbook
        except ImportError as exc: raise ValueError("XLSX解析依赖未安装，请安装 openpyxl") from exc
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        ws = wb.active
        values = list(ws.values)
        headers = [str(v or "") for v in (values[0] if values else [])]
        rows = [dict(zip(headers, values_row)) for values_row in values[1:]]
    else:
        raise ValueError("仅支持 .csv 和 .xlsx 文件")
    actual_mapping = mapping or detect_mapping(headers)
    missing = [field for field in REQUIRED_FIELDS if field not in actual_mapping]
    if missing: raise ValueError(f"缺少必需字段: {', '.join(missing)}")
    if not rows: raise ValueError("文件没有数据行")
    valid, errors, seen = [], [], set()
    for index, row in enumerate(rows, start=2):
        try:
            item = {field: row.get(actual_mapping[field]) for field in REQUIRED_FIELDS}
            if any(item[field] in (None, "") for field in REQUIRED_FIELDS): raise ValueError("存在空值")
            if any(isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")) for value in item.values()): raise ValueError("检测到可能的公式注入内容")
            order_id = str(item["order_id"]).strip()
            if order_id in seen: raise ValueError("订单编号重复")
            seen.add(order_id)
            item.update(order_id=order_id, order_date=_parse_date(item["order_date"]), quantity=_int(item["quantity"]), unit_price=_decimal(item["unit_price"], "单价"), total_amount=_decimal(item["total_amount"], "销售金额"))
            for field in ("product_name", "category", "region"): item[field] = str(item[field]).strip()
            valid.append(item)
        except (ValueError, TypeError) as exc:
            errors.append({"row": index, "message": str(exc), "data": {k: str(v) for k, v in row.items()}})
    return valid, errors, actual_mapping


def create_dataset(db: Session, name: str, filename: str, rows: list[dict[str, Any]], errors: list[dict[str, Any]]) -> SalesDatasetModel:
    dataset = SalesDatasetModel(name=name, original_filename=filename, file_type=Path(filename).suffix.lower().lstrip("."), total_rows=len(rows)+len(errors), successful_rows=len(rows), failed_rows=len(errors))
    db.add(dataset); db.flush()
    db.add_all([SalesRecordModel(dataset_id=dataset.id, **row) for row in rows])
    db.commit(); db.refresh(dataset)
    return dataset

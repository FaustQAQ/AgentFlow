import uuid
import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models.sales import SalesDatasetModel, SalesRecordModel
from app.schemas.datasets import DatasetDetailResponse, DatasetListResponse, DatasetRecordResponse, DatasetResponse, UploadPreviewResponse
from app.services.sales_import import create_dataset, parse_bytes

router = APIRouter(prefix="/api/v1/datasets", tags=["datasets"])
_previews: dict[str, dict] = {}
MAX_FILE_SIZE = 10 * 1024 * 1024

@router.post("/upload", response_model=UploadPreviewResponse)
async def upload_dataset(file: UploadFile = File(...), name: str | None = Form(None), mapping: str | None = Form(None)):
    filename = file.filename or ""
    if not filename or filename.split(".")[-1].lower() not in {"csv", "xlsx"}:
        raise HTTPException(400, "仅支持 .csv 和 .xlsx 文件")
    content = await file.read()
    if not content: raise HTTPException(400, "文件为空")
    if len(content) > MAX_FILE_SIZE: raise HTTPException(413, "文件超过 10MB 限制")
    try: rows, errors, mapping = parse_bytes(filename, content, json.loads(mapping) if mapping else None)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc
    preview_id = uuid.uuid4().hex
    _previews[preview_id] = {"filename": filename, "name": name or filename.rsplit(".", 1)[0], "rows": rows, "errors": errors}
    return UploadPreviewResponse(preview_id=preview_id, filename=filename, headers=list(mapping.values()), mapping=mapping, total_rows=len(rows)+len(errors), successful_rows=len(rows), failed_rows=len(errors), preview_rows=[{k: (v.isoformat() if hasattr(v, "isoformat") else str(v)) for k, v in r.items()} for r in rows[:20]], errors=errors[:100])

@router.post("/{dataset_id}/import", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
def import_dataset(dataset_id: str, preview_id: str = Form(...), db: Session = Depends(get_db)):
    preview = _previews.pop(preview_id, None)
    if not preview: raise HTTPException(404, "导入预览不存在或已过期")
    try: return create_dataset(db, preview["name"], preview["filename"], preview["rows"], preview["errors"])
    except Exception as exc:
        db.rollback(); raise HTTPException(500, "数据集导入失败，事务已回滚") from exc

@router.get("", response_model=DatasetListResponse)
def list_datasets(db: Session = Depends(get_db)):
    items = db.scalars(select(SalesDatasetModel).order_by(SalesDatasetModel.created_at.desc())).all()
    return {"items": items, "total": len(items)}

@router.get("/{dataset_id}", response_model=DatasetDetailResponse)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    item = db.scalar(select(SalesDatasetModel).where(SalesDatasetModel.id == dataset_id))
    if not item: raise HTTPException(404, "数据集不存在")
    return item

@router.get("/{dataset_id}/records", response_model=list[DatasetRecordResponse])
def list_records(dataset_id: int, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    if not db.scalar(select(SalesDatasetModel.id).where(SalesDatasetModel.id == dataset_id)): raise HTTPException(404, "数据集不存在")
    return db.scalars(select(SalesRecordModel).where(SalesRecordModel.dataset_id == dataset_id).order_by(SalesRecordModel.order_date, SalesRecordModel.id).offset((page-1)*page_size).limit(page_size)).all()

@router.delete("/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    item = db.get(SalesDatasetModel, dataset_id)
    if not item: raise HTTPException(404, "数据集不存在")
    db.delete(item); db.commit()

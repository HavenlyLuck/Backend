# app/routers/inventory.py — 관리자 재고 관리 (품목 · 입고 기록)
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.inventory import (
    InventoryItemResponse, InventoryItemDetailResponse, InventoryReceiptResponse, InventoryReceiptUpdate,
)
from app.services.cloudinary import upload_image
from app.crud import inventory as inventory_crud

router = APIRouter()


@router.get("/items", response_model=list[InventoryItemResponse])
def list_items(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return inventory_crud.get_items(db)


@router.get("/items/{item_id}", response_model=InventoryItemDetailResponse)
def get_item(item_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    item = inventory_crud.get_item_detail(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="재고 품목을 찾을 수 없습니다")
    return item


# 상품에 연결된 재고 품목 (상점 수량 조정 화면에서 남은 재고를 보여주려고) — 연결이 없으면 null
@router.get("/products/{product_type}/{product_id}", response_model=Optional[InventoryItemResponse])
def get_item_for_product(
    product_type: Literal["raffle", "store", "kuji_prize", "kuji_last_one"],
    product_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    return inventory_crud.get_item_for_product(db, product_type, product_id)


# 입고 등록 — item_id가 있으면 그 품목에 추가 입고, 없으면 name(·image)으로 새 품목을 만든다
@router.post("/receipts", response_model=InventoryItemDetailResponse)
def create_receipt(
    quantity: int = Form(...),
    unit_cost: int = Form(...),
    received_at: date = Form(...),
    item_id: Optional[int] = Form(None),
    name: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    supplier: Optional[str] = Form(None),
    memo: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="수량은 1개 이상이어야 합니다")
    if unit_cost < 0:
        raise HTTPException(status_code=400, detail="단가는 0 이상이어야 합니다")
    name = (name or "").strip()
    if item_id is None and not name:
        raise HTTPException(status_code=400, detail="품목 이름을 입력해주세요")

    image_url = upload_image(image, folder="inventory_items") if item_id is None and image else None
    try:
        item_id = inventory_crud.create_receipt(
            db,
            item_id=item_id,
            name=name[:200] or None,
            image_url=image_url,
            quantity=quantity,
            unit_cost=unit_cost,
            received_at=received_at,
            supplier=(supplier or "").strip()[:100] or None,
            memo=(memo or "").strip()[:255] or None,
        )
    except inventory_crud.InventoryError as e:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return inventory_crud.get_item_detail(db, item_id)


@router.patch("/receipts/{receipt_id}", response_model=InventoryReceiptResponse)
def update_receipt(
    receipt_id: int,
    payload: InventoryReceiptUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    changes = payload.model_dump(exclude_unset=True)
    if "quantity" in changes and (changes["quantity"] is None or changes["quantity"] <= 0):
        raise HTTPException(status_code=400, detail="수량은 1개 이상이어야 합니다")
    if "unit_cost" in changes and (changes["unit_cost"] is None or changes["unit_cost"] < 0):
        raise HTTPException(status_code=400, detail="단가는 0 이상이어야 합니다")
    if "received_at" in changes and changes["received_at"] is None:
        raise HTTPException(status_code=400, detail="매입일을 입력해주세요")
    for key in ("supplier", "memo"):
        if key in changes:
            changes[key] = (changes[key] or "").strip() or None
    try:
        receipt = inventory_crud.update_receipt(db, receipt_id, changes)
    except inventory_crud.InventoryError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    if not receipt:
        raise HTTPException(status_code=404, detail="입고 기록을 찾을 수 없습니다")
    return receipt


@router.delete("/receipts/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    try:
        found = inventory_crud.delete_receipt(db, receipt_id)
    except inventory_crud.InventoryError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    if not found:
        raise HTTPException(status_code=404, detail="입고 기록을 찾을 수 없습니다")

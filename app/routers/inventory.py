# app/routers/inventory.py — 관리자 재고 관리 (품목 · 입고 기록)
from datetime import date
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Form, File, UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_admin
from app.models.user import User
from app.schemas.inventory import (
    InventoryItemResponse, InventoryItemDetailResponse, InventoryItemUpdate, InventoryReceiptResponse, InventoryReceiptUpdate,
)
from app.services.cloudinary import upload_image
from app.crud import inventory as inventory_crud

router = APIRouter()


# 예전 화면은 면세를 메모 앞 "[면세]"로 보냈다 — 떼어서 tax_free로 옮긴다. 반환: (메모, 면세 표시가 있었는지)
TAX_FREE_TAG = "[면세]"


def split_tax_free(memo: Optional[str]) -> tuple[Optional[str], bool]:
    memo = (memo or "").strip()
    if memo.startswith(TAX_FREE_TAG):
        return memo[len(TAX_FREE_TAG):].strip()[:255] or None, True
    return memo[:255] or None, False


def _clean_description(text: Optional[str]) -> Optional[str]:
    text = (text or "").strip()
    return text[:5000] or None


@router.get("/items", response_model=list[InventoryItemResponse])
def list_items(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    return inventory_crud.get_items(db)


@router.get("/items/{item_id}", response_model=InventoryItemDetailResponse)
def get_item(item_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    item = inventory_crud.get_item_detail(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="재고 품목을 찾을 수 없습니다")
    return item


# 상품 등록 — 입고 기록 없이 이름 · 사진 · 설명(상품정보제공고시)만 등록해 두고, 상품 게시에서 골라 쓴다
@router.post("/items", response_model=InventoryItemDetailResponse, status_code=201)
def create_item(
    name: str = Form(...),
    image: Optional[UploadFile] = File(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="상품명을 입력해주세요")
    image_url = upload_image(image, folder="inventory_items") if image else None
    item_id = inventory_crud.create_item(db, name=name[:200], image_url=image_url, description=_clean_description(description))
    return inventory_crud.get_item_detail(db, item_id)


# 이름 · 설명(상품 설명 · 상품정보제공고시) 고치기 — 이미 게시한 상품에는 영향 없고, 다음에 이 품목으로 게시할 때 복사된다
@router.patch("/items/{item_id}", response_model=InventoryItemDetailResponse)
def update_item(
    item_id: int,
    payload: InventoryItemUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    sent = payload.model_dump(exclude_unset=True)
    changes: dict = {}
    if "name" in sent:
        name = (sent["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="상품명을 입력해주세요")
        changes["name"] = name[:200]
    if "description" in sent:
        changes["description"] = _clean_description(sent["description"])
    if not inventory_crud.update_item(db, item_id, changes):
        raise HTTPException(status_code=404, detail="재고 품목을 찾을 수 없습니다")
    return inventory_crud.get_item_detail(db, item_id)


# 상품 등록에서 지우기 — 목록에서만 숨긴다 (이미 게시한 응모 · 쿠지 · 상점 상품은 그대로)
@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)):
    if not inventory_crud.delete_item(db, item_id):
        raise HTTPException(status_code=404, detail="재고 품목을 찾을 수 없습니다")


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
    description: Optional[str] = Form(None),
    tax_free: bool = Form(False),
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
    memo, tagged = split_tax_free(memo)
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
            memo=memo,
            description=_clean_description(description) if item_id is None else None,
            tax_free=tax_free or tagged,
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
    if "supplier" in changes:
        changes["supplier"] = (changes["supplier"] or "").strip()[:100] or None
    if "memo" in changes:
        changes["memo"], tagged = split_tax_free(changes["memo"])
        if tagged:
            changes["tax_free"] = True
    if "tax_free" in changes and changes["tax_free"] is None:
        del changes["tax_free"]
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

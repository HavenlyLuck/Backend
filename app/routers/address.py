# app/routers/address.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.address import AddressCreate, AddressResponse, AddressSearchResponse
from app.crud import address as address_crud
from app.services import juso

router = APIRouter()

# 내 배송지 목록 (기본 배송지가 맨 앞)
@router.get("/me", response_model=list[AddressResponse])
def get_my_addresses(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return address_crud.get_user_addresses(db, user.user_id)


# 도로명주소 검색 (행정안전부 주소 API 프록시)
@router.get("/search", response_model=AddressSearchResponse)
def search_address(
    keyword: str = Query(..., min_length=2, max_length=80),
    page: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
):
    try:
        return juso.search_address(keyword.strip(), page=page)
    except juso.JusoError as e:
        raise HTTPException(status_code=502, detail=str(e))


# 배송지 등록
@router.post("", response_model=AddressResponse)
def create_address(
    payload: AddressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipient = payload.recipient.strip()
    phone = payload.phone.strip()
    address1 = payload.address1.strip()
    if not recipient or not phone or not address1:
        raise HTTPException(status_code=400, detail="받는 사람, 연락처, 주소는 필수입니다")

    return address_crud.create_address(
        db,
        user_id=user.user_id,
        label=(payload.label or "").strip() or "배송지",
        recipient=recipient,
        phone=phone,
        zip_code=(payload.zip_code or "").strip() or None,
        address1=address1,
        address2=(payload.address2 or "").strip() or None,
        is_default=payload.is_default,
    )

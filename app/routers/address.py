# app/routers/address.py
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.address import AddressCreate, AddressResponse, AddressSearchResponse
from app.crud import address as address_crud
from app.services import juso

router = APIRouter()


# 연락처 — 숫자만 남겨 0으로 시작하는 9~12자리(휴대폰 010-…, 지역번호 02-…, 안심번호 050x-…)만 받는다.
# 택배 송장에 그대로 들어가므로 숫자만 저장한다. 형식이 틀리면 None
def normalize_contact_phone(value: str) -> Optional[str]:
    digits = re.sub(r"\D", "", value)
    return digits if re.fullmatch(r"0\d{8,11}", digits) else None

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
    phone = normalize_contact_phone(phone)
    if phone is None:
        raise HTTPException(status_code=400, detail="연락처를 정확히 입력해 주세요 (예: 010-1234-5678)")

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


# 기본 배송지 지정 — 기존 기본 배송지는 해제된다
@router.patch("/{address_id}/default", response_model=AddressResponse)
def set_default_address(
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    address = address_crud.set_default_address(db, user.user_id, address_id)
    if not address:
        raise HTTPException(status_code=404, detail="배송지를 찾을 수 없습니다")
    return address


# 배송지 삭제
@router.delete("/{address_id}", status_code=204)
def delete_address(
    address_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not address_crud.delete_address(db, user.user_id, address_id):
        raise HTTPException(status_code=404, detail="배송지를 찾을 수 없습니다")

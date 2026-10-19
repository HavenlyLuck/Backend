from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class AddressCreate(BaseModel):
    label: Optional[str] = None
    recipient: str
    phone: str
    zip_code: Optional[str] = None
    address1: str
    address2: Optional[str] = None
    is_default: bool = False


class AddressResponse(BaseModel):
    address_id: int
    label: str
    recipient: str
    phone: str
    zip_code: Optional[str] = None
    address1: str
    address2: Optional[str] = None
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AddressSearchItem(BaseModel):
    zip_code: str
    road_address: str
    jibun_address: str
    building_name: str


class AddressSearchResponse(BaseModel):
    total: int
    page: int
    items: list[AddressSearchItem]

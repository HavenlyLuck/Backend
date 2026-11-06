import logging
import re
from typing import Optional

import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
)

def upload_image(file: UploadFile, folder: str = "raffle_products") -> str:
    result = cloudinary.uploader.upload(file.file, folder=folder)
    return result["secure_url"]

def upload_video(file: UploadFile, folder: str = "raffle_draws") -> str:
    result = cloudinary.uploader.upload(file.file, folder=folder, resource_type="video")
    return result["secure_url"]


# 저장해 둔 이미지 주소에서 Cloudinary public_id를 뽑는다
# 예: https://res.cloudinary.com/<cloud>/image/upload/v1700000000/reviews/abc123.jpg → reviews/abc123
def _public_id(url: str) -> Optional[str]:
    match = re.search(r"/image/upload/(?:v\d+/)?(.+?)(?:\.[A-Za-z0-9]+)?$", url or "")
    return match.group(1) if match else None


def delete_image(url: str) -> None:
    """이미지 파일을 Cloudinary에서 지운다. 실패해도 예외를 내지 않고 로그만 남긴다 (DB 삭제는 이미 끝난 뒤라서)"""
    public_id = _public_id(url)
    if not public_id:
        return
    try:
        result = cloudinary.uploader.destroy(public_id, invalidate=True)   # invalidate: CDN 캐시도 지운다
        if result.get("result") not in ("ok", "not found"):
            logging.warning("cloudinary delete failed: %s %s", public_id, result)
    except Exception:
        logging.exception("cloudinary delete failed: %s", public_id)

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

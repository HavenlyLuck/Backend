from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base

class Review(Base):
    __tablename__ = "reviews"
    review_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    rating     = Column(SmallInteger, nullable=False)          # 별점 1~5
    title      = Column(String(200), nullable=False)
    content    = Column(Text, nullable=False)
    image_url  = Column(String(500), nullable=True)           # 후기 사진 (Cloudinary, 선택)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
    )

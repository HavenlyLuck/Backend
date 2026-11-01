from sqlalchemy import Column, Integer, SmallInteger, String, Text, DateTime, Enum, ForeignKey, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base

class Review(Base):
    __tablename__ = "reviews"
    review_id  = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    rating     = Column(SmallInteger, nullable=False)          # 별점 1~5
    # 받은 상품(보관함 1건)마다 후기 1개. 상품명·종류는 작성 당시 값으로 남겨 둔다 (상품이 지워져도 후기는 그대로 보이게)
    storage_item_id = Column(Integer, ForeignKey("storage_items.storage_item_id"), unique=True, nullable=True)
    product_name    = Column(String(200), nullable=True)
    product_type    = Column(Enum("raffle", "store", "kuji", name="review_product_type"), nullable=True)
    title      = Column(String(200), nullable=False)
    content    = Column(Text, nullable=False)
    image_url  = Column(String(500), nullable=True)           # 후기 사진 (Cloudinary, 선택)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("rating BETWEEN 1 AND 5", name="ck_reviews_rating_range"),
    )

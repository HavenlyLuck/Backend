from sqlalchemy.orm import Session
from typing import Optional

from app.models.store import StoreProduct


def create_store_product(
    db: Session,
    admin_id: int,
    product_name: str,
    description: Optional[str],
    point_type: str,
    price: int,
    stock: int,
    image_url: Optional[str],
) -> StoreProduct:
    product = StoreProduct(
        admin_id=admin_id,
        product_name=product_name,
        description=description,
        point_type=point_type,
        price=price,
        stock=stock,
        image_url=image_url,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


def get_store_products(db: Session, point_type: Optional[str] = None) -> list[StoreProduct]:
    query = db.query(StoreProduct)
    if point_type:
        query = query.filter(StoreProduct.point_type == point_type)
    return query.order_by(StoreProduct.created_at.desc()).all()

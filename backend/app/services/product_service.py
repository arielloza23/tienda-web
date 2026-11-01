from typing import Optional

from sqlalchemy.orm import Session

from app.models.product import Product, ProductVariant
from app.schemas.product import ProductCreate


def get_products(db: Session) -> list[Product]:
    return db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.id.asc()).all()


def get_product_by_id(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True)).first()


def create_product(db: Session, payload: ProductCreate) -> Product:
    existing_product = db.query(Product).filter(Product.slug == payload.slug).first()
    if existing_product is not None:
        raise ValueError("Ya existe un producto con ese slug.")

    product = Product(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        price_cents=payload.price_cents,
        is_active=payload.is_active,
    )

    seen_skus: set[str] = set()
    for variant_data in payload.variants:
        if variant_data.price_adjustment_cents < 0:
            raise ValueError("El ajuste de precio de una variante no puede ser negativo.")
        if variant_data.sku in seen_skus:
            raise ValueError(f"La SKU {variant_data.sku} está duplicada.")
        seen_skus.add(variant_data.sku)

        existing_variant = db.query(ProductVariant).filter(ProductVariant.sku == variant_data.sku).first()
        if existing_variant is not None:
            raise ValueError(f"La SKU {variant_data.sku} ya existe.")

        product.variants.append(
            ProductVariant(
                sku=variant_data.sku,
                size=variant_data.size,
                color=variant_data.color,
                price_adjustment_cents=variant_data.price_adjustment_cents,
            )
        )

    db.add(product)
    db.commit()
    db.refresh(product)
    return product

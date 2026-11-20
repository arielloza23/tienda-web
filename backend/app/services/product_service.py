from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem
from app.models.product import Product, ProductImage, ProductVariant
from app.schemas.product import ProductCreate, ProductUpdate, ProductStockUpdate


class ProductConflict(ValueError):
    pass


def get_admin_products(db: Session) -> list[Product]:
    return db.query(Product).order_by(Product.id.desc()).all()


def get_products(db: Session) -> list[Product]:
    return db.query(Product).filter(Product.is_active.is_(True)).order_by(Product.id.asc()).all()


def get_product_by_id(db: Session, product_id: int) -> Optional[Product]:
    return db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True)).first()


def create_product(db: Session, payload: ProductCreate) -> Product:
    existing_product = db.query(Product).filter(Product.slug == payload.slug).first()
    if existing_product is not None:
        raise ProductConflict("Ya existe un producto con ese identificador.")

    product = Product(
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        price_cents=payload.price_cents,
        is_active=payload.is_active,
        image_url=payload.image_url,
        stock_quantity=payload.stock_quantity,
    )

    _validate_variants(db, payload)
    product.variants = [ProductVariant(**variant.model_dump()) for variant in payload.variants]
    product.images = _validated_images(payload)

    db.add(product)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_unique_conflict(exc):
            raise ProductConflict("El identificador o SKU ya existe. Revisa el producto.") from exc
        raise
    db.refresh(product)
    return product


def _is_unique_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    message = str(exc.orig)
    return constraint in {"ix_products_slug", "ix_product_variants_sku"} or (
        "UNIQUE constraint failed: products.slug" in message
        or "UNIQUE constraint failed: product_variants.sku" in message
    )


def _validate_variants(db: Session, payload: ProductCreate | ProductUpdate) -> None:
    seen_skus: set[str] = set()
    for variant in payload.variants:
        if variant.sku in seen_skus:
            raise ProductConflict(f"La SKU {variant.sku} está duplicada.")
        seen_skus.add(variant.sku)
        existing = db.query(ProductVariant).filter(ProductVariant.sku == variant.sku).first()
        if existing is not None and existing.id != getattr(variant, "id", None):
            raise ProductConflict(
                f"La SKU {variant.sku} ya existe. No se pueden intercambiar ni reutilizar SKU de otras variantes en el mismo guardado."
            )
        if payload.price_cents + variant.price_adjustment_cents > 2147483647:
            raise ValueError("El precio de la variante excede el máximo permitido.")


def _validated_images(payload: ProductCreate | ProductUpdate) -> list[ProductImage]:
    colors = {variant.color.casefold(): variant.color for variant in payload.variants if variant.color}
    seen_images: set[tuple[str, str]] = set()
    images = []
    for position, image in enumerate(payload.images):
        color_key = image.color.casefold()
        if colors and color_key not in colors:
            raise ValueError("El color de cada foto debe pertenecer al producto. No mezcles fotos de otros colores.")
        key = (image.url, color_key)
        if key in seen_images:
            raise ValueError("No repitas una foto para el mismo color.")
        seen_images.add(key)
        images.append(ProductImage(
            url=image.url, alt=image.alt, color=colors.get(color_key, image.color), position=position,
        ))
    return images


def update_product(db: Session, product_id: int, payload: ProductUpdate) -> Product | None:
    # Serializa ediciones del mismo producto en PostgreSQL, incluidos borradores.
    product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
    if product is None:
        return None
    existing = db.query(Product).filter(Product.slug == payload.slug, Product.id != product_id).first()
    if existing is not None:
        raise ProductConflict("Ya existe un producto con ese identificador.")
    current = {variant.id: variant for variant in product.variants}
    retained_ids = {variant.id for variant in payload.variants if variant.id is not None}
    if not retained_ids.issubset(current):
        raise ValueError("Una variante no pertenece a este producto o ya no existe. Recarga el producto.")
    omitted_ids = set(current) - retained_ids
    if omitted_ids and db.query(OrderItem.id).filter(OrderItem.variant_id.in_(omitted_ids)).first() is not None:
        raise ProductConflict("No se puede eliminar una variante usada en pedidos. Consérvala para mantener el historial.")
    if not current and payload.variants and db.query(OrderItem.id).join(Order).filter(
        OrderItem.product_id == product_id, OrderItem.variant_id.is_(None), Order.inventory_deducted.is_(True)
    ).first() is not None:
        raise ProductConflict("No se pueden agregar variantes mientras existan pedidos que descontaron stock sin talla.")
    _validate_variants(db, payload)
    images = _validated_images(payload)

    # Ningún atributo persistente se cambia antes de completar todas las validaciones.
    if current and not payload.variants:
        # El campo base estaba dormido: no representa las unidades de las tallas retiradas.
        product.stock_quantity = 0
    for field, value in payload.model_dump(exclude={"variants", "images", "stock_quantity"}).items():
        setattr(product, field, value)
    variants = []
    for variant in payload.variants:
        values = variant.model_dump(exclude={"id"})
        if variant.id is None:
            instance = ProductVariant(**values)
        else:
            instance = current[variant.id]
            values.pop("stock_quantity", None)
            # Clientes anteriores omiten medidas: conservarlas; null explícito las borra.
            for measure in ("bust_cm", "waist_cm", "hip_cm"):
                if measure not in variant.model_fields_set:
                    values.pop(measure, None)
            for field, value in values.items():
                setattr(instance, field, value)
        variants.append(instance)
    product.variants = variants
    product.images = images
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if _is_unique_conflict(exc):
            raise ProductConflict("El identificador o SKU ya existe. Revisa el producto.") from exc
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if omitted_ids and (
            constraint in {"order_items_variant_id_fkey", "fk_order_items_variant_id_product_variants"}
            or (db.get_bind().dialect.name == "sqlite" and "FOREIGN KEY constraint failed" in str(exc.orig))
        ):
            raise ProductConflict("No se puede eliminar una variante usada en pedidos. Recarga el producto.") from exc
        raise
    db.refresh(product)
    return product


class StockConflict(ProductConflict):
    def __init__(self, message):
        self.detail = {"code": "stock_conflict", "message": message}
        super().__init__(message)


def update_stock(db: Session, product_id: int, payload: ProductStockUpdate) -> Product | None:
    try:
        product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
        if product is None:
            return None
        if payload.variant_id is None:
            if product.variants:
                raise ValueError("Selecciona la talla o variante para ajustar el stock.")
            model, target_id = Product, product_id
        else:
            if not any(v.id == payload.variant_id for v in product.variants):
                raise ValueError("La variante no pertenece a este producto.")
            model, target_id = ProductVariant, payload.variant_id
        result = db.execute(update(model).where(model.id == target_id, model.stock_quantity == payload.expected_quantity)
            .values(stock_quantity=payload.quantity).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise StockConflict("El stock cambió. Recarga el producto antes de ajustar las unidades.")
        db.commit()
        db.expire_all()
        return db.get(Product, product_id)
    except Exception:
        db.rollback()
        raise

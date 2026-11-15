import hashlib
import json
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductVariant
from app.schemas.order import OrderCreate


def get_orders(db: Session) -> list[Order]:
    return db.query(Order).order_by(Order.id.asc()).all()


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()


class IdempotencyConflict(ValueError):
    pass


def _request_hash(payload: OrderCreate) -> str:
    # Hash del contrato validado, independiente de valores actuales del catálogo.
    normalized = payload.model_dump(mode="json")
    for field in ("customer_name", "customer_phone", "delivery_address"):
        normalized[field] = normalized[field].strip()
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _existing_order(db: Session, key: str, request_hash: str) -> Order | None:
    order = db.query(Order).filter(Order.idempotency_key == key).first()
    if order is not None and order.request_hash != request_hash:
        raise IdempotencyConflict("La clave del pedido ya se usó con otros datos.")
    return order


def create_order(db: Session, payload: OrderCreate, idempotency_key: str | None = None) -> Order:
    request_hash = _request_hash(payload) if idempotency_key else None
    if idempotency_key:
        existing = _existing_order(db, idempotency_key, request_hash)
        if existing is not None:
            return existing

    customer_name = payload.customer_name.strip()
    customer_phone = payload.customer_phone.strip()
    delivery_address = payload.delivery_address.strip()
    if len(customer_name) < 2 or not any(character.isalpha() for character in customer_name):
        raise ValueError("Escribe un nombre válido para el pedido.")
    if sum(character.isdigit() for character in customer_phone) < 7:
        raise ValueError("Escribe un teléfono válido para coordinar la entrega.")
    if len(delivery_address) < 8:
        raise ValueError("Escribe una dirección de entrega completa.")

    subtotal = 0
    order_items: list[OrderItem] = []

    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product is None:
            raise ValueError(f"El producto {item.product_id} no existe.")
        if not product.is_active:
            raise ValueError(f"El producto {product.name} no está disponible.")

        variant = None
        if item.variant_id is not None:
            variant = (
                db.query(ProductVariant)
                .filter(
                    ProductVariant.id == item.variant_id,
                    ProductVariant.product_id == product.id,
                )
                .first()
            )
            if variant is None:
                raise ValueError("La talla seleccionada no pertenece a este producto.")
        elif product.variants:
            raise ValueError(f"Selecciona una talla para {product.name}.")

        unit_price_cents = product.price_cents + (variant.price_adjustment_cents if variant else 0)
        line_total = unit_price_cents * item.quantity
        subtotal += line_total
        if unit_price_cents < 0 or subtotal > 2_147_483_647:
            raise ValueError("El importe del pedido excede el máximo permitido.")

        order_items.append(
            OrderItem(
                product_id=product.id,
                variant_id=variant.id if variant else None,
                product_name=product.name,
                variant_label=(
                    " / ".join(value for value in (variant.color, variant.size) if value)
                    if variant
                    else None
                ),
                unit_price_cents=unit_price_cents,
                quantity=item.quantity,
                total_price_cents=line_total,
            )
        )

    order = Order(
        user_id=None,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        customer_name=customer_name,
        customer_phone=customer_phone,
        delivery_address=delivery_address,
        delivery_latitude=payload.delivery_latitude,
        delivery_longitude=payload.delivery_longitude,
        status=OrderStatus.PENDING.value,
        subtotal_cents=subtotal,
        shipping_total_cents=0,
        tax_total_cents=0,
        total_cents=subtotal,
    )

    for item in order_items:
        order.items.append(item)

    db.add(order)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Una restricción única resuelve también dos solicitudes simultáneas.
        if idempotency_key:
            existing = _existing_order(db, idempotency_key, request_hash)
            if existing is not None:
                return existing
        raise
    db.refresh(order)
    return order


def update_order_status(db: Session, order_id: int, new_status: str) -> Order:
    order = get_order_by_id(db, order_id)
    if order is None:
        raise ValueError("El pedido indicado no existe.")

    transitions = {
        OrderStatus.PENDING.value: {OrderStatus.PAID.value, OrderStatus.CANCELLED.value},
        OrderStatus.PAID.value: {OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value},
        OrderStatus.SHIPPED.value: {OrderStatus.DELIVERED.value},
        OrderStatus.DELIVERED.value: set(),
        OrderStatus.CANCELLED.value: set(),
    }
    if new_status not in transitions[order.status]:
        raise ValueError(f"No se puede cambiar el pedido de {order.status} a {new_status}.")

    order.status = new_status
    db.commit()
    db.refresh(order)
    return order

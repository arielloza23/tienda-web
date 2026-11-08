from typing import Optional

from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductVariant
from app.models.user import User
from app.schemas.order import OrderCreate


def get_orders(db: Session) -> list[Order]:
    return db.query(Order).order_by(Order.id.asc()).all()


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()


def create_order(db: Session, payload: OrderCreate) -> Order:
    if payload.user_id is not None:
        user = db.query(User).filter(User.id == payload.user_id).first()
        if user is None:
            raise ValueError("El usuario indicado no existe.")

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
        user_id=payload.user_id,
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
    db.commit()
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

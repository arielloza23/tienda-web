from typing import Optional

from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate


def get_orders(db: Session) -> list[Order]:
    return db.query(Order).order_by(Order.id.asc()).all()


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()


def create_order(db: Session, payload: OrderCreate) -> Order:
    user = db.query(User).filter(User.id == payload.user_id).first()
    if user is None:
        raise ValueError("El usuario indicado no existe.")

    if payload.shipping_total_cents < 0 or payload.tax_total_cents < 0:
        raise ValueError("Los impuestos y envíos no pueden ser negativos.")

    subtotal = 0
    order_items: list[OrderItem] = []

    for item in payload.items:
        product = db.query(Product).filter(Product.id == item.product_id).first()
        if product is None:
            raise ValueError(f"El producto {item.product_id} no existe.")
        if not product.is_active:
            raise ValueError(f"El producto {product.name} no está disponible.")

        line_total = product.price_cents * item.quantity
        subtotal += line_total

        order_items.append(
            OrderItem(
                product_id=product.id,
                product_name=product.name,
                unit_price_cents=product.price_cents,
                quantity=item.quantity,
                total_price_cents=line_total,
            )
        )

    if not order_items:
        raise ValueError("El pedido debe incluir al menos un producto.")

    total = subtotal + payload.shipping_total_cents + payload.tax_total_cents

    order = Order(
        user_id=payload.user_id,
        status=OrderStatus.PENDING.value,
        subtotal_cents=subtotal,
        shipping_total_cents=payload.shipping_total_cents,
        tax_total_cents=payload.tax_total_cents,
        total_cents=total,
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

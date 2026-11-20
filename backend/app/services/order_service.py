import hashlib
import json
from typing import Optional

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.order import Order, OrderItem, OrderStatus
from app.models.product import Product, ProductVariant
from app.schemas.order import OrderCreate


def get_orders(db: Session) -> list[Order]:
    return db.query(Order).order_by(Order.id.asc()).all()


def get_order_by_id(db: Session, order_id: int) -> Optional[Order]:
    return db.query(Order).populate_existing().filter(Order.id == order_id).first()


class PriceChanged(ValueError):
    def __init__(self, items: list[dict], subtotal_cents: int):
        self.detail = {"code": "price_changed", "message": "Los precios cambiaron. Revisa el pedido antes de confirmar.", "items": items, "subtotal_cents": subtotal_cents}


class InventoryConflict(ValueError):
    def __init__(self, code: str, message: str, items: list[dict] | None = None):
        self.detail = {"code": code, "message": message}
        if items is not None:
            self.detail["items"] = items
        super().__init__(message)


def _inventory_lines(items):
    quantities = {}
    for item in items:
        key = (item.product_id, item.variant_id)
        quantities[key] = quantities.get(key, 0) + item.quantity
    return quantities


def _stock_target(db, product, variant_id):
    if product is None:
        return None
    if variant_id is None:
        return None if product.variants else product
    return db.query(ProductVariant).populate_existing().filter(
        ProductVariant.id == variant_id, ProductVariant.product_id == product.id).first()


def _check_available(db, products, quantities):
    missing = []
    for (pid, vid), quantity in quantities.items():
        target = _stock_target(db, products.get(pid), vid)
        available = target.stock_quantity if target is not None else 0
        if available < quantity:
            missing.append({"product_id": pid, "variant_id": vid, "quantity": quantity, "available_quantity": available})
    if missing:
        raise InventoryConflict("insufficient_stock", "No hay suficientes unidades. Revisa las tallas y cantidades.", missing)


class IdempotencyConflict(ValueError):
    pass


def _request_hash(payload: OrderCreate) -> str:
    # Hash del contrato validado, independiente de valores actuales del catálogo.
    normalized = payload.model_dump(mode="json")
    normalized.pop("analytics_session_id", None)
    for item in normalized["items"]:
        if item.get("expected_unit_price_cents") is None:
            item.pop("expected_unit_price_cents", None)
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
    changed_prices = []

    # La edición administrativa bloquea la misma fila padre; orden estable evita deadlocks.
    products = {product.id: product for product in db.query(Product).filter(
        Product.id.in_(sorted({item.product_id for item in payload.items}))
    ).order_by(Product.id).with_for_update().all()}
    if idempotency_key:
        existing = _existing_order(db, idempotency_key, request_hash)
        if existing is not None:
            return existing
    for item in payload.items:
        product = products.get(item.product_id)
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
        if item.expected_unit_price_cents is not None and item.expected_unit_price_cents != unit_price_cents:
            changed_prices.append({"product_id": product.id, "variant_id": variant.id if variant else None, "expected_unit_price_cents": item.expected_unit_price_cents, "current_unit_price_cents": unit_price_cents})
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

    if changed_prices:
        raise PriceChanged(changed_prices, subtotal)

    _check_available(db, products, _inventory_lines(order_items))

    order = Order(
        user_id=None,
        analytics_session_id=str(payload.analytics_session_id) if payload.analytics_session_id else None,
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
    try:
        # Mantener este hook permite sincronizar pruebas de dos administradores.
        order = get_order_by_id(db, order_id)
        if order is None:
            raise ValueError("El pedido indicado no existe.")
        transitions = {
            "pending": {"reserved", "cancelled"},
            "reserved": {"paid", "cancelled"},
            "paid": {"shipped", "cancelled"},
            "shipped": {"delivered"},
            "delivered": set(), "cancelled": set(),
        }
        previous = order.status
        deducted = order.inventory_deducted
        if new_status not in transitions.get(previous, set()):
            raise ValueError(f"No se puede cambiar el pedido de {previous} a {new_status}.")
        reserve = new_status == "reserved"
        restore = new_status == "cancelled" and deducted
        quantities = _inventory_lines(order.items) if reserve or restore else {}
        products = {p.id: p for p in db.query(Product).populate_existing().filter(
            Product.id.in_(sorted({pid for pid, _ in quantities}))).order_by(Product.id).with_for_update().all()} if quantities else {}
        # Compare-and-swap del estado y marcador antes de cualquier ajuste.
        result = db.execute(update(Order).where(Order.id == order_id, Order.status == previous,
            Order.inventory_deducted == deducted).values(status=new_status,
            inventory_deducted=True if reserve else False if restore else deducted)
            .execution_options(synchronize_session=False))
        if result.rowcount != 1:
            raise InventoryConflict("order_conflict", "El estado del pedido cambió. Actualiza la bandeja.")
        if reserve:
            _check_available(db, products, quantities)
        for (pid, vid), quantity in quantities.items():
            target = _stock_target(db, products.get(pid), vid)
            if target is None:
                raise InventoryConflict("stock_conflict", "La estructura del producto cambió. Revisa el pedido.")
            model = Product if vid is None else ProductVariant
            condition = model.stock_quantity >= quantity if reserve else model.stock_quantity <= 2147483647 - quantity
            result = db.execute(update(model).where(model.id == target.id, condition)
                .values(stock_quantity=model.stock_quantity - quantity if reserve else model.stock_quantity + quantity)
                .execution_options(synchronize_session=False))
            if result.rowcount != 1:
                code = "insufficient_stock" if reserve else "stock_conflict"
                raise InventoryConflict(code, "El stock cambió o excede el máximo. Revisa las existencias.")
        db.commit()
        db.refresh(order)
        return order
    except Exception:
        db.rollback()
        raise

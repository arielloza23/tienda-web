from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.order import Order
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate
from app.services import order_service


def product(client, price_cents=1500):
    result = client.post("/api/v1/products", json={
        "name": "Producto prueba", "slug": "producto-prueba", "price_cents": price_cents,
    })
    assert result.status_code == 201
    return result.json()["id"]


def payload(product_id, **changes):
    return {
        "customer_name": "Cliente Prueba", "customer_phone": "0991234567",
        "delivery_address": "Calle Principal 123, Quito",
        "items": [{"product_id": product_id, "quantity": 1}], **changes,
    }


def test_public_order_cannot_claim_another_account(client, anon_client, db_session):
    product_id = product(client)
    victim = db_session.query(User).first()
    response = anon_client.post("/api/v1/orders", json=payload(product_id, user_id=victim.id))
    assert response.status_code == 422
    assert db_session.query(Order).count() == 0
    response = anon_client.post("/api/v1/orders", json=payload(product_id, user_id=None))
    assert response.status_code == 201
    assert response.json()["user_id"] is None


@pytest.mark.parametrize("items", [
    [{"product_id": 1, "quantity": 101}],
    [{"product_id": 1, "quantity": True}],
    [{"product_id": 1, "quantity": 1.5}],
    [{"product_id": 1, "quantity": 1}] * 51,
    [{"product_id": 1, "quantity": 60}, {"product_id": 1, "quantity": 60}],
])
def test_order_rejects_excessive_or_noninteger_quantities(anon_client, items):
    assert anon_client.post("/api/v1/orders", json=payload(1, items=items)).status_code == 422


def test_order_rejects_integer_overflow(client, db_session):
    product_id = product(client, price_cents=2_147_483_647)
    response = client.post("/api/v1/orders", json=payload(product_id, items=[{"product_id": product_id, "quantity": 2}]))
    assert response.status_code == 400
    assert db_session.query(Order).count() == 0


def test_idempotency_replay_keeps_original_price_and_order(client, db_session):
    product_id = product(client)
    headers = {"Idempotency-Key": str(uuid4())}
    body = payload(product_id)
    first = client.post("/api/v1/orders", json=body, headers=headers)
    assert first.status_code == 201
    stored_product = db_session.get(Product, product_id)
    stored_product.price_cents = 9999
    stored_product.is_active = False
    db_session.commit()
    replay = client.post("/api/v1/orders", json=body, headers=headers)
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert db_session.query(Order).count() == 1
    assert "idempotency_key" not in first.json()
    assert "request_hash" not in first.json()


def test_idempotency_conflict_and_malformed_header(client, db_session):
    product_id = product(client)
    headers = {"Idempotency-Key": str(uuid4())}
    assert client.post("/api/v1/orders", json=payload(product_id), headers=headers).status_code == 201
    changed = client.post("/api/v1/orders", json=payload(product_id, delivery_address="Otra dirección 456, Quito"), headers=headers)
    assert changed.status_code == 409
    assert db_session.query(Order).count() == 1
    invalid = client.post("/api/v1/orders", json=payload(product_id), headers={"Idempotency-Key": "bad"})
    assert invalid.status_code == 422


def test_requests_without_header_remain_compatible(client, db_session):
    product_id = product(client)
    for _ in range(2):
        assert client.post("/api/v1/orders", json=payload(product_id)).status_code == 201
    assert db_session.query(Order).count() == 2


def test_concurrent_idempotent_requests_create_one_order(tmp_path, monkeypatch):
    # Base temporal y sesiones/conexiones independientes para probar la restricción única.
    engine = create_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}", connect_args={"timeout": 15})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        entry = Product(name="Producto", slug="race", price_cents=100, is_active=True)
        db.add(entry)
        db.commit()
        product_id = entry.id
    barrier = Barrier(2)
    thread_state = local()
    original = order_service._existing_order

    def synchronized_lookup(db, key, fingerprint):
        found = original(db, key, fingerprint)
        if not getattr(thread_state, "checked", False):
            thread_state.checked = True
            barrier.wait(timeout=10)
        return found

    monkeypatch.setattr(order_service, "_existing_order", synchronized_lookup)
    key = str(uuid4())

    def create():
        with Session(engine) as db:
            return order_service.create_order(db, OrderCreate(**payload(product_id)), key).id

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            ids = list(pool.map(lambda _: create(), range(2)))
        assert ids[0] == ids[1]
        with Session(engine) as db:
            assert len(db.scalars(select(Order)).all()) == 1
    finally:
        engine.dispose()

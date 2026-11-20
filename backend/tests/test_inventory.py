from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductVariant
from app.services import order_service

BASE = '/api/v1/products'


def product(client, variants=True, stock=1, slug='inventory'):
    body = {'name': 'Inventario', 'slug': slug, 'price_cents': 1200, 'stock_quantity': stock}
    if variants:
        body['variants'] = [{'sku': f'{slug}-M', 'size': 'M', 'stock_quantity': stock},
                            {'sku': f'{slug}-L', 'size': 'L', 'stock_quantity': 1}]
    response = client.post(BASE, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def body(p, quantity=1, vid='default'):
    variant_id = p['variants'][0]['id'] if p['variants'] and vid == 'default' else None if vid == 'default' else vid
    return {'customer_name': 'Cliente Prueba', 'customer_phone': '0991234567', 'delivery_address': 'Calle Principal 123',
            'items': [{'product_id': p['id'], 'variant_id': variant_id, 'quantity': quantity}]}


def order(client, p, quantity=1):
    response = client.post('/api/v1/orders', json=body(p, quantity))
    assert response.status_code == 201, response.text
    return response.json()['id']


def status(client, oid, value):
    return client.patch(f'/api/v1/orders/{oid}/status', params={'new_status': value})


def stock(client, p):
    return client.get(f"{BASE}/{p['id']}").json()


@pytest.mark.parametrize('variants', [False, True])
def test_manual_reserve_paid_cancel_exactly_once(client, db_session, variants):
    p = product(client, variants)
    a, b = order(client, p), order(client, p)
    assert stock(client, p)['stock_quantity'] == (2 if variants else 1)
    assert status(client, a, 'paid').status_code == 400
    assert status(client, a, 'reserved').status_code == 200
    assert stock(client, p)['stock_quantity'] == (1 if variants else 0)
    failure = status(client, b, 'reserved')
    assert failure.status_code == 409 and failure.json()['detail']['code'] == 'insufficient_stock'
    assert status(client, a, 'paid').status_code == 200
    assert stock(client, p)['stock_quantity'] == (1 if variants else 0)
    assert status(client, a, 'cancelled').status_code == 200
    assert stock(client, p)['stock_quantity'] == (2 if variants else 1)
    assert status(client, a, 'cancelled').status_code == 400
    assert status(client, b, 'reserved').status_code == 200
    db_session.expire_all()
    assert db_session.get(Order, a).inventory_deducted is False
    assert db_session.get(Order, b).inventory_deducted is True


def test_pending_cancellation_and_legacy_paid_never_restore(client, db_session):
    p = product(client, False)
    oid = order(client, p)
    assert status(client, oid, 'cancelled').status_code == 200
    legacy = Order(status='paid', items=[OrderItem(product_id=p['id'], product_name='Old', unit_price_cents=1200, quantity=9, total_price_cents=10800)])
    db_session.add(legacy); db_session.commit()
    assert status(client, legacy.id, 'cancelled').status_code == 200
    assert stock(client, p)['stock_quantity'] == 1


def test_create_checks_aggregate_stock_without_reserving(client, db_session):
    p = product(client, False)
    payload = body(p)
    payload['items'] *= 2
    result = client.post('/api/v1/orders', json=payload)
    assert result.status_code == 409
    assert result.json()['detail']['items'][0]['quantity'] == 2
    assert db_session.query(Order).count() == 0
    assert stock(client, p)['stock_quantity'] == 1


def test_all_lines_reserve_atomically_and_restore_aggregates(client, db_session):
    p = product(client, stock=3)
    payload = body(p)
    payload['items'] *= 2
    payload['items'].append({'product_id': p['id'], 'variant_id': p['variants'][1]['id'], 'quantity': 1})
    oid = client.post('/api/v1/orders', json=payload).json()['id']
    # A stale pending order loses its second line stock before reservation.
    second = db_session.get(ProductVariant, p['variants'][1]['id']); second.stock_quantity = 0; db_session.commit()
    assert status(client, oid, 'reserved').status_code == 409
    assert stock(client, p)['variants'][0]['stock_quantity'] == 3
    assert db_session.get(Order, oid).status == 'pending'
    second.stock_quantity = 1; db_session.commit()
    assert status(client, oid, 'reserved').status_code == 200
    assert [v['stock_quantity'] for v in stock(client, p)['variants']] == [1, 0]
    assert status(client, oid, 'cancelled').status_code == 200
    assert [v['stock_quantity'] for v in stock(client, p)['variants']] == [3, 1]


def test_stock_patch_compare_swap_and_editor_preserves_units(client):
    p = product(client)
    vid = p['variants'][0]['id']
    path = f"{BASE}/{p['id']}/stock"
    assert client.patch(path, json={'variant_id': vid, 'quantity': 7, 'expected_quantity': 1}).status_code == 200
    stale = client.patch(path, json={'variant_id': vid, 'quantity': 4, 'expected_quantity': 1})
    assert stale.status_code == 409 and stale.json()['detail']['code'] == 'stock_conflict'
    edit = {k: v for k, v in p.items() if k != 'id'}
    edit['name'] = 'Editor anterior'
    saved = client.put(f"{BASE}/{p['id']}", json=edit)
    assert saved.status_code == 200, saved.text
    assert saved.json()['variants'][0]['stock_quantity'] == 7
    assert saved.json()['stock_quantity'] == 8
    assert client.patch(path, json={'quantity': 2, 'expected_quantity': 1}).status_code == 400
    other = product(client, slug='other')
    assert client.patch(path, json={'variant_id': other['variants'][0]['id'], 'quantity': 2, 'expected_quantity': 1}).status_code == 400


@pytest.mark.parametrize('value', [-1, 2147483648, True, '2', 1.5])
def test_stock_strict_validation(client, value):
    p = product(client, False)
    assert client.patch(f"{BASE}/{p['id']}/stock", json={'quantity': value, 'expected_quantity': 1}).status_code == 422
    assert client.post(BASE, json={'name': 'Invalid', 'slug': 'invalid', 'price_cents': 1, 'stock_quantity': value}).status_code == 422


def test_stock_authentication_even_with_bypass(client, monkeypatch, db_session):
    from app.core.config import settings
    from app.models.user import User
    p = product(client, False)
    path = f"{BASE}/{p['id']}/stock"
    patch = {'quantity': 5, 'expected_quantity': 1}
    monkeypatch.setattr(settings, 'auth_enabled', False)
    assert client.patch(path, json=patch, headers={'Authorization': ''}).status_code == 401
    user = db_session.query(User).first(); user.role = 'customer'; db_session.commit()
    assert client.patch(path, json=patch).status_code == 403


def test_reserved_base_prevents_variant_conversion_pending_base_cannot_reserve_phantom(client):
    p = product(client, False)
    pending = order(client, p)
    oid = order(client, p)
    assert status(client, oid, 'reserved').status_code == 200
    edit = {k: v for k, v in p.items() if k != 'id'}
    edit['variants'] = [{'sku': 'NEW-SIZE-M', 'size': 'M'}]
    assert client.put(f"{BASE}/{p['id']}", json=edit).status_code == 409
    assert status(client, oid, 'cancelled').status_code == 200
    assert client.put(f"{BASE}/{p['id']}", json=edit).status_code == 200
    assert status(client, pending, 'reserved').status_code == 409
    assert stock(client, p)['variants'][0]['stock_quantity'] == 1


def test_overflow_restore_rolls_back_status_and_stock(client, db_session):
    p = product(client, False)
    oid = order(client, p)
    assert status(client, oid, 'reserved').status_code == 200
    assert client.patch(f"{BASE}/{p['id']}/stock", json={'quantity': 2147483647, 'expected_quantity': 0}).status_code == 200
    assert status(client, oid, 'cancelled').status_code == 409
    db_session.expire_all()
    assert db_session.get(Order, oid).status == 'reserved'
    assert db_session.get(Order, oid).inventory_deducted is True
    assert stock(client, p)['stock_quantity'] == 2147483647


@pytest.mark.parametrize('operation', ['reserve', 'cancel'])
def test_concurrent_stock_transitions_once(tmp_path, monkeypatch, operation):
    engine = create_engine(f"sqlite:///{(tmp_path / 'race.db').as_posix()}", connect_args={'timeout': 20})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        p = Product(name='Race', slug='race', price_cents=100, stock_quantity=1 if operation == 'reserve' else 0)
        db.add(p); db.flush()
        def entry():
            return Order(status='pending' if operation == 'reserve' else 'reserved', inventory_deducted=operation == 'cancel',
                         items=[OrderItem(product_id=p.id, product_name='Race', unit_price_cents=100, quantity=1, total_price_cents=100)])
        a = entry(); b = entry() if operation == 'reserve' else a
        db.add_all([a,b]); db.commit(); ids = [a.id,b.id]; pid = p.id
    barrier = Barrier(2)
    original = order_service.get_order_by_id
    def read(db, oid):
        value = original(db, oid); barrier.wait(timeout=10); return value
    monkeypatch.setattr(order_service, 'get_order_by_id', read)
    def run(oid):
        with Session(engine) as db:
            try:
                order_service.update_order_status(db, oid, 'reserved' if operation == 'reserve' else 'cancelled')
                return True
            except order_service.InventoryConflict:
                return False
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(run, ids)) == [False, True]
        with Session(engine) as db:
            assert db.get(Product, pid).stock_quantity == (0 if operation == 'reserve' else 1)
    finally:
        engine.dispose()


@pytest.mark.parametrize('table', ['products', 'product_variants'])
def test_database_enforces_stock_bounds(db_session, table):
    p = Product(name='Bounds', slug='bounds', price_cents=1)
    p.variants = [ProductVariant(sku='BOUNDS')]
    db_session.add(p); db_session.commit()
    for invalid in (-1, 2147483648):
        with pytest.raises(IntegrityError):
            db_session.execute(text(f'UPDATE {table} SET stock_quantity=:invalid'), {'invalid': invalid})
            db_session.commit()
        db_session.rollback()

def test_failed_second_inventory_write_rolls_back_everything(client, db_session, monkeypatch):
    from types import SimpleNamespace
    from sqlalchemy.sql.dml import Update
    p = product(client)
    payload = body(p)
    payload['items'].append({'product_id': p['id'], 'variant_id': p['variants'][1]['id'], 'quantity': 1})
    oid = client.post('/api/v1/orders', json=payload).json()['id']
    execute = db_session.execute
    count = 0
    def fail_second(statement, *args, **kwargs):
        nonlocal count
        if isinstance(statement, Update) and statement.table.name == 'product_variants':
            count += 1
            if count == 2:
                return SimpleNamespace(rowcount=0)
        return execute(statement, *args, **kwargs)
    monkeypatch.setattr(db_session, 'execute', fail_second)
    with pytest.raises(order_service.InventoryConflict):
        order_service.update_order_status(db_session, oid, 'reserved')
    assert count == 2
    assert db_session.get(Order, oid).status == 'pending'
    assert db_session.get(Order, oid).inventory_deducted is False
    assert [v.stock_quantity for v in db_session.get(Product, p['id']).variants] == [1, 1]

def test_removing_last_variant_does_not_resurrect_hidden_base_stock(client):
    p = product(client)
    assert client.patch(f"{BASE}/{p['id']}/stock", json={'variant_id': p['variants'][0]['id'], 'quantity': 0, 'expected_quantity': 1}).status_code == 200
    # Una segunda talla también se agota; ninguna tiene pedidos históricos.
    assert client.patch(f"{BASE}/{p['id']}/stock", json={'variant_id': p['variants'][1]['id'], 'quantity': 0, 'expected_quantity': 1}).status_code == 200
    edit = {k: v for k, v in p.items() if k != 'id'}
    edit['variants'] = []
    saved = client.put(f"{BASE}/{p['id']}", json=edit)
    assert saved.status_code == 200, saved.text
    assert saved.json()['variants'] == [] and saved.json()['stock_quantity'] == 0
    assert client.post('/api/v1/orders', json=body(saved.json())).status_code == 409
    adjusted = client.patch(f"{BASE}/{p['id']}/stock", json={'quantity': 1, 'expected_quantity': 0})
    assert adjusted.status_code == 200 and adjusted.json()['stock_quantity'] == 1
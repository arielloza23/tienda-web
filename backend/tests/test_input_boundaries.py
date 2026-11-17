"""Malformed public input must fail validation before reaching database drivers."""
import pytest
from app.models.product import Product

TOO_LARGE = 10**100

@pytest.mark.parametrize('path', [
    f'/api/v1/products/{TOO_LARGE}',
    f'/api/v1/products/{TOO_LARGE}/reviews',
    f'/api/v1/orders/{TOO_LARGE}',
])
def test_oversized_path_ids_are_validation_errors(client, path):
    assert client.get(path).status_code == 422

@pytest.mark.parametrize('field', ['product_id', 'variant_id'])
def test_oversized_checkout_ids_do_not_reach_database(anon_client, field):
    item = {'product_id': 1, 'quantity': 1, field: TOO_LARGE}
    response = anon_client.post('/api/v1/orders', json={
        'customer_name': 'Cliente temporal', 'customer_phone': '0991234567',
        'delivery_address': 'Calle temporal 123', 'items': [item],
    })
    assert response.status_code == 422


def test_oversized_review_offset_is_rejected(anon_client, db_session):
    product = Product(name='Temporal', slug='temporal', price_cents=100)
    db_session.add(product); db_session.commit()
    assert anon_client.get(f'/api/v1/products/{product.id}/reviews', params={'offset': str(TOO_LARGE)}).status_code == 422


def test_oversized_product_edit_ids_are_rejected(client):
    body = {'name': 'Temporal', 'slug': 'temporal', 'price_cents': 100,
            'variants': [{'id': TOO_LARGE, 'sku': 'TEST-M'}], 'images': []}
    assert client.put('/api/v1/products/1', json=body).status_code == 422
    body['variants'] = []
    assert client.put(f'/api/v1/products/{TOO_LARGE}', json=body).status_code == 422


def test_oversized_status_order_id_is_rejected(client):
    assert client.patch(f'/api/v1/orders/{TOO_LARGE}/status', params={'new_status': 'paid'}).status_code == 422
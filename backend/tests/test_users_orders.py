import pytest
from fastapi.testclient import TestClient

from sqlalchemy.orm import Session

from app.models.user import User


def test_create_user_success(client: TestClient, db_session: Session) -> None:
    payload = {
        "email": "juan@example.com",
        "full_name": "Juan Pérez",
        "password": "supersecret123",
    }

    response = client.post("/api/v1/users", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == payload["email"]
    assert body["full_name"] == payload["full_name"]
    assert body["role"] == "customer"
    assert "password_hash" not in body

    user = db_session.query(User).filter(User.email == payload["email"]).one()
    assert user.password_hash.startswith("pbkdf2_sha256$600000$")
    assert user.password_hash != payload["password"]


def test_create_order_success(client: TestClient) -> None:
    product_payload = {
        "name": "Teclado Mecánico",
        "slug": "teclado-mecanico",
        "description": "Teclado con switches azules.",
        "price_cents": 199900,
        "is_active": True,
        "variants": [],
    }
    product_response = client.post("/api/v1/products", json=product_payload)
    assert product_response.status_code == 201

    user_payload = {
        "email": "maria@example.com",
        "full_name": "María López",
        "password": "password123",
    }
    user_response = client.post("/api/v1/users", json=user_payload)
    assert user_response.status_code == 201
    user_id = user_response.json()["id"]
    order_payload = {
        "user_id": user_id,
        "customer_name": "María López",
        "customer_phone": "+593 987 654 321",
        "delivery_address": "Av. Amazonas 123, Quito",
        "items": [{"product_id": product_response.json()["id"], "quantity": 2}],
    }

    invalid_order_response = client.post(
        "/api/v1/orders",
        json={**order_payload, "status": "shipped"},
    )
    assert invalid_order_response.status_code == 422

    order_response = client.post("/api/v1/orders", json=order_payload)
    assert order_response.status_code == 201
    body = order_response.json()
    assert body["user_id"] == user_id
    assert body["customer_name"] == "María López"
    assert body["status"] == "pending"
    assert body["subtotal_cents"] == 399800
    assert body["total_cents"] == 399800
    assert body["items"][0]["quantity"] == 2

    order_id = body["id"]
    invalid_transition = client.patch(
        f"/api/v1/orders/{order_id}/status",
        params={"new_status": "delivered"},
    )
    assert invalid_transition.status_code == 400

    for next_status in ("paid", "shipped", "delivered"):
        response = client.patch(
            f"/api/v1/orders/{order_id}/status",
            params={"new_status": next_status},
        )
        assert response.status_code == 200
        assert response.json()["status"] == next_status

    terminal_transition = client.patch(
        f"/api/v1/orders/{order_id}/status",
        params={"new_status": "cancelled"},
    )
    assert terminal_transition.status_code == 400


def test_create_order_does_not_require_stock(client: TestClient) -> None:
    product_response = client.post(
        "/api/v1/products",
        json={
            "name": "Mouse Gamer",
            "slug": "mouse-gamer",
            "price_cents": 59000,
            "is_active": True,
            "variants": [],
        },
    )
    assert product_response.status_code == 201

    user_response = client.post(
        "/api/v1/users",
        json={
            "email": "ana@example.com",
            "full_name": "Ana García",
            "password": "secret1234",
        },
    )
    assert user_response.status_code == 201

    response = client.post(
        "/api/v1/orders",
        json={
            "user_id": user_response.json()["id"],
            "customer_name": "Ana García",
            "customer_phone": "0991234567",
            "delivery_address": "Calle 10 y Avenida 5, Quito",
            "items": [{"product_id": product_response.json()["id"], "quantity": 20}],
        },
    )
    assert response.status_code == 201
    assert response.json()["items"][0]["quantity"] == 20


def test_guest_checkout_saves_delivery_data_and_variant_price(client: TestClient) -> None:
    product_response = client.post(
        "/api/v1/products",
        json={
            "name": "Top de encaje",
            "slug": "top-encaje-checkout",
            "price_cents": 2990,
            "variants": [
                {
                    "sku": "TOP-NEG-M-CHECKOUT",
                    "size": "M",
                    "color": "Negro",
                    "price_adjustment_cents": 500,
                }
            ],
        },
    )
    assert product_response.status_code == 201
    product = product_response.json()

    response = client.post(
        "/api/v1/orders",
        json={
            "customer_name": "Lucía Pérez",
            "customer_phone": "+593 987 506 872",
            "delivery_address": "Av. Amazonas 123, Quito",
            "items": [
                {
                    "product_id": product["id"],
                    "variant_id": product["variants"][0]["id"],
                    "quantity": 2,
                }
            ],
        },
    )

    assert response.status_code == 201
    order = response.json()
    assert order["user_id"] is None
    assert order["customer_phone"] == "+593 987 506 872"
    assert order["delivery_address"] == "Av. Amazonas 123, Quito"
    assert order["status"] == "pending"
    assert order["subtotal_cents"] == 6980
    assert order["items"][0]["variant_label"] == "Negro / M"
    assert order["items"][0]["unit_price_cents"] == 3490

def _simple_product(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/products",
        json={"name": "Body Encaje", "slug": "body-encaje", "price_cents": 2500},
    )
    assert response.status_code == 201
    return response.json()


def _guest_order(product_id: int, **extra) -> dict:
    return {
        "customer_name": "Lucía Pérez",
        "customer_phone": "0987506872",
        "delivery_address": "Av. Amazonas 123, Quito",
        "items": [{"product_id": product_id, "quantity": 1}],
        **extra,
    }


def test_order_saves_delivery_coordinates(client: TestClient) -> None:
    product = _simple_product(client)
    response = client.post(
        "/api/v1/orders",
        json=_guest_order(product["id"], delivery_latitude=-0.1807, delivery_longitude=-78.4678),
    )
    assert response.status_code == 201
    assert response.json()["delivery_latitude"] == -0.1807
    assert response.json()["delivery_longitude"] == -78.4678


@pytest.mark.parametrize(
    "coordinates",
    [
        {"delivery_latitude": -0.18},
        {"delivery_latitude": 91, "delivery_longitude": 0},
        {"delivery_latitude": 0, "delivery_longitude": -181},
    ],
)
def test_order_rejects_invalid_coordinates(client: TestClient, coordinates: dict) -> None:
    product = _simple_product(client)
    response = client.post("/api/v1/orders", json=_guest_order(product["id"], **coordinates))
    assert response.status_code == 422

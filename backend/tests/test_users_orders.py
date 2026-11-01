import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_user_success(client: TestClient) -> None:
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

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == payload["email"]).one()
        assert user.password_hash.startswith("pbkdf2_sha256$600000$")
        assert user.password_hash != payload["password"]
    finally:
        db.close()


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
        "shipping_total_cents": 1500,
        "tax_total_cents": 0,
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
    assert body["status"] == "pending"
    assert body["subtotal_cents"] == 399800
    assert body["total_cents"] == 401300
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
            "items": [{"product_id": product_response.json()["id"], "quantity": 20}],
        },
    )
    assert response.status_code == 201
    assert response.json()["items"][0]["quantity"] == 20
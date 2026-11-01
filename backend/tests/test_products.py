import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

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


def test_list_products_returns_empty_list(client: TestClient) -> None:
    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert response.json() == []


def test_create_product_success(client: TestClient) -> None:
    payload = {
        "name": "Auriculares Pro",
        "slug": "auriculares-pro",
        "description": "Auriculares inalámbricos con cancelación de ruido.",
        "price_cents": 259900,
        "is_active": True,
        "variants": [
            {
                "sku": "AUR-STD-BLK",
                "size": None,
                "color": "black",
                "price_adjustment_cents": 0,
            }
        ],
    }

    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == payload["name"]
    assert body["price_cents"] == payload["price_cents"]
    assert "stock" not in body
    assert body["variants"][0]["sku"] == payload["variants"][0]["sku"]


def test_create_product_rejects_negative_values(client: TestClient) -> None:
    payload = {
        "name": "Cargador USB",
        "slug": "cargador-usb",
        "price_cents": -100,
        "variants": [],
    }

    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 422
    assert "price_cents" in str(response.json()["detail"][0]["loc"])


def test_list_products_only_returns_available_products(client: TestClient) -> None:
    for product in (
        {"name": "Producto visible", "slug": "producto-visible", "price_cents": 1000},
        {
            "name": "Producto oculto",
            "slug": "producto-oculto",
            "price_cents": 2000,
            "is_active": False,
        },
    ):
        response = client.post("/api/v1/products", json=product)
        assert response.status_code == 201

    response = client.get("/api/v1/products")
    assert response.status_code == 200
    assert [product["slug"] for product in response.json()] == ["producto-visible"]

    inactive_product = client.get("/api/v1/products/2")
    assert inactive_product.status_code == 404

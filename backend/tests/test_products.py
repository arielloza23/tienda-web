from fastapi.testclient import TestClient


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


def test_product_image_url(client: TestClient) -> None:
    payload = {
        "name": "Body Encaje",
        "slug": "body-encaje",
        "price_cents": 2500,
        "image_url": "https://images.example.com/body.jpg",
    }
    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 201
    assert response.json()["image_url"] == payload["image_url"]

    insecure = client.post(
        "/api/v1/products",
        json={**payload, "slug": "otro", "image_url": "javascript:alert(1)"},
    )
    assert insecure.status_code == 422

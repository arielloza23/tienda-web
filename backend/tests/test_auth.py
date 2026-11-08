import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token

CUSTOMER = {
    "email": "cliente@example.com",
    "full_name": "Cliente Prueba",
    "password": "cliente-password-1",
}

ADMIN_ONLY_REQUESTS = [
    ("get", "/api/v1/users", None),
    ("get", "/api/v1/orders", None),
    ("get", "/api/v1/orders/1", None),
    ("patch", "/api/v1/orders/1/status?new_status=paid", None),
    ("post", "/api/v1/products", {"name": "X", "slug": "x", "price_cents": 100}),
]


def _login(client: TestClient, email: str, password: str):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def _customer_token(client: TestClient) -> str:
    assert client.post("/api/v1/users", json=CUSTOMER).status_code == 201
    response = _login(client, CUSTOMER["email"], CUSTOMER["password"])
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ONLY_REQUESTS)
def test_admin_endpoints_require_login(anon_client: TestClient, method, url, body) -> None:
    response = anon_client.request(method, url, json=body)
    assert response.status_code == 401


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ONLY_REQUESTS)
def test_admin_endpoints_reject_customers(anon_client: TestClient, method, url, body) -> None:
    token = _customer_token(anon_client)
    response = anon_client.request(
        method, url, json=body, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_public_endpoints_do_not_require_login(anon_client: TestClient) -> None:
    assert anon_client.get("/api/v1/products").status_code == 200
    assert anon_client.post("/api/v1/users", json=CUSTOMER).status_code == 201


def test_login_with_wrong_password_fails(anon_client: TestClient) -> None:
    anon_client.post("/api/v1/users", json=CUSTOMER)
    assert _login(anon_client, CUSTOMER["email"], "incorrecta").status_code == 401
    assert _login(anon_client, "nadie@example.com", "incorrecta").status_code == 401


def test_me_returns_current_user(anon_client: TestClient) -> None:
    token = _customer_token(anon_client)
    response = anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == CUSTOMER["email"]
    assert response.json()["role"] == "customer"


def test_invalid_and_expired_tokens_are_rejected(anon_client: TestClient) -> None:
    anon_client.post("/api/v1/users", json=CUSTOMER)
    expired = create_access_token(1, expires_minutes=-1)
    for token in ("no-es-un-token", expired):
        response = anon_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401


def test_registration_cannot_create_admins(anon_client: TestClient) -> None:
    response = anon_client.post("/api/v1/users", json={**CUSTOMER, "role": "admin"})
    if response.status_code == 201:
        assert response.json()["role"] == "customer"


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ONLY_REQUESTS)
def test_admin_endpoints_open_when_auth_disabled(
    anon_client: TestClient, monkeypatch, method, url, body
) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_enabled", False)
    response = anon_client.request(method, url, json=body)
    assert response.status_code not in (401, 403)

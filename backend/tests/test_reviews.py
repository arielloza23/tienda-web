from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.product import Product
from app.models.review import ProductReview
from app.models.user import User
from app.schemas.review import ReviewWrite
from app.services.review_service import save_review
from app.services.user_service import create_user
from app.schemas.user import UserCreate


@pytest.fixture
def product(db_session):
    item = Product(name="Vestido", slug="vestido-review", price_cents=1550, is_active=True)
    db_session.add(item)
    db_session.commit()
    return item


def customer(db, index=1, active=True, role="customer"):
    user = User(email=f"customer{index}@example.com", full_name=f"Cliente {index}",
                password_hash=hash_password("test-password-123"), role=role, is_active=active)
    db.add(user)
    db.commit()
    return user


def auth(user):
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


def url(product):
    return f"/api/v1/products/{product.id}/reviews"


def test_public_empty_and_no_private_metadata(anon_client, product):
    response = anon_client.get(url(product), headers={"Authorization": "Bearer invalid"})
    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "average_rating": None, "limit": 10, "offset": 0}


@pytest.mark.parametrize("auth_bypass", [False, True])
def test_guests_cannot_read_or_write_personal_review(anon_client, product, monkeypatch, auth_bypass):
    monkeypatch.setattr(settings, "auth_enabled", not auth_bypass)
    assert anon_client.get(url(product) + "/me").status_code == 401
    assert anon_client.put(url(product) + "/me", json={"rating": 5}).status_code == 401


@pytest.mark.parametrize("role", ["customer", "admin"])
def test_authenticated_user_can_create_and_edit_own_single_review(anon_client, product, db_session, role):
    user = customer(db_session, role=role)
    assert anon_client.get(url(product) + "/me", headers=auth(user)).json() is None
    created = anon_client.put(url(product) + "/me", headers=auth(user), json={"rating": 5, "comment": "  Excelente  "})
    assert created.status_code == 200
    result = created.json()
    assert result["author_name"] == "Cliente 1"
    assert result["comment"] == "Excelente"
    assert set(result) == {"id", "product_id", "author_name", "rating", "comment", "created_at", "updated_at"}
    assert result["created_at"].endswith("Z")
    updated = anon_client.put(url(product) + "/me", headers=auth(user), json={"rating": 2, "comment": None}).json()
    assert updated["id"] == result["id"]
    assert updated["comment"] == ""
    assert updated["created_at"] == result["created_at"]
    assert db_session.query(ProductReview).count() == 1
    assert anon_client.get(url(product) + "/me", headers=auth(user)).json() == updated


def test_inactive_user_cannot_review(anon_client, product, db_session):
    user = customer(db_session, active=False)
    assert anon_client.put(url(product) + "/me", headers=auth(user), json={"rating": 5}).status_code == 401


@pytest.mark.parametrize("rating", [0, 6, True, 3.5, "4", None])
def test_rejects_invalid_or_coerced_ratings(anon_client, product, db_session, rating):
    user = customer(db_session)
    assert anon_client.put(url(product) + "/me", headers=auth(user), json={"rating": rating}).status_code == 422
    assert db_session.query(ProductReview).count() == 0


@pytest.mark.parametrize("extra", [{"user_id": 999}, {"author_name": "Otra persona"}, {"product_id": 999}, {"comment": "x" * 2001}, {"comment": 10}])
def test_rejects_spoofing_and_invalid_comments(anon_client, product, db_session, extra):
    user = customer(db_session)
    assert anon_client.put(url(product) + "/me", headers=auth(user), json={"rating": 5, **extra}).status_code == 422


def test_aggregation_pagination_order_and_ownership(anon_client, product, db_session):
    first, second = customer(db_session), customer(db_session, 2)
    for user, rating in [(first, 2), (second, 5)]:
        assert anon_client.put(url(product) + "/me", headers=auth(user), json={"rating": rating}).status_code == 200
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for review in db_session.scalars(select(ProductReview)).all():
        review.created_at = timestamp
    db_session.commit()
    page = anon_client.get(url(product) + "?limit=1&offset=0").json()
    assert page["total"] == 2 and page["average_rating"] == 3.5
    assert page["items"][0]["author_name"] == second.full_name
    assert anon_client.get(url(product) + "?limit=1&offset=1").json()["items"][0]["author_name"] == first.full_name
    assert anon_client.get(url(product) + "?offset=99").json()["average_rating"] == 3.5
    assert anon_client.get(url(product) + "/me", headers=auth(first)).json()["rating"] == 2


@pytest.mark.parametrize("query", ["limit=0", "limit=51", "offset=-1"])
def test_pagination_limits(anon_client, product, query):
    assert anon_client.get(url(product) + "?" + query).status_code == 422


@pytest.mark.parametrize("missing", [False, True])
def test_missing_and_inactive_products_are_not_exposed(anon_client, product, db_session, missing):
    user = customer(db_session)
    if missing:
        product_id = 99999
    else:
        product.is_active = False
        db_session.commit()
        product_id = product.id
    path = f"/api/v1/products/{product_id}/reviews"
    assert anon_client.get(path).status_code == 404
    assert anon_client.get(path + "/me", headers=auth(user)).status_code == 404
    assert anon_client.put(path + "/me", headers=auth(user), json={"rating": 5}).status_code == 404


def test_checkout_still_accepts_guest_and_calculates_price(anon_client, product):
    response = anon_client.post("/api/v1/orders", json={"customer_name": "Invitado", "customer_phone": "0999999999",
        "delivery_address": "Calle temporal 123", "items": [{"product_id": product.id, "quantity": 2}]})
    assert response.status_code == 201
    assert response.json()["user_id"] is None
    assert response.json()["total_cents"] == 3100


def test_registration_trims_names_and_rejects_whitespace(anon_client):
    payload = {"email": "new@example.com", "full_name": "  ", "password": "test-password-123"}
    assert anon_client.post("/api/v1/users", json=payload).status_code == 422
    payload["full_name"] = "  Cliente Nuevo  "
    response = anon_client.post("/api/v1/users", json=payload)
    assert response.status_code == 201
    assert response.json()["full_name"] == "Cliente Nuevo"
    assert response.json()["role"] == "customer"
    assert anon_client.post("/api/v1/users", json=payload).status_code == 400


def test_concurrent_insert_conflict_updates_existing_review(product, db_session, monkeypatch):
    user = customer(db_session)
    existing = ProductReview(product_id=product.id, user_id=user.id, rating=1, comment="old")
    db_session.add(existing)
    db_session.commit()
    from app.services import review_service
    real_get = review_service.get_own_review
    calls = 0
    def first_lookup_misses(db, product_id, user_id):
        nonlocal calls
        calls += 1
        return None if calls == 1 else real_get(db, product_id, user_id)
    monkeypatch.setattr(review_service, "get_own_review", first_lookup_misses)
    result = save_review(db_session, product.id, user.id, ReviewWrite(rating=4))
    assert result.id == existing.id and result.rating == 4
    assert db_session.query(ProductReview).count() == 1


def test_unrelated_integrity_error_is_not_hidden(product, db_session, monkeypatch):
    user = customer(db_session)
    error = IntegrityError("statement", {}, Exception("different constraint"))
    monkeypatch.setattr(db_session, "commit", lambda: (_ for _ in ()).throw(error))
    with pytest.raises(IntegrityError) as caught:
        save_review(db_session, product.id, user.id, ReviewWrite(rating=4))
    assert caught.value is error


def test_registration_handles_unique_email_race(product, db_session, monkeypatch):
    user = customer(db_session)
    from app.services import user_service
    monkeypatch.setattr(user_service, "get_user_by_email", lambda *args: None)
    with pytest.raises(ValueError, match="Ya existe"):
        create_user(db_session, UserCreate(email=user.email, full_name="Otro cliente", password="test-password-123"))
    assert db_session.query(User).count() == 1

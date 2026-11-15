from copy import deepcopy

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.models.order import Order, OrderItem
from app.models.product import ProductVariant

BASE = "/api/v1/products"


def create(client, suffix="one"):
    response = client.post(BASE, json={
        "name": "Producto original", "slug": f"producto-{suffix}", "price_cents": 1500,
        "image_url": "https://example.com/cover.webp",
        "variants": [
            {"sku": f"SKU-{suffix}-M", "size": "M", "color": "Vino", "price_adjustment_cents": 100},
            {"sku": f"SKU-{suffix}-L", "size": "L", "color": "Vino"},
        ],
        "images": [{"url": "https://example.com/one.webp", "alt": "Foto original", "color": "Vino"}],
    })
    assert response.status_code == 201, response.text
    return response.json()


def editable(product):
    payload = deepcopy(product)
    payload.pop("id")
    for image in payload["images"]:
        image.pop("id")
    return payload


def current(client, product_id):
    return next(product for product in client.get(BASE + "/admin").json() if product["id"] == product_id)


def test_update_all_attributes_gallery_order_and_draft_visibility(client):
    original = create(client)
    payload = editable(original)
    payload.update(name="Editado", slug="nuevo-identificador", description="Nueva descripción", price_cents=2200,
                   image_url="https://example.com/new-cover.webp", is_active=False)
    payload["variants"][0].update(size="XL", color="Azul", price_adjustment_cents=300)
    payload["variants"][1]["color"] = "Azul"
    payload["images"] = [
        {"url": "https://example.com/b.webp", "alt": "Vista segunda", "color": "azul"},
        {"url": "https://example.com/a.webp", "alt": "Vista primera", "color": "Azul"},
    ]
    response = client.put(f"{BASE}/{original['id']}", json=payload)
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved["id"] == original["id"]
    assert [v["id"] for v in saved["variants"]] == [v["id"] for v in original["variants"]]
    for field in ("name", "slug", "description", "price_cents", "image_url", "is_active"):
        assert saved[field] == payload[field]
    assert saved["variants"][0]["size"] == "XL"
    assert saved["variants"][0]["price_adjustment_cents"] == 300
    assert [i["url"] for i in saved["images"]] == [i["url"] for i in payload["images"]]
    assert [i["color"] for i in saved["images"]] == ["Azul", "Azul"]
    assert client.get(BASE).json() == []
    payload["is_active"] = True
    assert client.put(f"{BASE}/{original['id']}", json=payload).status_code == 200
    assert len(client.get(BASE).json()) == 1


def test_add_and_remove_unreferenced_variant_without_changing_retained_id(client, db_session):
    original = create(client)
    payload = editable(original)
    payload["variants"].pop()
    payload["variants"].append({"id": None, "sku": "SKU-NEW", "color": "Vino", "size": "XS"})
    response = client.put(f"{BASE}/{original['id']}", json=payload)
    assert response.status_code == 200
    variants = response.json()["variants"]
    assert variants[0]["id"] == original["variants"][0]["id"]
    assert variants[1]["sku"] == "SKU-NEW"
    assert db_session.query(ProductVariant).filter(ProductVariant.sku == original["variants"][1]["sku"]).first() is None


@pytest.mark.parametrize("change,status", [
    ("foreign-id", 400), ("duplicate-id", 422), ("boolean-id", 422), ("string-id", 422), ("zero-id", 422),
    ("sku-swap", 409), ("sku-reuse-deleted", 409), ("duplicate-sku", 409),
    ("invalid-gallery", 400), ("repeat-gallery", 400), ("overflow-price", 400),
    ("negative-price", 422), ("boolean-price", 422), ("missing-images", 422), ("missing-variants", 422),
])
def test_invalid_edits_leave_everything_unchanged(client, change, status):
    original = create(client)
    other = create(client, "other")
    payload = editable(original)
    payload["name"] = "Debe conservar original"
    if change == "foreign-id": payload["variants"][0]["id"] = other["variants"][0]["id"]
    elif change == "duplicate-id": payload["variants"][1]["id"] = payload["variants"][0]["id"]
    elif change == "boolean-id": payload["variants"][0]["id"] = True
    elif change == "string-id": payload["variants"][0]["id"] = str(payload["variants"][0]["id"])
    elif change == "zero-id": payload["variants"][0]["id"] = 0
    elif change == "sku-swap":
        payload["variants"][0]["sku"], payload["variants"][1]["sku"] = payload["variants"][1]["sku"], payload["variants"][0]["sku"]
    elif change == "sku-reuse-deleted": payload["variants"] = [{"sku": original["variants"][1]["sku"], "color": "Vino"}]
    elif change == "duplicate-sku": payload["variants"][1]["sku"] = payload["variants"][0]["sku"]
    elif change == "invalid-gallery": payload["images"][0]["color"] = "Verde"
    elif change == "repeat-gallery": payload["images"].append(deepcopy(payload["images"][0]))
    elif change == "overflow-price": payload["price_cents"] = 2147483647
    elif change == "negative-price": payload["price_cents"] = -1
    elif change == "boolean-price": payload["price_cents"] = True
    elif change == "missing-images": payload.pop("images")
    elif change == "missing-variants": payload.pop("variants")
    response = client.put(f"{BASE}/{original['id']}", json=payload)
    assert response.status_code == status, response.text
    assert current(client, original["id"]) == original


@pytest.mark.parametrize("conflict", ["slug", "sku"])
def test_other_product_unique_conflicts_are_atomic(client, conflict):
    original = create(client)
    other = create(client, "other")
    payload = editable(original)
    payload.update(name="No guardar", price_cents=3500)
    if conflict == "slug": payload["slug"] = other["slug"]
    else: payload["variants"][0]["sku"] = other["variants"][0]["sku"]
    assert client.put(f"{BASE}/{original['id']}", json=payload).status_code == 409
    assert current(client, original["id"]) == original


def test_update_requires_authentication_even_with_development_bypass(client, monkeypatch):
    original = create(client)
    monkeypatch.setattr(settings, "auth_enabled", False)
    assert client.put(f"{BASE}/{original['id']}", json=editable(original), headers={"Authorization": ""}).status_code == 401


def test_customer_and_inactive_admin_cannot_update(client, db_session):
    from app.models.user import User
    original = create(client)
    admin = db_session.query(User).first()
    admin.role = "customer"
    db_session.commit()
    assert client.put(f"{BASE}/{original['id']}", json=editable(original)).status_code == 403
    admin.role = "admin"
    admin.is_active = False
    db_session.commit()
    assert client.put(f"{BASE}/{original['id']}", json=editable(original)).status_code == 401


def test_missing_product_returns_404(client):
    assert client.put(f"{BASE}/98765", json={"name": "No existe", "slug": "no-existe", "price_cents": 0, "variants": [], "images": []}).status_code == 404


@pytest.fixture
def foreign_keys(db_session):
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    assert db_session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    yield
    db_session.rollback()
    db_session.execute(text("PRAGMA foreign_keys=OFF"))


def test_order_snapshots_preserved_and_referenced_variant_cannot_be_removed(client, db_session, foreign_keys):
    original = create(client)
    order = Order(subtotal_cents=1600, total_cents=1600)
    item = OrderItem(product_id=original["id"], variant_id=original["variants"][0]["id"],
                     product_name=original["name"], variant_label="M / Vino", unit_price_cents=1600,
                     quantity=1, total_price_cents=1600)
    order.items.append(item)
    db_session.add(order)
    db_session.commit()
    snapshot = (item.product_name, item.variant_label, item.unit_price_cents, item.quantity, item.total_price_cents, item.variant_id)
    payload = editable(original)
    payload.update(name="Nuevo nombre", price_cents=4500)
    payload["variants"][0].update(size="XL", color="Azul", sku="SKU-UPDATED")
    assert client.put(f"{BASE}/{original['id']}", json=payload).status_code == 200
    db_session.refresh(item)
    db_session.refresh(order)
    assert (item.product_name, item.variant_label, item.unit_price_cents, item.quantity, item.total_price_cents, item.variant_id) == snapshot
    assert order.total_cents == 1600
    before = current(client, original["id"])
    payload = editable(before)
    payload.update(name="Nunca guardar", price_cents=100)
    payload["variants"].pop(0)
    payload["images"] = []
    response = client.put(f"{BASE}/{original['id']}", json=payload)
    assert response.status_code == 409
    assert current(client, original["id"]) == before
    db_session.refresh(item)
    assert item.variant_id == snapshot[-1]


def test_create_does_not_accept_existing_variant_ids(client):
    response = client.post(BASE, json={"name": "Producto", "slug": "sin-ids", "price_cents": 100,
                                      "variants": [{"id": 1, "sku": "SKU-ONE"}]})
    assert response.status_code == 422


@pytest.mark.parametrize("message", ["UNIQUE constraint failed: products.slug", "UNIQUE constraint failed: product_variants.sku", "FOREIGN KEY constraint failed"])
def test_commit_constraint_races_roll_back_all_changes(client, db_session, monkeypatch, message):
    import sqlite3
    from sqlalchemy.exc import IntegrityError
    from app.schemas.product import ProductUpdate
    from app.services.product_service import ProductConflict, update_product
    original = create(client)
    payload = editable(original)
    payload.update(name="No guardar", price_cents=100)
    payload["variants"].pop()
    payload["images"] = []
    def fail_commit():
        raise IntegrityError("simulated concurrent write", {}, sqlite3.IntegrityError(message))
    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(ProductConflict):
        update_product(db_session, original["id"], ProductUpdate.model_validate(payload))
    assert current(client, original["id"]) == original


def test_unknown_integrity_error_is_not_disguised_as_conflict(client, db_session, monkeypatch):
    import sqlite3
    from sqlalchemy.exc import IntegrityError
    from app.schemas.product import ProductUpdate
    from app.services.product_service import update_product
    original = create(client)
    payload = editable(original)
    payload["name"] = "No guardar"
    def fail_commit():
        raise IntegrityError("unexpected constraint", {}, sqlite3.IntegrityError("NOT NULL constraint failed: unexpected.column"))
    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(IntegrityError):
        update_product(db_session, original["id"], ProductUpdate.model_validate(payload))
    assert current(client, original["id"]) == original


@pytest.mark.parametrize("constraint", ["order_items_variant_id_fkey", "fk_order_items_variant_id_product_variants"])
def test_postgres_referenced_variant_race_is_conflict(client, db_session, monkeypatch, constraint):
    from types import SimpleNamespace
    from sqlalchemy.exc import IntegrityError
    from app.schemas.product import ProductUpdate
    from app.services.product_service import ProductConflict, update_product
    original = create(client)
    payload = editable(original)
    payload["name"] = "No guardar"
    payload["variants"].pop()
    error = RuntimeError("referenced variant")
    error.diag = SimpleNamespace(constraint_name=constraint)
    def fail_commit():
        raise IntegrityError("simulated concurrent order", {}, error)
    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(ProductConflict):
        update_product(db_session, original["id"], ProductUpdate.model_validate(payload))
    assert current(client, original["id"]) == original

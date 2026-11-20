import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.order import Order
from app.models.password_reset import PasswordResetToken
from app.models.product import Product
from app.models.user import User
from app.schemas.order import OrderCreate
from app.services import order_service, password_reset_service as recovery


def order_payload(pid, expected=None):
    item = {"product_id": pid, "quantity": 2}
    if expected is not None:
        item["expected_unit_price_cents"] = expected
    return {"customer_name": "Cliente Prueba", "customer_phone": "0991234567", "delivery_address": "Calle Prueba 123", "items": [item]}


def test_price_changed_rejects_without_order_then_confirms_and_replays(client, db_session):
    product = client.post("/api/v1/products", json={"name": "Prueba", "slug": "prueba", "price_cents": 1500, "stock_quantity": 2}).json()
    body = order_payload(product["id"], 1000)
    key = {"Idempotency-Key": str(uuid4())}
    response = client.post("/api/v1/orders", json=body, headers=key)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "price_changed" and detail["subtotal_cents"] == 3000
    assert detail["items"] == [{"product_id": product["id"], "variant_id": None, "expected_unit_price_cents": 1000, "current_unit_price_cents": 1500}]
    assert db_session.query(Order).count() == 0
    body["items"][0]["expected_unit_price_cents"] = 1500
    first = client.post("/api/v1/orders", json=body, headers=key)
    assert first.status_code == 201
    db_session.get(Product, product["id"]).price_cents = 1700
    db_session.commit()
    assert client.post("/api/v1/orders", json=body, headers=key).json() == first.json()


def test_hash_keeps_legacy_optional_null_fields():
    payload = OrderCreate(**order_payload(1))
    # Contrato anterior explicito: no inferir campos historicos desde el modelo nuevo.
    legacy = dict(order_payload(1), user_id=None, delivery_latitude=None, delivery_longitude=None)
    legacy["items"][0]["variant_id"] = None
    encoded = json.dumps(legacy, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert order_service._request_hash(payload) == hashlib.sha256(encoded.encode()).hexdigest()


@pytest.mark.parametrize("value", [True, "100", 1.5, -1, 2147483648])
def test_expected_price_strict(anon_client, value):
    assert anon_client.post("/api/v1/orders", json=order_payload(1, value)).status_code == 422


@pytest.mark.parametrize("value", [True, "90", 0, -2, 301, 10.12, float("inf")])
def test_measurement_validation(value):
    from pydantic import ValidationError
    from app.schemas.product import ProductVariantCreate
    with pytest.raises(ValidationError):
        ProductVariantCreate(sku="TEST", bust_cm=value)


def test_measurements_roundtrip_update(client):
    body = {"name": "Prueba", "slug": "prueba", "price_cents": 100, "variants": [{"sku": "TEST", "size": "M", "bust_cm": 90.5, "waist_cm": 70, "hip_cm": None}]}
    created = client.post("/api/v1/products", json=body)
    assert created.status_code == 201
    product = created.json()
    assert product["variants"][0]["bust_cm"] == 90.5
    product.pop("id")
    product["variants"][0]["hip_cm"] = 99.9
    edited = client.put("/api/v1/products/1", json=product)
    assert edited.status_code == 200 and edited.json()["variants"][0]["hip_cm"] == 99.9


@pytest.fixture
def configured_mail(monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.invalid")
    monkeypatch.setattr(settings, "smtp_from", "shop@example.invalid")
    monkeypatch.setattr(settings, "password_reset_url", "https://shop.example.invalid/#/reset-password")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    recovery._request_times.clear()
    sent = []
    monkeypatch.setattr(recovery, "send_reset_email", lambda email, token: sent.append((email, token)))
    return sent


def test_unconfigured_mail_honest_for_all(anon_client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", None)
    for email in ("known@example.com", "missing@example.com"):
        assert anon_client.post("/api/v1/auth/forgot-password", json={"email": email}).status_code == 503


def add_user(db, active=True):
    user = User(email="customer@example.com", full_name="Cliente", password_hash=hash_password("previous-password"), is_active=active)
    db.add(user)
    db.commit()
    return user


def test_recovery_generic_cooldown_reset_one_use_and_revoke_session(anon_client, db_session, configured_mail):
    user = add_user(db_session)
    old_token = create_access_token(user.id)
    known = anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    missing = anon_client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.com"})
    assert known.status_code == missing.status_code == 202 and known.json() == missing.json()
    anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert len(configured_mail) == 1
    token = configured_mail[0][1]
    record = db_session.query(PasswordResetToken).one()
    assert record.token_hash == hashlib.sha256(token.encode()).hexdigest() and token not in record.token_hash
    response = anon_client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-password-123"})
    assert response.status_code == 200
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
    assert anon_client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-password-456"}).status_code == 400
    login = anon_client.post("/api/v1/auth/login", json={"email": user.email, "password": "new-password-123"})
    assert login.status_code == 200
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + login.json()["access_token"]}).status_code == 200
    assert anon_client.post("/api/v1/auth/login", json={"email": user.email, "password": "previous-password"}).status_code == 401


def test_expired_invalid_and_previous_tokens(anon_client, db_session, configured_mail):
    user = add_user(db_session)
    anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    old = configured_mail[0][1]
    record = db_session.query(PasswordResetToken).one()
    record.created_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    for token in (old, "invalid-token"):
        assert anon_client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-password-123"}).status_code == 400
    anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert len(configured_mail) == 2
    assert anon_client.post("/api/v1/auth/reset-password", json={"token": old, "password": "new-password-123"}).status_code == 400


def test_smtp_failure_generic_and_no_sensitive_log(anon_client, db_session, configured_mail, monkeypatch, caplog):
    user = add_user(db_session)
    def fail(email, token):
        raise OSError(email + token)
    monkeypatch.setattr(recovery, "send_reset_email", fail)
    result = anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert result.status_code == 202 and user.email not in caplog.text


def test_rate_limit_returns_generic(configured_mail):
    assert all(recovery.allow_request("test-address") for _ in range(10))
    assert not recovery.allow_request("test-address")


def test_inactive_user_receives_generic_without_token(anon_client, db_session, configured_mail):
    user = add_user(db_session, active=False)
    response = anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert response.status_code == 202 and not configured_mail
    assert db_session.query(PasswordResetToken).count() == 0


def test_new_request_revokes_still_valid_link(anon_client, db_session, configured_mail):
    user = add_user(db_session)
    anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    old = configured_mail[0][1]
    db_session.query(PasswordResetToken).one().created_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    db_session.commit()
    anon_client.post("/api/v1/auth/forgot-password", json={"email": user.email})
    assert len(configured_mail) == 2
    assert anon_client.post("/api/v1/auth/reset-password", json={"token": old, "password": "new-password-123"}).status_code == 400
    assert anon_client.post("/api/v1/auth/reset-password", json={"token": configured_mail[1][1], "password": "new-password-123"}).status_code == 200


def test_smtp_uses_verified_starttls_and_fixed_fragment_url(monkeypatch):
    import ssl
    from pydantic import SecretStr
    events = []
    class SMTP:
        def __init__(self, host, port, timeout):
            assert host == "smtp.example.invalid" and port == 587 and timeout == 10
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def ehlo(self): events.append("ehlo")
        def starttls(self, context):
            assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
            events.append("tls")
        def login(self, user, password):
            assert user == "test-user" and password == "fake-secret"
            events.append("login")
        def send_message(self, message):
            assert message["To"] == "client@example.com"
            assert "https://shop.example.invalid/#/reset-password?token=fake_token" in message.get_content()
            events.append("send")
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.invalid")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_from", "shop@example.invalid")
    monkeypatch.setattr(settings, "smtp_user", "test-user")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("fake-secret"))
    monkeypatch.setattr(settings, "password_reset_url", "https://shop.example.invalid/#/reset-password")
    monkeypatch.setattr(settings, "smtp_starttls", True)
    monkeypatch.setattr(recovery.smtplib, "SMTP", SMTP)
    recovery.send_reset_email("client@example.com", "fake_token")
    assert events == ["ehlo", "tls", "ehlo", "login", "send"]


def test_legacy_token_without_version_still_works_before_reset(anon_client, db_session):
    import jwt
    from app.core.security import JWT_ALGORITHM
    user = add_user(db_session)
    token = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(minutes=10)}, settings.secret_key, algorithm=JWT_ALGORITHM)
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    user.token_version = 1
    db_session.commit()
    assert anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_old_editor_preserves_measurements_unless_explicit_null(client):
    created = client.post("/api/v1/products", json={"name": "Prueba", "slug": "prueba", "price_cents": 100, "variants": [{"sku": "TEST", "bust_cm": 90.5}]}).json()
    pid = created.pop("id")
    for field in ("bust_cm", "waist_cm", "hip_cm"):
        created["variants"][0].pop(field)
    edited = client.put(f"/api/v1/products/{pid}", json=created)
    assert edited.status_code == 200 and edited.json()["variants"][0]["bust_cm"] == 90.5
    created["variants"][0]["bust_cm"] = None
    assert client.put(f"/api/v1/products/{pid}", json=created).json()["variants"][0]["bust_cm"] is None


def test_concurrent_status_updates_cannot_overwrite_each_other(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.db.base import Base
    engine = create_engine(f"sqlite:///{(tmp_path / 'status-race.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        order = Order(status="pending", user_id=None, subtotal_cents=100, total_cents=100, shipping_total_cents=0, tax_total_cents=0)
        db.add(order)
        db.commit()
        order_id = order.id
    barrier = Barrier(2)
    original = order_service.get_order_by_id
    def synchronized_read(db, oid):
        order = original(db, oid)
        barrier.wait(timeout=10)
        return order
    monkeypatch.setattr(order_service, "get_order_by_id", synchronized_read)
    def change(status):
        with Session(engine) as db:
            try:
                return ("ok", order_service.update_order_status(db, order_id, status).status)
            except ValueError:
                return ("conflict", status)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(change, ["reserved", "cancelled"]))
        assert sum(result[0] == "ok" for result in results) == 1
        assert sum(result[0] == "conflict" for result in results) == 1
        with Session(engine) as db:
            assert db.get(Order, order_id).status == next(value for outcome, value in results if outcome == "ok")
    finally:
        engine.dispose()


def test_forgot_response_does_not_wait_for_smtp(db_session, configured_mail):
    import asyncio
    from fastapi import BackgroundTasks, Request
    from app.api.v1.auth import forgot_password
    from app.schemas.auth import ForgotPasswordRequest
    user = add_user(db_session)
    background = BackgroundTasks()
    request = Request({"type": "http", "client": ("unit-test", 1234), "headers": []})
    response = forgot_password(ForgotPasswordRequest(email=user.email), request, background, db_session)
    assert response.message == recovery.FORGOT_MESSAGE
    assert not configured_mail and len(background.tasks) == 1
    assert db_session.query(PasswordResetToken).count() == 1
    asyncio.run(background())
    assert len(configured_mail) == 1

@pytest.mark.parametrize('elapsed_seconds, accepted', [(0.5, True), (2, False)])
def test_reset_rechecks_expiry_after_waiting_and_hashing(db_session, monkeypatch, elapsed_seconds, accepted):
    user = add_user(db_session)
    original_hash = user.password_hash
    token = 'temporary-expiring-link'
    initial = datetime(2026, 1, 1, tzinfo=timezone.utc)
    record = PasswordResetToken(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(),
        created_at=initial - timedelta(minutes=29), expires_at=initial + timedelta(seconds=1))
    db_session.add(record); db_session.commit()

    class Clock:
        value = initial
        @classmethod
        def now(cls, tz):
            return cls.value

    def slow_hash(password):
        # Simulates elapsed time waiting for the account lock or deriving the hash.
        Clock.value = initial + timedelta(seconds=elapsed_seconds)
        return 'replacement-hash'

    monkeypatch.setattr(recovery, 'datetime', Clock)
    monkeypatch.setattr(recovery, 'hash_password', slow_hash)
    if accepted:
        recovery.reset_password(db_session, token, 'new-password-123')
    else:
        with pytest.raises(ValueError, match=recovery.INVALID_TOKEN):
            recovery.reset_password(db_session, token, 'new-password-123')
    db_session.expire_all()
    assert user.password_hash == ('replacement-hash' if accepted else original_hash)
    assert user.token_version == (1 if accepted else 0)
    assert record.used_at == (Clock.value.replace(tzinfo=None) if accepted else None)
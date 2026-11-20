from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from app.models.analytics import AnalyticsEvent
from app.models.product import Product, ProductVariant
from app.models.order import Order, OrderItem
from app.models.review import ProductReview
from app.models.user import User
from app.schemas.order import OrderCreate
from app.services.order_service import _request_hash, create_order
from app.services.analytics_service import dashboard
from app.api.v1.analytics import _rate_buckets


@pytest.fixture(autouse=True)
def reset_limits():
    _rate_buckets.clear()


@pytest.fixture
def product(db_session):
    p = Product(name="Temporal", slug="temporary", price_cents=1000, is_active=True, stock_quantity=100)
    db_session.add(p)
    db_session.commit()
    return p


def event(product, sid=None, kind="product_view", **kwargs):
    return dict(event_id=str(uuid4()), session_id=sid or str(uuid4()), event_type=kind,
                product_id=product.id, **kwargs)


def test_ingest_dedup_conflict_and_server_time(anon_client, db_session, product):
    e = event(product)
    assert anon_client.post("/api/v1/analytics/events", json={"events": [e,e]}).json() == {"accepted":1,"duplicates":1}
    assert anon_client.post("/api/v1/analytics/events", json={"events": [e]}).json() == {"accepted":0,"duplicates":1}
    assert db_session.query(AnalyticsEvent).count() == 1
    changed = dict(e, event_type="gallery_open")
    assert anon_client.post("/api/v1/analytics/events", json={"events": [changed]}).status_code == 409
    assert anon_client.post("/api/v1/analytics/events", json={"events": [dict(e, created_at="1900-01-01")]}).status_code == 422


@pytest.mark.parametrize("change", [{"email":"private@example.com"}, {"url":"https://example.com/?secret=yes"},
    {"event_type":"paid"}, {"product_id": True}, {"product_id":2147483648},
    {"event_type":"filter_apply", "target":"free text"}, {"variant_id":99999}])
def test_ingestion_rejects_unbounded_or_untrusted_values(anon_client, product, change):
    result = anon_client.post("/api/v1/analytics/events", json={"events":[dict(event(product), **change)]})
    assert result.status_code == 422
    assert "private@example.com" not in result.text
    assert "secret=yes" not in result.text


def test_limits_and_product_variant_relationship(anon_client, db_session, product):
    assert anon_client.post("/api/v1/analytics/events", content=b"x" * 16385).status_code == 413
    assert anon_client.post("/api/v1/analytics/events", json={"events":[event(product) for _ in range(21)]}).status_code == 422
    p2 = Product(name="Other", slug="other", price_cents=100)
    db_session.add(p2); db_session.flush()
    v = ProductVariant(product_id=p2.id, sku="OTHER", size="M", stock_quantity=1)
    db_session.add(v); db_session.commit()
    assert anon_client.post("/api/v1/analytics/events", json={"events":[event(product, variant_id=v.id)]}).status_code == 422
    for _ in range(12):
        assert anon_client.post("/api/v1/analytics/events", json={"events":[event(product, sid="11111111-1111-4111-8111-111111111111") for _ in range(20)]}).status_code == 202
    assert anon_client.post("/api/v1/analytics/events", json={"events":[event(product, sid="11111111-1111-4111-8111-111111111111")]}).status_code == 429


def test_dashboard_requires_actual_admin_even_bypass(anon_client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "auth_enabled", False)
    assert anon_client.get("/api/v1/analytics/dashboard").status_code == 401
    anon_client.post("/api/v1/users", json={"full_name":"Temporal", "email":"temp@example.com", "password":"password-test-123"})
    login = anon_client.post("/api/v1/auth/login", json={"email":"temp@example.com", "password":"password-test-123"})
    token = login.json()["access_token"]
    assert anon_client.get("/api/v1/analytics/dashboard", headers={"Authorization":f"Bearer {token}"}).status_code == 403


def test_dashboard_empty_cohort_and_period(client, product):
    response = client.get("/api/v1/analytics/dashboard?days=7")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["measurement_started_at"] is None
    assert data["products"][0]["order_conversion"] is None
    assert data["users"]["administrators"] == 1
    assert client.get("/api/v1/analytics/dashboard?days=8").status_code == 422


def test_session_cohort_math_no_fanout_historical_or_future_events(db_session, product):
    now = datetime(2026,11,20,18,tzinfo=timezone.utc)
    base = now.replace(tzinfo=None) - timedelta(hours=2)
    ids = [str(uuid4()) for _ in range(4)]
    def add(sid, kind, stamp):
        db_session.add(AnalyticsEvent(**event(product,sid,kind),created_at=stamp))
    add(ids[0],"product_view",base)
    add(ids[0],"product_view",base+timedelta(minutes=1))
    add(ids[1],"product_view",base)
    add(ids[0],"add_to_cart",base-timedelta(minutes=1)) # excluded before view
    add(ids[0],"add_to_cart",base+timedelta(minutes=2))
    add(ids[0],"add_to_cart",base+timedelta(minutes=3))
    add(ids[0],"checkout_start",base+timedelta(minutes=4))
    add(ids[2],"checkout_start",base) # no view
    add(ids[3],"product_view",base-timedelta(days=9))
    add(ids[3],"checkout_start",base)
    add(str(uuid4()),"product_view",base+timedelta(days=1)) # future rejected by window
    def order(sid, status, stamp, lines=1):
        o=Order(analytics_session_id=sid,status=status,created_at=stamp)
        o.items=[OrderItem(product_id=product.id, product_name=product.name,unit_price_cents=1000,quantity=1,total_price_cents=1000) for _ in range(lines)]
        db_session.add(o)
    order(ids[0],"paid",base+timedelta(minutes=5),2)
    order(ids[0],"delivered",base+timedelta(minutes=6))
    order(ids[1],"cancelled",base+timedelta(minutes=7))
    order(ids[2],"paid",base+timedelta(minutes=5))
    order(ids[3],"paid",base+timedelta(minutes=5))
    order(None,"paid",base)
    order(ids[1],"paid",base-timedelta(minutes=5)) # before view
    db_session.commit()
    data=dashboard(db_session,7,now)
    p=data["products"][0]
    assert p == dict(product_id=product.id,product_name=product.name,view_sessions=2,
        cart_sessions=1,checkout_sessions=1,order_sessions=2,paid_sessions=1,
        order_conversion=100.0,payment_conversion=50.0)
    assert data["orders"] == dict(total=7,reserved=0,paid=6,cancelled=1,unattributed=1)
    assert data["period_start"] == "2026-11-14T05:00:00+00:00"


def test_rankings_distinguish_comments_ratings_and_current_users(db_session, product):
    p2=Product(name="Higher",slug="higher",price_cents=100)
    u=User(email="one@example.com",full_name="One",password_hash="test",role="customer",is_active=True)
    u2=User(email="two@example.com",full_name="Two",password_hash="test",role="customer",is_active=False)
    db_session.add_all([p2,u,u2]);db_session.flush()
    db_session.add_all([ProductReview(product_id=product.id,user_id=u.id,rating=4,comment="Good"),
        ProductReview(product_id=product.id,user_id=u2.id,rating=2,comment="  "),
        ProductReview(product_id=p2.id,user_id=u.id,rating=5,comment="")]);db_session.commit()
    data=dashboard(db_session,30)
    assert data["users"] == dict(customers=2,active_customers=1,inactive_customers=1,administrators=0)
    assert data["most_commented"][0]["comments"] == 1
    assert data["most_commented"][0]["ratings"] == 2
    assert data["most_commented"][0]["average_rating"] == 3
    assert data["top_rated"][0]["product_id"] == p2.id


def test_attribution_does_not_modify_legacy_hash_or_idempotent_order(db_session, product):
    data=dict(customer_name="Temporal Persona",customer_phone="0991234567",delivery_address="Direccion temporal 123",items=[dict(product_id=product.id,quantity=1)])
    old=OrderCreate(**data)
    new=OrderCreate(**data,analytics_session_id=uuid4())
    assert _request_hash(old)==_request_hash(new)
    key=str(uuid4())
    original=create_order(db_session,old,key)
    retry=create_order(db_session,new,key)
    assert retry.id==original.id and retry.analytics_session_id is None
    created=create_order(db_session,new,str(uuid4()))
    assert created.analytics_session_id==str(new.analytics_session_id)


def test_conflicting_event_rolls_back_entire_batch(anon_client, db_session, product):
    original=event(product)
    assert anon_client.post("/api/v1/analytics/events",json={"events":[original]}).status_code==202
    fresh=event(product)
    result=anon_client.post("/api/v1/analytics/events",json={"events":[fresh,dict(original,event_type="reviews_open")]})
    assert result.status_code==409
    db_session.expire_all()
    assert db_session.get(AnalyticsEvent,fresh["event_id"]) is None
    assert db_session.query(AnalyticsEvent).count()==1

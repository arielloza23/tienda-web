from datetime import datetime, timedelta, timezone
from sqlalchemy import and_, case, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session
from app.models.analytics import AnalyticsEvent as Event
from app.models.order import Order, OrderItem
from app.models.product import Product, ProductVariant
from app.models.review import ProductReview
from app.models.user import User
from app.schemas.analytics import AnalyticsBatch, EVENT_TYPES


def ingest_events(db: Session, payload: AnalyticsBatch):
    # Valida todo el lote antes de escribir. Nunca acepta timestamps del navegador.
    unique = {}
    duplicates = 0
    fields = ("session_id", "event_type", "product_id", "variant_id", "target")
    for event in payload.events:
        data = event.model_dump(mode="json")
        eid = data["event_id"]
        if eid in unique:
            if unique[eid] != data:
                raise ValueError("event_conflict")
            duplicates += 1
        else:
            unique[eid] = data
    products = {p.id: p for p in db.query(Product).filter(Product.id.in_(
        {v["product_id"] for v in unique.values() if v["product_id"] is not None})).all()}
    variants = {v.id: v for v in db.query(ProductVariant).filter(ProductVariant.id.in_(
        {v["variant_id"] for v in unique.values() if v["variant_id"] is not None})).all()}
    for data in unique.values():
        pid, vid = data["product_id"], data["variant_id"]
        if pid is not None and (pid not in products or not products[pid].is_active):
            raise LookupError("Producto no disponible.")
        if vid is not None and (vid not in variants or variants[vid].product_id != pid):
            raise LookupError("La variante no pertenece al producto.")
    accepted = 0
    try:
        for eid, data in unique.items():
            existing = db.get(Event, eid)
            if existing:
                if any(getattr(existing, k) != data[k] for k in fields):
                    raise ValueError("event_conflict")
                duplicates += 1
                continue
            # Upsert atomico, sin SAVEPOINT que SQLite podria confirmar por separado.
            insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
            result = db.execute(insert(Event).values(**data).on_conflict_do_nothing(index_elements=["event_id"]))
            if result.rowcount:
                accepted += 1
            else:
                existing = db.get(Event, eid)
                if existing is None or any(getattr(existing, k) != data[k] for k in fields):
                    raise ValueError("event_conflict")
                duplicates += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"accepted": accepted, "duplicates": duplicates}


def dashboard(db: Session, days: int, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(timezone(timedelta(hours=-5)))
    start = (local.replace(hour=0, minute=0, second=0, microsecond=0)
             - timedelta(days=days - 1)).astimezone(timezone.utc)
    lower, upper = start.replace(tzinfo=None), now.replace(tzinfo=None)
    window = (Event.created_at >= lower, Event.created_at <= upper)
    first = (select(Event.product_id.label("pid"), Event.session_id.label("sid"),
                    func.min(Event.created_at).label("first_view"))
             .where(*window, Event.event_type == "product_view")
             .group_by(Event.product_id, Event.session_id).subquery())
    views = dict(db.execute(select(first.c.pid, func.count()).group_by(first.c.pid)).all())
    stages = {}
    for pid, kind, count in db.execute(select(Event.product_id, Event.event_type,
            func.count(func.distinct(Event.session_id))).join(first,
            and_(Event.product_id == first.c.pid, Event.session_id == first.c.sid,
                 Event.created_at >= first.c.first_view))
            .where(*window, Event.event_type.in_(["add_to_cart", "checkout_start"]))
            .group_by(Event.product_id, Event.event_type)):
        stages[(pid, kind)] = count
    paid_states = ["paid", "shipped", "delivered"]
    order_stages = {}
    # Distinct sessions, never order lines or units. Repeated lines cannot fan out.
    for pid, orders, paid in db.execute(select(OrderItem.product_id,
            func.count(func.distinct(Order.analytics_session_id)),
            func.count(func.distinct(case((Order.status.in_(paid_states), Order.analytics_session_id)))))
            .join(Order, Order.id == OrderItem.order_id)
            .join(first, and_(first.c.pid == OrderItem.product_id, first.c.sid == Order.analytics_session_id,
                             Order.created_at >= first.c.first_view))
            .where(Order.created_at >= lower, Order.created_at <= upper)
            .group_by(OrderItem.product_id)):
        order_stages[pid] = (orders, paid)
    products = []
    for product in db.query(Product).order_by(Product.name, Product.id):
        count = views.get(product.id, 0)
        orders, paid = order_stages.get(product.id, (0, 0))
        products.append({"product_id": product.id, "product_name": product.name,
            "view_sessions": count, "cart_sessions": stages.get((product.id, "add_to_cart"), 0),
            "checkout_sessions": stages.get((product.id, "checkout_start"), 0),
            "order_sessions": orders, "paid_sessions": paid,
            "order_conversion": round(orders * 100 / count, 2) if count else None,
            "payment_conversion": round(paid * 100 / count, 2) if count else None})
    products.sort(key=lambda p: (-p["view_sessions"], p["product_id"]))
    interactions = {kind: {"event_type": kind, "events": 0, "sessions": 0} for kind in EVENT_TYPES}
    for kind, count, sessions in db.execute(select(Event.event_type, func.count(),
            func.count(func.distinct(Event.session_id))).where(*window).group_by(Event.event_type)):
        if kind in interactions:
            interactions[kind].update(events=count, sessions=sessions)
    rankings = []
    for pid, name, comments, ratings, avg in db.execute(select(Product.id, Product.name,
            func.sum(case((func.length(func.trim(ProductReview.comment)) > 0, 1), else_=0)),
            func.count(ProductReview.id), func.avg(ProductReview.rating))
            .join(ProductReview, ProductReview.product_id == Product.id)
            .group_by(Product.id, Product.name)):
        rankings.append({"product_id": pid, "product_name": name, "comments": comments,
                         "ratings": ratings, "average_rating": round(float(avg), 2)})
    users = {"customers": 0, "active_customers": 0, "inactive_customers": 0, "administrators": 0}
    for role, active, count in db.execute(select(User.role, User.is_active, func.count()).group_by(User.role, User.is_active)):
        if role == "customer":
            users["customers"] += count
            users["active_customers" if active else "inactive_customers"] += count
        elif role == "admin":
            users["administrators"] += count
    orders = {"total": 0, "reserved": 0, "paid": 0, "cancelled": 0, "unattributed": 0}
    for status, sid, count in db.execute(select(Order.status, Order.analytics_session_id, func.count())
            .where(Order.created_at >= lower, Order.created_at <= upper)
            .group_by(Order.status, Order.analytics_session_id)):
        orders["total"] += count
        if status in ("reserved", "cancelled"):
            orders[status] += count
        if status in paid_states:
            orders["paid"] += count
        if sid is None:
            orders["unattributed"] += count
    started = db.scalar(select(func.min(Event.created_at)))
    return {"generated_at": now.isoformat(), "days": days, "period_start": start.isoformat(),
        "period_end": now.isoformat(), "timezone": "America/Guayaquil",
        "measurement_started_at": started.replace(tzinfo=timezone.utc).isoformat() if started else None,
        "users": users, "orders": orders, "interactions": list(interactions.values()),
        "most_commented": sorted([r for r in rankings if r["comments"] > 0], key=lambda r: (-r["comments"], -r["ratings"], r["product_id"]))[:10],
        "top_rated": sorted(rankings, key=lambda r: (-r["average_rating"], -r["ratings"], r["product_id"]))[:10],
        "products": products}

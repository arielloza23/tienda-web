"""Manual migration/query validation on an isolated PostgreSQL branch only."""
import getpass
import os
import sys
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path.cwd() / 'backend'))
print('READY_FOR_TEMPORARY_DATABASE', flush=True)
url = getpass.getpass('Temporary branch connection (hidden): ').strip()
if 'ep-falling-moon-bcthuh1c' in url or '-pooler.' in url or not url.startswith('postgresql://'):
    raise SystemExit('A direct isolated database is required')
url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
os.environ['DATABASE_URL'] = url
os.environ['APP_ENV'] = 'test'
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.models.analytics import AnalyticsEvent
from app.models.product import Product
from app.models.order import Order
from app.schemas.order import OrderCreate
from app.schemas.analytics import AnalyticsBatch
from app.services.analytics_service import dashboard, ingest_events
from app.services.order_service import create_order
engine = create_engine(url, connect_args={'connect_timeout': 15})
config = Config(str(Path.cwd() / 'backend/alembic.ini'))
config.set_main_option('script_location', str(Path.cwd() / 'backend/alembic'))
def counts():
    with engine.connect() as connection:
        return tuple(connection.execute(text('SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM products), (SELECT count(*) FROM orders), (SELECT count(*) FROM product_reviews), (SELECT coalesce(sum(stock_quantity),0) FROM product_variants)')).one())
try:
    before = counts()
    command.upgrade(config, 'head'); assert counts() == before
    command.downgrade(config, '20261120_inventory'); assert counts() == before
    command.upgrade(config, 'head'); assert counts() == before
    command.upgrade(config, 'head'); assert counts() == before
    print('POSTGRES_ANALYTICS_MIGRATION_OK: upgrade/downgrade/reupgrade preserved users/products/orders/reviews/stock.',flush=True)
    with Session(engine) as db:
        product=Product(name='Temporary dashboard validation',slug='dashboard-'+uuid4().hex,price_cents=100,stock_quantity=2)
        db.add(product);db.commit();pid=product.id
        sid,eid=str(uuid4()),str(uuid4())
        batch=AnalyticsBatch(events=[dict(event_id=eid,session_id=sid,event_type='product_view',product_id=pid)])
        assert ingest_events(db,batch)=={'accepted':1,'duplicates':0}
        assert ingest_events(db,batch)=={'accepted':0,'duplicates':1}
        body=OrderCreate(customer_name='Validation customer',customer_phone='0991234567',delivery_address='Temporary address 123',analytics_session_id=sid,items=[dict(product_id=pid,quantity=1)])
        oid=create_order(db,body,idempotency_key=str(uuid4())).id
        result=dashboard(db,30)
        row=next(p for p in result['products'] if p['product_id']==pid)
        assert row['view_sessions']==1 and row['order_sessions']==1 and row['order_conversion']==100,row
        assert row['payment_conversion']==0,row
        db.get(Order,oid).status='paid';db.commit()
        row=next(p for p in dashboard(db,30)['products'] if p['product_id']==pid)
        assert row['paid_sessions']==1 and row['payment_conversion']==100,row
        db.get(Order,oid).status='cancelled';db.commit()
        row=next(p for p in dashboard(db,30)['products'] if p['product_id']==pid)
        assert row['payment_conversion']==0,row
    print('POSTGRES_ANALYTICS_QUERIES_OK: dedup/cohort/server-order/current-payment/cancellation.',flush=True)
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    concurrent_event=dict(event_id=str(uuid4()),session_id=str(uuid4()),event_type='product_view',product_id=pid)
    barrier=Barrier(4)
    def send_duplicate(_):
        with Session(engine) as db:
            barrier.wait(timeout=30)
            return ingest_events(db,AnalyticsBatch(events=[concurrent_event]))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(send_duplicate,range(4)))
    assert sum(r['accepted'] for r in results)==1,results
    assert sum(r['duplicates'] for r in results)==3,results
    print('POSTGRES_ANALYTICS_CONCURRENCY_OK: four identical concurrent events persisted once.',flush=True)

finally:
    engine.dispose()

"""Validate migrations and inventory races on a dedicated Neon validation branch only."""
import os
import sys
import getpass
from pathlib import Path
from uuid import uuid4
from threading import Barrier
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, str(Path.cwd() / 'backend'))
print('READY_FOR_TEMPORARY_DATABASE', flush=True)
url = getpass.getpass('Temporary branch connection (hidden): ').strip()
if 'ep-falling-moon-bcthuh1c' in url or '-pooler.' in url or not url.startswith('postgresql://'):
    raise SystemExit('Validation requires a direct isolated connection')
url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
os.environ['DATABASE_URL'] = url
os.environ['APP_ENV'] = 'test'
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config
from app.models.product import Product, ProductVariant
from app.models.order import Order
from app.schemas.order import OrderCreate
from app.services import order_service
engine = create_engine(url, connect_args={'connect_timeout': 15})
config=Config(str(Path.cwd() / 'backend/alembic.ini'))
config.set_main_option('script_location', str(Path.cwd() / 'backend/alembic'))

def counts():
    with engine.connect() as c:
        return tuple(c.execute(text('SELECT (SELECT count(*) FROM products), (SELECT count(*) FROM users), (SELECT count(*) FROM orders)')).one())

def stock(pid):
    with Session(engine) as db:
        product=db.get(Product,pid)
        return product.variants[0].stock_quantity if product.variants else product.stock_quantity

def pending(pid, variant_id=None):
    with Session(engine) as db:
        item={'product_id':pid, 'quantity':1}
        if variant_id is not None: item['variant_id']=variant_id
        body=OrderCreate(customer_name='Validation customer', customer_phone='0991234567',
            delivery_address='Temporary validation address', items=[item])
        return order_service.create_order(db,body).id

def transition(oid,status):
    with Session(engine) as db:
        return order_service.update_order_status(db,oid,status).status

try:
    before=counts()
    command.upgrade(config,'head')
    assert counts()==before
    command.upgrade(config,'head')
    assert counts()==before
    with engine.connect() as c:
        assert c.execute(text('SELECT count(*) FROM products WHERE stock_quantity<>1')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM product_variants WHERE stock_quantity<>1')).scalar_one()==0
        assert c.execute(text('SELECT count(*) FROM orders WHERE inventory_deducted IS TRUE')).scalar_one()==0
    print('POSTGRES_MIGRATION_OK: existing products, users and orders preserved; stocks initialized to one; legacy orders not deducted.',flush=True)
    suffix=uuid4().hex[:10]
    with Session(engine) as db:
        product=Product(name='Inventory validation',slug='inventory-validation-'+suffix,price_cents=100,
            variants=[ProductVariant(sku='INV-M-'+suffix,size='M',color='Negro',stock_quantity=1)])
        db.add(product);db.commit();pid=product.id;vid=product.variants[0].id
    first,second=pending(pid,vid),pending(pid,vid)
    assert stock(pid)==1
    barrier=Barrier(2)
    original=order_service.get_order_by_id
    def synchronized_read(db,oid):
        order=original(db,oid)
        barrier.wait(timeout=30)
        return order
    order_service.get_order_by_id=synchronized_read
    def reserve(oid):
        try:
            transition(oid,'reserved');return ('ok',oid)
        except ValueError:
            return ('conflict',oid)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(reserve,[first,second]))
    order_service.get_order_by_id=original
    assert sum(result[0]=='ok' for result in outcomes)==1,outcomes
    winner=next(oid for result,oid in outcomes if result=='ok')
    loser=next(oid for result,oid in outcomes if result=='conflict')
    assert stock(pid)==0
    transition(winner,'paid');assert stock(pid)==0
    barrier=Barrier(2)
    order_service.get_order_by_id=synchronized_read
    def cancel(oid):
        try:
            transition(oid,'cancelled');return True
        except ValueError:return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(cancel,[winner,winner]))==[False,True]
    order_service.get_order_by_id=original
    assert stock(pid)==1
    try: transition(winner,'cancelled')
    except ValueError: pass
    else: raise AssertionError('Cancellation repeated unexpectedly')
    assert stock(pid)==1
    transition(loser,'reserved');assert stock(pid)==0
    transition(loser,'cancelled');assert stock(pid)==1
    print('POSTGRES_RACE_OK: only one order reserves last unit; pay no double deduction; two simultaneous cancellations return exactly once.',flush=True)
except Exception as exc:
    print('POSTGRES_VALIDATION_FAILED',type(exc).__name__,flush=True)
    raise SystemExit(1)
finally:
    engine.dispose()
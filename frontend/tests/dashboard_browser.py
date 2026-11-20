"""Real frontend/API integration with temporary inventory and orders only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import re
import threading
import time
sys.path.insert(0,str(Path.cwd()/'backend'))
import uvicorn
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.product import Product, ProductVariant
from app.models.order import Order
from app.models.analytics import AnalyticsEvent
from playwright.sync_api import sync_playwright, expect
database_directory=tempfile.TemporaryDirectory(prefix='dashboard-browser-',dir=Path.cwd()/'.pytest_cache')
database_path=Path(database_directory.name)/'browser.db'
engine=create_engine(f'sqlite:///{database_path.as_posix()}',connect_args={'check_same_thread':False})
Base.metadata.create_all(engine)
sessions=sessionmaker(bind=engine)
with sessions() as db:
    db.add(User(email='admin@example.com',full_name='Temporary admin',role='admin',is_active=True,password_hash=hash_password('test-password-123')))
    db.add(Product(name='Body inventario',slug='body-inventario',price_cents=1200,is_active=True,image_url='https://images.test/cover.png',variants=[
        ProductVariant(sku='INV-M-NEGRO',size='M',color='Negro',stock_quantity=1),
        ProductVariant(sku='INV-L-NEGRO',size='L',color='Negro',stock_quantity=0)]))
    db.commit()
    pid=db.scalar(select(Product.id));vid=db.scalar(select(ProductVariant.id).where(ProductVariant.size=='M'))
def override_db():
    with sessions() as db:yield db
app.dependency_overrides[get_db]=override_db
settings.auth_enabled=True
settings.cors_origins[:]=['http://127.0.0.1:8124']
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        if self.path.endswith('.js'):
            body=Path(self.translate_path(self.path)).read_bytes().replace(b'https://tienda-web-api.onrender.com',b'http://127.0.0.1:8123')
            self.send_response(200);self.send_header('Content-Type','application/javascript');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        else:super().do_GET()
static=ThreadingHTTPServer(('127.0.0.1',8124),partial(QuietHandler,directory=str(Path.cwd()/'frontend/dist/frontend/browser')))
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8123,log_level='warning'))
threads=[threading.Thread(target=server.run,daemon=True),threading.Thread(target=static.serve_forever,daemon=True)]
for thread in threads:thread.start()
for _ in range(100):
    if server.started:break
    time.sleep(.1)
assert server.started
image=BytesIO();Image.new('RGB',(30,40),'teal').save(image,'PNG')
try:
    with sync_playwright() as p:
        for browser_type in ('chromium', 'webkit'):
            browser=getattr(p,browser_type).launch(**({'executable_path':'C:/Program Files/Google/Chrome/Application/chrome.exe'} if browser_type=='chromium' else {}),headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('https://images.test/**',lambda route:route.fulfill(content_type='image/png',body=image.getvalue()))
            page.route('https://fonts.googleapis.com/**',lambda route:route.fulfill(content_type='text/css',body=''))
            page.goto('http://127.0.0.1:8124/')
            expect(page.locator('.showcase-details > h2')).to_have_text('Body inventario')
            page.get_by_role('button',name='Talla M, Negro',exact=True).click()
            page.get_by_role('button',name='A\u00f1adir a mi pedido',exact=True).click()
            page.locator('.topbar .cart-link').click()
            page.wait_for_timeout(2500)
            with sessions() as db:
                kinds=set(db.scalars(select(AnalyticsEvent.event_type)).all())
                assert {'product_view','variant_select','add_to_cart','checkout_start'} <= kinds,kinds
                sid=db.scalar(select(AnalyticsEvent.session_id).where(AnalyticsEvent.event_type=='product_view').order_by(AnalyticsEvent.created_at.desc()))
            response=page.request.post('http://127.0.0.1:8123/api/v1/orders',data={
                'customer_name':'Temporary dashboard customer','customer_phone':'0991234567','delivery_address':'Temporary address 123',
                'analytics_session_id':sid,'items':[{'product_id':pid,'variant_id':vid,'quantity':1}]})
            assert response.status==201,response.text()
            with sessions() as db:
                db.get(Order,response.json()['id']).status='paid';db.commit()
            page.goto('http://127.0.0.1:8124/#/admin')
            page.get_by_label('Correo electr\u00f3nico').fill('admin@example.com')
            page.get_by_label('Contrase\u00f1a',exact=True).fill('test-password-123')
            page.get_by_role('button',name='Iniciar sesi\u00f3n').click()
            page.get_by_role('button',name='Indicadores',exact=True).click()
            expect(page.get_by_role('heading',name='Conversi\u00f3n por producto',exact=True)).to_be_visible()
            expect(page.locator('.dashboard tbody')).to_contain_text('Body inventario')
            expect(page.locator('.dashboard tbody')).to_contain_text('100 %')
            expect(page.locator('.dashboard .error')).to_have_count(0)
            page.get_by_role('button',name='7 d\u00edas',exact=True).click()
            expect(page.get_by_role('button',name='7 d\u00edas',exact=True)).to_have_attribute('aria-pressed','true')
            expect(page.locator('.dashboard table')).to_be_visible()
            for width in (390,320):
                page.set_viewport_size({'width':width,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), (browser_type,width,page.evaluate('[...document.querySelectorAll("body *")].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width])'))
            page.screenshot(path=str(Path.cwd()/'.pytest_cache'/('dashboard-'+browser_type+'-mobile.png')),full_page=True)
            page.get_by_role('button',name='Cerrar sesi\u00f3n').click()
            expect(page.locator('app-admin-dashboard')).to_have_count(0)
            assert not errors,errors
            browser.close()
            print('DASHBOARD_BROWSER_OK:',browser_type,'real API events/admin/cohort/period/mobile/logout')
finally:
    server.should_exit=True;static.shutdown();static.server_close()
    for thread in threads:thread.join(timeout=10)
    engine.dispose()
    assert Path(database_directory.name).resolve().is_relative_to((Path.cwd()/'.pytest_cache').resolve())
    database_directory.cleanup()

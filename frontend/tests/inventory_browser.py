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
from playwright.sync_api import sync_playwright, expect
database_directory=tempfile.TemporaryDirectory(prefix='inventory-browser-',dir=Path.cwd()/'.pytest_cache')
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
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('https://images.test/**',lambda route:route.fulfill(content_type='image/png',body=image.getvalue()))
        page.route('https://fonts.googleapis.com/**',lambda route:route.fulfill(content_type='text/css',body=''))
        def quantity():
            with sessions() as db:return db.get(ProductVariant,vid).stock_quantity
        orders=[]
        for _ in range(2):
            response=page.request.post('http://127.0.0.1:8123/api/v1/orders',data={
                'customer_name':'Temporary customer','customer_phone':'0991234567','delivery_address':'Temporary address 123',
                'items':[{'product_id':pid,'variant_id':vid,'quantity':1,'expected_unit_price_cents':1200}]})
            assert response.status==201,response.text()
            orders.append(response.json()['id'])
        assert quantity()==1
        page.goto('http://127.0.0.1:8124/#/admin')
        page.get_by_label('Correo electr\u00f3nico').fill('admin@example.com')
        page.get_by_label('Contrase\u00f1a',exact=True).fill('test-password-123')
        page.get_by_role('button',name='Iniciar sesi\u00f3n').click()
        expect(page.get_by_role('heading',name='Crear producto',exact=True)).to_be_visible()
        page.get_by_role('button',name='Pedidos',exact=True).click()
        def choose(oid):page.locator('button.order-row').filter(has_text=f'Pedido #{oid}').click()
        choose(orders[0]);page.get_by_role('button',name='Reservar pedido',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Reservado');assert quantity()==0
        choose(orders[1]);page.get_by_role('button',name='Reservar pedido',exact=True).click()
        expect(page.locator('.orders [role=alert]')).to_be_visible()
        expect(page.locator('.detail h3')).to_contain_text('Pendiente');assert quantity()==0
        choose(orders[0]);page.get_by_role('button',name='Cancelar pedido',exact=True).click()
        page.get_by_role('button',name='S\u00ed, cancelar pedido',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Cancelado');assert quantity()==1
        choose(orders[1]);page.get_by_role('button',name='Reservar pedido',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Reservado');assert quantity()==0
        page.get_by_role('button',name='Marcar como pagado',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Pagado');assert quantity()==0
        page.get_by_role('button',name='Cancelar pedido',exact=True).click()
        page.get_by_role('button',name='S\u00ed, cancelar pedido',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Cancelado');assert quantity()==1
        page.get_by_role('button',name='Productos',exact=True).click()
        stock_button=page.get_by_role('button',name='Ajustar stock de Body inventario, M, Negro',exact=True)
        stock_button.click();page.locator('#stock-quantity').fill('3')
        page.get_by_role('button',name='Guardar stock',exact=True).click()
        expect(page.locator('[role=status]')).to_contain_text(re.compile('stock', re.I))
        assert quantity()==3
        stock_button.click();page.locator('#stock-quantity').fill('4')
        with sessions() as db:
            db.get(ProductVariant,vid).stock_quantity=2;db.commit()
        page.get_by_role('button',name='Guardar stock',exact=True).click()
        expect(page.locator('[role=alert]')).to_contain_text(re.compile('stock', re.I))
        assert quantity()==2
        page.get_by_role('link',name='Volver a la tienda',exact=True).click()
        expect(page.get_by_role('button',name='Talla L, Negro',exact=True)).to_have_count(0)
        page.get_by_role('button',name='Talla M, Negro',exact=True).click()
        add=page.get_by_role('button',name='A\u00f1adir a mi pedido',exact=True)
        add.click();add.click()
        expect(page.locator('.topbar .cart-count')).to_have_text('2')
        add.click();expect(page.locator('.topbar .cart-count')).to_have_text('2')
        page.locator('.topbar .cart-link').click()
        expect(page.locator('.quantity-control button').last).to_be_disabled()
        for width in (390,320):
            page.set_viewport_size({'width':width,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        # All sizes exhausted: the product disappears from both catalog and showcase.
        with sessions() as db:
            db.get(ProductVariant,vid).stock_quantity=0;db.commit()
        page.reload()
        expect(page.locator('.product-miniature')).to_have_count(0)
        expect(page.locator('.showcase-details > h2')).to_have_count(0)
        expect(page.get_by_text('No hay productos disponibles.',exact=True)).to_be_visible()
        with sessions() as db:
            db.get(ProductVariant,vid).stock_quantity=1;db.commit()
        page.reload()
        expect(page.locator('.product-miniature')).to_have_count(1)
        expect(page.locator('.showcase-details > h2')).to_have_text('Body inventario')
        assert not errors,errors
        browser.close()
        print('INVENTORY_BROWSER_OK: pending no deduction; reserve/conflict/pay/cancel; stock adjustment/stale conflict; sold-out size/cart limits; desktop/mobile.')
finally:
    server.should_exit=True;static.shutdown();static.server_close()
    for thread in threads:thread.join(timeout=10)
    engine.dispose()
    assert Path(database_directory.name).resolve().is_relative_to((Path.cwd()/'.pytest_cache').resolve())
    database_directory.cleanup()
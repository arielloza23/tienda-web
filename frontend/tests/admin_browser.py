from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path.cwd() / "backend"))
import uvicorn
from PIL import Image
from pydantic import SecretStr
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.models.order import Order
from app.models.product import Product
from app.services import image_service
from playwright.sync_api import sync_playwright, expect

# Todos los datos y las fotos de esta prueba son temporales.
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
sessions = sessionmaker(bind=engine)
with sessions() as db:
    db.add(User(email="admin@example.com", full_name="Admin de prueba", role="admin", is_active=True, password_hash=hash_password("test-password-123")))
    db.add(Product(name="Producto base", slug="producto-base", price_cents=1000, is_active=True))
    db.commit()

def override_db():
    with sessions() as db: yield db
app.dependency_overrides[get_db] = override_db
settings.auth_enabled = True
settings.cors_origins[:] = ["http://127.0.0.1:8124"]
settings.aws_endpoint_url_s3 = "https://storage.example"
settings.aws_access_key_id = "test"
settings.aws_secret_access_key = SecretStr("test")
settings.product_images_bucket = "photos"
settings.product_images_public_url = "https://images.test"
writes = []
class FakeStorage:
    def put_object(self, **kwargs): writes.append(kwargs)
image_service.get_storage_client = lambda: FakeStorage()

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        if self.path.endswith('.js'):
            body = Path(self.translate_path(self.path)).read_bytes().replace(b'https://tienda-web-api.onrender.com', b'http://127.0.0.1:8123')
            self.send_response(200)
            self.send_header('Content-Type', 'application/javascript')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
        else: super().do_GET()
static = ThreadingHTTPServer(("127.0.0.1", 8124), partial(QuietHandler, directory=str(Path.cwd() / "frontend/dist/frontend/browser")))
server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8123, log_level="warning"))
threads = [threading.Thread(target=server.run, daemon=True), threading.Thread(target=static.serve_forever, daemon=True)]
for thread in threads: thread.start()
for _ in range(100):
    if server.started: break
    time.sleep(0.1)
assert server.started
buffer = BytesIO(); Image.new("RGB", (30, 40), "red").save(buffer, format="PNG")
image_data = buffer.getvalue()
try:
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
        photo = Path(folder) / "photo.png"; photo.write_bytes(image_data)
        browser = playwright.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("https://images.test/**", lambda route: route.fulfill(status=200, content_type="image/png", body=image_data))
        page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, content_type="text/css", body=""))
        page.route("https://images.pexels.com/**", lambda route: route.fulfill(status=200, content_type="image/png", body=image_data))
        page.goto("http://127.0.0.1:8124/#/admin")
        page.get_by_label("Correo electrónico").fill("admin@example.com")
        page.get_by_label("Contraseña", exact=True).fill("test-password-123")
        page.get_by_role("button", name="Iniciar sesión").click()
        expect(page.get_by_role("heading", name="Crear producto", exact=True)).to_be_visible()
        page.get_by_label("Nombre", exact=True).fill("Body de prueba")
        page.get_by_label("Descripción", exact=True).fill("Descripción completa de prueba")
        page.get_by_label("Precio base (USD)").fill("15,50")
        page.get_by_label("Publicar como producto activo").uncheck()
        page.get_by_role("button", name="Agregar variante").click()
        page.get_by_label("SKU único").fill("BODY-VINO-M")
        page.get_by_label("Talla", exact=True).fill("M")
        page.get_by_label("Color", exact=True).fill("Vino")
        page.get_by_label("Importe adicional (USD)").fill("2.00")
        page.locator('#bust_cm-0').fill('92.5')
        page.locator('#waist_cm-0').fill('74')
        page.locator('#hip_cm-0').fill('98')
        page.locator("#cover-file").set_input_files(str(photo))
        expect(page.locator(".cover-preview img")).to_be_visible()
        page.get_by_role("button", name="Agregar foto").click()
        page.locator("#gallery-file-0").set_input_files(str(photo))
        expect(page.locator(".gallery-preview")).to_be_visible()
        page.get_by_label("Descripción de la foto").fill("Vista frontal")
        page.get_by_role("button", name="Crear producto", exact=True).click()
        expect(page.get_by_role("status")).to_contain_text("creado como borrador")
        assert len(writes) == 2
        with sessions() as db:
            created = db.scalars(select(Product).where(Product.slug == "body-de-prueba")).one()
            assert created.price_cents == 1550 and not created.is_active
            assert created.variants[0].price_adjustment_cents == 200 and created.images[0].color == "Vino"
            assert float(created.variants[0].bust_cm) == 92.5
            assert float(created.variants[0].waist_cm) == 74
            original_id = created.id
            original_variant_id = created.variants[0].id
            original_cover = created.image_url
            original_photo = created.images[0].url
        row = page.locator("li.product-row").filter(has_text="Body de prueba")
        row.get_by_role("button", name="Editar", exact=True).click()
        expect(page.get_by_role("heading", name="Editar producto", exact=True)).to_be_visible()
        expect(page.get_by_label("Nombre", exact=True)).to_have_value("Body de prueba")
        expect(page.locator('#bust_cm-0')).to_have_value('92.5')
        expect(page.get_by_label("Precio base (USD)")).to_have_value("15.50")
        expect(page.locator(".gallery-preview")).to_be_visible()
        page.get_by_label("Nombre", exact=True).fill("Cambio sin guardar")
        page.get_by_role("button", name="Cancelar edición", exact=True).click()
        expect(page.get_by_role("heading", name="Crear producto", exact=True)).to_be_visible()
        expect(row).to_contain_text("Body de prueba")
        row.get_by_role("button", name="Editar", exact=True).click()
        page.get_by_label("Nombre", exact=True).fill("Body actualizado")
        page.get_by_label("Precio base (USD)").fill("18,75")
        page.get_by_label("Talla", exact=True).fill("L")
        page.get_by_label("Publicar como producto activo").check()
        # Error del servidor: no perder la edición ni mutar el listado.
        update_route = "**/api/v1/products/" + str(original_id)
        page.route(update_route, lambda route: route.fulfill(status=409, content_type="application/json", body='{"detail":"Conflicto de prueba"}'))
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        expect(page.get_by_role("alert")).to_contain_text("Conflicto de prueba")
        expect(page.get_by_label("Nombre", exact=True)).to_have_value("Body actualizado")
        expect(row).to_contain_text("Body de prueba")
        page.unroute(update_route)
        page.get_by_role("button", name="Guardar cambios", exact=True).click()
        expect(page.get_by_role("status")).to_contain_text("actualizado")
        expect(page.get_by_role("heading", name="Crear producto", exact=True)).to_be_visible()
        expect(page.locator("li.product-row").filter(has_text="Body actualizado")).to_have_count(1)
        assert len(writes) == 2  # Las fotos existentes no se vuelven a subir.
        with sessions() as db:
            edited = db.get(Product, original_id)
            assert edited.name == "Body actualizado" and edited.price_cents == 1875 and edited.is_active
            assert edited.variants[0].id == original_variant_id and edited.variants[0].size == "L"
            assert edited.image_url == original_cover and edited.images[0].url == original_photo
        assert not any(value in page.evaluate("JSON.stringify(localStorage)") for value in ("access_token", "Bearer", "test-password-123"))
        page.get_by_role("link", name="Volver a la tienda").click()
        expect(page.locator(".topbar")).to_be_visible()
        page.get_by_role("link", name="Catálogo", exact=True).click()
        assert page.url.endswith("/#/")
        expect(page.locator(".product-miniature")).to_have_count(2)
        page.get_by_role("link", name="Administración", exact=True).click()
        expect(page.get_by_role("heading", name="Crear producto", exact=True)).to_be_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        # Crear un pedido invitado temporal y atenderlo desde el administrador.
        response = page.request.post('http://127.0.0.1:8123/api/v1/orders', data={
            'customer_name': 'Cliente temporal', 'customer_phone': '0991234567',
            'delivery_address': 'Dirección temporal de prueba',
            'items': [{'product_id': 1, 'quantity': 1, 'expected_unit_price_cents': 1000}],
        })
        assert response.status == 201, response.status
        order_id = response.json()['id']
        page.get_by_role('button',name='Pedidos',exact=True).click()
        expect(page.get_by_role('heading',name='Crear producto',exact=True)).not_to_be_visible()
        page.locator('button.order-row').filter(has_text=f'Pedido #{order_id}').click()
        expect(page.locator('.detail')).to_contain_text('Cliente temporal')
        page.get_by_role('button',name='Cancelar pedido',exact=True).click()
        expect(page.get_by_role('button',name='Sí, cancelar pedido',exact=True)).to_be_visible()
        page.get_by_role('button',name='Conservar pedido',exact=True).click()
        page.get_by_role('button',name='Marcar como pagado',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Pagado')
        page.get_by_role('button',name='Marcar como enviado',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Enviado')
        page.get_by_role('button',name='Marcar como entregado',exact=True).click()
        expect(page.locator('.detail h3')).to_contain_text('Entregado')
        expect(page.locator('.detail')).to_contain_text('estado final')
        page.locator('#order-filter').select_option('pending')
        expect(page.locator('button.order-row')).to_have_count(0)
        page.locator('#order-filter').select_option('delivered')
        expect(page.locator('button.order-row')).to_have_count(1)
        with sessions() as db:
            assert db.get(Order,order_id).status == 'delivered'
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_role("button", name="Cerrar sesión").click()
        expect(page.get_by_role("button", name="Iniciar sesión")).to_be_visible()
        assert not errors, errors
        browser.close()
        print("BROWSER_OK: admin order transitions, variant measurements, admin login, two file uploads, product creation and editing, cancel, conflict recovery, preserved variants/photos, hash links, mobile layout, logout.")
finally:
    server.should_exit = True; static.shutdown(); static.server_close()
    for thread in threads: thread.join(timeout=10)
    engine.dispose()

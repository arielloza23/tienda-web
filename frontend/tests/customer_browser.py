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
from app.models.product import Product
from app.models.order import Order
from app.services import image_service
from playwright.sync_api import sync_playwright, expect

# Todos los datos y las fotos de esta prueba son temporales.
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(engine)
sessions = sessionmaker(bind=engine)
with sessions() as db:
    db.add(User(email="admin@example.com", full_name="Admin de prueba", role="admin", is_active=True, password_hash=hash_password("test-password-123")))
    db.add(Product(name="Producto base", slug="producto-base", price_cents=1000, is_active=True))
    db.add(Product(name="Producto segundo", slug="producto-segundo", price_cents=1200, is_active=True))
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
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.add_init_script("window.open = () => null")
        errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, content_type="text/css", body=""))
        page.route("https://images.pexels.com/**", lambda route: route.fulfill(status=200, content_type="image/png", body=image_data))
        page.route("**tile.openstreetmap.org/**", lambda route: route.fulfill(status=200, content_type="image/png", body=image_data))
        page.route("https://photon.komoot.io/reverse**", lambda route: route.fulfill(status=200, content_type="application/json", body='{"features":[{"properties":{"street":"Calle de prueba","city":"Quito","country":"Ecuador"}}]}'))
        page.goto("http://127.0.0.1:8124/#/")
        expect(page.locator("#how-it-works")).to_have_count(1)
        expect(page.locator(".showcase > #how-it-works")).to_be_visible()
        layout_box=page.locator(".showcase-layout").bounding_box()
        guide_box=page.locator("#how-it-works").bounding_box()
        assert guide_box["y"] >= layout_box["y"]+layout_box["height"]-1
        for step in ("Encuentra tu pieza", "Marca tu ubicación", "Hablemos por WhatsApp"):
            expect(page.locator("#how-it-works").get_by_text(step, exact=True)).to_be_visible()
        page.locator("#how-it-works").screenshot(path=".local-backups/quick-buy-desktop.png")
        # El cliente puede finalizar su pedido sin registrarse ni iniciar sesión.
        page.get_by_role("button", name="Añadir a mi pedido").click()
        page.locator(".topbar").get_by_role("button", name="Tu pedido").click()
        page.get_by_label("Nombre y apellido").fill("Cliente invitado")
        page.get_by_label("Teléfono de contacto").fill("0991234567")
        page.locator(".delivery-location-field").scroll_into_view_if_needed()
        page.get_by_role("button", name="Marcar centro", exact=True).click()
        expect(page.get_by_label("Dirección de entrega", exact=True)).to_have_value("Calle de prueba, Quito, Ecuador")
        # El catálogo cambia mientras el comprador rellena los datos: no crear aún.
        with sessions() as db:
            db.get(Product, 1).price_cents = 1300
            db.commit()
        page.get_by_role("button", name="Confirmar mi pedido").click()
        expect(page.locator(".checkout-error")).to_contain_text("Los precios cambiaron")
        expect(page.locator(".cart-total")).to_contain_text("13.00")
        expect(page.get_by_label("Nombre y apellido")).to_have_value("Cliente invitado")
        expect(page.get_by_label("Dirección de entrega", exact=True)).to_have_value("Calle de prueba, Quito, Ecuador")
        with sessions() as db:
            assert db.scalars(select(Order)).first() is None
        page.get_by_role("button", name="Aceptar precios y confirmar", exact=True).click()
        expect(page.get_by_text("Pedido recibido", exact=True)).to_be_visible()
        with sessions() as db:
            order = db.scalars(select(Order)).one()
            assert order.user_id is None and order.total_cents == 1300
        receipt_id = order.id
        saved = page.evaluate("sessionStorage.getItem('tienda.receipt.v1')")
        assert saved and all(value not in saved for value in ('Cliente invitado', '0991234567', 'Calle de prueba', 'customer_phone', 'delivery_address', 'wa.me'))
        page.get_by_role("button", name="Volver al catálogo", exact=True).click()
        page.reload()
        page.get_by_role("button", name="Último pedido", exact=True).click()
        expect(page.get_by_role("heading", name=f"Resumen del pedido #{receipt_id}", exact=True)).to_be_visible()
        expect(page.locator(".confirmation-total")).to_contain_text("13.00")
        recovered_link = page.locator('.whatsapp-confirmation-link').get_attribute('href')
        from urllib.parse import unquote
        decoded = unquote(recovered_link)
        assert 'Subtotal de productos' in decoded and 'Envío y pago' in decoded
        assert all(value not in decoded for value in ('Cliente invitado','0991234567','Calle de prueba'))
        page.get_by_role("button", name="Olvidar comprobante", exact=True).click()
        assert page.evaluate("sessionStorage.getItem('tienda.receipt.v1')") is None
        page.get_by_role("button", name="Cerrar pedido", exact=True).click()
        expect(page.locator("app-product-reviews")).to_have_count(0)
        page.get_by_role("button", name="Ver opiniones de Producto base", exact=True).click()
        reviews_dialog=page.get_by_role("dialog", name="Opiniones de Producto base", exact=True)
        expect(reviews_dialog).to_be_visible()
        opinions = page.get_by_role("region", name="Opiniones del producto", exact=True)
        expect(opinions.get_by_role("button", name="Iniciar sesión para opinar", exact=True)).to_be_visible()
        opinions.get_by_role("button", name="Iniciar sesión para opinar", exact=True).click()
        account = page.get_by_role("dialog", name="Mi cuenta", exact=True)
        account.get_by_role("button", name="Crear cuenta", exact=True).click()
        account.get_by_label("Nombre visible", exact=True).fill("Cliente de prueba")
        account.get_by_label("Correo electrónico", exact=True).fill("customer@example.com")
        account.get_by_label("Contraseña", exact=True).fill("test-customer-password")
        with page.expect_response(lambda r: r.url.endswith("/api/v1/users"), timeout=5000) as signup_response:
            account.get_by_role("button", name="Registrarme", exact=True).click()
        assert signup_response.value.status == 201
        # El formulario de reseña aparece tras el registro y acceso.
        expect(opinions.get_by_role("radio", name="5 estrellas", exact=True)).to_be_visible()
        assert not any(character.isdigit() for character in opinions.locator(".rating-options").inner_text())
        opinions.get_by_role("radio", name="5 estrellas", exact=True).check()
        opinions.get_by_label("Tu comentario", exact=True).fill("Muy buen producto de prueba")
        opinions.get_by_role("button", name="Publicar opinión", exact=True).click()
        expect(opinions.get_by_text("Muy buen producto de prueba", exact=True)).to_be_visible()
        response = page.request.get("http://127.0.0.1:8123/api/v1/products/1/reviews").json()
        assert response["total"] == 1 and response["average_rating"] == 5
        assert "email" not in str(response) and "password" not in str(response)
        opinions.get_by_role("radio", name="3 estrellas", exact=True).check()
        opinions.get_by_role("radio", name="3 estrellas", exact=True).focus()
        opinions.get_by_role("radio", name="3 estrellas", exact=True).press("ArrowRight")
        expect(opinions.get_by_role("radio", name="4 estrellas", exact=True)).to_be_checked()
        opinions.get_by_role("radio", name="3 estrellas", exact=True).check()
        opinions.get_by_label("Tu comentario", exact=True).fill("Opinión actualizada")
        opinions.get_by_role("button", name="Actualizar opinión", exact=True).click()
        expect(opinions.get_by_text("Opinión actualizada", exact=True)).to_be_visible()
        response = page.request.get("http://127.0.0.1:8123/api/v1/products/1/reviews").json()
        assert response["total"] == 1 and response["average_rating"] == 3
        reviews_dialog.get_by_role("button", name="Cerrar opiniones", exact=True).click()
        expect(page.locator("app-product-reviews")).to_have_count(0)
        page.get_by_role("button", name="Siguiente producto: Producto segundo", exact=True).click()
        page.get_by_role("button", name="Ver opiniones de Producto segundo", exact=True).click()
        expect(page.get_by_role("dialog", name="Opiniones de Producto segundo", exact=True)).to_be_visible()
        expect(opinions.get_by_role("radio", name="3 estrellas", exact=True)).not_to_be_checked()
        expect(opinions.get_by_label("Tu comentario", exact=True)).to_have_value("")
        page.get_by_role("button", name="Cerrar opiniones", exact=True).click()
        page.get_by_role("button", name="Producto anterior: Producto base", exact=True).click()
        page.get_by_role("button", name="Ver opiniones de Producto base", exact=True).click()
        expect(opinions.get_by_label("Tu comentario", exact=True)).to_have_value("Opinión actualizada")
        page.get_by_role("button", name="Cerrar opiniones", exact=True).click()
        page.get_by_role("button", name="Mi cuenta", exact=True).click()
        account.get_by_role("button", name="Cerrar sesión", exact=True).click()
        account.get_by_role("button", name="Cerrar mi cuenta", exact=True).click()
        page.get_by_role("button", name="Ver opiniones de Producto base", exact=True).click()
        expect(opinions.get_by_role("button", name="Iniciar sesión para opinar", exact=True)).to_be_visible()
        expect(opinions.get_by_text("Opinión actualizada", exact=True)).to_be_visible()
        # Volver a entrar por la CTA, con el formulario de acceso existente.
        opinions.get_by_role("button", name="Iniciar sesión para opinar", exact=True).click()
        account.get_by_label("Correo electrónico", exact=True).fill("customer@example.com")
        account.get_by_label("Contraseña", exact=True).fill("test-customer-password")
        account.get_by_role("button", name="Iniciar sesión", exact=True).click()
        expect(opinions.get_by_role("radio", name="3 estrellas", exact=True)).to_be_checked()
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not any(value in page.evaluate("JSON.stringify(localStorage)") for value in ("access_token", "Bearer", "test-customer-password"))
        reviews_dialog.screenshot(path=".local-backups/reviews-mobile.png")
        reviews_dialog.press("Escape")
        expect(page.locator("app-product-reviews")).to_have_count(0)
        expect(page.get_by_role("button", name="Ver opiniones de Producto base", exact=True)).to_be_focused()
        assert not errors, errors
        browser.close()
        print("CUSTOMER_BROWSER_OK: price reconfirmation, safe receipt recovery, guest checkout, signup/login/logout, review 1..5, update without duplicate, public reading, product isolation, mobile layout.")
finally:
    server.should_exit = True; static.shutdown(); static.server_close()
    for thread in threads: thread.join(timeout=10)
    engine.dispose()

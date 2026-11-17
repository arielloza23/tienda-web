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
from app.services import image_service, password_reset_service
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
settings.smtp_host = 'smtp.example.invalid'
settings.smtp_port = 587
settings.smtp_from = 'store@example.com'
settings.smtp_starttls = True
settings.smtp_user = None
settings.password_reset_url = 'http://127.0.0.1:8124/#/reset-password'
sent = []
password_reset_service.send_reset_email = lambda email, token: sent.append((email, token))
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
        page = browser.new_page(viewport={"width":390,"height":844})
        errors = []; page.on("pageerror",lambda e:errors.append(str(e)))
        page.route("https://fonts.googleapis.com/**",lambda r:r.fulfill(status=200,content_type="text/css",body=""))
        page.route("https://images.pexels.com/**",lambda r:r.fulfill(status=200,content_type="image/png",body=image_data))
        old_login=page.request.post('http://127.0.0.1:8123/api/v1/auth/login',data={'email':'admin@example.com','password':'test-password-123'})
        assert old_login.status == 200
        old_token=old_login.json()['access_token']
        page.goto('http://127.0.0.1:8124/#/')
        page.get_by_role('button',name='Mi cuenta',exact=True).click()
        account=page.get_by_role('dialog',name='Mi cuenta',exact=True)
        account.get_by_role('button',name='Olvidé mi contraseña',exact=True).click()
        account.get_by_label('Correo electrónico',exact=True).fill('admin@example.com')
        account.get_by_role('button',name='Enviar enlace',exact=True).click()
        expect(account.locator('[role="status"]')).to_contain_text('Si existe una cuenta activa')
        assert len(sent) == 1
        page.goto('http://127.0.0.1:8124/#/reset-password?token='+sent[0][1])
        expect(page.get_by_role('heading',name='Una nueva contraseña.',exact=True)).to_be_visible()
        expect(page).to_have_url('http://127.0.0.1:8124/#/reset-password')
        page.get_by_label('Nueva contraseña',exact=True).fill('new-test-password-456')
        page.get_by_label('Repite la contraseña',exact=True).fill('new-test-password-456')
        page.get_by_role('button',name='Guardar contraseña',exact=True).click()
        expect(page.get_by_role('status')).to_contain_text('Tu contraseña fue actualizada')
        assert page.request.get('http://127.0.0.1:8123/api/v1/auth/me',headers={'Authorization':'Bearer '+old_token}).status == 401
        assert page.request.post('http://127.0.0.1:8123/api/v1/auth/login',data={'email':'admin@example.com','password':'test-password-123'}).status == 401
        assert page.request.post('http://127.0.0.1:8123/api/v1/auth/login',data={'email':'admin@example.com','password':'new-test-password-456'}).status == 200
        page.goto('http://127.0.0.1:8124/#/reset-password?token='+sent[0][1])
        page.get_by_label('Nueva contraseña',exact=True).fill('another-test-password-789')
        page.get_by_label('Repite la contraseña',exact=True).fill('another-test-password-789')
        page.get_by_role('button',name='Guardar contraseña',exact=True).click()
        expect(page.get_by_role('alert')).to_contain_text('ya venció')
        expect(page.locator('form')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors,errors
        browser.close()
        print('RECOVERY_BROWSER_OK: fake email, secret URL removed, one-use reset, previous sessions revoked and mobile layout')
finally:
    server.should_exit = True; static.shutdown(); static.server_close()
    for thread in threads: thread.join(timeout=10)
    engine.dispose()

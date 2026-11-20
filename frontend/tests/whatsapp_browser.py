"""Checkout WhatsApp handoff in WebKit and Chromium, without real orders or messages."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from io import BytesIO
from urllib.parse import urlparse, parse_qs
import sys
sys.path.insert(0,str(Path.cwd()/"backend"))
from app.schemas.analytics import AnalyticsBatch
import threading
import time
from PIL import Image
from playwright.sync_api import sync_playwright, expect

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

product = {"id": 1, "name": "Body de prueba", "slug": "body-test", "is_active": True,
           "price_cents": 1500, "stock_quantity": 1, "variants": [], "images": [], "image_url": "https://images.test/cover.png"}
receipt = {"id": 77, "status": "pending", "subtotal_cents": 1500, "total_cents": 1500,
           "items": [{"product_id": 1, "product_name": product["name"], "variant_label": None, "quantity": 1, "total_price_cents": 1500}]}
image = BytesIO(); Image.new("RGB", (40, 60), "teal").save(image, "PNG")
server = ThreadingHTTPServer(("127.0.0.1", 8124), partial(QuietHandler, directory=str(Path.cwd() / "frontend/dist/frontend/browser")))
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
try:
    with sync_playwright() as p:
        for engine in (p.webkit, p.chromium):
            options = {"executable_path": "C:/Program Files/Google/Chrome/Application/chrome.exe"} if engine.name == "chromium" else {}
            browser = engine.launch(headless=True, **options)
            for width in (390, 1440):
                context = browser.new_context(viewport={"width": width, "height": 844}, has_touch=True)
                page = context.new_page()
                errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
                posts = []; navigations = []; analytics = []
                def collect(route):
                    if width == 1440:
                        route.abort()  # Measurement unavailable must not block checkout/handoff.
                        return
                    batch = AnalyticsBatch.model_validate(route.request.post_data_json)
                    analytics.extend(e.model_dump(mode='json') for e in batch.events)
                    route.fulfill(status=202,json={"accepted":len(batch.events),"duplicates":0})
                page.route("**/api/v1/analytics/events", collect)
                # Any programmatic popup must never be needed to register or share the order.
                page.add_init_script("window.open = () => { throw new Error('Popup blocked'); }")
                page.route("**/api/v1/products", lambda route: route.fulfill(json=[product]))
                page.route("**/api/v1/products/*/reviews?*", lambda route: route.fulfill(json={"items": [], "total": 0, "average_rating": None, "limit": 10, "offset": 0}))
                page.route("https://images.test/**", lambda route: route.fulfill(content_type="image/png", body=image.getvalue()))
                page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(content_type="text/css", body=""))
                page.route("**tile.openstreetmap.org/**", lambda route: route.fulfill(content_type="image/png", body=image.getvalue()))
                page.route("https://photon.komoot.io/reverse**", lambda route: route.fulfill(json={"features": [{"properties": {"street": "Calle privada", "city": "Quito", "country": "Ecuador"}}]}))
                def create_order(route):
                    posts.append(route.request.post_data_json)
                    time.sleep(1)  # API response arrives after the original click handler.
                    route.fulfill(status=201, json=receipt)
                page.route("**/api/v1/orders", create_order)
                def handoff(route):
                    navigations.append(route.request.url)
                    route.fulfill(content_type="text/html", body="<p>WhatsApp handoff captured. No message sent.</p>")
                page.route("https://wa.me/**", handoff)
                page.goto("http://127.0.0.1:8124/#/")
                page.get_by_role("button", name="A\u00f1adir a mi pedido", exact=True).click()
                page.locator(".topbar").get_by_role("button", name="Tu pedido").click()
                page.get_by_label("Nombre y apellido").fill("Cliente temporal")
                page.get_by_label("Tel\u00e9fono de contacto").fill("0991234567")
                page.locator(".delivery-location-field").scroll_into_view_if_needed()
                page.get_by_role("button", name="Marcar centro", exact=True).click()
                expect(page.get_by_label("Direcci\u00f3n de entrega", exact=True)).to_have_value("Calle privada, Quito, Ecuador")
                page.get_by_role("button", name="Confirmar mi pedido", exact=True).click()
                expect(page.get_by_text("Pedido recibido", exact=True)).to_be_visible()
                link = page.get_by_role("link", name="Continuar en WhatsApp")
                expect(link).to_be_visible()
                assert len(posts) == 1 and not navigations
                assert link.get_attribute("target") is None
                url = link.get_attribute("href")
                assert urlparse(url).path == "/593987506872"
                message = parse_qs(urlparse(url).query)["text"][0]
                assert "#77" in message and "Body de prueba" in message and ("15.00" in message or "15,00" in message)
                assert not any(value in message for value in ("Cliente temporal", "0991234567", "Calle privada"))
                page.reload()
                page.get_by_role("button", name="\u00daltimo pedido", exact=True).click()
                expect(link).to_have_attribute("href", url)
                expect(page.locator(".topbar .cart-count")).to_have_text("0")
                link.click()
                expect(page).to_have_url(url)
                assert navigations == [url] and len(posts) == 1
                if width == 390:
                    page.wait_for_timeout(500)
                    assert any(e['event_type']=='whatsapp_click' and e['product_id']==1 for e in analytics),analytics
                # Going back preserves the receipt without creating another order.
                page.go_back()
                page.get_by_role("button", name="\u00daltimo pedido", exact=True).click()
                expect(page.get_by_role("heading", name="Resumen del pedido #77", exact=True)).to_be_visible()
                assert len(posts) == 1 and len(context.pages) == 1 and not errors, errors
                context.close()
            browser.close()
            print(f"WHATSAPP_BROWSER_OK: {engine.name}, mobile/desktop, blocked popups, delayed order, direct link, receipt reload/back, one order only.")
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=10)
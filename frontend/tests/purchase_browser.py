"""Prueba visual aislada de selección, guía de medidas y resumen del pedido."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import threading
from PIL import Image
from playwright.sync_api import sync_playwright, expect

products = [{
    "id": 1, "name": "Conjunto de prueba", "slug": "conjunto", "is_active": True,
    "price_cents": 1200, "image_url": "https://images.test/cover.webp",
    "images": [{"id": 1, "url": "https://images.test/red.webp", "alt": "Detalle rojo", "color": " rojo "},
               {"id": 2, "url": "https://images.test/blue.webp", "alt": "Detalle azul", "color": "Azul"}],
    "variants": [{"id": 11, "sku": "M-RED", "size": "M", "color": "Rojo", "price_adjustment_cents": 0, "bust_cm": 92.5, "waist_cm": 74, "hip_cm": 98},
                 {"id": 12, "sku": "M-BLUE", "size": "M", "color": "Azul", "price_adjustment_cents": 200},
                 {"id": 13, "sku": "L-BLUE", "size": "L", "color": "Azul", "price_adjustment_cents": 300}],
}, {"id": 2, "name": "Pieza sin opciones", "slug": "pieza", "is_active": True,
    "price_cents": 900, "image_url": None, "images": [], "variants": []}]

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

server = ThreadingHTTPServer(("127.0.0.1", 8124), partial(QuietHandler, directory=str(Path.cwd() / "frontend/dist/frontend/browser")))
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
image = BytesIO()
Image.new("RGB", (40, 60), "teal").save(image, "PNG")
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.route("**/api/v1/products", lambda r: r.fulfill(json=products))
        page.route("https://images.test/**", lambda r: r.fulfill(content_type="image/png", body=image.getvalue()))
        page.route("https://images.pexels.com/**", lambda r: r.fulfill(content_type="image/png", body=image.getvalue()))
        page.route("https://fonts.googleapis.com/**", lambda r: r.fulfill(content_type="text/css", body=""))
        page.goto("http://127.0.0.1:8124/#/")
        guide_trigger = page.get_by_role("button", name="Guía de tallas", exact=True)
        guide_trigger.click()
        guide = page.get_by_role("dialog", name="Guía de tallas", exact=True)
        expect(guide).to_be_visible()
        expect(guide).to_contain_text("Conjunto de prueba")
        for label in ("Busto", "Cintura", "Cadera"):
            expect(guide.get_by_role("heading", name=label, exact=True)).to_be_visible()
        expect(guide.get_by_role("table")).to_contain_text("92,5")
        expect(guide).to_contain_text("Son medidas de la prenda, no del cuerpo")
        for width in (320, 390):
            page.set_viewport_size({"width": width, "height": 844})
            assert guide.evaluate("e => e.scrollWidth <= e.clientWidth"), width
        page.screenshot(path=".local-backups/size-guide-mobile.png")
        guide.press("Escape")
        expect(guide).not_to_be_visible()
        expect(guide_trigger).to_be_focused()
        guide_trigger.click()
        guide.get_by_role("button", name="Cerrar guía de tallas", exact=True).click()
        expect(guide_trigger).to_be_focused()
        page.set_viewport_size({"width":1440,"height":1000})
        add = page.locator(".showcase-add")
        expect(add).to_be_disabled()
        expect(page.locator(".showcase-sizes button")).to_have_count(3)
        page.get_by_role("button", name="Talla M, Rojo", exact=True).click()
        expect(add).to_be_enabled()
        expect(page.locator(".showcase-price")).to_contain_text("12.00")
        add.click()
        page.get_by_role("button", name="Talla M, Azul", exact=True).click()
        expect(page.locator(".showcase-price")).to_contain_text("14.00")
        expect(page.locator(".showcase-photo img")).to_have_attribute("src", products[0]["image_url"])
        add.click()
        page.locator(".topbar .cart-link").click()
        cart = page.locator(".cart-panel")
        lines = cart.locator(".cart-item")
        expect(lines).to_have_count(2)
        expect(lines.nth(0).locator(".cart-thumbnail")).to_have_attribute("src", "https://images.test/red.webp")
        expect(lines.nth(1).locator(".cart-thumbnail")).to_have_attribute("src", "https://images.test/blue.webp")
        expect(lines.nth(0)).to_contain_text("Talla")
        expect(lines.nth(0)).to_contain_text("Color")
        expect(lines.nth(0)).to_contain_text("12.00")
        expect(lines.nth(1)).to_contain_text("14.00")
        lines.nth(1).locator(".quantity-control button").last.click()
        expect(lines.nth(1)).to_contain_text("28.00")
        expect(cart.locator(".cart-total")).to_contain_text("40.00")
        expect(cart).to_contain_text("Por coordinar por WhatsApp")
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            assert cart.evaluate("e => e.scrollWidth <= e.clientWidth"), width
        page.screenshot(path=".local-backups/purchase-cart-mobile.png")
        cart.get_by_role("button", name="Cerrar pedido", exact=True).click()
        page.locator(".stage-arrow-next").click()
        guide_trigger.click()
        expect(guide).to_contain_text("todavía no está publicada")
        expect(guide.get_by_role("table")).to_have_count(0)
        guide.press("Escape")
        expect(add).to_be_enabled()
        page.locator(".stage-arrow-prev").click()
        expect(add).to_be_disabled()
        assert not errors, errors
        browser.close()
        print("PURCHASE_BROWSER_OK: real variants, adjusted prices, color thumbnails, quantities, subtotal, product reset and 320/390px layout")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=10)

"""Validate catalog filters and cart restoration using temporary catalog data only."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from io import BytesIO
import threading
from PIL import Image
from playwright.sync_api import sync_playwright, expect

products = [
    {"id": 1, "name": "Body A", "slug": "body-a", "price_cents": 1000, "is_active": True,
     "image_url": "https://images.test/a.png", "images": [], "variants": [
        {"id": 11, "sku": "A-M-R", "size": "M", "color": "Rojo", "price_adjustment_cents": 1000},
        {"id": 12, "sku": "A-L-N", "size": "L", "color": "Negro", "price_adjustment_cents": 0}]},
    {"id": 2, "name": "Body B", "slug": "body-b", "price_cents": 1200, "is_active": True,
     "image_url": "https://images.test/b.png", "images": [], "variants": [
        {"id": 21, "sku": "B-M-R", "size": "M", "color": "Rojo", "price_adjustment_cents": 0}]},
    {"id": 3, "name": "Body C", "slug": "body-c", "price_cents": 800, "is_active": True,
     "image_url": "https://images.test/c.png", "images": [], "variants": []},
]
image = BytesIO(); Image.new("RGB", (40, 60), "teal").save(image, "PNG")
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass
server = ThreadingHTTPServer(("127.0.0.1", 8124), partial(QuietHandler, directory=str(Path.cwd() / "frontend/dist/frontend/browser")))
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
        for width in (1440, 390):
            page = browser.new_page(viewport={"width": width, "height": 900})
            errors = []; page.on("pageerror", lambda error: errors.append(str(error)))
            page.route("**/api/v1/products", lambda route: route.fulfill(json=products))
            page.route("**/api/v1/products/*/reviews?*", lambda route: route.fulfill(json={"items": [], "total": 0, "average_rating": None, "limit": 10, "offset": 0}))
            page.route("https://images.test/**", lambda route: route.fulfill(content_type="image/png", body=image.getvalue()))
            page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(content_type="text/css", body=""))
            page.goto("http://127.0.0.1:8124/#/")
            cards = page.locator(".product-miniature")
            expect(cards).to_have_count(3)
            page.locator("#catalog-size").select_option("M")
            page.locator("#catalog-max-price").fill("15")
            expect(cards).to_have_count(1)
            expect(cards.first).to_contain_text("Body B")
            page.locator(".color-filters").get_by_role("button", name="Negro", exact=True).click()
            expect(cards).to_have_count(0)
            expect(page.locator(".catalog-empty")).to_be_visible()
            page.locator(".catalog-empty").get_by_role("button").click()
            expect(cards).to_have_count(3)
            page.locator("#catalog-sort").select_option("price-desc")
            expect(cards.first).to_contain_text("Body B")
            page.locator("#catalog-sort").select_option("price-asc")
            expect(cards.first).to_contain_text("Body C")
            page.locator("#catalog-size").select_option("M")
            page.locator("#catalog-sort").select_option("price-desc")
            expect(cards.first).to_contain_text("Body A")
            expect(cards.first.locator(".miniature-price")).to_contain_text("20.00")
            # Cart restoration fetches current prices, keeping the exact selected variant.
            page.locator(".showcase-sizes").get_by_role("button", name="Talla M, Rojo", exact=True).click()
            page.get_by_role("button", name="Añadir a mi pedido", exact=True).click()
            expect(page.locator(".topbar .cart-count")).to_have_text("1")
            saved = page.evaluate("JSON.parse(localStorage.getItem('tienda.cart.v1'))")
            assert saved == {"version": 1, "items": [{"product_id": 1, "variant_id": 11, "quantity": 1}]}, saved
            products[0]["price_cents"] = 1300
            page.reload()
            expect(page.locator(".topbar .cart-count")).to_have_text("1")
            page.locator(".topbar").get_by_role("button", name="Tu pedido").click()
            expect(page.locator(".cart-total")).to_contain_text("23.00")
            expect(page.locator(".cart-panel")).to_contain_text("M")
            page.get_by_role("button", name="Vaciar pedido", exact=True).click()
            page.reload()
            expect(page.locator(".topbar .cart-count")).to_have_text("0")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
            assert not errors, errors
            products[0]["price_cents"] = 1000
            page.close()
        browser.close()
        print("CATALOG_CART_BROWSER_OK: combined filters, variant prices, ordering, empty/reset, cart reload/current prices/clear; desktop and mobile.")
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=10)
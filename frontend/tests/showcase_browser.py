from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
import json
import threading
from PIL import Image
from playwright.sync_api import sync_playwright, expect

class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args): pass

products = [
    {"id": 1, "name": "Producto A", "slug": "producto-a", "price_cents": 1500, "is_active": True,
     "image_url": "https://images.test/a-cover.webp",
     "variants": [{"id": 11, "sku": "A-M-VINO", "size": "M", "color": "Vino", "price_adjustment_cents": 0},
                  {"id": 12, "sku": "A-L-AZUL", "size": "L", "color": "Azul", "price_adjustment_cents": 100}],
     "images": [{"id": 101, "url": "https://images.test/a-detail.webp", "alt": "Detalle A vino", "color": "Vino"},
                {"id": 102, "url": "https://images.test/a-blue.webp", "alt": "Detalle A azul", "color": "Azul"}]},
    {"id": 2, "name": "Producto B", "slug": "producto-b", "price_cents": 2000, "is_active": True,
     "image_url": "https://images.test/b-cover.webp", "variants": [],
     "images": [{"id": 201, "url": "https://images.test/b-detail.webp", "alt": "Detalle B", "color": "Único"}]},
]
image = BytesIO(); Image.new("RGB", (40, 60), "teal").save(image, "PNG")
server = ThreadingHTTPServer(("127.0.0.1", 8124), partial(QuietHandler, directory=str(Path.cwd() / "frontend/dist/frontend/browser")))
thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="C:/Program Files/Google/Chrome/Application/chrome.exe", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        errors=[]; page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/api/v1/products", lambda route: route.fulfill(json=products))
        page.route("**/api/v1/products/*/reviews?*", lambda route: route.fulfill(json={"items": [], "total": 0, "average_rating": None, "limit": 10, "offset": 0}))
        page.route("https://images.test/**", lambda route: route.fulfill(content_type="image/png", body=image.getvalue()))
        page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(content_type="text/css", body=""))
        page.goto("http://127.0.0.1:8124/#/")
        stage=page.locator(".showcase-stage")
        cover=stage.locator(".showcase-photo img")
        dialog=page.locator(".photo-dialog")
        expect(cover).to_have_attribute("src", products[0]["image_url"])
        expect(stage.locator("img")).to_have_count(1)
        expect(page.locator(".showcase-media .photo-thumbnails")).to_have_count(0)
        page.get_by_role("button", name="Talla L, Azul", exact=True).click()
        expect(cover).to_have_attribute("src", products[0]["image_url"])
        cover.click()
        expect(dialog).to_be_visible()
        expect(dialog.locator("img")).to_have_attribute("src", products[0]["image_url"])
        dialog.locator("img").click()
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Siguiente foto", exact=True).click()
        expect(dialog.locator("img")).to_have_attribute("src", "https://images.test/a-detail.webp")
        dialog.get_by_role("button", name="Siguiente foto", exact=True).click()
        expect(dialog.locator("img")).to_have_attribute("src", "https://images.test/a-blue.webp")
        expect(page.locator(".showcase-details h2")).to_have_text("Producto A")
        dialog.press("ArrowLeft")
        expect(dialog.locator("img")).to_have_attribute("src", "https://images.test/a-detail.webp")
        dialog.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(cover).to_have_attribute("src", products[0]["image_url"])
        stage.focus(); stage.press("ArrowRight")
        expect(cover).to_have_attribute("src", products[1]["image_url"])
        expect(page.locator(".showcase-details h2")).to_have_text("Producto B")
        cover.click()
        expect(dialog.locator("img")).to_have_attribute("src", products[1]["image_url"])
        dialog.get_by_role("button", name="Siguiente foto", exact=True).click()
        expect(dialog.locator("img")).to_have_attribute("src", "https://images.test/b-detail.webp")
        dialog.press("Escape")
        stage.focus(); stage.press("ArrowLeft")
        expect(cover).to_have_attribute("src", products[0]["image_url"])
        stage.locator(".stage-arrow-next").click()
        expect(cover).to_have_attribute("src", products[1]["image_url"])
        stage.locator(".stage-arrow-prev").click()
        expect(cover).to_have_attribute("src", products[0]["image_url"])
        page.set_viewport_size({"width": 390, "height": 844})
        stage.scroll_into_view_if_needed()
        box=cover.bounding_box(); assert box
        x=box["x"]+box["width"]*0.7; y=box["y"]+box["height"]*0.5
        page.mouse.move(x,y); page.mouse.down(); page.mouse.move(x-110,y,steps=8); page.mouse.up()
        expect(cover).to_have_attribute("src", products[1]["image_url"])
        expect(dialog).not_to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        browser.close()
        print("SHOWCASE_BROWSER_OK: product-only navigation/swipe, stable cover across variants, click opens gallery, modal photos isolated, mobile layout.")
finally:
    server.shutdown(); server.server_close(); thread.join(timeout=10)

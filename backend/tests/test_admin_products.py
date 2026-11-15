from io import BytesIO
import re

from botocore.exceptions import ClientError
from PIL import Image
from pydantic import SecretStr
import pytest

from app.services import image_service

BASE = "/api/v1/products"


def photo(fmt="PNG", size=(24, 16), **options):
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=fmt, **options)
    return output.getvalue()


def payload(**changes):
    return {"name": "Producto prueba", "slug": "producto-prueba", "price_cents": 1500, **changes}


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setattr(image_service.settings, "aws_endpoint_url_s3", "https://s3.example")
    monkeypatch.setattr(image_service.settings, "aws_region", "us-east-1")
    monkeypatch.setattr(image_service.settings, "aws_access_key_id", "test")
    monkeypatch.setattr(image_service.settings, "aws_secret_access_key", SecretStr("test"))
    monkeypatch.setattr(image_service.settings, "product_images_bucket", "photos")
    monkeypatch.setattr(image_service.settings, "product_images_public_url", "https://cdn.example/photos")
    writes = []
    class FakeStorage:
        def put_object(self, **kwargs): writes.append(kwargs)
    monkeypatch.setattr(image_service, "get_storage_client", lambda: FakeStorage())
    return writes


def test_admin_lists_inactive_products_and_keeps_them_private(client, anon_client):
    result = client.post(BASE, json=payload(is_active=False, description="Todos los atributos",
        variants=[{"sku": "TEST-M", "size": "M", "color": "Vino", "price_adjustment_cents": 100}],
        images=[{"url": "https://example.com/photo.webp", "alt": "Vista frontal", "color": "Vino"}]))
    assert result.status_code == 201
    admin = client.get(BASE + "/admin")
    assert admin.status_code == 200 and len(admin.json()) == 1
    assert admin.json()[0]["variants"][0]["size"] == "M"
    assert anon_client.get(BASE).json() == []
    assert anon_client.get(BASE + "/admin", headers={"Authorization": ""}).status_code == 401


def test_customer_cannot_list_or_upload(anon_client):
    result = anon_client.post("/api/v1/users", json={"email": "customer@example.com", "full_name": "Cliente", "password": "testpassword123"})
    assert result.status_code == 201
    token = anon_client.post("/api/v1/auth/login", json={"email": "customer@example.com", "password": "testpassword123"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert anon_client.get(BASE + "/admin", headers=headers).status_code == 403
    assert anon_client.post(BASE + "/images", files={"file": ("foto.png", photo())}, headers=headers).status_code == 403


def test_upload_requires_real_admin_even_in_development(anon_client, monkeypatch):
    monkeypatch.setattr(image_service.settings, "auth_enabled", False)
    assert anon_client.post(BASE + "/images", files={"file": ("foto.png", photo())}).status_code == 401


@pytest.mark.parametrize("changes", [
    {"name": "  "}, {"slug": "Bad slug"}, {"description": "a" * 5001},
    {"variants": [{"sku": "SKU-ONE", "color": "a" * 51}]},
    {"price_cents": 2147483648}, {"price_cents": True},
])
def test_admin_validates_attributes_without_partial_products(client, changes):
    assert client.post(BASE, json=payload(**changes)).status_code == 422
    assert client.get(BASE + "/admin").json() == []


def test_duplicates_are_conflicts_and_do_not_create_partial_variants(client):
    first = client.post(BASE, json=payload(name="  Producto prueba  ", variants=[{"sku": " SKU-M ", "size": " M "}]))
    assert first.status_code == 201
    assert first.json()["name"] == "Producto prueba"
    assert first.json()["variants"][0]["sku"] == "SKU-M"
    assert client.post(BASE, json=payload()).status_code == 409
    assert client.post(BASE, json=payload(slug="otro-producto", variants=[{"sku": "SKU-M"}])).status_code == 409
    assert len(client.get(BASE + "/admin").json()) == 1


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP", "AVIF"])
def test_uploaded_content_is_validated_converted_and_persisted(client, storage, fmt):
    result = client.post(BASE + "/images", files={"file": ("anything.bin", photo(fmt), "application/octet-stream")})
    assert result.status_code == 201
    assert re.fullmatch(r"https://cdn\.example/photos/products/[a-f0-9]{32}\.webp", result.json()["url"])
    assert len(storage) == 1
    assert storage[0]["ContentType"] == "image/webp"
    with Image.open(BytesIO(storage[0]["Body"])) as image:
        assert image.format == "WEBP" and image.size == (24, 16)
        assert not image.getexif()


def test_upload_strips_metadata(client, storage):
    exif = Image.Exif(); exif[0x010E] = "Private location"
    result = client.post(BASE + "/images", files={"file": ("image.jpg", photo("JPEG", exif=exif), "image/jpeg")})
    assert result.status_code == 201
    with Image.open(BytesIO(storage[0]["Body"])) as image: assert not image.getexif()


@pytest.mark.parametrize("data, status", [(b"disguised text", 422), (b"x" * (8 * 1024 * 1024 + 1), 413)], ids=["invalid", "too-large"])
def test_upload_rejects_invalid_or_oversized_files(client, storage, data, status):
    assert client.post(BASE + "/images", files={"file": ("fake.png", data, "image/png")}).status_code == status
    assert storage == []


def test_upload_rejects_pixel_bombs_and_animation(client, storage):
    assert client.post(BASE + "/images", files={"file": ("large.png", photo(size=(5001, 4000)))}).status_code == 422
    output = BytesIO()
    first = Image.new("RGB", (16, 16), "red"); second = Image.new("RGB", (16, 16), "blue")
    first.save(output, format="PNG", save_all=True, append_images=[second], duration=100)
    assert client.post(BASE + "/images", files={"file": ("animation.png", output.getvalue())}).status_code == 422
    assert storage == []


def test_upload_reports_configuration_and_provider_errors_without_secrets(client, storage, monkeypatch):
    monkeypatch.setattr(image_service.settings, "product_images_bucket", None)
    assert client.post(BASE + "/images", files={"file": ("photo.png", photo())}).status_code == 503
    monkeypatch.setattr(image_service.settings, "product_images_bucket", "photos")
    class FailingStorage:
        def put_object(self, **kwargs): raise ClientError({"Error": {"Code": "AccessDenied", "Message": "private-secret"}}, "PutObject")
    monkeypatch.setattr(image_service, "get_storage_client", lambda: FailingStorage())
    result = client.post(BASE + "/images", files={"file": ("photo.png", photo())})
    assert result.status_code == 502 and "private-secret" not in result.text

"""Fotos de producto: comprobar contenido y guardar en almacenamiento persistente."""
from io import BytesIO
import warnings
from urllib.parse import urlsplit
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from PIL import Image, ImageOps, UnidentifiedImageError

from app.core.config import settings

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "AVIF"}


class ImageStorageError(Exception):
    def __init__(self, message: str, status_code: int = 503):
        super().__init__(message)
        self.status_code = status_code


def encode_product_image(content: bytes) -> bytes:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("La foto debe pesar como máximo 8 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(content)) as candidate:
                if candidate.format not in ALLOWED_FORMATS:
                    raise ValueError("Usa una foto JPEG, PNG, WebP o AVIF.")
                if candidate.width * candidate.height > MAX_IMAGE_PIXELS:
                    raise ValueError("La foto no puede superar 20 megapíxeles.")
                if getattr(candidate, "is_animated", False):
                    raise ValueError("Las fotos animadas no están permitidas.")
                candidate.verify()
            with Image.open(BytesIO(content)) as candidate:
                oriented = ImageOps.exif_transpose(candidate)
                # Imagen nueva: elimina EXIF, GPS, comentarios y perfiles embebidos.
                mode = "RGBA" if ("A" in oriented.getbands() or "transparency" in oriented.info) else "RGB"
                converted = oriented.convert(mode)
                clean = Image.new(mode, converted.size)
                clean.paste(converted)
                clean.thumbnail((2400, 2400))
                output = BytesIO()
                clean.save(output, format="WEBP", quality=88, method=4)
                return output.getvalue()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("El archivo no es una foto válida o está dañado.") from exc


def get_storage_client():
    return boto3.client(
        "s3", endpoint_url=settings.aws_endpoint_url_s3, region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key.get_secret_value(),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      connect_timeout=10, read_timeout=30, retries={"max_attempts": 2}),
    )


def upload_product_image(content: bytes) -> str:
    encoded = encode_product_image(content)
    public_url = settings.product_images_public_url or ""
    endpoint = settings.aws_endpoint_url_s3 or ""
    if not all((settings.product_images_bucket, settings.aws_access_key_id, settings.aws_secret_access_key)) or any(
        urlsplit(url).scheme != "https" or not urlsplit(url).netloc or urlsplit(url).query or urlsplit(url).fragment or urlsplit(url).username is not None
        for url in (public_url, endpoint)
    ):
        raise ImageStorageError("La carga de fotos aún no está configurada. Contacta al administrador del sistema.")
    key = f"products/{uuid4().hex}.webp"
    try:
        get_storage_client().put_object(
            Bucket=settings.product_images_bucket, Key=key, Body=encoded,
            ContentType="image/webp", CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError) as exc:
        raise ImageStorageError("No se pudo guardar la foto. Inténtalo nuevamente.", 502) from exc
    return f"{public_url.rstrip('/')}/{key}"

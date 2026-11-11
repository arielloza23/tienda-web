from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_db(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    engine = create_engine(url)
    yield config, engine
    engine.dispose()


def _schema_diff(engine) -> list:
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    # SQLite no conserva el nombre de algunas FK creadas en batch; no es un cambio real.
    return [entry for entry in diff if not (isinstance(entry, tuple) and entry[0] in {"add_fk", "remove_fk"})]


def test_upgrade_head_matches_models(alembic_db) -> None:
    config, engine = alembic_db
    command.upgrade(config, "head")
    assert _schema_diff(engine) == []


def test_downgrade_to_base_and_upgrade_again(alembic_db) -> None:
    config, engine = alembic_db
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    command.upgrade(config, "head")
    assert _schema_diff(engine) == []


def test_upgrade_adopts_database_created_with_create_all(alembic_db) -> None:
    """Bases antiguas creadas con create_all y sin alembic_version."""
    config, engine = alembic_db
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO products (name, slug, price_cents, is_active) "
                "VALUES ('Top', 'top-corse-encaje-negro', 1000, 1)"
            )
        )

    command.upgrade(config, "head")

    assert _schema_diff(engine) == []
    with engine.connect() as connection:
        image_url = connection.execute(text(
            "SELECT image_url FROM products WHERE slug = 'top-corse-encaje-negro'"
        )).scalar_one()
    assert image_url.startswith("https://images.pexels.com/")


def test_vestido_body_is_loaded_once_with_approved_price_and_photos(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    # Volver a aplicar después de retroceder tampoco duplica el catálogo.
    command.downgrade(config, "20261108_product_gallery")
    command.upgrade(config, "head")

    with engine.connect() as connection:
        product = connection.execute(text(
            "SELECT id, price_cents, image_url, is_active FROM products "
            "WHERE slug = 'vestido-body-de-encaje'"
        )).mappings().one()
        assert product["price_cents"] == 1500
        assert product["is_active"]
        assert product["image_url"].endswith("/vestido-body-de-encaje/portada.avif")
        variant = connection.execute(text(
            "SELECT size, color, price_adjustment_cents FROM product_variants "
            "WHERE product_id = :id"
        ), {"id": product["id"]}).one()
        assert tuple(variant) == ("M", "Vino", 0)
        photos = connection.execute(text(
            "SELECT url, color FROM product_images WHERE product_id = :id ORDER BY position"
        ), {"id": product["id"]}).all()
        assert len(photos) == 3
        assert all(photo.color == "Vino" for photo in photos)
        assert [photo.url.rsplit("/", 1)[-1] for photo in photos] == [
            "adicional-1.avif", "adicional-2.avif", "adicional-3.avif",
        ]


def test_conjunto_encaje_is_loaded_once_with_approved_price_and_photos(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, "head")
    command.downgrade(config, "20261111_vestido_body")
    command.upgrade(config, "head")
    with engine.connect() as connection:
        product = connection.execute(text(
            "SELECT id, name, price_cents, image_url, is_active FROM products "
            "WHERE slug = 'conjunto-de-lenceria-encaje'"
        )).mappings().one()
        assert product["name"] == "Conjunto de lencería encaje"
        assert product["price_cents"] == 1200
        assert product["is_active"]
        assert product["image_url"].endswith("/conjunto-de-lenceria-encaje/portada.avif")
        variant = connection.execute(text(
            "SELECT size, color, price_adjustment_cents FROM product_variants "
            "WHERE product_id = :id"
        ), {"id": product["id"]}).one()
        assert tuple(variant) == ("M", "Blanco", 0)
        photos = connection.execute(text(
            "SELECT url, color FROM product_images WHERE product_id = :id ORDER BY position"
        ), {"id": product["id"]}).all()
        assert len(photos) == 4
        assert all(photo.color == "Blanco" for photo in photos)
        assert [photo.url.rsplit("/", 1)[-1] for photo in photos] == [
            "adicional-1.avif", "adicional-2.avif", "adicional-3.avif", "adicional-4.avif",
        ]

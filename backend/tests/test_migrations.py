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


def test_idempotency_migration_preserves_existing_orders(alembic_db):
    from alembic import command
    config, engine = alembic_db
    command.upgrade(config, "20261111_conjunto_encaje")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO orders (id, status, subtotal_cents, total_cents, shipping_total_cents, tax_total_cents, created_at) VALUES (900, 'pending', 100, 100, 0, 0, CURRENT_TIMESTAMP)"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(text("SELECT total_cents, idempotency_key, request_hash FROM orders WHERE id=900")).one()
        assert tuple(row) == (100, None, None)
    command.downgrade(config, "20261111_conjunto_encaje")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT total_cents FROM orders WHERE id=900")).scalar_one() == 100
    command.upgrade(config, "head")



def test_reviews_migration_preserves_existing_data_and_constraints(alembic_db):
    from sqlalchemy.exc import IntegrityError
    config, engine = alembic_db
    command.upgrade(config, "20261115_order_idempotency")
    with engine.begin() as connection:
        product_id = connection.execute(text("SELECT id FROM products ORDER BY id LIMIT 1")).scalar_one()
        connection.execute(text("INSERT INTO users (id, email, full_name, password_hash, role, is_active) VALUES (800, 'migration@example.com', 'Temporal', 'fake', 'customer', 1)"))
        connection.execute(text("INSERT INTO orders (id, status, subtotal_cents, total_cents, shipping_total_cents, tax_total_cents, created_at) VALUES (800, 'pending', 700, 700, 0, 0, CURRENT_TIMESTAMP)"))
        product_count = connection.execute(text("SELECT COUNT(*) FROM products")).scalar_one()
    command.upgrade(config, "20261115_product_reviews")
    statement = text("INSERT INTO product_reviews (product_id, user_id, rating, comment, created_at, updated_at) VALUES (:product_id, 800, :rating, '', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)")
    with engine.begin() as connection:
        connection.execute(statement, {"product_id": product_id, "rating": 5})
    for rating in [5, 0, 6]:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(statement, {"product_id": product_id, "rating": rating})
    # Check validation independently of uniqueness.
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM product_reviews"))
    for rating in [0, 6]:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(statement, {"product_id": product_id, "rating": rating})
    command.downgrade(config, "20261115_order_idempotency")
    assert "product_reviews" not in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM products")).scalar_one() == product_count
        assert connection.execute(text("SELECT email FROM users WHERE id=800")).scalar_one() == 'migration@example.com'
        assert connection.execute(text("SELECT total_cents FROM orders WHERE id=800")).scalar_one() == 700
    command.upgrade(config, "head")
    assert _schema_diff(engine) == []


def test_checkout_recovery_preserves_data_on_upgrade_and_reupgrade(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, "20261115_product_reviews")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO users (id, email, full_name, password_hash, role, is_active) VALUES (999, 'temp@example.com', 'Temporal', 'fake', 'customer', 1)"))
        connection.execute(text("INSERT INTO orders (id, status, subtotal_cents, total_cents, shipping_total_cents, tax_total_cents, created_at) VALUES (999, 'pending', 100, 100, 0, 0, CURRENT_TIMESTAMP)"))
        before = connection.execute(text("SELECT id, sku, size, color FROM product_variants ORDER BY id")).all()
    command.upgrade(config, "20261116_checkout_recovery")
    with engine.begin() as connection:
        assert connection.execute(text("SELECT token_version FROM users WHERE id=999")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM product_variants WHERE bust_cm IS NOT NULL OR waist_cm IS NOT NULL OR hip_cm IS NOT NULL")).scalar_one() == 0
        connection.execute(text("UPDATE product_variants SET bust_cm=90.5 WHERE id=:id"), {"id": before[0].id})
    command.downgrade(config, "20261115_product_reviews")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT id, sku, size, color FROM product_variants ORDER BY id")).all() == before
        assert connection.execute(text("SELECT total_cents FROM orders WHERE id=999")).scalar_one() == 100
        assert connection.execute(text("SELECT email FROM users WHERE id=999")).scalar_one() == "temp@example.com"
    command.upgrade(config, "head")
    assert _schema_diff(engine) == []


def test_inventory_migration_initializes_once_and_preserves_legacy_orders(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, '20261116_catalog_products')
    with engine.begin() as c:
        c.execute(text("INSERT INTO orders (id,status,subtotal_cents,total_cents,shipping_total_cents,tax_total_cents,created_at) VALUES (987,'paid',1500,1500,0,0,CURRENT_TIMESTAMP)"))
        products = c.execute(text('SELECT id,name,price_cents FROM products ORDER BY id')).all()
        variants = c.execute(text('SELECT id,sku,size,color FROM product_variants ORDER BY id')).all()
    command.upgrade(config, 'head')
    with engine.begin() as c:
        assert c.execute(text('SELECT id,name,price_cents FROM products ORDER BY id')).all() == products
        assert c.execute(text('SELECT id,sku,size,color FROM product_variants ORDER BY id')).all() == variants
        assert c.execute(text('SELECT stock_quantity FROM product_variants')).scalars().all() == [1] * len(variants)
        assert c.execute(text('SELECT stock_quantity FROM products')).scalars().all() == [1] * len(products)
        assert not c.execute(text('SELECT inventory_deducted FROM orders WHERE id=987')).scalar_one()
        c.execute(text('UPDATE product_variants SET stock_quantity=5 WHERE id=:id'), {'id': variants[0].id})
    command.upgrade(config, 'head')
    with engine.connect() as c:
        assert c.execute(text('SELECT stock_quantity FROM product_variants WHERE id=:id'), {'id': variants[0].id}).scalar_one() == 5
        assert c.execute(text('SELECT status,total_cents FROM orders WHERE id=987')).one() == ('paid',1500)
    command.downgrade(config, '20261116_catalog_products')
    command.upgrade(config, 'head')
    assert _schema_diff(engine) == []


def test_inventory_migration_downgrade_refuses_losing_reservations(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, 'head')
    with engine.begin() as c:
        c.execute(text("INSERT INTO orders (id,status,inventory_deducted,subtotal_cents,total_cents,shipping_total_cents,tax_total_cents,created_at) VALUES (988,'reserved',true,100,100,0,0,CURRENT_TIMESTAMP)"))
    with pytest.raises(RuntimeError, match='inventario'):
        command.downgrade(config, '20261116_catalog_products')
    with engine.connect() as c:
        assert c.execute(text('SELECT status,inventory_deducted FROM orders WHERE id=988')).one() == ('reserved',True)
        assert c.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '20261120_inventory'
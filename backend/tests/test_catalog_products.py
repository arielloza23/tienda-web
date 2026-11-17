from pathlib import Path
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from app.core.config import settings

EXPECTED = (
    ("body-de-encaje-transparente-negro", 804, "Negro", "BET-NEGRO-M", 3),
    ("conjunto-6-piezas", 3696, "Multicolor", "C6-MULTI-M", 4),
    ("conjunto-de-lenceria-encaje-3-piezas", 1040, "Negro", "CLE3-NEGRO-M", 4),
    ("conjunto-de-lenceria-encaje-3-rojo", 1518, "Rojo", "CLE3-ROJO-M", 5),
    ("conjunto-de-navidad", 1724, "Rojo", "NAV-ROJO-M", 3),
)


def test_catalog_preserves_existing_products_and_admin_edits(tmp_path, monkeypatch):
    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{(tmp_path / 'catalog.db').as_posix()}"
    monkeypatch.setattr(settings, "database_url", url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(config, "20261116_checkout_recovery")
    engine = sa.create_engine(url)
    try:
        metadata = sa.MetaData()
        metadata.reflect(bind=engine)
        products, variants, images = [metadata.tables[name] for name in
            ("products", "product_variants", "product_images")]
        with engine.connect() as connection:
            previous_products = {row.id: dict(row._mapping) for row in connection.execute(sa.select(products))}
        command.upgrade(config, "head")
        with engine.connect() as connection:
            all_products = {row.slug: row._mapping for row in connection.execute(sa.select(products))}
            assert len(all_products) == len(previous_products) + len(EXPECTED)
            for slug, price, color, sku, image_count in EXPECTED:
                product = all_products[slug]
                assert product["price_cents"] == price
                assert product["is_active"]
                base = f"https://arielloza23.github.io/tienda-web/productos/{slug}"
                assert product["image_url"] == f"{base}/portada.avif"
                variant = connection.execute(sa.select(variants).where(
                    variants.c.product_id == product["id"])).mappings().one()
                assert (variant["size"], variant["color"], variant["sku"]) == ("M", color, sku)
                assert variant["price_adjustment_cents"] == 0
                assert all(variant[name] is None for name in ("bust_cm", "waist_cm", "hip_cm"))
                gallery = connection.execute(sa.select(images).where(
                    images.c.product_id == product["id"]).order_by(images.c.position)).mappings().all()
                assert len(gallery) == image_count
                assert [image["url"] for image in gallery] == [
                    f"{base}/adicional-{i}.avif" for i in range(1, image_count + 1)]
                assert all(image["color"] == color for image in gallery)
                asset_dir = backend.parent / "frontend" / "public" / "productos" / slug
                assert (asset_dir / "portada.avif").is_file()
                assert all((asset_dir / f"adicional-{i}.avif").is_file() for i in range(1, image_count + 1))
            for product_id, expected in previous_products.items():
                actual = connection.execute(sa.select(products).where(products.c.id == product_id)).mappings().one()
                assert dict(actual) == expected
        with engine.begin() as connection:
            connection.execute(products.update().where(products.c.slug == EXPECTED[0][0]).values(
                price_cents=999, name="Nombre editado", is_active=False))
            before = {table.name: [dict(row) for row in connection.execute(
                sa.select(table).order_by(table.c.id)).mappings()] for table in (products, variants, images)}
        command.downgrade(config, "20261116_checkout_recovery")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            after = {table.name: [dict(row) for row in connection.execute(
                sa.select(table).order_by(table.c.id)).mappings()] for table in (products, variants, images)}
        assert after == before
    finally:
        engine.dispose()
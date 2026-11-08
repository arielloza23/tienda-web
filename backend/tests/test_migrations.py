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
        image_url = connection.execute(text("SELECT image_url FROM products")).scalar_one()
    assert image_url.startswith("https://images.pexels.com/")

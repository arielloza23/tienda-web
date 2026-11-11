import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+psycopg"])
def test_hosted_database_url_uses_installed_driver(scheme):
    settings = Settings(
        _env_file=None,
        database_url=f"{scheme}://shop:pass%40word@db.example/shop?sslmode=require",
    )
    url = make_url(settings.database_url)
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "pass@word"
    assert url.query["sslmode"] == "require"


def test_sqlite_url_is_preserved():
    settings = Settings(_env_file=None, database_url="sqlite:///./shop.db")
    assert settings.database_url == "sqlite:///./shop.db"

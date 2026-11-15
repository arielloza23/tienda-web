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


@pytest.mark.parametrize("options", [
    {"auth_enabled": False, "secret_key": "a" * 40},
    {"auth_enabled": True, "secret_key": "dev-secret-key-change"},
    {"auth_enabled": True, "secret_key": "short"},
    {"auth_enabled": True, "secret_key": " " * 40},
])
def test_production_rejects_insecure_settings(options):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", **options)


def test_production_accepts_explicit_security():
    settings = Settings(_env_file=None, app_env="production", auth_enabled=True, secret_key="a" * 40)
    assert settings.auth_enabled


def test_development_allows_explicit_auth_bypass():
    settings = Settings(_env_file=None, app_env="development", auth_enabled=False)
    assert not settings.auth_enabled

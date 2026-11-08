import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole

SQLALCHEMY_DATABASE_URL = "sqlite://"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

ADMIN_EMAIL = "admin@tienda.com"
ADMIN_PASSWORD = "admin-password-123"


@pytest.fixture(autouse=True)
def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def anon_client() -> TestClient:
    """Cliente sin autenticar."""

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def client(anon_client: TestClient) -> TestClient:
    """Cliente autenticado como administrador."""
    db = TestingSessionLocal()
    try:
        db.add(
            User(
                email=ADMIN_EMAIL,
                full_name="Admin Tienda",
                password_hash=hash_password(ADMIN_PASSWORD),
                role=UserRole.ADMIN.value,
            )
        )
        db.commit()
    finally:
        db.close()

    response = anon_client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    anon_client.headers["Authorization"] = f"Bearer {response.json()['access_token']}"
    return anon_client


@pytest.fixture(autouse=True)
def auth_enabled(monkeypatch):
    """Los tests asumen seguridad activa aunque el .env local la desactive."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)

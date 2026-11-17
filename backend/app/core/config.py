from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "Tienda Web API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./tienda_web.db"
    secret_key: str = "dev-secret-key-change"
    access_token_expire_minutes: int = 60
    # Solo para desarrollo: con False, los endpoints de admin quedan abiertos.
    auth_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:4200"]
    aws_endpoint_url_s3: str | None = None
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    product_images_bucket: str | None = None
    product_images_public_url: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    smtp_starttls: bool = True
    password_reset_url: str | None = None

    @field_validator("password_reset_url")
    @classmethod
    def validate_reset_url(cls, value):
        if value is not None:
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or not parsed.fragment.endswith("/reset-password") or "?" in parsed.fragment:
                raise ValueError("PASSWORD_RESET_URL debe apuntar a /#/reset-password sin parámetros.")
            if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
                raise ValueError("PASSWORD_RESET_URL requiere HTTPS.")
        return value

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Render y Neon entregan URLs sin el nombre del driver instalado.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.app_env == "production":
            if not self.auth_enabled:
                raise ValueError("Producción requiere AUTH_ENABLED=true.")
            if self.secret_key.strip() == "dev-secret-key-change" or len(self.secret_key.strip()) < 32:
                raise ValueError("Producción requiere SECRET_KEY aleatoria de al menos 32 caracteres.")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )


settings = Settings()

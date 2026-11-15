from typing import Literal

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

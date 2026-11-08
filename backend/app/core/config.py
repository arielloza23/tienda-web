from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tienda Web API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./tienda_web.db"
    secret_key: str = "dev-secret-key-change"
    access_token_expire_minutes: int = 60
    # Solo para desarrollo: con False, los endpoints de admin quedan abiertos.
    auth_enabled: bool = True
    cors_origins: list[str] = ["http://localhost:4200"]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

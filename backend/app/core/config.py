from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Tienda Web API"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./tienda_web.db"
    secret_key: str = "dev-secret-key-change"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

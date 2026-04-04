from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Detection AI API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "change-me-for-local-dev"
    access_token_expire_minutes: int = 480
    database_url: str = "sqlite:///./detection_ai.db"
    cors_origins: str = "http://localhost:5173"
    bootstrap_admin_email: str = "admin@example.com"
    bootstrap_admin_password: str = "Admin12345!"
    bootstrap_admin_full_name: str = "System Admin"
    internal_api_token: str = "internal-local-token"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://ledgerlite@localhost/ledgerlite"
    provider_api_key: str
    webhook_secret: str
    provider_url: str = "http://provider:8001"
    callback_url: str = "http://wallet:8000/v1/webhooks/provider"
    provider_public_url: str = "http://localhost:8001"
    provider_timeout: float = 5.0
    rate_limit_enabled: bool = True


@lru_cache
def settings() -> Settings:
    return Settings()

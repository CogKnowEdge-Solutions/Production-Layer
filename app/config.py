from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    log_level: str = "info"

    database_url: str = "sqlite:///./carematch.db"

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_default: int = 3600

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    seed_admin_username: str = "admin"
    seed_admin_password: str = "admin-password-change-me"
    seed_coordinator_username: str = "coordinator"
    seed_coordinator_password: str = "coordinator-password-change-me"
    seed_provider_username: str = "provider"
    seed_provider_password: str = "provider-password-change-me"
    seed_auditor_username: str = "auditor"
    seed_auditor_password: str = "auditor-password-change-me"

    rate_limit_per_minute: int = 100

    api_prefix: str = "/api/v1"

    @property
    def is_testing(self) -> bool:
        return self.env == "testing"


@lru_cache
def get_settings() -> Settings:
    return Settings()

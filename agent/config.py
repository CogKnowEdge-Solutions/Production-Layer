from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-oss-20b:free"
    agent_api_url: str = "http://localhost:8000"
    agent_max_retries: int = 2


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()

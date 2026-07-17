from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    model_reasoning: str = "gemini-2.0-flash"
    model_fast: str = "gemini-2.0-flash"
    embed_model: str = "text-embedding-004"
    database_url: str = "postgresql://claimguard:claimguard@localhost:5432/claimguard"
    data_dir: str = "data"

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

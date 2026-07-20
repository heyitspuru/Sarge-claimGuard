from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    llm_provider: str = "mock"
    gemini_api_key: str = ""
    model_reasoning: str = "gemini-2.5-flash"
    model_fast: str = "gemini-2.5-flash"
    embed_model: str = "gemini-embedding-001"
    database_url: str = "postgresql://claimguard:claimguard@localhost:5432/claimguard"
    data_dir: str = "data"

    # --- auth (see docs/AUTH.md; the login flow is a labelled simulator) ---
    session_ttl_min: int = 60
    otp_ttl_sec: int = 300
    otp_max_attempts: int = 5
    # Demo staff account. Seeded, not registerable. Override in .env for anything
    # that is not a local demo.
    staff_email: str = "claims@demo-hospital.test"
    staff_password: str = "demo-claims-officer"
    cookie_secure: bool = False  # True behind HTTPS; False so local http:// dev works

    model_config = {"env_file": ".env"}


@lru_cache
def get_settings() -> Settings:
    return Settings()

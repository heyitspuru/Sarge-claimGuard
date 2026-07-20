"""Test hygiene: force the deterministic mock LLM provider for every test,
regardless of what .env sets. Keeps the suite offline and free even when a
developer has LLM_PROVIDER=gemini in their .env for real eval runs.

db-marked tests still use the real database_url from .env (they connect to a
running Postgres or skip); only the LLM provider is pinned here.
"""
import pytest

from claimguard.config import get_settings


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

"""Test hygiene: force the deterministic mock LLM provider for every test,
regardless of what .env sets. Keeps the suite offline and free even when a
developer has LLM_PROVIDER=gemini in their .env for real eval runs.

The pin is applied at BOTH times, and it needs both:

  - **Import time (below).** conftest is imported before test modules are
    collected, so this covers module-level code in a test file. Fixtures do not
    exist yet at collection, so a module-level provider call would otherwise hit
    the real API — which is exactly what `tests/integration/test_pipeline.py` did
    for a long time: one real embedding call per suite run, on a file whose own
    docstring promised "no network, no real model calls". It only surfaced when a
    DNS failure turned a 15-second suite into a 23-minute one.
  - **Per test (the fixture).** Restores the pin if an individual test monkeypatches
    the provider, and clears the settings cache on both sides.

db-marked tests still use the real database_url from .env (they connect to a
running Postgres or skip); only the LLM provider is pinned here.
"""
import os

import pytest

from claimguard.config import get_settings

# Before any test module is imported. See the note above — this is load-bearing.
os.environ["LLM_PROVIDER"] = "mock"
get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _force_mock_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()

from claimguard.config import get_settings


def test_defaults_are_mock_provider():
    s = get_settings()
    assert s.llm_provider in ("mock", "gemini")
    assert s.data_dir == "data"

import pytest


@pytest.fixture(autouse=True)
def offline_copilot(monkeypatch):
    """Never call the Claude API from tests; tests that need Claude pass a fake client."""
    monkeypatch.setenv("COPILOT_OFFLINE", "1")

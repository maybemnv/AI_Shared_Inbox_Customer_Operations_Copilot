import pytest

from app.environment import RuntimeConfigurationError, validate_runtime


def test_non_fixture_runtime_requires_durable_dependencies(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("QUEUE_PROVIDER", raising=False)
    monkeypatch.delenv("AUTH_BEARER_TOKEN", raising=False)
    with pytest.raises(RuntimeConfigurationError, match="DATABASE_URL"):
        validate_runtime()

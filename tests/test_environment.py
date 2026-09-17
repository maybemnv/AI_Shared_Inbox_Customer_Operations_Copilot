import pytest

from app.environment import RuntimeConfigurationError, validate_runtime


def test_non_fixture_runtime_requires_durable_dependencies(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("QUEUE_PROVIDER", raising=False)
    monkeypatch.delenv("AUTH_BEARER_TOKEN", raising=False)
    with pytest.raises(RuntimeConfigurationError, match="DATABASE_URL"):
        validate_runtime()


def test_non_fixture_runtime_rejects_developer_cors(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://server")
    monkeypatch.setenv("QUEUE_PROVIDER", "postgres-outbox")
    monkeypatch.setenv("AUTH_BEARER_TOKEN", "server-token")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")

    with pytest.raises(RuntimeConfigurationError, match="localhost"):
        validate_runtime()

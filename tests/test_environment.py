import pytest
from pathlib import Path

from app.environment import RuntimeConfigurationError, validate_runtime


def test_fixture_readme_direct_launch_selects_local_fixture():
    readme = (Path(__file__).parents[1] / "README.md").read_text(encoding="utf-8")

    assert '$env:APP_ENV = "local-fixture"; uv run' in readme


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

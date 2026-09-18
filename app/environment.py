"""Runtime boundary for the fixture-only checkout."""

from __future__ import annotations

import os
from urllib.parse import urlparse


class RuntimeConfigurationError(ValueError):
    """Raised when fixture code is selected for a deploy environment."""


def app_environment() -> str:
    value = os.getenv("APP_ENV", "local-fixture").strip().lower()
    if value not in {"local-fixture", "staging", "production"}:
        raise RuntimeConfigurationError(
            "APP_ENV must be local-fixture, staging, or production"
        )
    return value


def validate_runtime() -> None:
    if app_environment() == "local-fixture":
        return
    missing = [
        name for name in ("DATABASE_URL", "QUEUE_PROVIDER", "AUTH_BEARER_TOKEN")
        if not os.getenv(name)
    ]
    if missing:
        raise RuntimeConfigurationError(
            "production runtime requires: "
            + ", ".join(missing)
            + "; use APP_ENV=local-fixture for the fixture repository"
        )
    if os.getenv("QUEUE_PROVIDER") not in {"redis", "postgres-outbox"}:
        raise RuntimeConfigurationError("QUEUE_PROVIDER must be redis or postgres-outbox outside fixture mode")
    origins = [item.strip() for item in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if item.strip()]
    if any(urlparse(origin).hostname in {"localhost", "127.0.0.1", "::1"} for origin in origins):
        raise RuntimeConfigurationError("localhost CORS origins are only allowed in APP_ENV=local-fixture")


def is_local_fixture() -> bool:
    return app_environment() == "local-fixture"

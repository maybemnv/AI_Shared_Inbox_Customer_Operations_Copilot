"""Durable PostgreSQL repository compatibility boundary for the inbox domain."""

from __future__ import annotations

import pickle
from collections.abc import Callable

from app.ingestion import InMemoryInbox


class PostgresInbox(InMemoryInbox):
    """Persist the existing domain state atomically without changing route contracts.

    The normalized tables remain the migration target for reporting and SQL-level
    constraints. This snapshot is the smallest safe bridge for the current rich
    in-process aggregate while those contract tests are built.
    """

    _MUTATIONS = frozenset({
        "reset", "ingest", "run_ai", "edit_draft", "approve_draft", "send_draft",
        "sync_connector", "retry_sync", "start_sla", "evaluate_sla", "resolve_conversation",
        "assign_conversation", "claim_conversation", "add_comment", "add_internal_comment",
    })

    def __init__(self, database_url: str) -> None:
        super().__init__()
        self.database_url = database_url
        self._load()

    def __getattribute__(self, name: str):
        value = super().__getattribute__(name)
        if name in PostgresInbox._MUTATIONS and callable(value):
            return lambda *args, **kwargs: self._mutate(value, *args, **kwargs)
        return value

    def _mutate(self, method: Callable, *args, **kwargs):
        with self._lock:
            with self._connect() as connection, connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    ("inbox:production",),
                )
                self._load_cursor(cursor)
                result = method(*args, **kwargs)
                self._persist_cursor(cursor)
                return result

    def _connect(self):
        import psycopg

        return psycopg.connect(self.database_url)

    def _load(self) -> None:
        with self._connect() as connection, connection.cursor() as cursor:
            self._load_cursor(cursor)

    def _load_cursor(self, cursor) -> None:
        cursor.execute(
            "SELECT payload FROM inbox_runtime_snapshots WHERE workspace_id = %s",
            ("production",),
        )
        row = cursor.fetchone()
        if row is None:
            return
        state = pickle.loads(bytes(row[0]))  # noqa: S301 - database is a trusted service boundary
        for name, value in state.items():
            setattr(self, name, value)

    def _persist(self) -> None:
        state = {
            name: value for name, value in vars(self).items() if name not in {"_lock", "database_url"}
        }
        payload = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        with self._connect() as connection, connection.cursor() as cursor:
            self._persist_cursor(cursor, payload)

    def _persist_cursor(self, cursor, payload: bytes | None = None) -> None:
        if payload is None:
            state = {
                name: value for name, value in vars(self).items() if name not in {"_lock", "database_url"}
            }
            payload = pickle.dumps(state, protocol=pickle.HIGHEST_PROTOCOL)
        cursor.execute(
            "INSERT INTO inbox_runtime_snapshots (workspace_id, payload, updated_at) "
            "VALUES (%s, %s, now()) ON CONFLICT (workspace_id) DO UPDATE SET "
            "payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at",
            ("production", payload),
        )

"""The app's own tables live in a dedicated Postgres schema, not `public`.

Since PostgreSQL 15 ordinary roles can't create in `public`; the app SP does have
CREATE on the database (from the app's Lakebase resource), so it creates and owns
APP_SCHEMA itself — no DATABRICKS_SUPERUSER needed for its own tables.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest


class _FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self._result: Any = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params: Any = None):
        sql_n = " ".join(sql.split())
        self._conn.executed.append((sql_n, params))
        if sql_n.startswith("SELECT to_regclass"):
            self._result = (tuple(p in self._conn.existing for p in params),)
        elif sql_n.startswith("SELECT 1 FROM schema_migrations"):
            self._result = [(1,)] if params[0] in self._conn.applied else []
        else:
            self._result = None

    def fetchone(self):
        if isinstance(self._result, list):
            return self._result[0] if self._result else None
        return self._result[0] if self._result else None


class _FakeConn:
    def __init__(self, existing=(), applied=()):
        self.existing = set(existing)      # "schema.table" names that exist
        self.applied = set(applied)        # migration versions already recorded
        self.executed: list[tuple[str, Any]] = []
        self.commits = 0

    def cursor(self):
        return _FakeCursor(self)

    def commit(self):
        self.commits += 1


@pytest.fixture
def conn_mod(monkeypatch):
    from data_classification_review_app.backend.db import connection as mod
    return mod


def _run_init_db(mod, monkeypatch, conn):
    monkeypatch.setattr(mod, "get_conn", lambda: conn)
    monkeypatch.setattr(mod, "putconn", lambda c, **k: None)
    asyncio.run(mod.init_db())
    return [sql for sql, _ in conn.executed]


# ── connection search_path ───────────────────────────────────────────────────────
def test_lakebase_dsn_sets_search_path(conn_mod, monkeypatch):
    monkeypatch.setenv("LAKEBASE_HOST", "ep-x.database.cloud.databricks.com")
    monkeypatch.setenv("LAKEBASE_USER", "sp-id")
    dsn = conn_mod._build_dsn(token="tok")
    assert dsn["options"] == f"-c search_path={conn_mod.APP_SCHEMA}"
    assert conn_mod.APP_SCHEMA == "data_classification_review_app"


def test_lakebase_dsn_uses_configured_database(conn_mod, monkeypatch):
    monkeypatch.setenv("LAKEBASE_HOST", "ep-x.database.cloud.databricks.com")
    monkeypatch.setenv("LAKEBASE_DATABASE", "classification_audit")
    assert conn_mod._build_dsn(token="tok")["dbname"] == "classification_audit"


@pytest.mark.parametrize("value", [None, ""])
def test_lakebase_dsn_defaults_to_databricks_postgres(conn_mod, monkeypatch, value):
    """Unset, or empty (the bundle variable's default), falls back to the default
    database — an empty dbname would make libpq use the user name instead."""
    monkeypatch.setenv("LAKEBASE_HOST", "ep-x.database.cloud.databricks.com")
    if value is None:
        monkeypatch.delenv("LAKEBASE_DATABASE", raising=False)
    else:
        monkeypatch.setenv("LAKEBASE_DATABASE", value)
    assert conn_mod._build_dsn(token="tok")["dbname"] == "databricks_postgres"


def test_bundle_connects_to_synced_table_database():
    """The app reads the synced table from the database it connects to, so the bundle
    must feed LAKEBASE_DATABASE and CLASSIFICATION_SYNC_PG_DATABASE the same value."""
    import pathlib
    import re
    text = (pathlib.Path(__file__).parents[2] / "databricks.yml").read_text()
    env = dict(re.findall(r"- name: (\w+)\n\s+value: (.+)", text))
    assert env["LAKEBASE_DATABASE"] == env["CLASSIFICATION_SYNC_PG_DATABASE"]
    assert env["LAKEBASE_DATABASE"] == "${var.lakebase_logical_db}"


def test_local_dsn_sets_search_path(conn_mod, monkeypatch):
    monkeypatch.delenv("LAKEBASE_HOST", raising=False)
    assert conn_mod._build_dsn()["options"] == f"-c search_path={conn_mod.APP_SCHEMA}"


# ── init_db ──────────────────────────────────────────────────────────────────────
def test_init_db_creates_app_schema_before_anything_else(conn_mod, monkeypatch):
    sqls = _run_init_db(conn_mod, monkeypatch, _FakeConn())
    assert sqls[0] == f'CREATE SCHEMA IF NOT EXISTS "{conn_mod.APP_SCHEMA}"'
    tracking = next(i for i, s in enumerate(sqls) if "CREATE TABLE IF NOT EXISTS schema_migrations" in s)
    assert tracking > 0
    assert not any("SET SCHEMA" in s for s in sqls)           # fresh install: nothing to move


def test_init_db_applies_only_pending_migrations(conn_mod, monkeypatch):
    conn = _FakeConn(applied={"001_initial", "002_decisions_class_tag"})
    sqls = _run_init_db(conn_mod, monkeypatch, conn)
    recorded = [p[0] for s, p in conn.executed if s.startswith("INSERT INTO schema_migrations")]
    assert recorded == ["003_tag_config", "004_tag_config_metadata", "005_proposal_state"]
    assert any("CREATE TABLE IF NOT EXISTS tag_config" in s for s in sqls)


def test_init_db_leaves_legacy_public_tables_alone(conn_mod, monkeypatch):
    """An install from before APP_SCHEMA has its tables in `public`. The app no longer
    moves them (that needs table ownership): it starts with its own tables, and an admin
    copies the old data with the optional upgrade notebook (upgrade/)."""
    legacy = {"public.schema_migrations", "public.principals", "public.steward_assignments",
              "public.decisions", "public.tag_config", "public.tag_policy_cache"}
    conn = _FakeConn(existing=legacy)
    sqls = _run_init_db(conn_mod, monkeypatch, conn)
    assert not any("public" in x for x in sqls)
    recorded = [p[0] for x, p in conn.executed if x.startswith("INSERT INTO schema_migrations")]
    assert recorded == ["001_initial", "002_decisions_class_tag", "003_tag_config",
                        "004_tag_config_metadata", "005_proposal_state"]

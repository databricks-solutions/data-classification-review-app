from __future__ import annotations
import pathlib
import pytest

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src" / "data_classification_review_app" / "backend" / "db" / "migrations"
)
SYNCED = "default.classification_results"


@pytest.fixture(scope="session")
def _pg_server(tmp_path_factory):
    """Embedded Postgres (pip `pgserver`). Run: uv run --with pgserver pytest"""
    pgserver = pytest.importorskip("pgserver")
    srv = pgserver.get_server(str(tmp_path_factory.mktemp("pg")), cleanup_mode="stop")
    yield srv


class PgHelper:
    def __init__(self, conn):
        self.conn = conn

    def query(self, sql, params=None):
        from psycopg2.extras import RealDictCursor
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()] if cur.description else []

    def add_result(self, catalog, schema, table, column, tag, confidence="HIGH",
                   frequency=0.9, detected="2026-09-01 06:00:00"):
        self.query(
            'INSERT INTO "default".classification_results '
            "(catalog_name, schema_name, table_name, column_name, class_tag, confidence, "
            "frequency, latest_detected_time, first_detected_time) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (catalog, schema, table, column, tag, confidence, frequency, detected, detected),
        )

    def add_decision(self, column_key, status, modified_tag=None, reviewer="rev@x.com",
                     decided_at="2026-09-02 10:00:00+00", user_added=False, comment=None,
                     applied_at=None, class_tag=None):
        self.query(
            "INSERT INTO decisions (column_key, status, modified_tag, comment, reviewer, "
            "decided_at, user_added, applied_at, class_tag) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (column_key, status, modified_tag, comment, reviewer, decided_at, user_added,
             applied_at, class_tag),
        )

    def add_principal(self, pid, kind="user"):
        self.query(
            "INSERT INTO principals (id, name, kind) VALUES (%s,%s,%s) ON CONFLICT DO NOTHING",
            (pid, pid, kind),
        )

    def add_assignment(self, principal, scope, catalog, schema=None, table=None, kind="user"):
        self.add_principal(principal, kind)
        self.query(
            "INSERT INTO steward_assignments (principal, principal_kind, scope, catalog, "
            "schema_name, table_name) VALUES (%s,%s,%s,%s,%s,%s)",
            (principal, kind, scope, catalog, schema, table),
        )


@pytest.fixture
def pg(_pg_server, monkeypatch):
    """Fresh app schema + synced table; read_model.db_query routed to the embedded DB."""
    import psycopg2
    from data_classification_review_app.backend.db import read_model
    conn = psycopg2.connect(_pg_server.get_uri())
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute('DROP SCHEMA IF EXISTS data_classification_review_app CASCADE')
        cur.execute('DROP SCHEMA IF EXISTS "default" CASCADE')
        cur.execute('CREATE SCHEMA data_classification_review_app')
        cur.execute('CREATE SCHEMA "default"')
        cur.execute("SET search_path = data_classification_review_app")
        for mf in sorted(MIGRATIONS.glob("*.sql")):
            cur.execute(mf.read_text())
        cur.execute(
            'CREATE TABLE "default".classification_results ('
            " catalog_name text, schema_name text, table_name text, column_name text,"
            " class_tag text, confidence text, frequency double precision,"
            " latest_detected_time timestamp, first_detected_time timestamp,"
            " PRIMARY KEY (catalog_name, schema_name, table_name, column_name, class_tag))"
        )
    helper = PgHelper(conn)
    monkeypatch.setattr(read_model, "db_query", helper.query)
    monkeypatch.setattr(read_model, "IS_MOCK", False)
    monkeypatch.setenv("CLASSIFICATION_SYNCED_TABLE", SYNCED)
    monkeypatch.delenv("CLASSIFICATION_CATALOG_FILTER", raising=False)
    yield helper
    conn.close()

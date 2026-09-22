"""Idempotent seed: populate the local PGLite DB from mock data on startup."""
from __future__ import annotations
import json
from .connection import execute, query as db_query


_CREATE_TABLE_COLUMNS = """
CREATE TABLE IF NOT EXISTS table_columns (
  catalog_name    TEXT NOT NULL,
  schema_name     TEXT NOT NULL,
  table_name      TEXT NOT NULL,
  column_name     TEXT NOT NULL,
  data_type       TEXT NOT NULL DEFAULT 'string',
  class_tag       TEXT,
  confidence      TEXT,
  frequency       FLOAT,
  samples         JSONB DEFAULT '[]',
  latest_detected_time TIMESTAMPTZ DEFAULT now(),
  PRIMARY KEY (catalog_name, schema_name, table_name, column_name)
)
"""


def seed_db() -> None:
    from ..mock.data import PRINCIPALS, STEWARD_ASSIGNMENTS, PRE_DECISIONS, _RAW, _row_to_col
    execute(_CREATE_TABLE_COLUMNS)

    # 1. Principals
    if not db_query("SELECT 1 FROM principals LIMIT 1"):
        for p in PRINCIPALS.values():
            execute(
                "INSERT INTO principals "
                "(id, name, email, kind, initials, accent, team, members, is_admin) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (p["id"], p["name"], p.get("email"), p["kind"],
                 p["initials"], p["accent"], p.get("team"), p.get("members"), p["is_admin"]),
            )

    # 2. Steward assignments (let DB generate UUIDs — mock string IDs are not valid UUIDs)
    if not db_query("SELECT 1 FROM steward_assignments LIMIT 1"):
        for a in STEWARD_ASSIGNMENTS:
            execute(
                "INSERT INTO steward_assignments "
                "(principal, principal_kind, scope, catalog, schema_name, table_name) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (a["principal"], a["principal_kind"], a["scope"],
                 a["catalog"], a.get("schema_name"), a.get("table_name")),
            )

    # 3. All columns (classified and unclassified)
    if not db_query("SELECT 1 FROM table_columns LIMIT 1"):
        for row in _RAW:
            col = _row_to_col(row)
            execute(
                "INSERT INTO table_columns "
                "(catalog_name, schema_name, table_name, column_name, data_type, "
                "class_tag, confidence, frequency, samples) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                (col["catalog"], col["schema"], col["table"], col["column"],
                 col["data_type"], col.get("class_tag"), col.get("confidence"),
                 col.get("frequency"), json.dumps(col.get("samples", []))),
            )

    # 4. Pre-existing decisions
    if not db_query("SELECT 1 FROM decisions LIMIT 1"):
        for col_key, d in PRE_DECISIONS.items():
            execute(
                "INSERT INTO decisions "
                "(column_key, status, modified_tag, comment, reviewer, decided_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (col_key, d["status"], d.get("modified_tag"),
                 d.get("comment"), d["reviewer"], d["decided_at"]),
            )

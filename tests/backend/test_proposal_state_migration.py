"""Migration 005 backfills proposal_state from the decisions already recorded."""
from __future__ import annotations
import pathlib

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[2]
    / "src" / "data_classification_review_app" / "backend" / "db" / "migrations"
)


def test_005_backfills_latest_state_per_column_tag(_pg_server):
    import psycopg2
    from psycopg2.extras import RealDictCursor
    conn = psycopg2.connect(_pg_server.get_uri())
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("DROP SCHEMA IF EXISTS mig005 CASCADE")
    cur.execute("CREATE SCHEMA mig005")
    cur.execute("SET search_path = mig005")
    files = sorted(MIGRATIONS.glob("*.sql"))
    for mf in [f for f in files if f.name < "005"]:
        cur.execute(mf.read_text())

    def dec(key, status, decided_at, class_tag=None, modified_tag=None, user_added=False):
        cur.execute(
            "INSERT INTO decisions (column_key, status, modified_tag, reviewer, decided_at, "
            "user_added, class_tag) VALUES (%s,%s,%s,'r',%s,%s,%s)",
            (key, status, modified_tag, decided_at, user_added, class_tag),
        )

    dec("c.s.t.a", "rejected", "2026-09-01 00:00+00")                     # legacy, superseded
    dec("c.s.t.a", "approved", "2026-09-02 00:00+00")                     # legacy, latest
    dec("c.s.t.a", "modified", "2026-09-03 00:00+00", class_tag="x", modified_tag="y")
    dec("c.s.t.b", "approved", "2026-09-01 00:00+00", modified_tag="u", user_added=True)
    dec("steward:a.b.c.d@x.com", "steward_added", "2026-09-01 00:00+00")

    for mf in [f for f in files if f.name >= "005"]:
        cur.execute(mf.read_text())

    cur.execute(
        "SELECT column_name, class_tag, user_added, status, modified_tag FROM proposal_state "
        "ORDER BY column_name, class_tag"
    )
    assert cur.fetchall() == [
        {"column_name": "a", "class_tag": "", "user_added": False, "status": "approved", "modified_tag": None},
        {"column_name": "a", "class_tag": "x", "user_added": False, "status": "modified", "modified_tag": "y"},
        {"column_name": "b", "class_tag": "u", "user_added": True, "status": "approved", "modified_tag": "u"},
    ]

    # New decisions keep it current through the trigger.
    dec("c.s.t.a", "rejected", "2026-09-04 00:00+00", class_tag="x")
    cur.execute("SELECT status FROM proposal_state WHERE column_name = 'a' AND class_tag = 'x'")
    assert cur.fetchone()["status"] == "rejected"

    # The legacy-copy notebook writes schema-qualified, without the app search_path.
    cur.execute("SET search_path = public")
    cur.execute(
        "INSERT INTO mig005.decisions (column_key, status, reviewer, decided_at, class_tag) "
        "VALUES ('c.s.t.n', 'approved', 'r', '2026-09-01 00:00+00', 'q')"
    )
    cur.execute("SELECT status FROM mig005.proposal_state WHERE column_name = 'n'")
    assert cur.fetchone()["status"] == "approved"
    cur.execute("DROP SCHEMA mig005 CASCADE")
    conn.close()

"""Upgrade helper: copy the app tables an earlier version left in `public` into the
app schema. Run optionally by an admin from upgrade/copy_legacy_public_tables."""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "upgrade"))
import legacy_copy as lc  # noqa: E402

APP = "data_classification_review_app"
ALL_VERSIONS = {"001_initial", "002_decisions_class_tag", "003_tag_config",
                "004_tag_config_metadata"}
_COLS = {
    "schema_migrations": ["version", "applied_at"],
    "principals": ["id", "name", "email", "kind", "initials", "accent", "team", "members",
                   "is_admin"],
    "steward_assignments": ["id", "principal", "principal_kind", "scope", "catalog",
                            "schema_name", "table_name"],
    "decisions": ["id", "column_key", "scan_ts", "status", "modified_tag", "comment",
                  "reviewer", "decided_at", "user_added", "applied_at", "class_tag"],
    "tag_config": ["tag_key", "enabled", "updated_at"],
    "tag_policy_cache": ["tag_key", "description", "allowed_values"],
}


class _Cursor:
    """Answers the handful of statements legacy_copy issues, over an in-memory model:
    db[schema][table] = {"cols": [...], "rows": int}; versions live in db[s]["@versions"]."""

    def __init__(self, conn):
        self.conn = conn
        self._rows: list[tuple] = []
        self.rowcount = -1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql: str, params: Any = None):
        sql = " ".join(sql.split())
        self.conn.executed.append(sql)
        if self.conn.fail_on and self.conn.fail_on in sql:
            raise RuntimeError(f"boom: {sql}")
        db = self.conn.work
        if m := re.fullmatch(r"SELECT to_regclass\(%s\) IS NOT NULL", sql):
            s, t = re.fullmatch(r'"(.+)"\."(.+)"', params[0]).groups()
            self._rows = [(t in db.get(s, {}),)]
        elif sql.startswith("SELECT column_name FROM information_schema.columns"):
            s, t = params
            self._rows = [(c,) for c in db.get(s, {}).get(t, {}).get("cols", [])]
        elif m := re.fullmatch(r'SELECT version FROM "(.+)"\.schema_migrations', sql):
            self._rows = [(v,) for v in sorted(db[m[1]]["@versions"])]
        elif m := re.fullmatch(r'SELECT count\(\*\) FROM "(.+)"\."(.+)"', sql):
            self._rows = [(db[m[1]][m[2]]["rows"],)]
        elif m := re.fullmatch(r'INSERT INTO "(.+)"\.schema_migrations \(version\) VALUES \(%s\) '
                               r'ON CONFLICT DO NOTHING RETURNING version', sql):
            versions = db[m[1]]["@versions"]
            if params[0] in versions:
                self._rows = []
            else:
                versions.add(params[0])
                self._rows = [(params[0],)]
        elif m := re.fullmatch(r'INSERT INTO "(.+)"\."(.+)" \((.+)\) SELECT (.+) FROM "(.+)"\."(.+)" '
                               r'ON CONFLICT DO NOTHING', sql):
            tgt, table, cols, sel, src, src_table = m.groups()
            assert table == src_table and cols == sel
            n = db[src][table]["rows"] - self.conn.conflicts.get(table, 0)
            db[tgt][table]["rows"] += n
            self.rowcount = n
        elif m := re.fullmatch(r'DROP TABLE "(.+)"\."(.+)"', sql):
            del db[m[1]][m[2]]
        else:
            raise AssertionError(f"unexpected SQL: {sql}")

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Conn:
    def __init__(self, db, *, fail_on: str | None = None, conflicts=None):
        self.committed = db
        self.work = copy.deepcopy(db)
        self.executed: list[str] = []
        self.fail_on = fail_on
        self.conflicts = conflicts or {}
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return _Cursor(self)

    def commit(self):
        self.committed = copy.deepcopy(self.work)
        self.commits += 1

    def rollback(self):
        self.work = copy.deepcopy(self.committed)
        self.rollbacks += 1


def _schema(rows: dict[str, int], versions=ALL_VERSIONS, cols=None):
    cols = cols or {}
    s: dict[str, Any] = {t: {"cols": cols.get(t, _COLS[t]), "rows": n} for t, n in rows.items()}
    s["schema_migrations"] = {"cols": _COLS["schema_migrations"], "rows": len(versions)}
    s["@versions"] = set(versions)
    return s


def _legacy_db(**over):
    public = _schema({"principals": 3, "steward_assignments": 0, "decisions": 6,
                      "tag_config": 1066, "tag_policy_cache": 1066})
    app = _schema({"principals": 1, "steward_assignments": 0, "decisions": 0,
                   "tag_config": 0, "tag_policy_cache": 0})
    db = {"public": public, APP: app}
    db.update(over)
    return db


def _inserts(conn):
    return [s for s in conn.executed if s.startswith("INSERT INTO") and "schema_migrations" not in s]


# ── dry run ──────────────────────────────────────────────────────────────────────
def test_dry_run_reports_counts_and_writes_nothing():
    conn = _Conn(_legacy_db())
    out = lc.copy_legacy_tables(conn, dry_run=True)
    assert out["status"] == "dry_run"
    assert out["tables"]["decisions"] == {"source_rows": 6, "target_rows": 0, "inserted": None}
    assert out["tables"]["principals"]["target_rows"] == 1
    assert _inserts(conn) == []
    assert lc.MARKER not in conn.committed[APP]["@versions"]


def test_dry_run_is_the_default():
    conn = _Conn(_legacy_db())
    assert lc.copy_legacy_tables(conn)["status"] == "dry_run"
    assert _inserts(conn) == []


# ── copy ─────────────────────────────────────────────────────────────────────────
def test_copy_inserts_in_fk_order_and_marks_target_in_one_transaction():
    conn = _Conn(_legacy_db())
    out = lc.copy_legacy_tables(conn, dry_run=False)
    assert out["status"] == "copied"
    order = [re.search(r'INSERT INTO "[^"]+"\."([^"]+)"', s)[1] for s in _inserts(conn)]
    assert order == ["principals", "steward_assignments", "decisions", "tag_config",
                     "tag_policy_cache"]
    assert out["tables"]["tag_config"]["inserted"] == 1066
    assert conn.commits == 1
    assert lc.MARKER in conn.committed[APP]["@versions"]
    assert conn.committed[APP]["decisions"]["rows"] == 6
    # the marker is claimed before any data is copied
    claim = next(i for i, s in enumerate(conn.executed) if "RETURNING version" in s)
    first_insert = conn.executed.index(_inserts(conn)[0])
    assert claim < first_insert


def test_copy_keeps_rows_the_app_already_has():
    """ON CONFLICT DO NOTHING: e.g. an admin principal created at first login wins."""
    conn = _Conn(_legacy_db(), conflicts={"principals": 1})
    out = lc.copy_legacy_tables(conn, dry_run=False)
    assert out["tables"]["principals"]["inserted"] == 2
    assert all(s.endswith("ON CONFLICT DO NOTHING") for s in _inserts(conn))


def test_copy_uses_only_columns_both_sides_have():
    """A legacy table from an older layout (no decisions.class_tag) still copies."""
    old_cols = {"decisions": [c for c in _COLS["decisions"] if c != "class_tag"]}
    db = _legacy_db()
    db["public"]["decisions"]["cols"] = old_cols["decisions"]
    conn = _Conn(db)
    lc.copy_legacy_tables(conn, dry_run=False)
    decisions_sql = next(s for s in _inserts(conn) if '"decisions"' in s)
    assert '"class_tag"' not in decisions_sql
    assert '"column_key"' in decisions_sql


def test_copy_skips_tables_missing_from_source():
    db = _legacy_db()
    del db["public"]["tag_policy_cache"]
    conn = _Conn(db)
    out = lc.copy_legacy_tables(conn, dry_run=False)
    assert out["tables"]["tag_policy_cache"] == {"source_rows": None, "target_rows": 0,
                                                 "inserted": None}
    assert not any('"tag_policy_cache"' in s for s in _inserts(conn))


def test_second_run_is_a_noop():
    conn = _Conn(_legacy_db())
    lc.copy_legacy_tables(conn, dry_run=False)
    conn.executed.clear()
    out = lc.copy_legacy_tables(conn, dry_run=False)
    assert out["status"] == "already_copied"
    assert _inserts(conn) == []
    assert conn.committed[APP]["decisions"]["rows"] == 6


def test_concurrent_claim_lost_copies_nothing(monkeypatch):
    """Another run claimed the marker between our check and our claim: skip."""
    db = _legacy_db()
    conn = _Conn(db)
    real_execute = _Cursor.execute

    def racing_execute(self, sql, params=None):
        if "RETURNING version" in sql:
            self.conn.work[APP]["@versions"].add(lc.MARKER)   # the other run got there first
        return real_execute(self, sql, params)

    monkeypatch.setattr(_Cursor, "execute", racing_execute)
    out = lc.copy_legacy_tables(conn, dry_run=False)
    assert out["status"] == "already_copied"
    assert _inserts(conn) == []
    assert conn.rollbacks >= 1


def test_failure_rolls_back_everything_including_marker():
    conn = _Conn(_legacy_db(), fail_on='INSERT INTO "data_classification_review_app"."decisions"')
    with pytest.raises(RuntimeError):
        lc.copy_legacy_tables(conn, dry_run=False)
    assert conn.commits == 0
    assert lc.MARKER not in conn.committed[APP]["@versions"]
    assert conn.committed[APP]["principals"]["rows"] == 1     # nothing half-copied
    # and a retry after fixing the cause goes through
    conn.fail_on = None
    assert lc.copy_legacy_tables(conn, dry_run=False)["status"] == "copied"


# ── preconditions ────────────────────────────────────────────────────────────────
def test_requires_target_initialised_by_new_app_version():
    db = _legacy_db()
    del db[APP]
    with pytest.raises(lc.LegacyCopyError, match="Start the new app version"):
        lc.copy_legacy_tables(_Conn(db), dry_run=True)


def test_requires_legacy_tables_in_source():
    db = _legacy_db()
    db["public"] = {}
    with pytest.raises(lc.LegacyCopyError, match="nothing to copy"):
        lc.copy_legacy_tables(_Conn(db), dry_run=True)


def test_requires_target_migrations_to_cover_source():
    db = _legacy_db()
    db[APP]["@versions"] = {"001_initial", "002_decisions_class_tag"}
    with pytest.raises(lc.LegacyCopyError, match="003_tag_config"):
        lc.copy_legacy_tables(_Conn(db), dry_run=True)


def test_rejects_same_or_unsafe_schema_names():
    with pytest.raises(lc.LegacyCopyError):
        lc.copy_legacy_tables(_Conn(_legacy_db()), source_schema=APP, target_schema=APP)
    with pytest.raises(lc.LegacyCopyError):
        lc.copy_legacy_tables(_Conn(_legacy_db()), source_schema='public"; DROP', dry_run=True)


# ── drop legacy ──────────────────────────────────────────────────────────────────
def test_drop_legacy_requires_completed_copy():
    conn = _Conn(_legacy_db())
    with pytest.raises(lc.LegacyCopyError, match="not been copied"):
        lc.drop_legacy_tables(conn)
    assert not any(s.startswith("DROP") for s in conn.executed)


def test_drop_legacy_after_copy_drops_children_first():
    conn = _Conn(_legacy_db())
    lc.copy_legacy_tables(conn, dry_run=False)
    dropped = lc.drop_legacy_tables(conn)
    assert dropped == ["steward_assignments", "principals", "decisions", "tag_config",
                       "tag_policy_cache", "schema_migrations"]
    assert [t for t in conn.committed["public"] if not t.startswith("@")] == []
    assert conn.committed[APP]["decisions"]["rows"] == 6

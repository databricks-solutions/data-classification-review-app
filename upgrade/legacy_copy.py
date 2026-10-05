"""Copy the app tables an earlier version left in `public` into the app schema.

Versions before the dedicated ``data_classification_review_app`` Postgres schema kept
their tables in ``public``. The app no longer moves them at startup (that needs
ownership of the tables); a new install starts with its own, SP-owned tables. This
module is the optional upgrade step an **admin** runs, as themselves, from the
``copy_legacy_public_tables`` notebook next to it.

- Copies ``INSERT … SELECT`` over the columns both sides have, in FK order, with
  ``ON CONFLICT DO NOTHING`` — rows the new app already wrote (e.g. admin principals
  created at first login) are kept.
- All tables plus a marker row in the target's ``schema_migrations`` commit in one
  transaction. The marker is claimed first (``INSERT … ON CONFLICT DO NOTHING
  RETURNING``), so a second or concurrent run copies nothing.
- The legacy tables are left in place unless ``drop_legacy_tables`` is called.

Needs SELECT on the legacy tables and INSERT on the app's tables — the Lakebase
project owner or a ``databricks_superuser`` member has both.
"""
from __future__ import annotations

import re

APP_SCHEMA = "data_classification_review_app"
MARKER = "000_legacy_public_copy"

# FK order: steward_assignments.principal references principals(id).
TABLES = ("principals", "steward_assignments", "decisions", "tag_config", "tag_policy_cache")

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class LegacyCopyError(Exception):
    """A precondition isn't met; the message says what to do."""


def _q(ident: str) -> str:
    return '"' + ident.replace('"', '""') + '"'


def _validate(source_schema: str, target_schema: str) -> None:
    for name in (source_schema, target_schema):
        if not _IDENT_RE.match(name):
            raise LegacyCopyError(f"Invalid schema name: {name!r}")
    if source_schema == target_schema:
        raise LegacyCopyError("source_schema and target_schema must differ")


def _exists(cur, schema: str, table: str) -> bool:
    cur.execute("SELECT to_regclass(%s) IS NOT NULL", (f"{_q(schema)}.{_q(table)}",))
    return bool(cur.fetchone()[0])


def _columns(cur, schema: str, table: str) -> list[str]:
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
        (schema, table),
    )
    return [r[0] for r in cur.fetchall()]


def _versions(cur, schema: str) -> set[str]:
    cur.execute(f"SELECT version FROM {_q(schema)}.schema_migrations")
    return {r[0] for r in cur.fetchall()}


def _count(cur, schema: str, table: str) -> int:
    cur.execute(f"SELECT count(*) FROM {_q(schema)}.{_q(table)}")
    return int(cur.fetchone()[0])


def _check(cur, source_schema: str, target_schema: str) -> set[str]:
    """Raise unless both sides are in a copyable state; return the target's versions."""
    if not _exists(cur, target_schema, "schema_migrations"):
        raise LegacyCopyError(
            f"{target_schema}.schema_migrations doesn't exist. Start the new app version "
            f"once (it creates its tables in {target_schema}), then run this again.")
    if not _exists(cur, source_schema, "schema_migrations"):
        raise LegacyCopyError(
            f"No legacy app tables in {source_schema} ({source_schema}.schema_migrations "
            f"doesn't exist): nothing to copy.")
    target_versions = _versions(cur, target_schema)
    missing = sorted(_versions(cur, source_schema) - target_versions)
    if missing:
        raise LegacyCopyError(
            f"{target_schema} is behind {source_schema}: missing migrations "
            f"{', '.join(missing)}. Deploy and start the newer app version first.")
    return target_versions


def _plan(cur, source_schema: str, target_schema: str) -> dict[str, dict]:
    tables = {}
    for t in TABLES:
        in_source = _exists(cur, source_schema, t)
        tables[t] = {
            "source_rows": _count(cur, source_schema, t) if in_source else None,
            "target_rows": _count(cur, target_schema, t),
            "inserted": None,
        }
    return tables


def copy_legacy_tables(conn, source_schema: str = "public",
                       target_schema: str = APP_SCHEMA, *, dry_run: bool = True) -> dict:
    """Copy the legacy app tables once. Returns ``{"status", "tables"}`` where status is
    ``dry_run`` | ``copied`` | ``already_copied`` and tables maps each table to
    ``source_rows`` / ``target_rows`` (before the copy) / ``inserted``."""
    _validate(source_schema, target_schema)
    try:
        with conn.cursor() as cur:
            target_versions = _check(cur, source_schema, target_schema)
            tables = _plan(cur, source_schema, target_schema)
            if MARKER in target_versions:
                conn.rollback()
                return {"status": "already_copied", "tables": tables}
            if dry_run:
                conn.rollback()
                return {"status": "dry_run", "tables": tables}

            # Claim first: a concurrent run blocks on the marker's key, then skips.
            cur.execute(
                f"INSERT INTO {_q(target_schema)}.schema_migrations (version) VALUES (%s) "
                f"ON CONFLICT DO NOTHING RETURNING version", (MARKER,))
            if cur.fetchone() is None:
                conn.rollback()
                return {"status": "already_copied", "tables": tables}

            for t in TABLES:
                if tables[t]["source_rows"] is None:
                    continue
                source_cols = set(_columns(cur, source_schema, t))
                cols = [c for c in _columns(cur, target_schema, t) if c in source_cols]
                if not cols:
                    raise LegacyCopyError(f"{source_schema}.{t} and {target_schema}.{t} "
                                          f"share no columns")
                col_list = ", ".join(_q(c) for c in cols)
                cur.execute(
                    f"INSERT INTO {_q(target_schema)}.{_q(t)} ({col_list}) "
                    f"SELECT {col_list} FROM {_q(source_schema)}.{_q(t)} "
                    f"ON CONFLICT DO NOTHING")
                tables[t]["inserted"] = cur.rowcount
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"status": "copied", "tables": tables}


def drop_legacy_tables(conn, source_schema: str = "public",
                       target_schema: str = APP_SCHEMA) -> list[str]:
    """Drop the legacy tables, only once the copy has committed. Returns what was dropped.

    Children first (steward_assignments before principals); no CASCADE, so anything
    else depending on them makes this fail instead of silently dropping it.
    """
    _validate(source_schema, target_schema)
    dropped = []
    try:
        with conn.cursor() as cur:
            if (not _exists(cur, target_schema, "schema_migrations")
                    or MARKER not in _versions(cur, target_schema)):
                raise LegacyCopyError(
                    f"The legacy tables have not been copied into {target_schema} yet "
                    f"(no {MARKER} marker); copy them first.")
            for t in ("steward_assignments", "principals", "decisions", "tag_config",
                      "tag_policy_cache", "schema_migrations"):
                if _exists(cur, source_schema, t):
                    cur.execute(f"DROP TABLE {_q(source_schema)}.{_q(t)}")
                    dropped.append(t)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return dropped

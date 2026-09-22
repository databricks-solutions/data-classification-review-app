from __future__ import annotations
import httpx
from databricks.sdk import WorkspaceClient


def _w() -> WorkspaceClient:
    # Credentials resolved automatically: env vars, profile, or Databricks Apps OAuth.
    return WorkspaceClient()


def get_table(full_name: str, token: str | None = None, host: str | None = None) -> dict:
    """Return TableInfo dict with 'comment' (table description) and a 'columns' list —
    each column also carries its own 'comment' (column description) — for the given
    three-part name."""
    if token and host:
        base = f"https://{host}" if not host.startswith("http") else host
        resp = httpx.get(
            f"{base.rstrip('/')}/api/2.1/unity-catalog/tables/{full_name}",
            headers=_uc_headers(token),
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        return {
            "comment": body.get("comment"),
            "columns": [
                {
                    "name": c.get("name"), "type_text": c.get("type_text", ""),
                    "type_name": c.get("type_name", ""), "comment": c.get("comment"),
                }
                for c in body.get("columns", [])
            ],
        }
    w = _w()
    t = w.tables.get(full_name)
    columns = [
        {"name": c.name, "type_text": c.type_text, "type_name": str(c.type_name), "comment": c.comment}
        for c in (t.columns or [])
    ]
    return {"comment": t.comment, "columns": columns}


def _uc_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def column_tag_exists(token: str, host: str, catalog: str, schema: str, table: str, column: str, tag: str) -> bool:
    """Check if a column already has the given tag via the UC REST API."""
    base = f"https://{host}" if not host.startswith("http") else host
    resp = httpx.get(
        f"{base.rstrip('/')}/api/2.1/unity-catalog/tables/{catalog}.{schema}.{table}",
        headers=_uc_headers(token),
        timeout=30,
    )
    if resp.status_code != 200:
        return False
    for col in resp.json().get("columns", []):
        if col.get("name") == column:
            return any(t.get("key") == tag for t in col.get("tags", []))
    return False


def set_column_tag(token: str, host: str, catalog: str, schema: str, table: str, column: str, tag: str) -> None:
    """Set a column tag via the UC REST API (no SQL scope required)."""
    base = f"https://{host}" if not host.startswith("http") else host
    full_name = f"{catalog}.{schema}.{table}"
    resp = httpx.patch(
        f"{base.rstrip('/')}/api/2.1/unity-catalog/tables/{full_name}",
        headers=_uc_headers(token),
        json={"columns": [{"name": column, "tags": [{"key": tag, "value": ""}]}]},
        timeout=30,
    )
    resp.raise_for_status()


def get_column_tags(catalog: str, schema: str, table: str,
                     token: str | None, host: str | None) -> list[dict]:
    """Return column-level UC tags for the given table via information_schema.column_tags.
    Raises on failure — the caller decides how to report it (see routes/tables.py)."""
    from .warehouse import execute_sql
    rows = execute_sql(
        f"SELECT column_name, tag_name, tag_value FROM `{catalog}`.information_schema.column_tags "
        f"WHERE schema_name='{schema}' AND table_name='{table}'",
        token=token, host=host,
    )
    return [
        {"column_name": r["column_name"], "tag_name": r["tag_name"], "tag_value": r.get("tag_value")}
        for r in rows
    ]


def get_table_level_tags(catalog: str, schema: str, table: str,
                          token: str | None, host: str | None) -> list[str]:
    """Return the table's own UC tags (not column tags) via information_schema.table_tags.

    The dedicated entity-tag-assignments REST/SDK API (used in an earlier version of
    this function — see docs/superpowers/specs/2026-07-02-uc-metadata-source-benchmarks.md)
    403s for OBO tokens issued to a Databricks App: the app's declared `user_api_scopes`
    (databricks.yml) don't cover whatever scope that API requires, even though the same
    OBO token succeeds against GetTable and information_schema.column_tags for the same
    user on the same table (confirmed via production app logs). information_schema is
    already used for column_tags via the same execute_sql/warehouse path, which does not
    have this scope problem, so it's used here too for consistency and to avoid the gap.
    Raises on failure — the caller decides how to report it."""
    from .warehouse import execute_sql
    rows = execute_sql(
        f"SELECT tag_name, tag_value FROM `{catalog}`.information_schema.table_tags "
        f"WHERE schema_name='{schema}' AND table_name='{table}'",
        token=token, host=host,
    )
    return [f"{r['tag_name']}={r['tag_value']}" if r.get("tag_value") else r["tag_name"] for r in rows]

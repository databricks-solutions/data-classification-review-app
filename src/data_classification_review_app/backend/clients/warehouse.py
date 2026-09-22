from __future__ import annotations
import os
import re
import httpx
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

_IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_TAG_RE = re.compile(r'^[A-Za-z0-9_.]+$')


def validate_identifier(v: str, name: str = "identifier") -> str:
    """Raise ValueError if v is not a safe SQL identifier (letters, digits, underscores, hyphens)."""
    if not _IDENTIFIER_RE.match(v):
        raise ValueError(f"Invalid {name}: {v!r}")
    return v


def quote_identifier(v: str) -> str:
    """Wrap a single SQL identifier in backticks, escaping embedded backticks."""
    return "`" + v.replace("`", "``") + "`"


def quote_full_name(full_name: str) -> str:
    """Quote a dot-separated catalog.schema.table name as `cat`.`schema`.`table`."""
    return ".".join(quote_identifier(p) for p in full_name.split("."))


def validate_tag(v: str) -> str:
    """Raise ValueError if v is not a safe UC tag name (letters, digits, underscores, dots)."""
    if not _TAG_RE.match(v):
        raise ValueError(f"Invalid tag: {v!r}")
    return v


def _sdk() -> WorkspaceClient:
    # Let the SDK resolve credentials automatically (env vars, profile, Databricks Apps
    # OAuth injection). Avoid passing host= explicitly so the Apps runtime token isn't
    # overridden by a stale env var.
    return WorkspaceClient()


def execute_sql(sql: str, token: str | None = None, host: str | None = None) -> list[dict]:
    """Execute SQL on the configured warehouse and return rows as list of dicts.

    When token and host are provided, calls the REST API directly via httpx so the
    OBO Bearer token is passed without SDK auth wrapping (avoids `sql` scope issues).
    """
    warehouse_id = os.environ["WAREHOUSE_ID"]
    if token and host:
        base = f"https://{host}" if not host.startswith("http") else host
        resp = httpx.post(
            f"{base.rstrip('/')}/api/2.0/sql/statements",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"statement": sql, "wait_timeout": "30s", "warehouse_id": warehouse_id},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        state = data.get("status", {}).get("state", "")
        if state != "SUCCEEDED":
            err = data.get("status", {}).get("error", {})
            raise RuntimeError(f"SQL failed [{err.get('error_code')}]: {err.get('message')}")
        result = data.get("result") or {}
        if not result.get("data_array"):
            return []
        cols = [c["name"] for c in data.get("manifest", {}).get("schema", {}).get("columns", [])]
        return [dict(zip(cols, row)) for row in result["data_array"]]

    w = WorkspaceClient(token=token, auth_type="pat") if token else _sdk()
    response = w.statement_execution.execute_statement(
        warehouse_id=warehouse_id,
        statement=sql,
        wait_timeout="30s",
    )
    if response.status.state != StatementState.SUCCEEDED:
        err = response.status.error
        raise RuntimeError(f"SQL failed [{err.error_code}]: {err.message}")
    if not response.result or not response.result.data_array:
        return []
    cols = [c.name for c in response.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in response.result.data_array]

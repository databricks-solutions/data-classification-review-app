from __future__ import annotations
import os
import re
import time
from typing import Any, Callable
import httpx
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementState

_IDENTIFIER_RE = re.compile(r'^[A-Za-z0-9_-]+$')
_TAG_RE = re.compile(r'^[A-Za-z0-9_.]+$')

# A statement not finished within the submit's wait_timeout (e.g. while a stopped
# warehouse starts) comes back PENDING/RUNNING with no error and keeps running; poll
# it up to _MAX_WAIT_S more before canceling.
_IN_PROGRESS = {"PENDING", "RUNNING"}
_POLL_INTERVAL_S = 2.0
_MAX_WAIT_S = 300.0
_sleep = time.sleep


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


def _await_statement(resp: Any, state_of: Callable[[Any], str],
                     poll: Callable[[], Any], cancel: Callable[[], None]) -> Any:
    """Poll a statement while it is PENDING/RUNNING; cancel and raise past _MAX_WAIT_S."""
    waited = 0.0
    while state_of(resp) in _IN_PROGRESS:
        if waited >= _MAX_WAIT_S:
            cancel()
            raise RuntimeError(f"SQL still {state_of(resp)} after waiting "
                               f"{int(waited)}s more for the warehouse; statement canceled")
        _sleep(_POLL_INTERVAL_S)
        waited += _POLL_INTERVAL_S
        resp = poll()
    return resp


def execute_sql(sql: str, token: str | None = None, host: str | None = None) -> list[dict]:
    """Execute SQL on the configured warehouse and return rows as list of dicts.

    When token and host are provided, calls the REST API directly via httpx so the
    OBO Bearer token is passed without SDK auth wrapping (avoids `sql` scope issues).
    """
    warehouse_id = os.environ["WAREHOUSE_ID"]
    if token and host:
        base = f"https://{host}" if not host.startswith("http") else host
        url = f"{base.rstrip('/')}/api/2.0/sql/statements"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        resp = httpx.post(
            url,
            headers=headers,
            json={"statement": sql, "wait_timeout": "30s", "warehouse_id": warehouse_id},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        statement_url = f"{url}/{data.get('statement_id')}"

        def _get() -> dict:
            r = httpx.get(statement_url, headers=headers, timeout=60)
            r.raise_for_status()
            return r.json()

        data = _await_statement(
            data, lambda d: d.get("status", {}).get("state", ""), _get,
            lambda: httpx.post(f"{statement_url}/cancel", headers=headers, timeout=60))
        state = data.get("status", {}).get("state", "")
        if state != "SUCCEEDED":
            err = data.get("status", {}).get("error")
            if not err:
                raise RuntimeError(f"SQL failed ({state or 'unknown state'}) with no error details")
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
    statement_id = response.statement_id
    response = _await_statement(
        response, lambda r: r.status.state.value,
        lambda: w.statement_execution.get_statement(statement_id),
        lambda: w.statement_execution.cancel_execution(statement_id))
    if response.status.state != StatementState.SUCCEEDED:
        err = response.status.error
        if err is None:
            raise RuntimeError(f"SQL failed ({response.status.state.value}) with no error details")
        raise RuntimeError(f"SQL failed [{err.error_code}]: {err.message}")
    if not response.result or not response.result.data_array:
        return []
    cols = [c.name for c in response.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in response.result.data_array]

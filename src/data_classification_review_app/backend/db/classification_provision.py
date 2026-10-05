"""Provisioning of the classification read path, run by the app at startup.

The app runs as its own service principal, so doing this here — rather than in the
install script under the deploying user — means the SP **creates and owns**:

1. the deduped view over the classification results table. A Unity Catalog view
   executes with its owner's privileges, so an SP-owned view (with SELECT on the
   source system table) is what lets the SNAPSHOT synced table populate regardless
   of who installed the app;
2. the SNAPSHOT Lakebase synced table over that view, and so its DLT pipeline
   (which runs as its owner, the SP). Creating it runs the initial snapshot;
3. the ``classification_sync`` job — a single pipeline task that refreshes that
   pipeline on a schedule (see ``classification_job``).

Best-effort and idempotent: never raises into startup, and every start re-applies
the view and the job definition, and creates the synced table only if missing.

The outcome of the last run (state, failed step, error, grant hint) is kept in memory
and surfaced to admins on the overview page, whose Refresh re-runs provisioning via
``start_provisioning`` while it isn't ready.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from ..clients.warehouse import execute_sql, quote_full_name
from ..core._config import logger
from .classification_job import build_job_settings, ensure_sync_job

_DEFAULT_CRON = "0 0 0 */1 * ?"   # daily at 00:00 UTC

# Projection for the deduped view. Mirrors what the read path expects; the PK is the
# subset that identifies one detection per column-tag.
_VIEW_COLUMNS = (
    "catalog_name", "schema_name", "table_name", "column_name", "class_tag",
    "confidence", "frequency", "latest_detected_time", "first_detected_time",
)
_PRIMARY_KEY_COLUMNS = [
    "catalog_name", "schema_name", "table_name", "column_name", "class_tag",
]


# ── provisioning status ──────────────────────────────────────────────────────────
# In-process state guarded by a threading.Lock. This relies on the app running a
# single uvicorn worker (app.yml ``--workers 1``): every request — from any user —
# sees the same state, and the lock makes ``start_provisioning`` single-flight. With
# several workers/instances each process would have its own state and could run
# provisioning concurrently (e.g. two ``jobs.create`` → duplicate sync jobs).
#
# state: pending (not attempted yet) | running | ready | failed | not_configured
#        | disabled (mock mode)
_lock = threading.Lock()
_ERROR_MAX_LEN = 2000


def _initial_status() -> dict:
    return {"state": "pending", "step": None, "error": None, "hint": None, "updated_at": None}


_status = _initial_status()


def _set_status(state: str, *, step: str | None = None, error: str | None = None,
                hint: str | None = None) -> None:
    with _lock:
        _status.update(state=state, step=step,
                       error=error[:_ERROR_MAX_LEN] if error else None, hint=hint,
                       updated_at=datetime.now(timezone.utc).isoformat())


def provisioning_status() -> dict:
    """Snapshot of the last provisioning run, plus the app SP grants must go to."""
    with _lock:
        snapshot = dict(_status)
    snapshot["service_principal"] = os.environ.get("DATABRICKS_CLIENT_ID", "").strip() or None
    return snapshot


def _step_hint(step: str, env: dict[str, str]) -> str:
    """What the app service principal needs for ``step`` — shown next to the error."""
    view_uc = env["CLASSIFICATION_VIEW_UC"]
    catalog, _, rest = view_uc.partition(".")
    schema = f"{catalog}.{rest.partition('.')[0]}"
    branch = env["CLASSIFICATION_SYNC_BRANCH"]              # projects/<p>/branches/<b>
    project = branch.split("/")[1] if branch.startswith("projects/") else branch
    if step == "view":
        return (f"The app service principal needs USE CATALOG on `{catalog}`, "
                f"ALL PRIVILEGES on `{schema}`, and SELECT on "
                f"`{env['CLASSIFICATION_RESULTS_TABLE']}` (with USE CATALOG / USE SCHEMA "
                f"on its catalog and schema).")
    if step == "synced_table":
        return (f"The app service principal needs CAN USE on the Lakebase project "
                f"`{project}` and ALL PRIVILEGES on `{schema}`, where the synced table "
                f"`{env['CLASSIFICATION_SYNCED_TABLE_UC']}` is registered.")
    if step == "pipeline":
        return (f"The synced table `{env['CLASSIFICATION_SYNCED_TABLE_UC']}` was created, "
                f"but its pipeline wasn't assigned in time. Check its status in Catalog "
                f"Explorer, then retry.")
    return ("The app service principal couldn't create or update the "
            "classification sync job. Check the error, then retry.")


def start_provisioning() -> threading.Thread | None:
    """Run ``provision_classification`` in a background thread unless one is running.

    Single-flight: returns the started thread, or None when a run is already in
    progress (startup run, or another admin's Retry).
    """
    with _lock:
        if _status["state"] == "running":
            return None
        _status.update(state="running", step=None, error=None, hint=None,
                       updated_at=datetime.now(timezone.utc).isoformat())

    def _run() -> None:
        try:
            provision_classification()
        except Exception as exc:  # provision_classification shouldn't raise; belt and braces
            logger.exception("classification provisioning crashed")
            _set_status("failed", error=str(exc))
            return
        if provisioning_status()["state"] == "running":
            _set_status("failed", error="provisioning ended without reporting a result")

    thread = threading.Thread(target=_run, name="classification-provision", daemon=True)
    thread.start()
    return thread


def build_view_sql(view_uc: str, source_table: str) -> str:
    """CREATE OR REPLACE VIEW <view> AS <latest-per-column-tag dedup over source>."""
    cols = ", ".join(_VIEW_COLUMNS)
    return (
        f"CREATE OR REPLACE VIEW {quote_full_name(view_uc)} AS\n"
        f"SELECT {cols}\n"
        f"FROM {quote_full_name(source_table)}\n"
        f"WHERE class_tag IS NOT NULL\n"
        f"QUALIFY ROW_NUMBER() OVER (\n"
        f"  PARTITION BY catalog_name, schema_name, table_name, column_name, class_tag\n"
        f"  ORDER BY latest_detected_time DESC\n"
        f") = 1"
    )


def ensure_view(view_uc: str, source_table: str) -> None:
    """Create/replace the SP-owned view on the configured warehouse (as the SP)."""
    execute_sql(build_view_sql(view_uc, source_table))
    logger.info("classification view ready: %s", view_uc)


def _synced_table_resource_name(synced_uc: str) -> str:
    """Full resource name the postgres synced-table API uses for get/delete."""
    return f"synced_tables/{synced_uc}"


def ensure_synced_table(ws, *, synced_uc: str, view_uc: str,
                        branch: str, postgres_database: str) -> bool:
    """Create the SNAPSHOT synced table if it doesn't already exist.

    Uses the Lakebase **Autoscaling** synced-table API (``postgres.*``), which targets
    a project branch + Postgres database — not the classic ``database.*`` API, which
    requires a provisioned Database Instance that Autoscaling workspaces don't have.

    Returns True when a create was issued, False when it already existed.
    """
    from databricks.sdk.errors import NotFound

    try:
        ws.postgres.get_synced_table(name=_synced_table_resource_name(synced_uc))
        logger.info("synced table already exists: %s", synced_uc)
        return False
    except NotFound:
        pass

    from databricks.sdk.service.postgres import (
        SyncedTable,
        SyncedTableSyncedTableSpec,
        SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy as SchedulingPolicy,
    )

    # synced_table_id is the bare UC tuple "catalog.schema.table"; the API prepends
    # the "synced_tables/" resource prefix itself.
    ws.postgres.create_synced_table(
        synced_table_id=synced_uc,
        synced_table=SyncedTable(spec=SyncedTableSyncedTableSpec(
            branch=branch,
            postgres_database=postgres_database,
            source_table_full_name=view_uc,
            primary_key_columns=list(_PRIMARY_KEY_COLUMNS),
            scheduling_policy=SchedulingPolicy.SNAPSHOT,
            create_database_objects_if_missing=True,
        )),
    )
    logger.info("synced table created: %s (source %s)", synced_uc, view_uc)
    return True


def wait_for_pipeline_id(ws, synced_uc: str, *, timeout_s: float = 900, interval_s: float = 10,
                         sleep: Callable[[float], None] = time.sleep) -> str | None:
    """Poll the synced table until its backing pipeline id is assigned (None on timeout).

    A freshly created synced table only gets a pipeline id once its pipeline
    resources are provisioned, which can take a few minutes.
    """
    waited = 0.0
    while True:
        table = ws.postgres.get_synced_table(name=_synced_table_resource_name(synced_uc))
        pipeline_id = getattr(getattr(table, "status", None), "pipeline_id", None)
        if pipeline_id:
            return pipeline_id
        if waited >= timeout_s:
            return None
        sleep(interval_s)
        waited += interval_s


def provision_classification(ws=None, *, sleep: Callable[[float], None] = time.sleep) -> None:
    """Best-effort: view → synced table → pipeline id → refresh job. Never raises.

    Skipped entirely in mock mode or when not configured. Each step needs the
    previous one, so a failure stops there (logged and recorded in the status); the
    next start, or an admin's Retry, re-runs it.
    """
    if os.environ.get("USE_MOCK_DATA", "false").lower() == "true":
        _set_status("disabled")
        return

    env = {k: os.environ.get(k, "").strip() for k in (
        "CLASSIFICATION_VIEW_UC", "CLASSIFICATION_RESULTS_TABLE",
        "CLASSIFICATION_SYNCED_TABLE_UC", "CLASSIFICATION_SYNC_BRANCH",
        "CLASSIFICATION_SYNC_PG_DATABASE",
    )}
    if not all(env.values()):
        missing = [k for k, v in env.items() if not v]
        logger.info("classification provisioning skipped — not configured (%s)", ", ".join(missing))
        _set_status("not_configured",
                    error=f"Missing app environment: {', '.join(missing)}",
                    hint="Re-run scripts/install.sh so the bundle sets these variables.")
        return
    view_uc = env["CLASSIFICATION_VIEW_UC"]
    synced_uc = env["CLASSIFICATION_SYNCED_TABLE_UC"]

    def fail(step: str, exc: Exception | None = None, error: str | None = None) -> None:
        _set_status("failed", step=step, error=error or str(exc), hint=_step_hint(step, env))

    _set_status("running", step="view")
    try:
        ensure_view(view_uc, env["CLASSIFICATION_RESULTS_TABLE"])
    except Exception as exc:
        logger.exception("classification view provisioning failed (continuing)")
        fail("view", exc)
        return  # no point creating the synced table if its source view is missing

    _set_status("running", step="synced_table")
    try:
        if ws is None:
            from databricks.sdk import WorkspaceClient
            ws = WorkspaceClient()
        ensure_synced_table(ws, synced_uc=synced_uc, view_uc=view_uc,
                            branch=env["CLASSIFICATION_SYNC_BRANCH"],
                            postgres_database=env["CLASSIFICATION_SYNC_PG_DATABASE"])
        _set_status("running", step="pipeline")
        pipeline_id = wait_for_pipeline_id(ws, synced_uc, sleep=sleep)
    except Exception as exc:
        logger.exception("synced-table provisioning failed (continuing)")
        fail(provisioning_status()["step"] or "synced_table", exc)
        return
    if not pipeline_id:
        logger.warning("synced table %s has no pipeline id yet — sync job not created; "
                       "the next app start retries", synced_uc)
        fail("pipeline", error=f"Synced table {synced_uc} has no pipeline id yet.")
        return

    _set_status("running", step="job")
    try:
        from ... import __version__
        settings = build_job_settings(
            pipeline_id=pipeline_id,
            cron=os.environ.get("CLASSIFICATION_SYNC_CRON", "").strip() or _DEFAULT_CRON,
            app_version=__version__,
        )
        managers = os.environ.get("CLASSIFICATION_SYNC_JOB_MANAGERS", "").split(",")
        ensure_sync_job(ws, settings, managers)
    except Exception as exc:
        logger.exception("classification sync job provisioning failed (continuing)")
        fail("job", exc)
        return
    _set_status("ready")

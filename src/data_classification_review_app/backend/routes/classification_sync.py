from __future__ import annotations
import os
import threading
from databricks.sdk.errors import DatabricksError, NotFound, ResourceConflict
from fastapi import APIRouter, HTTPException
from ..core import Dependencies
from ..core._config import logger
from ..db import classification_provision as provision
from .stewards import _assert_admin

router = APIRouter()

# SyncedTableState values that mean a sync is actively in progress.
_RUNNING_STATES = {
    "SYNCED_TABLE_PROVISIONING",
    "SYNCED_TABLE_PROVISIONING_INITIAL_SNAPSHOT",
    "SYNCED_TABLE_PROVISIONING_PIPELINE_RESOURCES",
    "SYNCED_TABLE_ONLINE_TRIGGERED_UPDATE",
    "SYNCED_TABLE_ONLINE_UPDATING_PIPELINE_RESOURCES",
    "SYNCED_TABLE_ONLINE_CONTINUOUS_UPDATE",
}

# Serializes the check-then-start of a pipeline refresh across concurrent admin
# requests (single uvicorn worker — see classification_provision).
_refresh_lock = threading.Lock()
_NO_SYNC: dict = {"state": None, "last_sync_end": None, "running": False, "pipeline_id": None}


def _synced_table_name() -> str:
    name = os.environ.get("CLASSIFICATION_SYNCED_TABLE_UC", "").strip()
    if not name:
        raise HTTPException(status_code=503, detail="classification_sync_not_configured")
    return f"synced_tables/{name}"


def _sync_state(ws) -> dict:
    """Read the synced table's data-sync status via the Lakebase Autoscaling API.

    Also resolves the backing DLT pipeline id from the status, so callers don't have
    to be told the id at deploy time (it only exists once the synced table is created).
    """
    name = _synced_table_name()                  # 503 before touching the API if unset
    t = ws.postgres.get_synced_table(name=name)
    st = getattr(t, "status", None)
    state = getattr(st, "detailed_state", None)
    last = getattr(st, "last_sync_time", None)
    if last is None:
        ls = getattr(st, "last_sync", None)
        last = getattr(ls, "sync_end_time", None) if ls is not None else None
    if last is not None and not isinstance(last, (str, int, float)):
        if hasattr(last, "ToJsonString"):          # SDK protobuf Timestamp → RFC 3339
            last = last.ToJsonString()
        else:
            last = getattr(last, "isoformat", lambda: str(last))()
    raw = getattr(state, "value", state)         # enum.value, or the raw string
    state_str = str(raw) if raw is not None else None
    running = state_str in _RUNNING_STATES
    pipeline_id = getattr(st, "pipeline_id", None)
    return {"state": state_str, "last_sync_end": last, "running": running,
            "pipeline_id": pipeline_id}


@router.get("/classification-sync/status", operation_id="classificationSyncStatus")
def get_sync_status(ws: Dependencies.Client, headers: Dependencies.Headers):
    _assert_admin(headers)
    prov = provision.provisioning_status()
    try:
        state = _sync_state(ws)
    except (HTTPException, NotFound):
        # Not configured / not created yet — the provisioning status explains why.
        state = dict(_NO_SYNC)
    except DatabricksError as exc:
        logger.warning("classification sync status unavailable: %s", exc)
        state = dict(_NO_SYNC)
    state.pop("pipeline_id", None)   # internal detail; not part of the status response
    state["running"] = bool(state["running"]) or prov["state"] == "running"
    state["provisioning"] = prov
    return state


@router.post("/classification-sync/refresh", operation_id="classificationSyncRefresh")
def refresh_sync(ws: Dependencies.Client, headers: Dependencies.Headers):
    _assert_admin(headers)
    # Until provisioning has succeeded there is no synced table / pipeline to refresh:
    # re-run provisioning instead (single-flight, in the background).
    if provision.provisioning_status()["state"] not in ("ready", "disabled"):
        started = provision.start_provisioning() is not None
        return {"started": started, "running": True, "provisioning": True}

    with _refresh_lock:
        state = _sync_state(ws)
        if state["running"]:
            return {"started": False, "running": True}
        # Resolve the pipeline by the synced table's own status rather than a deploy-time
        # env var — the id only exists once the synced table has been provisioned.
        pipeline_id = (state.get("pipeline_id") or "").strip()
        if not pipeline_id:
            raise HTTPException(status_code=503, detail="classification_sync_not_configured")
        try:
            ws.pipelines.start_update(pipeline_id=pipeline_id)
        except ResourceConflict:
            # An update is already active (another admin, or the scheduled job) and the
            # synced-table state hasn't caught up yet.
            return {"started": False, "running": True}
    return {"started": True, "running": True}

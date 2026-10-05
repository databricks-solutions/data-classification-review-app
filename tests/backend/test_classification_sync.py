from __future__ import annotations
import pytest
from pydantic import SecretStr


def _headers(email="admin@example.com"):
    from data_classification_review_app.backend.core._headers import DatabricksAppsHeaders
    return DatabricksAppsHeaders(host=None, user_name=None, user_id=None,
        user_email=email, request_id=None, token=SecretStr("tok"))


class _FakePipelines:
    def __init__(self): self.started = None
    def start_update(self, pipeline_id): self.started = pipeline_id
    def get_update(self, pipeline_id, update_id): ...


class _FakeWS:
    def __init__(self):
        self.pipelines = _FakePipelines()


def _prov(state="ready", **kw):
    return {"state": state, "step": None, "error": None, "hint": None,
            "updated_at": None, "service_principal": "sp-1", **kw}


@pytest.fixture(autouse=True)
def _provisioning_ready(monkeypatch):
    """Default: provisioning finished, so Refresh drives the pipeline as before."""
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: _prov("ready"))


def test_status_requires_admin(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    from fastapi import HTTPException
    monkeypatch.setattr(mod, "_assert_admin", lambda h: (_ for _ in ()).throw(HTTPException(status_code=403)))
    with pytest.raises(HTTPException) as exc:
        mod.get_sync_status(ws=_FakeWS(), headers=_headers("x@y.z"))
    assert exc.value.status_code == 403


def test_refresh_starts_pipeline(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    # pipeline id is resolved from the synced-table status, not an env var
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": "IDLE", "last_sync_end": None, "running": False, "pipeline_id": "pipe-1"})
    ws = _FakeWS()
    out = mod.refresh_sync(ws=ws, headers=_headers())
    assert out == {"started": True, "running": True}
    assert ws.pipelines.started == "pipe-1"


def test_refresh_noop_when_running(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": "RUNNING", "last_sync_end": None, "running": True, "pipeline_id": "pipe-1"})
    ws = _FakeWS()
    out = mod.refresh_sync(ws=ws, headers=_headers())
    assert out == {"started": False, "running": True}
    assert ws.pipelines.started is None


def test_refresh_503_when_pipeline_unresolved(monkeypatch):
    """refresh_sync raises 503 when the synced-table status has no pipeline id yet."""
    from data_classification_review_app.backend.routes import classification_sync as mod
    from fastapi import HTTPException
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": "IDLE", "last_sync_end": None, "running": False, "pipeline_id": None})
    ws = _FakeWS()
    with pytest.raises(HTTPException) as exc:
        mod.refresh_sync(ws=ws, headers=_headers())
    assert exc.value.status_code == 503
    assert exc.value.detail == "classification_sync_not_configured"


def test_refresh_503_when_pipeline_id_empty(monkeypatch):
    """refresh_sync raises 503 when the resolved pipeline id is an empty string."""
    from data_classification_review_app.backend.routes import classification_sync as mod
    from fastapi import HTTPException
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": "IDLE", "last_sync_end": None, "running": False, "pipeline_id": ""})
    ws = _FakeWS()
    with pytest.raises(HTTPException) as exc:
        mod.refresh_sync(ws=ws, headers=_headers())
    assert exc.value.status_code == 503
    assert exc.value.detail == "classification_sync_not_configured"


def test_sync_state_running_classification(monkeypatch):
    """_sync_state correctly classifies SyncedTableState enum values as running / not-running."""
    from data_classification_review_app.backend.routes import classification_sync as mod

    monkeypatch.setenv("CLASSIFICATION_SYNCED_TABLE_UC", "main.default.cls_proposals")

    class _FakeState:
        def __init__(self, value): self.value = value

    class _FakeSyncStatus:
        def __init__(self, state_value):
            self.detailed_state = _FakeState(state_value)
            self.last_sync_time = "2026-01-01T00:00:00Z"
            self.pipeline_id = "pipe-42"

    class _FakeTable:
        def __init__(self, state_value):
            self.status = _FakeSyncStatus(state_value)

    class _FakePostgres:
        def __init__(self, state_value): self._state_value = state_value
        def get_synced_table(self, name): return _FakeTable(self._state_value)

    class _FakeWSWithDB:
        def __init__(self, state_value): self.postgres = _FakePostgres(state_value)

    # A running state must be detected as running
    result_running = mod._sync_state(_FakeWSWithDB("SYNCED_TABLE_ONLINE_UPDATING_PIPELINE_RESOURCES"))
    assert result_running["running"] is True
    assert result_running["state"] == "SYNCED_TABLE_ONLINE_UPDATING_PIPELINE_RESOURCES"
    assert result_running["pipeline_id"] == "pipe-42"

    # A non-running state must NOT be detected as running
    result_idle = mod._sync_state(_FakeWSWithDB("SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE"))
    assert result_idle["running"] is False
    assert result_idle["state"] == "SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE"


def test_sync_state_serializes_sdk_protobuf_timestamp(monkeypatch):
    """Regression: the SDK parses status.last_sync.sync_end_time into a protobuf
    Timestamp (no isoformat()); str() of it is "seconds: …\\nnanos: …", which the UI
    renders as "Invalid Date". It must come out as an RFC 3339 string."""
    from datetime import datetime
    from databricks.sdk.service.postgres import SyncedTable
    from data_classification_review_app.backend.routes import classification_sync as mod

    monkeypatch.setenv("CLASSIFICATION_SYNCED_TABLE_UC", "cat.sch.results")
    # Real payload shape returned by GET /api/2.0/postgres/synced_tables/<uc>.
    table = SyncedTable.from_dict({"status": {
        "detailed_state": "SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE",
        "last_sync": {"sync_end_time": "2026-09-25T13:25:39.139437Z",
                      "sync_start_time": "2026-09-25T13:25:24.889248Z"},
        "pipeline_id": "pipe-1",
    }})

    class _WS:
        class postgres:
            @staticmethod
            def get_synced_table(name): return table

    out = mod._sync_state(_WS())
    assert out["last_sync_end"] == "2026-09-25T13:25:39.139437Z"
    datetime.fromisoformat(out["last_sync_end"])   # parseable (JS Date accepts RFC 3339 too)
    assert out["running"] is False


def test_router_assembles_with_classification_sync_routes():
    """Regression: classification_sync must use its own APIRouter(), not the
    create_router() singleton. Using the singleton makes router.include_router
    self-include and app import dies with 'Cannot include the same APIRouter
    instance into itself'. Importing the assembled router exercises that path."""
    from data_classification_review_app.backend.router import router
    paths = {getattr(r, "path", "") for r in router.routes}
    assert any(p.endswith("/classification-sync/status") for p in paths)
    assert any(p.endswith("/classification-sync/refresh") for p in paths)


# ── provisioning surfaced through status / refresh ──────────────────────────────
def test_status_includes_provisioning_and_tolerates_missing_synced_table(monkeypatch):
    from databricks.sdk.errors import NotFound
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setenv("CLASSIFICATION_SYNCED_TABLE_UC", "cat.sch.results")
    failed = _prov("failed", step="view", error="PERMISSION_DENIED", hint="grant it")
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: failed)

    class _WS:
        class postgres:
            @staticmethod
            def get_synced_table(name): raise NotFound("no synced table")

    out = mod.get_sync_status(ws=_WS(), headers=_headers())
    assert out["state"] is None and out["last_sync_end"] is None
    assert out["running"] is False
    assert out["provisioning"] == failed
    assert "pipeline_id" not in out


def test_status_does_not_503_when_synced_table_unset(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.delenv("CLASSIFICATION_SYNCED_TABLE_UC", raising=False)
    nc = _prov("not_configured", error="Missing app environment: CLASSIFICATION_SYNCED_TABLE_UC")
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: nc)
    out = mod.get_sync_status(ws=_FakeWS(), headers=_headers())
    assert out["state"] is None
    assert out["provisioning"]["state"] == "not_configured"


def test_status_running_while_provisioning(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: _prov("running", step="view"))
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": None, "last_sync_end": None, "running": False, "pipeline_id": None})
    out = mod.get_sync_status(ws=_FakeWS(), headers=_headers())
    assert out["running"] is True


@pytest.mark.parametrize("state", ["failed", "not_configured", "pending"])
def test_refresh_reruns_provisioning_when_not_ready(monkeypatch, state):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: _prov(state))
    started = []
    monkeypatch.setattr(mod.provision, "start_provisioning", lambda: started.append(1) or object())
    monkeypatch.setattr(mod, "_sync_state", lambda ws: pytest.fail("must not touch the pipeline"))
    ws = _FakeWS()
    out = mod.refresh_sync(ws=ws, headers=_headers())
    assert out == {"started": True, "running": True, "provisioning": True}
    assert started == [1]
    assert ws.pipelines.started is None


def test_refresh_while_provisioning_running_is_noop(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: _prov("running"))
    monkeypatch.setattr(mod.provision, "start_provisioning", lambda: None)
    out = mod.refresh_sync(ws=_FakeWS(), headers=_headers())
    assert out == {"started": False, "running": True, "provisioning": True}


def test_refresh_mock_mode_uses_pipeline_path(monkeypatch):
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod.provision, "provisioning_status", lambda: _prov("disabled"))
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": "IDLE", "last_sync_end": None, "running": False, "pipeline_id": "pipe-1"})
    ws = _FakeWS()
    assert mod.refresh_sync(ws=ws, headers=_headers()) == {"started": True, "running": True}
    assert ws.pipelines.started == "pipe-1"


def test_refresh_active_update_conflict_reports_running(monkeypatch):
    """Two admins refreshing at once: the pipeline rejects the second start_update
    because an update is already active — report it as running, not a 500."""
    from databricks.sdk.errors import ResourceConflict
    from data_classification_review_app.backend.routes import classification_sync as mod
    monkeypatch.setattr(mod, "_assert_admin", lambda h: None)
    monkeypatch.setattr(mod, "_sync_state", lambda ws: {
        "state": "IDLE", "last_sync_end": None, "running": False, "pipeline_id": "pipe-1"})
    ws = _FakeWS()

    def conflict(pipeline_id):
        raise ResourceConflict("An active update already exists")

    ws.pipelines.start_update = conflict
    assert mod.refresh_sync(ws=ws, headers=_headers()) == {"started": False, "running": True}

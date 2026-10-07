from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from databricks.sdk.errors import NotFound

_ENV = {
    "USE_MOCK_DATA": "false",
    "CLASSIFICATION_VIEW_UC": "cat.sch.view_v",
    "CLASSIFICATION_RESULTS_TABLE": "system.data_classification.results",
    "CLASSIFICATION_SYNCED_TABLE_UC": "cat.sch.results",
    "CLASSIFICATION_SYNC_BRANCH": "projects/x/branches/prod",
    "CLASSIFICATION_SYNC_PG_DATABASE": "databricks_postgres",
    "CLASSIFICATION_SYNC_CRON": "0 0 */6 * * ?",
    "CLASSIFICATION_SYNC_JOB_MANAGERS": "dep@x.com,admin@x.com",
}


class _FakePostgres:
    """Synced table that is missing until created; pipeline id appears after N gets."""

    def __init__(self, exists: bool, pipeline_id: str | None = "pipe-1", ready_after: int = 0):
        self._exists = exists
        self._pipeline_id = pipeline_id
        self._ready_after = ready_after
        self.gets = 0
        self.created: Any = None
        self.created_id = None

    def get_synced_table(self, name):
        if not self._exists:
            raise NotFound(f"no such table: {name}")
        self.gets += 1
        pid = self._pipeline_id if self.gets > self._ready_after else None
        return SimpleNamespace(status=SimpleNamespace(pipeline_id=pid))

    def create_synced_table(self, synced_table, synced_table_id):
        self.created = synced_table
        self.created_id = synced_table_id
        self._exists = True
        return synced_table


class _FakeWS:
    def __init__(self, **pg):
        self.postgres: Any = _FakePostgres(**pg)


@pytest.fixture
def env(monkeypatch):
    for k, v in _ENV.items():
        monkeypatch.setenv(k, v)
    return monkeypatch


@pytest.fixture
def mod():
    from data_classification_review_app.backend.db import classification_provision
    return classification_provision


@pytest.fixture
def calls(monkeypatch, mod):
    """Stub the warehouse + job side effects and record what was called."""
    rec: dict[str, Any] = {"sql": [], "job": None}
    monkeypatch.setattr(mod, "execute_sql", lambda sql: rec["sql"].append(sql))

    def _ensure_job(ws, settings, managers):
        rec["job"] = (settings, managers)
        return 101

    monkeypatch.setattr(mod, "ensure_sync_job", _ensure_job)
    return rec


# ── view SQL ─────────────────────────────────────────────────────────────────────
def test_build_view_sql_shape(mod):
    sql = mod.build_view_sql("cat.sch.view_v", "system.data_classification.results")
    assert "CREATE OR REPLACE VIEW `cat`.`sch`.`view_v` AS" in sql
    assert "FROM `system`.`data_classification`.`results`" in sql
    assert "WHERE class_tag IS NOT NULL" in sql
    assert "QUALIFY ROW_NUMBER() OVER" in sql
    assert sql.rstrip().endswith("= 1")


# ── ensure_synced_table ──────────────────────────────────────────────────────────
def test_ensure_synced_table_skips_when_exists(mod):
    ws = _FakeWS(exists=True)
    assert mod.ensure_synced_table(
        ws, synced_uc="cat.sch.results", view_uc="cat.sch.view_v",
        branch="projects/x/branches/prod", postgres_database="databricks_postgres",
    ) is False
    assert ws.postgres.created is None


def test_ensure_synced_table_creates_snapshot_with_pk(mod):
    from databricks.sdk.service.postgres import (
        SyncedTableSyncedTableSpecSyncedTableSchedulingPolicy as SchedulingPolicy,
    )
    ws = _FakeWS(exists=False)
    assert mod.ensure_synced_table(
        ws, synced_uc="cat.sch.results", view_uc="cat.sch.view_v",
        branch="projects/x/branches/prod", postgres_database="databricks_postgres",
    ) is True
    assert ws.postgres.created_id == "cat.sch.results"
    spec = ws.postgres.created.spec
    assert spec.source_table_full_name == "cat.sch.view_v"
    assert spec.scheduling_policy == SchedulingPolicy.SNAPSHOT
    assert spec.primary_key_columns == [
        "catalog_name", "schema_name", "table_name", "column_name", "class_tag",
    ]
    assert spec.branch == "projects/x/branches/prod"
    assert spec.postgres_database == "databricks_postgres"
    assert spec.create_database_objects_if_missing is True


# ── wait_for_pipeline_id ─────────────────────────────────────────────────────────
def test_wait_for_pipeline_id_polls_until_assigned(mod):
    ws = _FakeWS(exists=True, pipeline_id="pipe-9", ready_after=2)
    slept = []
    assert mod.wait_for_pipeline_id(ws, "cat.sch.results", timeout_s=60, interval_s=5,
                                    sleep=slept.append) == "pipe-9"
    assert slept == [5, 5]


def test_wait_for_pipeline_id_gives_up(mod):
    ws = _FakeWS(exists=True, pipeline_id=None)
    slept = []
    assert mod.wait_for_pipeline_id(ws, "cat.sch.results", timeout_s=20, interval_s=5,
                                    sleep=slept.append) is None
    assert sum(slept) == 20


# ── provision_classification orchestration ───────────────────────────────────────
def test_provision_creates_view_synced_table_then_pipeline_job(env, mod, calls):
    ws = _FakeWS(exists=False, pipeline_id="pipe-7")
    mod.provision_classification(ws=ws, sleep=lambda s: None)
    assert calls["sql"] == [mod.build_view_sql("cat.sch.view_v", "system.data_classification.results")]
    assert ws.postgres.created_id == "cat.sch.results"
    settings, managers = calls["job"]
    assert settings.tasks[0].pipeline_task.pipeline_id == "pipe-7"
    assert settings.schedule.quartz_cron_expression == "0 0 */6 * * ?"
    assert settings.tags["app_version"]          # tagged with the running app version
    assert managers == ["dep@x.com", "admin@x.com"]


def test_provision_view_failure_stops_before_synced_table(env, mod, calls, monkeypatch):
    def boom(sql):
        raise RuntimeError("no SELECT on system table")

    monkeypatch.setattr(mod, "execute_sql", boom)
    ws = _FakeWS(exists=False)
    mod.provision_classification(ws=ws, sleep=lambda s: None)   # must not raise
    assert ws.postgres.created is None
    assert calls["job"] is None


def test_provision_no_pipeline_id_skips_job(env, mod, calls):
    ws = _FakeWS(exists=True, pipeline_id=None)
    mod.provision_classification(ws=ws, sleep=lambda s: None)
    assert calls["job"] is None


def test_provision_skips_in_mock_mode(env, mod, calls):
    env.setenv("USE_MOCK_DATA", "true")
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    assert calls["sql"] == [] and calls["job"] is None


@pytest.mark.parametrize("missing", [
    "CLASSIFICATION_VIEW_UC", "CLASSIFICATION_RESULTS_TABLE", "CLASSIFICATION_SYNCED_TABLE_UC",
    "CLASSIFICATION_SYNC_BRANCH", "CLASSIFICATION_SYNC_PG_DATABASE",
])
def test_provision_skips_when_unconfigured(env, mod, calls, missing):
    env.delenv(missing)
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    assert calls["sql"] == [] and calls["job"] is None


def test_provision_job_failure_is_non_fatal(env, mod, calls, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("PERMISSION_DENIED")

    monkeypatch.setattr(mod, "ensure_sync_job", boom)
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)   # no raise


# ── provisioning status (surfaced to admins on the overview page) ───────────────
@pytest.fixture(autouse=True)
def _fresh_status(monkeypatch, mod):
    """Each test starts from a clean, never-attempted provisioning status."""
    monkeypatch.setattr(mod, "_status", mod._initial_status())


def test_status_ready_after_success(env, mod, calls):
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    st = mod.provisioning_status()
    assert st["state"] == "ready"
    assert st["step"] is None and st["error"] is None and st["hint"] is None
    assert st["updated_at"]


def test_status_failed_on_view_with_grant_hint(env, mod, calls, monkeypatch):
    def boom(sql):
        raise RuntimeError("SQL failed [BAD_REQUEST]: PERMISSION_DENIED: User does not have "
                           "USE CATALOG on Catalog 'cat'.")

    monkeypatch.setattr(mod, "execute_sql", boom)
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    st = mod.provisioning_status()
    assert st["state"] == "failed"
    assert st["step"] == "view"
    assert "USE CATALOG on Catalog 'cat'" in st["error"]
    assert "USE CATALOG on `cat`" in st["hint"]
    assert "`cat.sch`" in st["hint"]
    assert "`system.data_classification.results`" in st["hint"]


def test_status_failed_on_synced_table_mentions_lakebase_project(env, mod, calls):
    from databricks.sdk.errors import PermissionDenied

    ws = _FakeWS(exists=False)

    def deny(**kw):
        raise PermissionDenied("no CAN_USE on project")

    ws.postgres.create_synced_table = deny
    mod.provision_classification(ws=ws, sleep=lambda s: None)
    st = mod.provisioning_status()
    assert st["state"] == "failed" and st["step"] == "synced_table"
    assert "no CAN_USE on project" in st["error"]
    assert "Lakebase project `x`" in st["hint"]


def test_status_failed_when_pipeline_id_never_assigned(env, mod, calls):
    mod.provision_classification(ws=_FakeWS(exists=True, pipeline_id=None), sleep=lambda s: None)
    st = mod.provisioning_status()
    assert st["state"] == "failed" and st["step"] == "pipeline"
    assert "cat.sch.results" in st["hint"]


def test_status_failed_on_job(env, mod, calls, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("PERMISSION_DENIED: cannot create job")

    monkeypatch.setattr(mod, "ensure_sync_job", boom)
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    st = mod.provisioning_status()
    assert st["state"] == "failed" and st["step"] == "job"
    assert "cannot create job" in st["error"]


def test_status_not_configured_lists_missing_env(env, mod, calls):
    env.delenv("CLASSIFICATION_VIEW_UC")
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    st = mod.provisioning_status()
    assert st["state"] == "not_configured"
    assert "CLASSIFICATION_VIEW_UC" in st["error"]


def test_status_disabled_in_mock_mode(env, mod, calls):
    env.setenv("USE_MOCK_DATA", "true")
    mod.provision_classification(ws=_FakeWS(exists=False), sleep=lambda s: None)
    assert mod.provisioning_status()["state"] == "disabled"


def test_status_reports_app_service_principal(env, mod):
    env.setenv("DATABRICKS_CLIENT_ID", "sp-123")
    assert mod.provisioning_status()["service_principal"] == "sp-123"


def test_start_provisioning_is_single_flight(env, mod, monkeypatch):
    """Two admins clicking Retry at once (or a click during the startup run) must not
    start a second concurrent run — it could create a duplicate sync job."""
    import threading

    release = threading.Event()
    runs = []

    def slow_provision():
        runs.append(1)
        release.wait(5)
        mod._set_status("ready")

    monkeypatch.setattr(mod, "provision_classification", slow_provision)
    first = mod.start_provisioning()
    assert first is not None
    assert mod.provisioning_status()["state"] == "running"
    assert mod.start_provisioning() is None          # already running → no second thread
    release.set()
    first.join(5)
    assert runs == [1]
    assert mod.provisioning_status()["state"] == "ready"
    second = mod.start_provisioning()               # finished → can run again
    assert second is not None
    second.join(5)


def test_start_provisioning_marks_failed_if_run_crashes(env, mod, monkeypatch):
    def crash():
        raise RuntimeError("unexpected")

    monkeypatch.setattr(mod, "provision_classification", crash)
    mod.start_provisioning().join(5)
    st = mod.provisioning_status()
    assert st["state"] == "failed"
    assert "unexpected" in st["error"]

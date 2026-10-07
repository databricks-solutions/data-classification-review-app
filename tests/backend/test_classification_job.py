from __future__ import annotations

from types import SimpleNamespace
from typing import Any

_SP = "sp-app-id"


class _FakeJobs:
    def __init__(self, existing=()):
        self._existing = list(existing)
        self.created: Any = None
        self.reset_calls = []
        self.permissions: Any = None

    def list(self, name=None):
        return [j for j in self._existing if j.settings.name == name]

    def create(self, **kwargs):
        self.created = kwargs
        return SimpleNamespace(job_id=101)

    def reset(self, job_id, new_settings):
        self.reset_calls.append((job_id, new_settings))

    def update_permissions(self, job_id, access_control_list=None):
        self.permissions = (job_id, access_control_list)


class _FakeWS:
    def __init__(self, existing=()):
        self.jobs: Any = _FakeJobs(existing)
        self.current_user = SimpleNamespace(me=lambda: SimpleNamespace(user_name=_SP))


def _existing_job(job_id, creator):
    from data_classification_review_app.backend.db import classification_job as mod
    return SimpleNamespace(job_id=job_id, creator_user_name=creator,
                           settings=SimpleNamespace(name=mod.SYNC_JOB_NAME))


def _settings(pipeline_id="pipe-1"):
    from data_classification_review_app.backend.db import classification_job as mod
    return mod.build_job_settings(pipeline_id=pipeline_id, cron="0 0 0 */1 * ?",
                                  app_version="9.9.9")


# ── job definition ─────────────────────────────────────────────────────────────
def test_build_job_settings_single_pipeline_task():
    from data_classification_review_app.backend.db import classification_job as mod
    s = _settings("pipe-42")
    assert s.name == mod.SYNC_JOB_NAME
    assert s.max_concurrent_runs == 1
    assert len(s.tasks) == 1
    task = s.tasks[0]
    assert task.task_key == "refresh_synced_table"
    assert task.pipeline_task.pipeline_id == "pipe-42"
    assert task.pipeline_task.full_refresh is False
    assert task.notebook_task is None
    assert s.schedule.quartz_cron_expression == "0 0 0 */1 * ?"
    assert s.schedule.timezone_id == "UTC"
    assert s.schedule.pause_status.value == "UNPAUSED"
    # deploy.sh waits for the job tagged with the version it just deployed
    assert s.tags == {"managed_by": "data-classification-review-app", "app_version": "9.9.9"}
    # no run_as: the job runs as its creator — the app SP
    assert s.run_as is None


def test_managers_acl_dedups_and_maps_service_principals():
    from data_classification_review_app.backend.db import classification_job as mod
    acl = mod.managers_acl(["dep@x.com", "admin@x.com", "dep@x.com",
                            "0a1b2c3d-0000-1111-2222-333344445555", " "])
    assert [(a.user_name, a.service_principal_name) for a in acl] == [
        ("dep@x.com", None), ("admin@x.com", None),
        (None, "0a1b2c3d-0000-1111-2222-333344445555"),
    ]
    assert all(a.permission_level.value == "CAN_MANAGE" for a in acl)


# ── ensure_sync_job: create vs reset ────────────────────────────────────────────
def test_ensure_sync_job_creates_when_missing():
    from data_classification_review_app.backend.db import classification_job as mod
    ws = _FakeWS()
    job_id = mod.ensure_sync_job(ws, _settings(), managers=["dep@x.com"])
    assert job_id == 101
    assert ws.jobs.created["name"] == mod.SYNC_JOB_NAME
    assert ws.jobs.created["tasks"][0].pipeline_task.pipeline_id == "pipe-1"
    assert ws.jobs.created["tags"]["app_version"] == "9.9.9"
    assert "run_as" not in ws.jobs.created
    assert ws.jobs.reset_calls == []
    pid, acl = ws.jobs.permissions
    assert pid == "101" and acl[0].user_name == "dep@x.com"


def test_ensure_sync_job_resets_own_existing_job():
    """Every start re-applies the definition — e.g. a new pipeline id or app version."""
    from data_classification_review_app.backend.db import classification_job as mod
    ws = _FakeWS(existing=[_existing_job(7, _SP)])
    job_id = mod.ensure_sync_job(ws, _settings("pipe-new"), managers=[])
    assert job_id == 7
    assert ws.jobs.created is None
    (reset_id, new_settings), = ws.jobs.reset_calls
    assert reset_id == 7
    assert new_settings.tasks[0].pipeline_task.pipeline_id == "pipe-new"
    assert ws.jobs.permissions is None   # no managers → no ACL call


def test_ensure_sync_job_ignores_same_named_job_from_another_creator():
    """A leftover (e.g. the old bundle-managed, deployer-owned job) must not be reset."""
    from data_classification_review_app.backend.db import classification_job as mod
    ws = _FakeWS(existing=[_existing_job(7, "deployer@x.com")])
    job_id = mod.ensure_sync_job(ws, _settings(), managers=[])
    assert job_id == 101
    assert ws.jobs.reset_calls == []

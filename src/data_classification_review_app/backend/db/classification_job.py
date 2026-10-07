"""Create/update the classification_sync job as the app service principal.

The job has a single **pipeline** task that refreshes the synced table's pipeline on
a schedule. The app creates it (see ``classification_provision``), running as its SP,
because a job runs as its creator and running as yourself needs no extra role — a
deployer-created job with ``run_as`` = SP would need the "Service Principal User"
role on the SP, which only an account admin can grant on locked-down workspaces.
The pipeline itself runs as its owner: the SP, which created the synced table.
"""
from __future__ import annotations

import re

from ..core._config import logger

SYNC_JOB_NAME = "data-classification-review classification sync"
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def build_job_settings(*, pipeline_id: str, cron: str, app_version: str):
    """The job definition. No run_as — the job runs as its creator (the app SP).

    Tagged with ``app_version`` so scripts/deploy.sh can tell that the app it just
    deployed has finished provisioning.
    """
    from databricks.sdk.service.jobs import (
        CronSchedule, JobSettings, PauseStatus, PipelineTask, Task,
    )

    return JobSettings(
        name=SYNC_JOB_NAME,
        max_concurrent_runs=1,
        tags={"managed_by": "data-classification-review-app", "app_version": app_version},
        schedule=CronSchedule(quartz_cron_expression=cron, timezone_id="UTC",
                              pause_status=PauseStatus.UNPAUSED),
        tasks=[Task(
            task_key="refresh_synced_table",
            pipeline_task=PipelineTask(pipeline_id=pipeline_id, full_refresh=False),
        )],
    )


def managers_acl(managers: list[str]):
    """CAN_MANAGE for each manager (deployer + admins); UUIDs are SP application ids."""
    from databricks.sdk.service.jobs import JobAccessControlRequest, JobPermissionLevel

    acl, seen = [], set()
    for m in (x.strip() for x in managers):
        if not m or m in seen:
            continue
        seen.add(m)
        if _UUID_RE.match(m):
            acl.append(JobAccessControlRequest(service_principal_name=m,
                                               permission_level=JobPermissionLevel.CAN_MANAGE))
        else:
            acl.append(JobAccessControlRequest(user_name=m,
                                               permission_level=JobPermissionLevel.CAN_MANAGE))
    return acl


def ensure_sync_job(ws, settings, managers: list[str]) -> int:
    """Create the job, or reset the one this SP created earlier. Returns the job id.

    Only a job *created by this SP* is reused, so a same-named job owned by someone
    else (e.g. the old bundle-managed, deployer-owned job) is never touched.
    """
    me = ws.current_user.me().user_name
    own = [j for j in ws.jobs.list(name=settings.name) if j.creator_user_name == me]
    if own:
        job_id = own[0].job_id
        ws.jobs.reset(job_id, settings)
        logger.info("classification sync job updated: %s", job_id)
    else:
        job_id = ws.jobs.create(
            name=settings.name,
            max_concurrent_runs=settings.max_concurrent_runs,
            tags=settings.tags,
            schedule=settings.schedule,
            tasks=settings.tasks,
        ).job_id
        logger.info("classification sync job created: %s", job_id)

    acl = managers_acl(managers)
    if acl:
        # PATCH semantics: adds the managers, keeps the SP's IS_OWNER.
        ws.jobs.update_permissions(str(job_id), access_control_list=acl)
    return job_id

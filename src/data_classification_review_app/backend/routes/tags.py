from __future__ import annotations
import logging
import os
from fastapi import APIRouter, HTTPException
from ..models import TagConfigOut, TagRefreshOut, TagPatchIn, TagPatchOut
from ..db.connection import query as db_query, execute
from ..core.dependencies import Dependencies
from ..routes.stewards import _assert_admin

logger = logging.getLogger(__name__)

IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"

router = APIRouter()


def _is_system_tag(tag_key: str) -> bool:
    return tag_key.startswith("class.")


def _upsert_tag(tag_key: str, enabled: bool, description: str | None = None, allowed_values: list[str] | None = None) -> None:
    execute(
        "INSERT INTO tag_config (tag_key, enabled, updated_at) VALUES (%s, %s, now()) "
        "ON CONFLICT (tag_key) DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = now()",
        (tag_key, enabled),
    )
    if description is not None or allowed_values is not None:
        execute(
            "INSERT INTO tag_policy_cache (tag_key, description, allowed_values) VALUES (%s, %s, %s) "
            "ON CONFLICT (tag_key) DO UPDATE SET "
            "  description = EXCLUDED.description, "
            "  allowed_values = EXCLUDED.allowed_values",
            (tag_key, description, allowed_values or []),
        )


def _count_active_proposals(tag_key: str) -> int:
    rows = db_query(
        "SELECT COUNT(*) AS cnt FROM decisions "
        "WHERE status NOT IN ('applied', 'rejected') "
        "AND (class_tag = %s OR modified_tag = %s)",
        (tag_key, tag_key),
    )
    return int(rows[0]["cnt"]) if rows else 0


@router.get("/tags", response_model=list[TagConfigOut], operation_id="listTags")
def list_tags(enabled_only: bool = False, headers: Dependencies.Headers = None):
    if not enabled_only:
        _assert_admin(headers)
    rows = db_query(
        "SELECT tc.tag_key, tc.enabled, tpc.description, tpc.allowed_values "
        "FROM tag_config tc "
        "LEFT JOIN tag_policy_cache tpc ON tc.tag_key = tpc.tag_key "
        "ORDER BY tc.tag_key"
    )
    result = [TagConfigOut(key=r["tag_key"], enabled=r["enabled"], description=r.get("description"), allowed_values=r.get("allowed_values") or []) for r in rows]
    if enabled_only:
        result = [t for t in result if t.enabled]
    return result


@router.post("/tags/refresh", response_model=TagRefreshOut, operation_id="refreshTags")
def refresh_tags(headers: Dependencies.Headers = None):
    _assert_admin(headers)

    if IS_MOCK:
        mock_keys = [
            "class.name", "class.email_address", "class.phone_number",
            "class.location", "class.address", "class.ssn", "class.credit_card",
            "class.date_of_birth", "class.ip_address", "class.gender", "class.bank_account",
        ]
        uc_tags = [{"tag_key": k, "description": None, "values": []} for k in mock_keys]
    else:
        try:
            from databricks.sdk import WorkspaceClient
            w = WorkspaceClient()
            policies = list(w.tag_policies.list_tag_policies())
            uc_tags = [
                {
                    "tag_key": p.tag_key,
                    "description": p.description,
                    "values": [{"name": v.name} for v in (p.values or []) if v.name],
                }
                for p in policies if p.tag_key
            ]
        except Exception as e:
            logger.error("Failed to fetch tag policies from UC: %s", e, exc_info=True)
            raise HTTPException(502, "Failed to fetch tags from Databricks. Check workspace connectivity.")

    existing = {r["tag_key"] for r in db_query("SELECT tag_key FROM tag_config")}
    new_tags = [p for p in uc_tags if p["tag_key"] not in existing]

    added_enabled = 0
    added_disabled = 0
    for policy in uc_tags:
        tag_key = policy["tag_key"]
        description = policy.get("description")
        allowed_values = [v["name"] for v in policy.get("values", []) if v.get("name")]
        if tag_key not in existing:
            enabled = _is_system_tag(tag_key)
            _upsert_tag(tag_key, enabled, description, allowed_values)
            if enabled:
                added_enabled += 1
            else:
                added_disabled += 1
        else:
            # Always refresh metadata for existing tags
            execute(
                "INSERT INTO tag_policy_cache (tag_key, description, allowed_values) VALUES (%s, %s, %s) "
                "ON CONFLICT (tag_key) DO UPDATE SET "
                "  description = EXCLUDED.description, "
                "  allowed_values = EXCLUDED.allowed_values",
                (tag_key, description, allowed_values),
            )


    total_rows = db_query("SELECT COUNT(*) AS cnt FROM tag_config")
    total = int(total_rows[0]["cnt"]) if total_rows else 0

    return TagRefreshOut(
        added=len(new_tags),
        added_enabled=added_enabled,
        added_disabled=added_disabled,
        total=total,
    )


@router.patch("/tags/{tag_key}", response_model=TagPatchOut, operation_id="patchTag")
def patch_tag(tag_key: str, body: TagPatchIn, headers: Dependencies.Headers = None):
    _assert_admin(headers)

    if not body.enabled:
        count = _count_active_proposals(tag_key)
        if count > 0 and not body.force:
            return TagPatchOut(key=tag_key, enabled=True, active_proposals=count)
        _upsert_tag(tag_key, False)
        return TagPatchOut(key=tag_key, enabled=False, active_proposals=count if body.force else 0)

    _upsert_tag(tag_key, True)
    return TagPatchOut(key=tag_key, enabled=True, active_proposals=0)

from __future__ import annotations
import logging
import os
from fastapi import APIRouter, Request
from ..models import ApplyTagItem, ApplyTagsIn, ApplyTagsOut
from ..db.connection import execute, query as db_query
from ..core.dependencies import Dependencies

router = APIRouter()
IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"
logger = logging.getLogger(__name__)


def _get_reviewer(request: Request, headers: "Dependencies.Headers") -> str:
    if IS_MOCK:
        return request.headers.get("X-Mock-User", "jamie.diaz")
    return headers.user_email or os.environ.get("DEV_USER_EMAIL") or "unknown"


def _record_applied(item: ApplyTagItem, tag: str, reviewer: str) -> None:
    """Mark this proposal's decisions applied and record the 'applied' decision."""
    execute(
        "UPDATE decisions SET applied_at = now() WHERE column_key = %s AND user_added = %s "
        "AND CASE WHEN user_added THEN COALESCE(modified_tag, class_tag) ELSE class_tag END = %s",
        (item.column_key, item.user_added, item.class_tag),
    )
    execute(
        "INSERT INTO decisions (column_key, status, modified_tag, class_tag, reviewer, user_added, applied_at) "
        "VALUES (%s,'applied',%s,%s,%s,%s,now())",
        (item.column_key, tag, item.class_tag, reviewer, item.user_added),
    )


@router.post("/apply-tags", response_model=ApplyTagsOut, operation_id="applyTags")
def apply_tags(body: ApplyTagsIn, request: Request, headers: Dependencies.Headers):
    if not IS_MOCK and not headers.token:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="User token required to apply tags")
    token = headers.token.get_secret_value() if headers.token else None
    # X-Forwarded-Host is the app's own domain — use DATABRICKS_HOST env var for the workspace URL
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    if not host:
        try:
            from databricks.sdk import WorkspaceClient
            host = (WorkspaceClient().config.host or "").rstrip("/")
        except Exception:
            pass
    applied, skipped, errors = 0, 0, []
    reviewer = _get_reviewer(request, headers)

    for item in body.items:
        col_key = item.column_key
        parts = col_key.split(".")
        if len(parts) < 4:
            errors.append({"column_key": col_key, "error": "invalid column key format"})
            continue
        catalog, schema, table, column = parts[0], parts[1], parts[2], ".".join(parts[3:])

        # Resolve the tag: a steward-added proposal applies its own tag; a scanner proposal
        # applies its modified tag, if any — its own decision first, else a legacy
        # whole-column one (class_tag '').
        tag = item.class_tag
        if not item.user_added:
            state = db_query(
                "SELECT modified_tag FROM proposal_state WHERE catalog_name = %s AND schema_name = %s "
                "AND table_name = %s AND column_name = %s AND NOT user_added AND class_tag IN (%s, '') "
                "ORDER BY class_tag = '' LIMIT 1",
                (catalog, schema, table, column, item.class_tag),
            )
            if state and state[0].get("modified_tag"):
                tag = state[0]["modified_tag"]

        if not tag:
            skipped += 1
            continue

        if IS_MOCK:
            _record_applied(item, tag, reviewer)
            applied += 1
            continue

        # Tags with constrained values are stored as "key=value"; split before validation
        if '=' in tag:
            tag_key, tag_value = tag.split('=', 1)
        else:
            tag_key, tag_value = tag, ''

        try:
            from ..clients.warehouse import validate_identifier, validate_tag
            catalog = validate_identifier(catalog, "catalog")
            schema = validate_identifier(schema, "schema")
            table = validate_identifier(table, "table")
            column = validate_identifier(column, "column")
            tag_key = validate_tag(tag_key)
            if tag_value:
                tag_value = validate_tag(tag_value)
        except ValueError as ve:
            errors.append({"column_key": col_key, "error": str(ve)})
            continue

        from ..clients.warehouse import execute_sql
        try:
            # information_schema is catalog-scoped in Unity Catalog — there is no
            # top-level one, so it must be qualified with the target catalog
            # (`catalog` is already validated as a safe identifier above).
            existing = execute_sql(
                f"SELECT tag_name FROM `{catalog}`.information_schema.column_tags "
                f"WHERE schema_name='{schema}' "
                f"AND table_name='{table}' AND column_name='{column}' AND tag_name='{tag_key}'",
                token=token, host=host,
            )
        except Exception as e:
            logger.error("apply_tags check failed for %s: %s", col_key, e, exc_info=True)
            errors.append({"column_key": col_key, "error": str(e)})
            continue
        if existing:
            skipped += 1
            continue
        try:
            execute_sql(
                f"ALTER TABLE `{catalog}`.`{schema}`.`{table}` "
                f"ALTER COLUMN `{column}` SET TAGS ('{tag_key}' = '{tag_value}')",
                token=token, host=host,
            )
            _record_applied(item, tag, reviewer)
            applied += 1
        except Exception as e:
            errors.append({"column_key": col_key, "error": str(e)})

    return ApplyTagsOut(applied=applied, skipped=skipped, errors=errors)

from __future__ import annotations
import logging
import os
import uuid
from fastapi import APIRouter, HTTPException, Query
from ..models import PrincipalOut, PrincipalSearchResult, StewardAssignmentOut, StewardAssignmentIn, PatchStewardIn, PrincipalIn
from ..db.connection import query as db_query, execute, execute_returning
from ..core.dependencies import Dependencies
from ..core._scim import get_user_registered_group_ids

logger = logging.getLogger(__name__)

IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"


def _assert_admin(headers: Dependencies.Headers) -> None:
    email = (headers.user_email or "").strip() if headers else ""
    admin_emails = {e.strip() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()}
    if email in admin_emails:
        return
    rows = db_query("SELECT is_admin FROM principals WHERE id = %s", (email,))
    if not rows or not rows[0]["is_admin"]:
        raise HTTPException(403, "Admin access required")


def _build_assignment_key(scope: str, catalog: str, schema_name: str | None, table_name: str | None) -> str:
    if scope == "catalog":
        return f"assignment:catalog:{catalog}"
    if scope == "schema":
        return f"assignment:schema:{catalog}.{schema_name}"
    return f"assignment:table:{catalog}.{schema_name}.{table_name}"


def _principal_label(principal_id: str) -> str:
    """Return 'kind Name' for a principal, falling back to the raw ID if not found."""
    rows = db_query("SELECT name, kind FROM principals WHERE id = %s", (principal_id,))
    if rows:
        return f"{rows[0]['kind']} {rows[0]['name']}"
    return principal_id


def _log_admin_action(actor: str, status: str, column_key: str, comment: str) -> None:
    try:
        execute(
            "INSERT INTO decisions (column_key, status, reviewer, comment, user_added) "
            "VALUES (%s, %s, %s, %s, false)",
            (column_key, status, actor, comment),
        )
    except Exception:
        logger.warning("Failed to log admin action %s for %s", status, column_key, exc_info=True)


router = APIRouter()


@router.get("/stewards/search", response_model=list[PrincipalSearchResult], operation_id="searchStewards")
def search_stewards(
    q: str = Query(..., min_length=2),
    kind: str = Query("all"),
    headers: Dependencies.Headers = None,
    ws: Dependencies.Client = None,
):
    if IS_MOCK:
        raise HTTPException(501, "Principal search is not available in mock mode")
    existing_ids = {r["id"] for r in db_query("SELECT id FROM principals")}
    from ..core._scim import search_principals
    try:
        return search_principals(ws, q, kind, existing_ids)
    except Exception as e:
        logger.error("SCIM search failed for q=%r kind=%r: %s", q, kind, e, exc_info=True)
        raise HTTPException(
            502,
            "SCIM search failed. Ensure the app service principal has been granted "
            "workspace admin or SCIM read permissions.",
        )


def _principal_out(r: dict) -> PrincipalOut:
    return PrincipalOut(
        id=r["id"], name=r["name"], email=r.get("email"), kind=r["kind"],
        initials=r["initials"], accent=r["accent"], team=r.get("team"),
        members=r.get("members"), is_admin=r["is_admin"],
        assignment_count=r.get("assignment_count", 0),
    )


@router.post("/stewards", response_model=PrincipalOut, operation_id="createSteward")
def create_steward(body: PrincipalIn, headers: Dependencies.Headers = None):
    if not IS_MOCK:  # admin guard intentionally skipped in mock/dev mode
        _assert_admin(headers)
    execute(
        "INSERT INTO principals (id, name, email, kind, initials, accent, members, is_admin) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, false) ON CONFLICT (id) DO NOTHING",
        (body.id, body.name, body.email, body.kind, body.initials, body.accent, body.members),
    )
    rows = db_query("SELECT * FROM principals WHERE id = %s", (body.id,))
    if not rows:
        raise HTTPException(500, "Failed to create principal")
    actor = (headers.user_email or "unknown") if headers else "unknown"
    _log_admin_action(actor, "steward_added", f"steward:{body.id}", f"Added {body.kind} {body.name}")
    return _principal_out(rows[0])


@router.get("/stewards", response_model=list[PrincipalOut], operation_id="listStewards")
def get_stewards():
    rows = db_query(
        "SELECT p.*, COALESCE(a.cnt, 0) AS assignment_count "
        "FROM principals p "
        "LEFT JOIN (SELECT principal, COUNT(*) AS cnt FROM steward_assignments GROUP BY principal) a "
        "ON p.id = a.principal "
        "ORDER BY p.name"
    )
    return [_principal_out(r) for r in rows]


def _get_effective_group_ids(
    user_email: str,
    ws,
    registered_group_ids: list[str],
) -> list[str]:
    if not ws or not registered_group_ids:
        return []
    return get_user_registered_group_ids(ws, user_email, registered_group_ids)


@router.get("/stewards/{principal_id}/assignments", response_model=list[StewardAssignmentOut], operation_id="listAssignments")
def get_assignments(principal_id: str, ws: Dependencies.Client = None):
    direct = db_query(
        "SELECT * FROM steward_assignments WHERE principal = %s", (principal_id,)
    )

    group_assignments: list[dict] = []
    if not IS_MOCK:
        # Only resolve group memberships for user principals.
        p_rows = db_query("SELECT kind FROM principals WHERE id = %s", (principal_id,))
        is_user = not p_rows or p_rows[0]["kind"] == "user"
        if is_user:
            registered_groups = db_query("SELECT id FROM principals WHERE kind = 'group'")
            registered_ids = [r["id"] for r in registered_groups]
            matched_ids = _get_effective_group_ids(principal_id, ws, registered_ids)
            if matched_ids:
                group_assignments = db_query(
                    "SELECT * FROM steward_assignments WHERE principal = ANY(%s)",
                    (matched_ids,),
                )

    seen_ids: set[str] = set()
    result: list[StewardAssignmentOut] = []
    for r in direct + group_assignments:
        row_id = str(r["id"])
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        result.append(StewardAssignmentOut(
            id=row_id, principal=r["principal"], principal_kind=r["principal_kind"],
            scope=r["scope"], catalog=r["catalog"],
            schema_name=r.get("schema_name"), table_name=r.get("table_name"),
        ))
    return result


@router.post("/stewards/assignments", response_model=StewardAssignmentOut, operation_id="createAssignment")
def create_assignment(body: StewardAssignmentIn, headers: Dependencies.Headers = None):
    if not IS_MOCK:  # admin guard intentionally skipped in mock/dev mode
        _assert_admin(headers)
    row = execute_returning(
        "INSERT INTO steward_assignments "
        "(principal, principal_kind, scope, catalog, schema_name, table_name) "
        "VALUES (%s,%s,%s,%s,%s,%s) RETURNING *",
        (body.principal, body.principal_kind, body.scope,
         body.catalog, body.schema_name, body.table_name),
    )
    path = _build_assignment_key(body.scope, body.catalog, body.schema_name, body.table_name)
    actor = (headers.user_email or "unknown") if headers else "unknown"
    _log_admin_action(actor, "scope_added", path, f"Assigned {path.split(':', 1)[1]} to {_principal_label(body.principal)}")
    return StewardAssignmentOut(
        id=str(row["id"]), principal=row["principal"], principal_kind=row["principal_kind"],
        scope=row["scope"], catalog=row["catalog"],
        schema_name=row.get("schema_name"), table_name=row.get("table_name"),
    )


@router.delete("/stewards/assignments/{assignment_id}", status_code=204, operation_id="deleteAssignment")
def delete_assignment(assignment_id: str, headers: Dependencies.Headers = None):
    if not IS_MOCK:  # admin guard intentionally skipped in mock/dev mode
        _assert_admin(headers)
    a_rows = db_query("SELECT * FROM steward_assignments WHERE id = %s", (assignment_id,))
    execute("DELETE FROM steward_assignments WHERE id = %s", (assignment_id,))
    if a_rows:
        a = a_rows[0]
        path = _build_assignment_key(a["scope"], a["catalog"], a.get("schema_name"), a.get("table_name"))
        actor = (headers.user_email or "unknown") if headers else "unknown"
        _log_admin_action(actor, "scope_removed", path, f"Removed {path.split(':', 1)[1]} from {_principal_label(a['principal'])}")


@router.delete("/stewards/{principal_id}", status_code=204, operation_id="deleteSteward")
def delete_steward(principal_id: str, headers: Dependencies.Headers = None):
    if not IS_MOCK:  # admin guard intentionally skipped in mock/dev mode
        _assert_admin(headers)
    p_rows = db_query("SELECT name, kind FROM principals WHERE id = %s", (principal_id,))
    name = p_rows[0]["name"] if p_rows else principal_id
    kind = p_rows[0]["kind"] if p_rows else "user"
    execute("DELETE FROM principals WHERE id = %s", (principal_id,))
    actor = (headers.user_email or "unknown") if headers else "unknown"
    _log_admin_action(actor, "steward_removed", f"steward:{principal_id}", f"Removed {kind} {name}")


@router.patch("/stewards/{principal_id}", response_model=PrincipalOut, operation_id="patchSteward")
def patch_steward(principal_id: str, body: PatchStewardIn, headers: Dependencies.Headers = None):
    if not IS_MOCK:  # admin guard intentionally skipped in mock/dev mode
        _assert_admin(headers)
    execute("UPDATE principals SET is_admin = %s WHERE id = %s", (body.is_admin, principal_id))
    rows = db_query("SELECT * FROM principals WHERE id = %s", (principal_id,))
    if not rows:
        raise HTTPException(404, "Principal not found")
    actor = (headers.user_email or "unknown") if headers else "unknown"
    status = "role_granted" if body.is_admin else "role_revoked"
    verb = "Granted admin to" if body.is_admin else "Revoked admin from"
    _log_admin_action(actor, status, f"steward:{principal_id}", f"{verb} {rows[0]['kind']} {rows[0]['name']}")
    return _principal_out(rows[0])

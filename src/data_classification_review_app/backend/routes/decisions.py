from __future__ import annotations
import os
from fastapi import APIRouter, Request, Query
from typing import Optional
from ..models import DecisionPatchIn, DecisionOut, SaveDecisionsOut
from ..db.connection import query as db_query, execute
from ..core.dependencies import Dependencies

router = APIRouter()
IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"


def _get_reviewer(request: Request, headers: "Dependencies.Headers") -> str:
    if IS_MOCK:
        return request.headers.get("X-Mock-User", "jamie.diaz")
    return headers.user_email or os.environ.get("DEV_USER_EMAIL") or "unknown"


@router.post("/decisions", response_model=SaveDecisionsOut, operation_id="saveDecisions")
def post_decisions(patches: list[DecisionPatchIn], request: Request, headers: Dependencies.Headers):
    reviewer = _get_reviewer(request, headers)
    for p in patches:
        if p.user_added:
            execute(
                "INSERT INTO decisions (column_key, status, modified_tag, comment, reviewer, user_added, class_tag) "
                "VALUES (%s,%s,%s,%s,%s,true,%s)",
                (p.column_key, p.status, p.modified_tag, p.comment, reviewer, p.class_tag),
            )
        else:
            execute(
                "INSERT INTO decisions (column_key, status, modified_tag, comment, reviewer, class_tag) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (p.column_key, p.status, p.modified_tag, p.comment, reviewer, p.class_tag),
            )
    return SaveDecisionsOut(saved=len(patches))


@router.get("/decisions", response_model=list[DecisionOut], operation_id="listDecisions")
def get_decisions(reviewer: Optional[str] = Query(None), since: Optional[str] = Query(None)):
    sql = "SELECT * FROM decisions WHERE 1=1"
    params: list = []
    if reviewer:
        sql += " AND reviewer = %s"
        params.append(reviewer)
    if since:
        sql += " AND decided_at >= %s"
        params.append(since)
    sql += " ORDER BY decided_at DESC"
    rows = db_query(sql, params or None)
    result = []
    for r in rows:
        parts = r["column_key"].split(".")
        col   = parts[-1] if len(parts) >= 4 else ""
        tbl   = parts[-2] if len(parts) >= 4 else ""
        sch   = parts[-3] if len(parts) >= 4 else ""
        cat   = parts[0]  if len(parts) >= 4 else ""
        result.append(DecisionOut(
            id=str(r["id"]) if r.get("id") else None,
            column_key=r["column_key"],
            scan_ts=str(r["scan_ts"]) if r.get("scan_ts") else None,
            status=r["status"], modified_tag=r.get("modified_tag"),
            comment=r.get("comment"), reviewer=r["reviewer"],
            decided_at=str(r["decided_at"]), user_added=r["user_added"],
            applied_at=str(r["applied_at"]) if r.get("applied_at") else None,
            catalog=cat, schema_name=sch, table=tbl, column=col,
            class_tag=r.get("class_tag"),
        ))
    return result

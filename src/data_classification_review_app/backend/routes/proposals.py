from __future__ import annotations
import os
from fastapi import APIRouter, Query
from typing import Optional
from ..models import ProposalOut
from ..db.connection import query as db_query

router = APIRouter()
IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"


def _dedupe_latest(rows: list[dict]) -> list[dict]:
    """Collapse classification scan results to one row per (catalog, schema, table,
    column, class_tag), keeping the most recent scan by latest_detected_time.

    `system.data_classification.results` is an append log: every scan run inserts a
    new row per detected column-tag, so a table scanned N times yields N identical
    rows. Without this, each historical scan surfaces as a duplicate proposal.
    Distinct tags on the same column are preserved (they are not duplicates).
    """
    latest: dict[tuple, dict] = {}
    for r in rows:
        key = (
            r.get("catalog_name"), r.get("schema_name"), r.get("table_name"),
            r.get("column_name"), r.get("class_tag"),
        )
        # ISO-style timestamps sort lexicographically; missing time sorts first so a
        # real timestamp always wins.
        t = str(r.get("latest_detected_time") or "")
        prev = latest.get(key)
        if prev is None or t >= str(prev.get("latest_detected_time") or ""):
            latest[key] = r
    return list(latest.values())


def _decision_for(decisions: dict[tuple, dict], column_key: str, class_tag: str | None) -> dict:
    """Return the latest decision recorded against one (column, class tag).

    A column can carry several detected classes, each judged separately, so a verdict
    must not leak onto the column's other tags. Decisions written before `class_tag`
    was recorded have none, and predate per-tag verdicts, so they cover every tag on
    the column.
    """
    return decisions.get((column_key, class_tag)) or decisions.get((column_key, None)) or {}


def _owner_for(steward_rows: list[dict], catalog: str, schema: str, table: str) -> str:
    """Return the most-specific assigned steward: table > schema > catalog."""
    table_match = schema_match = catalog_match = None
    for a in steward_rows:
        if a["scope"] == "table" and a["catalog"] == catalog \
                and a.get("schema_name") == schema and a.get("table_name") == table:
            table_match = a["principal"]
        elif a["scope"] == "schema" and a["catalog"] == catalog \
                and a.get("schema_name") == schema:
            schema_match = a["principal"]
        elif a["scope"] == "catalog" and a["catalog"] == catalog:
            catalog_match = a["principal"]
    return table_match or schema_match or catalog_match or "unknown"


def _get_proposals() -> list[dict]:
    if IS_MOCK:
        rows = db_query(
            "SELECT catalog_name, schema_name, table_name, column_name, data_type, "
            "class_tag, confidence, frequency, "
            "latest_detected_time::text AS latest_detected_time "
            "FROM table_columns WHERE class_tag IS NOT NULL"
        )
    else:
        from ..clients.warehouse import execute_sql, quote_full_name
        catalog_filter = os.environ.get("CLASSIFICATION_CATALOG_FILTER", "").strip()
        where = "WHERE class_tag IS NOT NULL"
        if catalog_filter:
            catalogs = ", ".join(f"'{c.strip()}'" for c in catalog_filter.split(",") if c.strip())
            where += f" AND catalog_name IN ({catalogs})"
        results_table = os.environ.get(
            "CLASSIFICATION_RESULTS_TABLE", "system.data_classification.results"
        )
        rows = [
            {**r, "data_type": r.get("data_type", "string")}
            for r in execute_sql(
                "SELECT catalog_name, schema_name, table_name, column_name, "
                "class_tag, confidence, frequency, "
                "CAST(latest_detected_time AS STRING) AS latest_detected_time "
                f"FROM {quote_full_name(results_table)} {where}"
            )
        ]

    # Each scan run appends a fresh row per column-tag; collapse to the latest so the
    # steward view shows each column-tag once (see issue #38).
    rows = _dedupe_latest(rows)

    decisions = {
        (r["column_key"], r.get("class_tag")): r
        for r in db_query(
            "SELECT DISTINCT ON (column_key, class_tag) * FROM decisions "
            "WHERE user_added = false ORDER BY column_key, class_tag, decided_at DESC"
        )
    }
    steward_rows = db_query("SELECT * FROM steward_assignments")

    result = []
    for r in rows:
        key = f"{r['catalog_name']}.{r['schema_name']}.{r['table_name']}.{r['column_name']}"
        d = _decision_for(decisions, key, r["class_tag"])
        result.append({
            "key": key,
            "catalog": r["catalog_name"],
            "schema_name": r["schema_name"],
            "table": r["table_name"],
            "column": r["column_name"],
            "data_type": r.get("data_type", "string"),
            "table_key": f"{r['catalog_name']}.{r['schema_name']}.{r['table_name']}",
            "class_tag": r["class_tag"],
            "confidence": r.get("confidence"),
            "frequency": float(r["frequency"]) if r.get("frequency") is not None else None,
            "latest_detected_time": str(r.get("latest_detected_time", "")),
            "owner": _owner_for(steward_rows, r["catalog_name"], r["schema_name"], r["table_name"]),
            "status": d.get("status", "pending"),
            "modified_tag": d.get("modified_tag"),
            "comment": d.get("comment"),
            "reviewer": d.get("reviewer"),
            "decided_at": str(d["decided_at"]) if d.get("decided_at") else None,
            "user_added": False,
            "applied_at": str(d["applied_at"]) if d.get("applied_at") else None,
        })

    # Include user-added proposals from the decisions table.
    # Key uses "{column_key}:{modified_tag}" to stay unique per added tag.
    user_added_rows = db_query(
        "SELECT DISTINCT ON (column_key, modified_tag) "
        "column_key, modified_tag, status, comment, reviewer, decided_at, applied_at "
        "FROM decisions WHERE user_added = true "
        "ORDER BY column_key, modified_tag, decided_at DESC"
    )
    for d in user_added_rows:
        col_key = d["column_key"]
        parts = col_key.split(".", 3)
        if len(parts) != 4:
            continue
        catalog_name, schema_name, table_name, column_name = parts
        modified_tag = d.get("modified_tag") or ""
        result.append({
            "key": f"{col_key}:{modified_tag}",
            "catalog": catalog_name,
            "schema_name": schema_name,
            "table": table_name,
            "column": column_name,
            "data_type": "",
            "table_key": f"{catalog_name}.{schema_name}.{table_name}",
            "class_tag": modified_tag,
            "confidence": None,
            "frequency": None,
            "latest_detected_time": None,
            "owner": _owner_for(steward_rows, catalog_name, schema_name, table_name),
            "status": d.get("status", "approved"),
            "modified_tag": None,
            "comment": d.get("comment"),
            "reviewer": d.get("reviewer"),
            "decided_at": str(d["decided_at"]) if d.get("decided_at") else None,
            "user_added": True,
            "applied_at": str(d["applied_at"]) if d.get("applied_at") else None,
        })

    return result


@router.get("/proposals", response_model=list[ProposalOut], operation_id="listProposals")
def get_proposals(
    catalog: Optional[str] = Query(None),
    schema: Optional[str] = Query(None),
    table: Optional[str] = Query(None),
    owner: Optional[str] = Query(None),
):
    proposals = _get_proposals()
    if catalog: proposals = [p for p in proposals if p["catalog"] == catalog]
    if schema:  proposals = [p for p in proposals if p.get("schema_name") == schema]
    if table:   proposals = [p for p in proposals if p["table"] == table]
    if owner:   proposals = [p for p in proposals if p.get("owner") == owner]
    return proposals

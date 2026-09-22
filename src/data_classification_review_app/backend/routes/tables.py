from __future__ import annotations
import json
import os
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Query
from ..models import TableSummaryOut, ColumnDetailOut, ColumnsResponse, ColumnSamplesOut, TableSamplesOut
from ..db.connection import query as db_query
from ..core.dependencies import Dependencies

router = APIRouter()
IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"


def _build_tables(proposals: list[dict]) -> list[dict]:
    tables: dict[str, dict] = {}
    for p in proposals:
        k = p["table_key"]
        if k not in tables:
            tables[k] = {
                "key": k, "catalog": p["catalog"], "schema": p.get("schema_name") or p.get("schema", ""),
                "table": p["table"], "owner": p.get("owner", ""),
                "last_scan": (p.get("latest_detected_time") or "2026-05-19 06:00")[:10],
                "total_cols": 0, "proposal_count": 0,
                "pending": 0, "approved": 0, "rejected": 0, "modified": 0,
                "high_conf": 0, "low_conf": 0, "proposals": [],
            }
        t = tables[k]
        t["proposal_count"] += 1
        status = p.get("status", "pending")
        t[status] = t.get(status, 0) + 1
        if p.get("confidence") == "HIGH": t["high_conf"] += 1
        if p.get("confidence") == "LOW":  t["low_conf"] += 1
        t["proposals"].append(p)

    if IS_MOCK:
        # Count total columns (including unclassified) from DB
        col_counts_rows = db_query(
            "SELECT catalog_name||'.'||schema_name||'.'||table_name AS tkey, COUNT(*) AS cnt "
            "FROM table_columns GROUP BY 1"
        )
        col_counts = {r["tkey"]: int(r["cnt"]) for r in col_counts_rows}
        for t in tables.values():
            t["total_cols"] = col_counts.get(t["key"], t["proposal_count"])
    else:
        for t in tables.values():
            if t["total_cols"] == 0:
                t["total_cols"] = t["proposal_count"]
    return list(tables.values())


@router.get("/tables", response_model=list[TableSummaryOut], operation_id="listTables")
def get_tables():
    from .proposals import _get_proposals
    return _build_tables(_get_proposals())


@router.get("/tables/{catalog}/{schema}/{table}/columns", response_model=ColumnsResponse, operation_id="listColumns")
def get_columns(catalog: str, schema: str, table: str, headers: Dependencies.Headers):
    full_name = f"{catalog}.{schema}.{table}"
    if IS_MOCK:
        from ..mock.data import TABLE_DESCRIPTIONS, COLUMN_DESCRIPTIONS, TABLE_TAGS
        steward_rows = db_query("SELECT * FROM steward_assignments")
        from .proposals import _owner_for
        owner = _owner_for(steward_rows, catalog, schema, table)
        rows = db_query(
            "SELECT column_name, data_type, class_tag, confidence, frequency "
            "FROM table_columns WHERE catalog_name=%s AND schema_name=%s AND table_name=%s",
            (catalog, schema, table),
        )
        result = []
        for c in rows:
            column_key = f"{full_name}.{c['column_name']}"
            result.append(ColumnDetailOut(
                catalog=catalog, schema_name=schema, table=table,
                column=c["column_name"], data_type=c["data_type"],
                table_key=full_name, owner=owner, existing_tags=[],
                class_tag=c.get("class_tag"), confidence=c.get("confidence"),
                frequency=float(c["frequency"]) if c.get("frequency") is not None else None,
                column_description=COLUMN_DESCRIPTIONS.get(column_key),
            ))
        return ColumnsResponse(
            columns=result,
            table_description=TABLE_DESCRIPTIONS.get(full_name),
            table_tags=TABLE_TAGS.get(full_name, []),
        )

    from ..clients.warehouse import validate_identifier, execute_sql, quote_full_name
    try:
        catalog = validate_identifier(catalog, "catalog")
        schema = validate_identifier(schema, "schema")
        table = validate_identifier(table, "table")
    except ValueError as e:
        raise HTTPException(400, str(e))

    from ..clients.uc_client import get_table, get_column_tags, get_table_level_tags
    from ..core._config import logger

    # validate_identifier above ensures catalog/schema/table are [A-Za-z0-9_-]+ — safe to interpolate.
    token = headers.token.get_secret_value() if headers.token else None
    _raw_host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    workspace_host = _raw_host if _raw_host.startswith("http") else f"https://{_raw_host}"

    try:
        table_info = get_table(full_name, token=token, host=workspace_host)
    except Exception as e:
        status = getattr(getattr(e, "response", None), "status_code", None)
        if status in (401, 403):
            return ColumnsResponse(columns=[], metadata_denied=True)
        raise HTTPException(status_code=status or 500, detail=str(e))

    table_description = table_info.get("comment")

    try:
        table_tags = get_table_level_tags(catalog, schema, table, token, workspace_host)
        table_tags_denied = False
    except Exception as e:
        logger.warning("Table tags fetch failed: %s", e)
        table_tags = []
        table_tags_denied = True

    try:
        tag_list = get_column_tags(catalog, schema, table, token, workspace_host)
        column_tags_denied = False
    except Exception as e:
        logger.warning("Column tags fetch failed: %s", e)
        tag_list = []
        column_tags_denied = True

    col_tags: dict[str, list[str]] = defaultdict(list)
    for t in tag_list:
        col_name = t.get("column_name")
        if col_name:
            tag_key = t.get("tag_name", "")
            tag_val = t.get("tag_value")
            col_tags[col_name].append(f"{tag_key}={tag_val}" if tag_val else tag_key)

    results_table = os.environ.get(
        "CLASSIFICATION_RESULTS_TABLE", "system.data_classification.results"
    )
    cls_rows = execute_sql(
        "SELECT column_name, class_tag, confidence, frequency "
        f"FROM {quote_full_name(results_table)} "
        f"WHERE catalog_name='{catalog}' AND schema_name='{schema}' AND table_name='{table}'"
    )
    cls_map = {r["column_name"]: r for r in cls_rows}

    result = []
    for col in table_info.get("columns", []):
        col_name = col["name"]
        cls = cls_map.get(col_name, {})
        result.append(ColumnDetailOut(
            catalog=catalog, schema_name=schema, table=table, column=col_name,
            data_type=col.get("type_text", col.get("type_name", "string")),
            table_key=full_name, owner="",
            existing_tags=col_tags.get(col_name, []),
            class_tag=cls.get("class_tag"), confidence=cls.get("confidence"),
            frequency=float(cls["frequency"]) if cls.get("frequency") is not None else None,
            column_description=col.get("comment"),
        ))
    return ColumnsResponse(
        columns=result,
        table_description=table_description,
        table_tags=table_tags,
        table_tags_denied=table_tags_denied,
        column_tags_denied=column_tags_denied,
    )


@router.get("/tables/{catalog}/{schema}/{table}/samples", response_model=TableSamplesOut, operation_id="getTableSamples")
def get_table_samples(
    catalog: str, schema: str, table: str,
    headers: Dependencies.Headers,
    columns: list[str] = Query(...),
):
    if IS_MOCK:
        result = []
        for column in columns:
            rows = db_query(
                "SELECT samples FROM table_columns "
                "WHERE catalog_name=%s AND schema_name=%s AND table_name=%s AND column_name=%s",
                (catalog, schema, table, column),
            )
            raw = rows[0].get("samples") if rows else []
            raw = raw or []
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = []
            result.append(ColumnSamplesOut(column=column, samples=[str(v) for v in raw[:5]]))
        return TableSamplesOut(columns=result, denied=False)

    from ..clients.warehouse import validate_identifier, execute_sql, quote_identifier
    try:
        catalog = validate_identifier(catalog, "catalog")
        schema = validate_identifier(schema, "schema")
        table = validate_identifier(table, "table")
        columns = [validate_identifier(c, "column") for c in columns]
    except ValueError as e:
        raise HTTPException(400, str(e))

    token = headers.token.get_secret_value() if headers.token else None
    if not token:
        return TableSamplesOut(columns=[], denied=True)

    _raw_host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    workspace_host = _raw_host if _raw_host.startswith("http") else f"https://{_raw_host}"

    from ..core._config import logger
    select_list = ", ".join(
        f"slice(collect_set({quote_identifier(c)}), 1, 5) AS {quote_identifier(c)}"
        for c in columns
    )
    sql = (
        f"SELECT {select_list} FROM "
        f"(SELECT * FROM `{catalog}`.`{schema}`.`{table}` TABLESAMPLE (1000 ROWS))"
    )

    try:
        rows = execute_sql(sql, token=token, host=workspace_host)
    except Exception as e:
        err = str(e)
        if any(code in err for code in ("DELTA_TABLE_NOT_FOUND", "DELTA_PATH_DOES_NOT_EXIST")):
            logger.warning("Table samples storage error (treating as permitted): %s", e)
            return TableSamplesOut(columns=[], denied=False)
        logger.warning("Table samples query failed: %s", e)
        return TableSamplesOut(columns=[], denied=True)

    if not rows:
        return TableSamplesOut(columns=[ColumnSamplesOut(column=c, samples=[]) for c in columns], denied=False)

    row = rows[0]
    result = []
    for c in columns:
        raw = row.get(c) or []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = []
        result.append(ColumnSamplesOut(column=c, samples=[str(v) for v in raw]))
    return TableSamplesOut(columns=result, denied=False)

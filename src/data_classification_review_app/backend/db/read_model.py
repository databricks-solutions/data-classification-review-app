"""Server-side read model over the classification synced table + decisions (#13).

Every list and aggregate the UI needs is computed here in Postgres, so the browser never
receives the whole estate (~800k proposals on a large workspace). All queries run over one
"universe" CTE: synced-table scan proposals LEFT JOIN their current decision in
`proposal_state`, UNION ALL user-added proposals from `proposal_state`.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
import psycopg2
from .connection import query as db_query

IS_MOCK = os.environ.get("USE_MOCK_DATA", "false").lower() == "true"

STATUSES = ("pending", "approved", "rejected", "modified", "applied")
_COLUMN_KEY_SQL = "s.catalog_name || '.' || s.schema_name || '.' || s.table_name || '.' || s.column_name"


class SyncPendingError(RuntimeError):
    """Raised when the classification synced table has not been created yet."""


def _quote_pg_name(name: str) -> str:
    """Quote a dot-separated Postgres name ("schema.table" → "\"schema\".\"table\"").

    The synced table lands in a Postgres schema named after its UC schema, which can be
    a reserved word — the installer's default is `default`.
    """
    return ".".join('"' + p.replace('"', '""') + '"' for p in name.split("."))


def _q(sql: str, params: list) -> list[dict]:
    try:
        return db_query(sql, tuple(params) if params else None)
    except psycopg2.errors.UndefinedTable as e:
        raise SyncPendingError(str(e))


def _source_sql() -> tuple[str, list]:
    """Scan proposals: one row per (catalog, schema, table, column, class_tag)."""
    if IS_MOCK:
        return (
            "SELECT catalog_name, schema_name, table_name, column_name, data_type, "
            "class_tag, confidence, frequency, latest_detected_time::text AS latest_detected_time "
            "FROM table_columns WHERE class_tag IS NOT NULL",
            [],
        )
    synced = os.environ.get("CLASSIFICATION_SYNCED_TABLE", "").strip()
    if not synced:
        raise SyncPendingError("CLASSIFICATION_SYNCED_TABLE is not set")
    sql = (
        "SELECT catalog_name, schema_name, table_name, column_name, 'string'::text AS data_type, "
        "class_tag, confidence, frequency, latest_detected_time::text AS latest_detected_time "
        f"FROM {_quote_pg_name(synced)} WHERE class_tag IS NOT NULL"
    )
    params: list = []
    names = [c.strip() for c in os.environ.get("CLASSIFICATION_CATALOG_FILTER", "").split(",") if c.strip()]
    if names:
        sql += " AND catalog_name = ANY(%s)"
        params.append(names)
    return sql, params


def _state_join(alias: str, tag_expr: str) -> str:
    return (
        f"LEFT JOIN proposal_state {alias} ON {alias}.catalog_name = s.catalog_name"
        f" AND {alias}.schema_name = s.schema_name AND {alias}.table_name = s.table_name"
        f" AND {alias}.column_name = s.column_name AND {alias}.class_tag = {tag_expr}"
        f" AND NOT {alias}.user_added"
    )


def _decided(field: str) -> str:
    """The proposal's own decision, else a legacy whole-column one (proposal_state class_tag '')."""
    return f"CASE WHEN d.status IS NOT NULL THEN d.{field} ELSE w.{field} END"


def _with_universe() -> tuple[str, list]:
    src, params = _source_sql()
    # proposal_key is unique per proposal; the decision identity is (column_key, class_tag, user_added).
    sql = f"""WITH universe AS (
  SELECT s.catalog_name, s.schema_name, s.table_name, s.column_name, s.data_type,
         s.class_tag, s.confidence, s.frequency, s.latest_detected_time,
         {_COLUMN_KEY_SQL} AS column_key,
         {_COLUMN_KEY_SQL} || '|' || s.class_tag AS proposal_key,
         COALESCE({_decided('status')}, 'pending') AS status, {_decided('modified_tag')} AS modified_tag,
         {_decided('comment')} AS comment, {_decided('reviewer')} AS reviewer,
         {_decided('decided_at')} AS decided_at, {_decided('applied_at')} AS applied_at,
         false AS user_added
  FROM ({src}) s
  {_state_join('d', 's.class_tag')}
  {_state_join('w', "''")}
  UNION ALL
  SELECT s.catalog_name, s.schema_name, s.table_name, s.column_name, ''::text, s.class_tag,
         NULL, NULL, NULL,
         {_COLUMN_KEY_SQL}, {_COLUMN_KEY_SQL} || '|' || s.class_tag || '|user',
         s.status, NULL, s.comment, s.reviewer, s.decided_at, s.applied_at, true
  FROM proposal_state s WHERE s.user_added
)
"""
    return sql, params


def _owner_join(alias: str) -> str:
    """Most specific covering steward assignment (table > schema > catalog) as `own`."""
    return f"""LEFT JOIN LATERAL (
  SELECT sa.principal FROM steward_assignments sa
  WHERE sa.catalog = {alias}.catalog_name
    AND (sa.scope = 'catalog'
      OR (sa.scope = 'schema' AND sa.schema_name = {alias}.schema_name)
      OR (sa.scope = 'table' AND sa.schema_name = {alias}.schema_name
          AND sa.table_name = {alias}.table_name))
  ORDER BY CASE sa.scope WHEN 'table' THEN 0 WHEN 'schema' THEN 1 ELSE 2 END, sa.principal
  LIMIT 1
) own ON true"""


OWNER_EXPR = "COALESCE(own.principal, 'unknown')"


@dataclass
class ProposalFilters:
    catalog: str | None = None
    schema: str | None = None
    table: str | None = None
    tag: str | None = None
    statuses: list[str] | None = None
    steward: str | None = None
    search: str | None = None
    confidence: str | None = None   # 'HIGH' | 'LOW' | 'NONE'


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _where(f: ProposalFilters) -> tuple[str, list, bool]:
    """Return (" WHERE ..." or "", params, needs_owner_join)."""
    conds: list[str] = []
    params: list = []
    if f.catalog:
        conds.append("u.catalog_name = %s"); params.append(f.catalog)
    if f.schema:
        conds.append("u.schema_name = %s"); params.append(f.schema)
    if f.table:
        conds.append("u.table_name = %s"); params.append(f.table)
    if f.tag:
        conds.append("COALESCE(NULLIF(u.modified_tag, ''), u.class_tag) = %s"); params.append(f.tag)
    if f.statuses:
        conds.append("u.status = ANY(%s)"); params.append(list(f.statuses))
    if f.confidence == "NONE":
        conds.append("u.confidence IS NULL")
    elif f.confidence:
        conds.append("u.confidence = %s"); params.append(f.confidence)
    if f.search and f.search.strip():
        conds.append(
            "(u.catalog_name || '.' || u.schema_name || '.' || u.table_name || '.' || "
            "u.column_name || ' ' || u.class_tag) ILIKE %s"
        )
        params.append(f"%{_escape_like(f.search.strip())}%")
    needs_owner = bool(f.steward)
    if f.steward:
        if f.steward != "unknown":
            # Necessary-condition prefilter: prunes rows before the LATERAL owner join fires.
            # A row can only be owned by this steward if one of their assignments covers it.
            conds.append(
                "EXISTS (SELECT 1 FROM steward_assignments sx"
                " WHERE sx.principal = %s AND sx.catalog = u.catalog_name"
                " AND (sx.scope = 'catalog'"
                " OR (sx.scope = 'schema' AND sx.schema_name = u.schema_name)"
                " OR (sx.scope = 'table' AND sx.schema_name = u.schema_name"
                " AND sx.table_name = u.table_name)))"
            )
            params.append(f.steward)
        conds.append(f"{OWNER_EXPR} = %s"); params.append(f.steward)
    return (" WHERE " + " AND ".join(conds)) if conds else "", params, needs_owner


def _ts(v) -> str | None:
    return str(v) if v is not None else None


def _proposal_out(r: dict) -> dict:
    c, s, t = r["catalog_name"], r["schema_name"], r["table_name"]
    return {
        "key": r["proposal_key"],
        "column_key": r["column_key"],
        "catalog": c,
        "schema_name": s,
        "table": t,
        "column": r["column_name"],
        "data_type": r["data_type"] or "",
        "table_key": f"{c}.{s}.{t}",
        "class_tag": r["class_tag"],
        "confidence": r.get("confidence"),
        "frequency": float(r["frequency"]) if r.get("frequency") is not None else None,
        "latest_detected_time": r.get("latest_detected_time"),
        "owner": r["owner"],
        "status": r["status"],
        "modified_tag": r.get("modified_tag"),
        "comment": r.get("comment"),
        "reviewer": r.get("reviewer"),
        "decided_at": _ts(r.get("decided_at")),
        "user_added": bool(r["user_added"]),
        "applied_at": _ts(r.get("applied_at")),
    }


_ORDER = " ORDER BY u.catalog_name, u.schema_name, u.table_name, u.column_name, u.class_tag, u.proposal_key"


def _status_sums(col: str = "n") -> str:
    return ", ".join(
        f"COALESCE(SUM({col}) FILTER (WHERE status = '{s}'), 0) AS {s}" for s in STATUSES
    )


def _counts(d: dict) -> dict:
    return {k: int(d.get(k) or 0) for k in ("total",) + STATUSES}


def overview_stats(catalog: str | None) -> dict:
    head, params = _with_universe()
    where = ""
    if catalog:
        where = " WHERE u.catalog_name = %s"
        params = params + [catalog]
    sums = _status_sums()
    sql = head + f""", agg AS MATERIALIZED (
  SELECT u.catalog_name, u.schema_name, u.table_name, u.class_tag, u.status, COUNT(*) AS n
  FROM universe u{where}
  GROUP BY 1, 2, 3, 4, 5
), per_table AS (
  SELECT catalog_name, schema_name, table_name, status, SUM(n) AS n FROM agg GROUP BY 1, 2, 3, 4
)
SELECT
  (SELECT COALESCE(SUM(n), 0) FROM agg) AS total,
  (SELECT row_to_json(x) FROM (SELECT {sums} FROM agg) x) AS by_status,
  (SELECT COUNT(*) FROM (SELECT DISTINCT catalog_name, schema_name, table_name FROM agg) x) AS table_count,
  (SELECT COALESCE(json_agg(x ORDER BY x.catalog), '[]'::json) FROM (
     SELECT catalog_name AS catalog, COUNT(DISTINCT (schema_name, table_name)) AS tables,
            SUM(n) AS total, {sums}
     FROM agg GROUP BY catalog_name) x) AS by_catalog,
  (SELECT COALESCE(json_agg(x ORDER BY x.total DESC, x.tag), '[]'::json) FROM (
     SELECT class_tag AS tag, SUM(n) AS total, {sums}
     FROM agg GROUP BY class_tag) x) AS by_tag,
  (SELECT COALESCE(json_agg(x ORDER BY x.owner), '[]'::json) FROM (
     SELECT {OWNER_EXPR} AS owner, SUM(pt.n) AS total, {_status_sums('pt.n')}
     FROM per_table pt {_owner_join('pt')} GROUP BY 1) x) AS by_owner
"""
    r = _q(sql, params)[0]
    by_status = r["by_status"] or {}
    out = _counts({**by_status, "total": r["total"]})
    decided = out["approved"] + out["rejected"] + out["modified"]
    out["approval_rate"] = int((out["approved"] + out["modified"]) * 100 / decided + 0.5) if decided else 0
    out["table_count"] = int(r["table_count"])
    out["by_catalog"] = [{"catalog": c["catalog"], "tables": int(c["tables"]), **_counts(c)} for c in r["by_catalog"]]
    out["by_tag"] = [{"tag": t["tag"], **_counts(t)} for t in r["by_tag"]]
    out["by_owner"] = [{"owner": o["owner"], **_counts(o)} for o in r["by_owner"]]
    return out


def _distinct(col: str, where: str = "", params: list | None = None) -> list[str]:
    head, hp = _with_universe()
    sql = head + f"SELECT DISTINCT u.{col} AS v FROM universe u{where} ORDER BY 1"
    return [r["v"] for r in _q(sql, hp + (params or [])) if r["v"]]


def facets(catalog: str | None, schema: str | None) -> dict:
    schemas = (
        _distinct("schema_name", " WHERE u.catalog_name = %s", [catalog]) if catalog
        else _distinct("schema_name")
    )
    tables = (
        _distinct("table_name", " WHERE u.catalog_name = %s AND u.schema_name = %s", [catalog, schema])
        if catalog and schema else []
    )
    stewards = [r["principal"] for r in _q(
        "SELECT DISTINCT principal FROM steward_assignments ORDER BY 1", []
    )]
    return {
        "catalogs": _distinct("catalog_name"),
        "schemas": schemas,
        "tables": tables,
        "tags": _distinct("class_tag"),
        "stewards": stewards + ["unknown"],
    }


def _cone(assignments: list[dict], alias: str = "u") -> tuple[str, list]:
    """SQL predicate: row is covered by any of the given steward assignments."""
    clauses: list[str] = []
    params: list = []
    for a in assignments:
        if a["scope"] == "catalog":
            clauses.append(f"{alias}.catalog_name = %s")
            params.append(a["catalog"])
        elif a["scope"] == "schema":
            clauses.append(f"({alias}.catalog_name = %s AND {alias}.schema_name = %s)")
            params += [a["catalog"], a.get("schema_name")]
        else:
            clauses.append(
                f"({alias}.catalog_name = %s AND {alias}.schema_name = %s AND {alias}.table_name = %s)"
            )
            params += [a["catalog"], a.get("schema_name"), a.get("table_name")]
    if not clauses:
        return "FALSE", []
    return "(" + " OR ".join(clauses) + ")", params


def coverage(assignment: dict, limit: int = 200) -> dict:
    head, hp = _with_universe()
    cone, cp = _cone([assignment])
    sql = head + (
        "SELECT u.catalog_name, u.schema_name, u.table_name, COUNT(*) AS n, "
        "COUNT(*) FILTER (WHERE u.status = 'pending') AS pending "
        f"FROM universe u WHERE {cone} GROUP BY 1, 2, 3 ORDER BY 1, 2, 3"
    )
    rows = _q(sql, hp + cp)
    return {
        "table_count": len(rows),
        "proposal_count": sum(int(r["n"]) for r in rows),
        "pending": sum(int(r["pending"]) for r in rows),
        "tables": [f"{r['catalog_name']}.{r['schema_name']}.{r['table_name']}" for r in rows[:limit]],
    }


def _mock_col_counts() -> dict[str, int]:
    rows = _q(
        "SELECT catalog_name || '.' || schema_name || '.' || table_name AS tkey, COUNT(*) AS cnt "
        "FROM table_columns GROUP BY 1",
        [],
    )
    return {r["tkey"]: int(r["cnt"]) for r in rows}


def table_summaries(assignments: list[dict], search: str | None = None) -> list[dict]:
    if not assignments:
        return []
    head, hp = _with_universe()
    cone, cp = _cone(assignments)
    having, sp = "", []
    if search and search.strip():
        pat = f"%{_escape_like(search.strip())}%"
        having = (
            " HAVING bool_or(u.catalog_name ILIKE %s OR u.schema_name ILIKE %s "
            "OR u.table_name ILIKE %s OR u.column_name ILIKE %s)"
        )
        sp = [pat] * 4
    sql = head + f"""SELECT t.*, {OWNER_EXPR} AS owner FROM (
  SELECT u.catalog_name, u.schema_name, u.table_name,
         COUNT(*) AS proposal_count,
         COUNT(*) FILTER (WHERE u.status = 'pending') AS pending,
         COUNT(*) FILTER (WHERE u.status = 'approved') AS approved,
         COUNT(*) FILTER (WHERE u.status = 'rejected') AS rejected,
         COUNT(*) FILTER (WHERE u.status = 'modified') AS modified,
         COUNT(*) FILTER (WHERE u.confidence = 'HIGH') AS high_conf,
         COUNT(*) FILTER (WHERE u.confidence = 'LOW') AS low_conf,
         MAX(u.latest_detected_time) AS last_scan,
         array_agg(DISTINCT u.class_tag ORDER BY u.class_tag) FILTER (WHERE u.class_tag <> '') AS tags
  FROM universe u WHERE {cone}
  GROUP BY 1, 2, 3{having}
) t {_owner_join('t')}
ORDER BY t.catalog_name, t.schema_name, t.table_name"""
    rows = _q(sql, hp + cp + sp)
    col_counts = _mock_col_counts() if IS_MOCK and rows else {}
    out = []
    for r in rows:
        key = f"{r['catalog_name']}.{r['schema_name']}.{r['table_name']}"
        count = int(r["proposal_count"])
        out.append({
            "key": key, "catalog": r["catalog_name"], "schema": r["schema_name"],
            "table": r["table_name"], "owner": r["owner"],
            "last_scan": (r["last_scan"] or "")[:10] or "—",
            "total_cols": col_counts.get(key, count),
            "proposal_count": count,
            **{k: int(r[k]) for k in ("pending", "approved", "rejected", "modified", "high_conf", "low_conf")},
            "tags": list(r["tags"] or []),
            "proposals": [],
        })
    return out


def table_detail(catalog: str, schema: str, table: str) -> dict | None:
    rows = table_summaries(
        [{"scope": "table", "catalog": catalog, "schema_name": schema, "table_name": table}]
    )
    if not rows:
        return None
    summary = rows[0]
    summary["proposals"], _ = list_proposals(
        ProposalFilters(catalog=catalog, schema=schema, table=table), page_size=None
    )
    return summary


def list_proposals(f: ProposalFilters, page: int = 1, page_size: int | None = 50) -> tuple[list[dict], int]:
    head, hp = _with_universe()
    where, wp, needs_owner = _where(f)
    sql = head + f"SELECT u.*, {OWNER_EXPR} AS owner FROM universe u {_owner_join('u')}" + where + _ORDER
    params = hp + wp
    if page_size is not None:
        sql += " LIMIT %s OFFSET %s"
        params = params + [page_size, (max(page, 1) - 1) * page_size]
    items = [_proposal_out(r) for r in _q(sql, params)]
    if page_size is None:
        return items, len(items)
    count_sql = (
        head + "SELECT COUNT(*) AS n FROM universe u "
        + (_owner_join("u") if needs_owner else "") + where
    )
    total = int(_q(count_sql, hp + wp)[0]["n"])
    return items, total

from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from ..models import ProposalOut, ProposalPageOut, FacetsOut, OverviewStatsOut
from ..db import read_model as rm
from ..db.read_model import SyncPendingError, ProposalFilters

router = APIRouter()

def sync_pending_http() -> HTTPException:
    """Return a fresh 503 HTTPException for classification_sync_pending (never share instances)."""
    return HTTPException(status_code=503, detail="classification_sync_pending")


def _owner_for(steward_rows: list[dict], catalog: str, schema: str, table: str) -> str:
    """Return the most-specific assigned steward: table > schema > catalog.

    Ties at the same level go to the smallest principal id (same rule as the SQL read model).
    """
    best: dict[str, str] = {}
    for a in steward_rows:
        if a["catalog"] != catalog:
            continue
        scope = a["scope"]
        if scope == "table" and not (a.get("schema_name") == schema and a.get("table_name") == table):
            continue
        if scope == "schema" and a.get("schema_name") != schema:
            continue
        if scope in ("table", "schema", "catalog") and (scope not in best or a["principal"] < best[scope]):
            best[scope] = a["principal"]
    return best.get("table") or best.get("schema") or best.get("catalog") or "unknown"


@router.get("/proposals", response_model=ProposalPageOut, operation_id="listProposals")
def get_proposals(
    catalog: Optional[str] = Query(None),
    schema: Optional[str] = Query(None),
    table: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    status: Optional[list[str]] = Query(None),
    steward: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    confidence: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    f = ProposalFilters(catalog=catalog, schema=schema, table=table, tag=tag, statuses=status,
                        steward=steward, search=search, confidence=confidence)
    try:
        items, total = rm.list_proposals(f, page, page_size)
    except SyncPendingError:
        raise sync_pending_http()
    return ProposalPageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/proposals/decided", response_model=list[ProposalOut], operation_id="listDecidedProposals")
def get_decided_proposals():
    """Approved / modified / applied proposals for Apply tags — bounded by human decisions."""
    try:
        items, _ = rm.list_proposals(
            ProposalFilters(statuses=["approved", "modified", "applied"]), page_size=None
        )
    except SyncPendingError:
        raise sync_pending_http()
    return items


@router.get("/proposals/facets", response_model=FacetsOut, operation_id="getProposalFacets")
def get_proposal_facets(catalog: Optional[str] = Query(None), schema: Optional[str] = Query(None)):
    try:
        return rm.facets(catalog, schema)
    except SyncPendingError:
        raise sync_pending_http()


@router.get("/overview/stats", response_model=OverviewStatsOut, operation_id="getOverviewStats")
def get_overview_stats(catalog: Optional[str] = Query(None)):
    try:
        return rm.overview_stats(catalog)
    except SyncPendingError:
        raise sync_pending_http()

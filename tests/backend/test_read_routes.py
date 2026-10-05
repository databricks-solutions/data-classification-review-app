from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from data_classification_review_app.backend.routes import proposals as pr
from data_classification_review_app.backend.routes import tables as tr
from data_classification_review_app.backend.routes import stewards as sr


@pytest.fixture
def client(pg, monkeypatch):
    from fastapi import FastAPI
    from data_classification_review_app.backend.core._defaults import _WorkspaceClientDependency
    # get_assignments reads steward_assignments through its own module binding
    monkeypatch.setattr(sr, "db_query", pg.query)
    monkeypatch.setattr(sr, "IS_MOCK", True)   # direct assignments only, no SCIM
    app = FastAPI()
    app.include_router(pr.router, prefix="/api")
    app.include_router(tr.router, prefix="/api")
    app.dependency_overrides = {_WorkspaceClientDependency.__call__: lambda: None}
    return TestClient(app)


def _seed(pg):
    pg.add_result("c1", "s1", "t1", "email", "class.email_address")
    pg.add_result("c1", "s1", "t2", "phone", "class.phone_number")
    pg.add_assignment("st@x.com", "schema", "c1", "s1")


def test_proposals_page(client, pg):
    _seed(pg)
    r = client.get("/api/proposals", params={"page": 1, "page_size": 1, "status": ["pending"]})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2 and body["page"] == 1 and body["page_size"] == 1
    assert len(body["items"]) == 1 and body["items"][0]["owner"] == "st@x.com"


def test_proposals_page_size_cap(client, pg):
    assert client.get("/api/proposals", params={"page_size": 501}).status_code == 422


def test_decided_facets_stats_coverage(client, pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved")
    assert [p["column_key"] for p in client.get("/api/proposals/decided").json()] == ["c1.s1.t1.email"]
    assert client.get("/api/proposals/facets", params={"catalog": "c1", "schema": "s1"}).json()["tables"] == ["t1", "t2"]
    st = client.get("/api/overview/stats").json()
    assert st["total"] == 2 and st["pending"] == 1 and st["by_owner"][0]["owner"] == "st@x.com"
    cov = client.get("/api/coverage", params={"catalog": "c1", "schema": "s1"}).json()
    assert cov["table_count"] == 2 and cov["pending"] == 1


def test_tables_scoped_to_steward(client, pg):
    _seed(pg)
    pg.add_result("c2", "s", "t", "x", "class.ssn")
    rows = client.get("/api/tables", params={"steward": "st@x.com"}).json()
    assert [r["key"] for r in rows] == ["c1.s1.t1", "c1.s1.t2"] and rows[0]["proposals"] == []
    assert client.get("/api/tables", params={"steward": "nobody@x.com"}).json() == []
    assert client.get("/api/tables").status_code == 422


def test_table_detail_route(client, pg):
    _seed(pg)
    d = client.get("/api/tables/c1/s1/t1").json()
    assert d["key"] == "c1.s1.t1" and len(d["proposals"]) == 1
    assert client.get("/api/tables/c1/s1/nope").status_code == 404


@pytest.mark.parametrize("path", [
    "/api/proposals", "/api/proposals/decided", "/api/proposals/facets",
    "/api/overview/stats", "/api/tables?steward=st@x.com", "/api/tables/c/s/t",
    "/api/coverage?catalog=c",
])
def test_sync_pending_is_503_everywhere(client, pg, path):
    pg.add_assignment("st@x.com", "catalog", "c")
    pg.query('DROP TABLE "default".classification_results')
    r = client.get(path)
    assert r.status_code == 503 and r.json()["detail"] == "classification_sync_pending"

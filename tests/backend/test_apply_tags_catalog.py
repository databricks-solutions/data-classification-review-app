from __future__ import annotations
from unittest.mock import MagicMock, patch
from pydantic import SecretStr


def _headers(token="tok", email="me@example.com"):
    from data_classification_review_app.backend.core._headers import DatabricksAppsHeaders
    return DatabricksAppsHeaders(
        host=None, user_name=None, user_id=None, user_email=email,
        request_id=None, token=SecretStr(token),
    )


def test_existing_tag_check_is_catalog_qualified(monkeypatch):
    """The information_schema lookup must be qualified with the target catalog;
    Unity Catalog has no top-level information_schema."""
    from data_classification_review_app.backend.routes import apply_tags as mod
    from data_classification_review_app.backend.models import ApplyTagsIn

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    body = ApplyTagsIn(items=[{
        "column_key": "corporate.human_resources.training_records.instructor_name",
        "class_tag": "class.name",
    }])

    captured: list[str] = []

    def fake_execute_sql(sql, token=None, host=None):
        captured.append(sql)
        return []  # no existing tag, and ALTER returns nothing

    with patch.object(mod, "db_query", return_value=[]), \
         patch.object(mod, "execute", return_value=None), \
         patch("data_classification_review_app.backend.clients.warehouse.execute_sql", fake_execute_sql):
        out = mod.apply_tags(body, MagicMock(), _headers())

    assert out.applied == 1
    select_sql = captured[0]
    assert "`corporate`.information_schema.column_tags" in select_sql
    # Must not reference a bare, catalog-less information_schema.
    assert "FROM information_schema.column_tags" not in select_sql


def test_check_failure_is_reported_as_error(monkeypatch):
    """A failing information_schema check surfaces as a per-column error, not a crash."""
    from data_classification_review_app.backend.routes import apply_tags as mod
    from data_classification_review_app.backend.models import ApplyTagsIn

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    body = ApplyTagsIn(items=[{
        "column_key": "corporate.compliance.regulatory_filings.document_url",
        "class_tag": "class.url",
    }])

    def boom(sql, token=None, host=None):
        raise RuntimeError("SQL failed")

    with patch.object(mod, "db_query", return_value=[]), \
         patch.object(mod, "execute", return_value=None), \
         patch("data_classification_review_app.backend.clients.warehouse.execute_sql", boom):
        out = mod.apply_tags(body, MagicMock(), _headers())

    assert out.applied == 0
    assert len(out.errors) == 1
    assert out.errors[0]["column_key"] == "corporate.compliance.regulatory_filings.document_url"


# ── per-(column, tag) apply, against the embedded Postgres ──────────────────────
def _apply_with_pg(pg, monkeypatch, items):
    from data_classification_review_app.backend.routes import apply_tags as mod
    from data_classification_review_app.backend.models import ApplyTagsIn

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)
    monkeypatch.setattr(mod, "db_query", pg.query)
    monkeypatch.setattr(mod, "execute", pg.query)
    alters: list[str] = []

    def fake_execute_sql(sql, token=None, host=None):
        if sql.startswith("ALTER"):
            alters.append(sql)
        return []

    with patch("data_classification_review_app.backend.clients.warehouse.execute_sql", fake_execute_sql):
        out = mod.apply_tags(ApplyTagsIn(items=items), MagicMock(), _headers())
    return out, alters


def test_applies_every_decided_tag_of_one_column(pg, monkeypatch):
    from data_classification_review_app.backend.db import read_model as rm
    pg.add_result("c", "s", "t", "BirthDate", "class.date_of_birth")
    pg.add_result("c", "s", "t", "BirthDate", "start_date")
    pg.add_decision("c.s.t.BirthDate", "approved", class_tag="class.date_of_birth")
    pg.add_decision("c.s.t.BirthDate", "modified", modified_tag="hire_date", class_tag="start_date")

    out, alters = _apply_with_pg(pg, monkeypatch, [
        {"column_key": "c.s.t.BirthDate", "class_tag": "class.date_of_birth"},
        {"column_key": "c.s.t.BirthDate", "class_tag": "start_date"},
    ])

    assert out.applied == 2 and out.errors == []
    assert "SET TAGS ('class.date_of_birth' = '')" in alters[0]
    assert "SET TAGS ('hire_date' = '')" in alters[1]
    items, _ = rm.list_proposals(rm.ProposalFilters(table="t"))
    assert {i["class_tag"]: i["status"] for i in items} == {
        "class.date_of_birth": "applied", "start_date": "applied",
    }
    assert all(i["applied_at"] for i in items)


def test_applying_one_tag_leaves_legacy_decision_for_the_other(pg, monkeypatch):
    from data_classification_review_app.backend.db import read_model as rm
    pg.add_result("c", "s", "t", "col", "a")
    pg.add_result("c", "s", "t", "col", "b")
    pg.add_decision("c.s.t.col", "modified", modified_tag="z")   # legacy: whole column

    out, alters = _apply_with_pg(pg, monkeypatch, [{"column_key": "c.s.t.col", "class_tag": "a"}])

    assert out.applied == 1 and "SET TAGS ('z' = '')" in alters[0]
    by_tag = {i["class_tag"]: i["status"] for i in rm.list_proposals(rm.ProposalFilters())[0]}
    assert by_tag == {"a": "applied", "b": "modified"}


def test_applies_user_added_tag(pg, monkeypatch):
    from data_classification_review_app.backend.db import read_model as rm
    pg.add_decision("c.s.t.col", "approved", modified_tag="class.ssn", user_added=True)
    pg.add_decision("c.s.t.col", "approved", modified_tag="class.name", user_added=True)

    out, alters = _apply_with_pg(pg, monkeypatch, [
        {"column_key": "c.s.t.col", "class_tag": "class.ssn", "user_added": True},
    ])

    assert out.applied == 1 and "SET TAGS ('class.ssn' = '')" in alters[0]
    by_tag = {i["class_tag"]: i["status"] for i in rm.list_proposals(rm.ProposalFilters())[0]}
    assert by_tag == {"class.ssn": "applied", "class.name": "approved"}

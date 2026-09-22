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

    body = ApplyTagsIn(
        column_keys=["corporate.human_resources.training_records.instructor_name"],
        class_tags={"corporate.human_resources.training_records.instructor_name": "class.name"},
    )

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

    body = ApplyTagsIn(
        column_keys=["corporate.compliance.regulatory_filings.document_url"],
        class_tags={"corporate.compliance.regulatory_filings.document_url": "class.url"},
    )

    def boom(sql, token=None, host=None):
        raise RuntimeError("SQL failed")

    with patch.object(mod, "db_query", return_value=[]), \
         patch.object(mod, "execute", return_value=None), \
         patch("data_classification_review_app.backend.clients.warehouse.execute_sql", boom):
        out = mod.apply_tags(body, MagicMock(), _headers())

    assert out.applied == 0
    assert len(out.errors) == 1
    assert out.errors[0]["column_key"] == "corporate.compliance.regulatory_filings.document_url"

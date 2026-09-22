from __future__ import annotations
from pydantic import SecretStr


def _headers(token="tok"):
    from data_classification_review_app.backend.core._headers import DatabricksAppsHeaders
    return DatabricksAppsHeaders(
        host=None, user_name=None, user_id=None, user_email="me@example.com",
        request_id=None, token=SecretStr(token) if token else None,
    )


def test_success_surfaces_descriptions_and_tags(monkeypatch):
    """A fully successful fetch surfaces table/column descriptions and both tag levels,
    with every denied flag False."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table",
        lambda full_name, token=None, host=None: {
            "comment": "The employees table",
            "columns": [
                {"name": "ssn", "type_text": "string", "type_name": "STRING",
                 "comment": "Social security number"},
            ],
        },
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table_level_tags",
        lambda catalog, schema, table, token, host: ["pii_reviewed"],
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_column_tags",
        lambda catalog, schema, table, token, host: [
            {"column_name": "ssn", "tag_name": "class.ssn", "tag_value": None},
        ],
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        lambda sql, token=None, host=None: [],
    )

    result = mod.get_columns("corporate", "human_resources", "employees", headers=_headers())

    assert result.table_description == "The employees table"
    assert result.table_tags == ["pii_reviewed"]
    assert result.metadata_denied is False
    assert result.table_tags_denied is False
    assert result.column_tags_denied is False
    assert result.columns[0].column_description == "Social security number"
    assert result.columns[0].existing_tags == ["class.ssn"]


def test_get_table_permission_failure_sets_metadata_denied(monkeypatch):
    """A 403 from GetTable is reported as metadata_denied, not raised as an error."""
    import httpx
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    class _FakeResponse:
        status_code = 403

    def boom(full_name, token=None, host=None):
        raise httpx.HTTPStatusError("Forbidden", request=None, response=_FakeResponse())

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table", boom,
    )

    result = mod.get_columns("corporate", "human_resources", "employees", headers=_headers())

    assert result.metadata_denied is True
    assert result.columns == []
    assert result.table_description is None


def test_get_table_non_permission_failure_still_raises(monkeypatch):
    """A non-403/401 failure (e.g. 500) still raises, preserving existing behavior for
    genuine errors."""
    import httpx
    import pytest
    from fastapi import HTTPException
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    class _FakeResponse:
        status_code = 500

    def boom(full_name, token=None, host=None):
        raise httpx.HTTPStatusError("Server error", request=None, response=_FakeResponse())

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table", boom,
    )

    with pytest.raises(HTTPException) as exc_info:
        mod.get_columns("corporate", "human_resources", "employees", headers=_headers())

    assert exc_info.value.status_code == 500


def test_table_tags_failure_is_isolated(monkeypatch):
    """A failure fetching table-level tags does not block descriptions or column tags."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table",
        lambda full_name, token=None, host=None: {"comment": "desc", "columns": []},
    )

    def boom(catalog, schema, table, token, host):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table_level_tags", boom,
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_column_tags",
        lambda catalog, schema, table, token, host: [],
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        lambda sql, token=None, host=None: [],
    )

    result = mod.get_columns("corporate", "human_resources", "employees", headers=_headers())

    assert result.table_tags_denied is True
    assert result.table_tags == []
    assert result.table_description == "desc"
    assert result.column_tags_denied is False


def test_column_tags_failure_is_isolated(monkeypatch):
    """A failure fetching column-level tags does not block descriptions or table tags."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table",
        lambda full_name, token=None, host=None: {
            "comment": "desc",
            "columns": [{"name": "ssn", "type_text": "string", "type_name": "STRING", "comment": None}],
        },
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table_level_tags",
        lambda catalog, schema, table, token, host: ["pii_reviewed"],
    )

    def boom(catalog, schema, table, token, host):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_column_tags", boom,
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        lambda sql, token=None, host=None: [],
    )

    result = mod.get_columns("corporate", "human_resources", "employees", headers=_headers())

    assert result.column_tags_denied is True
    assert result.columns[0].existing_tags == []
    assert result.table_tags == ["pii_reviewed"]
    assert result.table_description == "desc"


def test_mock_mode_returns_seeded_description_and_tags(monkeypatch):
    """Mock mode surfaces the static TABLE_DESCRIPTIONS/COLUMN_DESCRIPTIONS/TABLE_TAGS
    dicts, with every denied flag always False."""
    from data_classification_review_app.backend.routes import tables as mod
    from data_classification_review_app.backend.mock import data as mock_data

    monkeypatch.setattr(mod, "IS_MOCK", True)
    monkeypatch.setitem(
        mock_data.TABLE_DESCRIPTIONS, "00vsdb.agent_analytics.tickets_bronze",
        "Ticket intake bronze table",
    )
    monkeypatch.setitem(
        mock_data.COLUMN_DESCRIPTIONS, "00vsdb.agent_analytics.tickets_bronze.ticket_id",
        "Unique ticket identifier",
    )
    monkeypatch.setitem(
        mock_data.TABLE_TAGS, "00vsdb.agent_analytics.tickets_bronze", ["pii_reviewed"],
    )

    def fake_db_query(sql, params=None):
        if "steward_assignments" in sql:
            return []
        return [{"column_name": "ticket_id", "data_type": "string", "class_tag": None,
                  "confidence": None, "frequency": None}]

    monkeypatch.setattr(mod, "db_query", fake_db_query)

    result = mod.get_columns("00vsdb", "agent_analytics", "tickets_bronze", headers=_headers())

    assert result.table_description == "Ticket intake bronze table"
    assert result.table_tags == ["pii_reviewed"]
    assert result.metadata_denied is False
    assert result.table_tags_denied is False
    assert result.column_tags_denied is False
    assert result.columns[0].column_description == "Unique ticket identifier"

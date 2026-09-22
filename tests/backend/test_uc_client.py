from __future__ import annotations


class _FakeResponse:
    def __init__(self, json_body):
        self._json = json_body

    def raise_for_status(self):
        pass

    def json(self):
        return self._json


def test_get_table_rest_branch_includes_comments(monkeypatch):
    """The REST branch (OBO token+host) surfaces table and column `comment` fields."""
    from data_classification_review_app.backend.clients import uc_client as mod

    def fake_get(url, headers=None, timeout=None):
        return _FakeResponse({
            "comment": "Table description",
            "columns": [
                {"name": "id", "type_text": "int", "type_name": "INT", "comment": "Primary key"},
                {"name": "name", "type_text": "string", "type_name": "STRING"},
            ],
        })

    monkeypatch.setattr(mod.httpx, "get", fake_get)

    result = mod.get_table("cat.sch.tbl", token="tok", host="example.com")

    assert result["comment"] == "Table description"
    assert result["columns"][0]["comment"] == "Primary key"
    assert result["columns"][1]["comment"] is None


def test_get_table_sdk_branch_includes_comments(monkeypatch):
    """The SDK branch (no token/host — service principal) surfaces comment fields via
    TableInfo.comment / ColumnInfo.comment."""
    from data_classification_review_app.backend.clients import uc_client as mod

    class _FakeColumn:
        def __init__(self, name, comment=None):
            self.name = name
            self.type_text = "string"
            self.type_name = "STRING"
            self.comment = comment

    class _FakeTableInfo:
        comment = "SDK table description"
        columns = [_FakeColumn("id", "Primary key"), _FakeColumn("name")]

    class _FakeTablesApi:
        def get(self, full_name):
            return _FakeTableInfo()

    class _FakeWorkspaceClient:
        tables = _FakeTablesApi()

    monkeypatch.setattr(mod, "_w", lambda: _FakeWorkspaceClient())

    result = mod.get_table("cat.sch.tbl")

    assert result["comment"] == "SDK table description"
    assert result["columns"][0]["comment"] == "Primary key"
    assert result["columns"][1]["comment"] is None


def test_get_column_tags_is_catalog_qualified(monkeypatch):
    """Column tags come from information_schema.column_tags, qualified with the target
    catalog (Unity Catalog has no top-level information_schema)."""
    from data_classification_review_app.backend.clients import uc_client as mod

    captured: list[str] = []

    def fake_execute_sql(sql, token=None, host=None):
        captured.append(sql)
        return [
            {"column_name": "ssn", "tag_name": "class.ssn", "tag_value": None},
            {"column_name": "ssn", "tag_name": "sensitivity", "tag_value": "high"},
        ]

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        fake_execute_sql,
    )

    result = mod.get_column_tags("corporate", "human_resources", "employees", "tok", "example.com")

    sql = captured[0]
    assert "`corporate`.information_schema.column_tags" in sql
    assert "FROM information_schema.column_tags" not in sql
    assert result == [
        {"column_name": "ssn", "tag_name": "class.ssn", "tag_value": None},
        {"column_name": "ssn", "tag_name": "sensitivity", "tag_value": "high"},
    ]


def test_get_column_tags_propagates_failure(monkeypatch):
    """Failures are not swallowed here — the route decides how to report them."""
    import pytest
    from data_classification_review_app.backend.clients import uc_client as mod

    def boom(sql, token=None, host=None):
        raise RuntimeError("SQL failed")

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql", boom,
    )

    with pytest.raises(RuntimeError):
        mod.get_column_tags("corporate", "human_resources", "employees", "tok", "example.com")


def test_get_table_level_tags_is_catalog_qualified(monkeypatch):
    """Table tags come from information_schema.table_tags, qualified with the target
    catalog, formatting values as 'key=value' (or bare 'key' when there's no value).

    This replaced an earlier entity-tag-assignments REST/SDK implementation, which 403s
    for OBO tokens issued to a Databricks App (confirmed against a real deployment) even
    though the same token succeeds against information_schema.column_tags."""
    from data_classification_review_app.backend.clients import uc_client as mod

    captured: list[str] = []

    def fake_execute_sql(sql, token=None, host=None):
        captured.append(sql)
        return [
            {"tag_name": "pii_reviewed", "tag_value": None},
            {"tag_name": "owner", "tag_value": "data-gov-team"},
        ]

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        fake_execute_sql,
    )

    result = mod.get_table_level_tags("cat", "sch", "tbl", "tok", "example.com")

    sql = captured[0]
    assert "`cat`.information_schema.table_tags" in sql
    assert "FROM information_schema.table_tags" not in sql
    assert result == ["pii_reviewed", "owner=data-gov-team"]


def test_get_table_level_tags_propagates_failure(monkeypatch):
    """Failures are not swallowed here — the route decides how to report them."""
    import pytest
    from data_classification_review_app.backend.clients import uc_client as mod

    def boom(sql, token=None, host=None):
        raise RuntimeError("SQL failed")

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql", boom,
    )

    with pytest.raises(RuntimeError):
        mod.get_table_level_tags("cat", "sch", "tbl", "tok", "example.com")

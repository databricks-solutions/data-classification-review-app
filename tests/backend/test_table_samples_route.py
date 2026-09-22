from __future__ import annotations
from pydantic import SecretStr
from data_classification_review_app.backend.models import ColumnSamplesOut, TableSamplesOut


def _headers(token="tok"):
    from data_classification_review_app.backend.core._headers import DatabricksAppsHeaders
    return DatabricksAppsHeaders(
        host=None, user_name=None, user_id=None, user_email="me@example.com",
        request_id=None, token=SecretStr(token) if token else None,
    )


def test_success_returns_samples_per_column(monkeypatch):
    """A successful query returns one ColumnSamplesOut per requested column, denied=False."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    captured_sql = []

    def fake_execute_sql(sql, token=None, host=None):
        captured_sql.append(sql)
        return [{"national_id": ["123-45-6789"], "status": ["active", "on_leave"]}]

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        fake_execute_sql,
    )

    result = mod.get_table_samples(
        "corporate", "human_resources", "employees",
        columns=["national_id", "status"],
        headers=_headers(),
    )

    assert result.denied is False
    by_col = {c.column: c.samples for c in result.columns}
    assert by_col["national_id"] == ["123-45-6789"]
    assert by_col["status"] == ["active", "on_leave"]
    sql = captured_sql[0]
    assert "TABLESAMPLE (1000 ROWS)" in sql
    assert "collect_set(`national_id`)" in sql
    assert "collect_set(`status`)" in sql


def test_empty_rows_returns_empty_samples_per_column(monkeypatch):
    """When the warehouse returns no rows at all, each requested column gets an empty
    samples list, denied=False."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    def fake_execute_sql(sql, token=None, host=None):
        return []

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        fake_execute_sql,
    )

    result = mod.get_table_samples(
        "corporate", "human_resources", "employees",
        columns=["national_id", "status"],
        headers=_headers(),
    )

    assert result == TableSamplesOut(
        columns=[
            ColumnSamplesOut(column="national_id", samples=[]),
            ColumnSamplesOut(column="status", samples=[]),
        ],
        denied=False,
    )


def test_non_string_values_are_stringified(monkeypatch):
    """Non-string raw values (e.g. ints) returned by the warehouse are stringified before
    being placed in the samples list."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    def fake_execute_sql(sql, token=None, host=None):
        return [{"some_col": [1, 2, 3]}]

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        fake_execute_sql,
    )

    result = mod.get_table_samples(
        "corporate", "human_resources", "employees",
        columns=["some_col"],
        headers=_headers(),
    )

    assert result.denied is False
    by_col = {c.column: c.samples for c in result.columns}
    assert by_col["some_col"] == ["1", "2", "3"]


def test_permission_failure_reports_denied_not_error(monkeypatch):
    """A SQL failure (e.g. PERMISSION_DENIED) surfaces as denied=True, not a raised error."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    def boom(sql, token=None, host=None):
        raise RuntimeError("SQL failed [PERMISSION_DENIED]: User does not have SELECT")

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql", boom,
    )

    result = mod.get_table_samples(
        "corporate", "human_resources", "employees",
        columns=["national_id"],
        headers=_headers(),
    )

    assert result.denied is True
    assert result.columns == []


def test_storage_missing_error_is_not_denied(monkeypatch):
    """DELTA_TABLE_NOT_FOUND means the user has visibility but storage is gone — not a
    permission denial."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    def boom(sql, token=None, host=None):
        raise RuntimeError("SQL failed [DELTA_TABLE_NOT_FOUND]: path missing")

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql", boom,
    )

    result = mod.get_table_samples(
        "corporate", "human_resources", "employees",
        columns=["national_id"],
        headers=_headers(),
    )

    assert result.denied is False
    assert result.columns == []


def test_no_token_is_denied(monkeypatch):
    """Local dev without the Apps runtime (no OBO token) can't run the OBO query — treat
    as denied rather than guessing."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setattr(mod, "IS_MOCK", False)

    result = mod.get_table_samples(
        "corporate", "human_resources", "employees",
        columns=["national_id"],
        headers=_headers(token=None),
    )

    assert result.denied is True
    assert result.columns == []


def test_old_per_column_route_is_removed():
    from data_classification_review_app.backend.routes import tables as mod
    assert not hasattr(mod, "get_column_samples")


def test_get_columns_route_has_no_samples_gate(monkeypatch):
    """get_columns no longer runs a LIMIT 0 check or fetches samples."""
    from data_classification_review_app.backend.routes import tables as mod

    monkeypatch.setenv("DATABRICKS_HOST", "https://example.azuredatabricks.net")
    monkeypatch.setattr(mod, "IS_MOCK", False)

    calls = []

    def fake_execute_sql(sql, token=None, host=None):
        calls.append(sql)
        return []

    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.warehouse.execute_sql",
        fake_execute_sql,
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table",
        lambda full_name, token=None, host=None: {"columns": []},
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_column_tags",
        lambda catalog, schema, table, token, host: [],
    )
    monkeypatch.setattr(
        "data_classification_review_app.backend.clients.uc_client.get_table_level_tags",
        lambda catalog, schema, table, token, host: [],
    )

    mod.get_columns("corporate", "human_resources", "employees", headers=_headers())

    assert not any("LIMIT 0" in c for c in calls)

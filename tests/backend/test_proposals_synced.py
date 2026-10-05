from __future__ import annotations
import pytest
from data_classification_review_app.backend.db import read_model as rm


def test_dedupe_latest_removed():
    from data_classification_review_app.backend.routes import proposals as mod
    assert not hasattr(mod, "_dedupe_latest")
    assert not hasattr(mod, "_get_proposals")


@pytest.mark.parametrize("value", [None, "", "   "])
def test_unset_or_blank_synced_table_env_raises_sync_pending(monkeypatch, value):
    monkeypatch.setattr(rm, "IS_MOCK", False)
    if value is None:
        monkeypatch.delenv("CLASSIFICATION_SYNCED_TABLE", raising=False)
    else:
        monkeypatch.setenv("CLASSIFICATION_SYNCED_TABLE", value)
    with pytest.raises(rm.SyncPendingError):
        rm.list_proposals(rm.ProposalFilters())


def test_synced_table_name_is_quoted_for_reserved_schema(monkeypatch):
    """The synced table lands in a Postgres schema named after the UC schema; with the
    installer default `default` (a reserved word) an unquoted name is a syntax error."""
    monkeypatch.setattr(rm, "IS_MOCK", False)
    monkeypatch.setenv("CLASSIFICATION_SYNCED_TABLE", "default.classification_results")
    seen = []

    def fake_db_query(sql, params=None):
        seen.append(sql)
        return [{"n": 0}] if "COUNT(*) AS n" in sql else []

    monkeypatch.setattr(rm, "db_query", fake_db_query)
    rm.list_proposals(rm.ProposalFilters())
    assert 'FROM "default"."classification_results"' in seen[0]

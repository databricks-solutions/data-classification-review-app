from __future__ import annotations
import pytest
from data_classification_review_app.backend.db import read_model as rm
from data_classification_review_app.backend.db.read_model import ProposalFilters as F


def _seed(pg):
    pg.add_result("c1", "s1", "t1", "email", "class.email_address")
    pg.add_result("c1", "s1", "t1", "email", "class.name", confidence="LOW")
    pg.add_result("c1", "s1", "t2", "phone", "class.phone_number", confidence=None)
    pg.add_result("c2", "s9", "t9", "ssn", "class.ssn")


def test_list_returns_all_rows_sorted_with_pending_status(pg):
    _seed(pg)
    items, total = rm.list_proposals(F())
    assert total == 4
    assert [i["column_key"] for i in items] == [
        "c1.s1.t1.email", "c1.s1.t1.email", "c1.s1.t2.phone", "c2.s9.t9.ssn",
    ]
    assert [i["class_tag"] for i in items[:2]] == ["class.email_address", "class.name"]
    first = items[0]
    assert first["status"] == "pending" and first["owner"] == "unknown"
    assert first["table_key"] == "c1.s1.t1" and first["data_type"] == "string"
    assert first["schema_name"] == "s1" and first["table"] == "t1" and first["column"] == "email"
    assert first["user_added"] is False and first["latest_detected_time"].startswith("2026-09-01")


def test_legacy_whole_column_decision_is_shared_by_all_tags_and_latest_wins(pg):
    """Decisions recorded before per-tag decisions (no class_tag) cover every tag of the column."""
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "rejected", decided_at="2026-09-01 00:00:00+00")
    pg.add_decision("c1.s1.t1.email", "approved", decided_at="2026-09-03 00:00:00+00", comment="ok")
    items, _ = rm.list_proposals(F(table="t1"))
    assert [i["status"] for i in items] == ["approved", "approved"]
    assert items[0]["comment"] == "ok" and items[0]["reviewer"] == "rev@x.com"
    assert items[0]["decided_at"].startswith("2026-09-03")


def test_user_added_rows_are_included_with_synthetic_key(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.col.with.dots", "approved", modified_tag="class.ssn", user_added=True)
    items, total = rm.list_proposals(F(catalog="c1", schema="s1", table="t1"))
    assert total == 3
    ua = [i for i in items if i["user_added"]][0]
    assert ua["key"] == "c1.s1.t1.col.with.dots|class.ssn|user"
    assert ua["column_key"] == "c1.s1.t1.col.with.dots"
    assert ua["column"] == "col.with.dots" and ua["class_tag"] == "class.ssn"
    assert ua["status"] == "approved" and ua["modified_tag"] is None and ua["data_type"] == ""


def test_filters(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t2.phone", "modified", modified_tag="class.ssn")
    assert rm.list_proposals(F(catalog="c2"))[1] == 1
    assert rm.list_proposals(F(catalog="c1", schema="s1", table="t2"))[1] == 1
    assert rm.list_proposals(F(statuses=["pending"]))[1] == 3
    assert rm.list_proposals(F(statuses=["modified", "approved"]))[1] == 1
    # tag filter matches the effective tag (modified_tag, else class_tag)
    assert {i["column_key"] for i in rm.list_proposals(F(tag="class.ssn"))[0]} == {"c1.s1.t2.phone", "c2.s9.t9.ssn"}
    assert rm.list_proposals(F(confidence="LOW"))[1] == 1
    assert rm.list_proposals(F(confidence="NONE"))[1] == 1
    assert rm.list_proposals(F(search="PHONE"))[1] == 1          # case-insensitive, column + tag haystack
    assert rm.list_proposals(F(search="c1.s1.t1"))[1] == 2


def test_search_treats_like_wildcards_literally(pg):
    pg.add_result("c", "s", "t", "a_b", "class.name")
    pg.add_result("c", "s", "t", "axb", "class.name")
    pg.add_result("c", "s", "t", "pct", "class.name")
    assert [i["column"] for i in rm.list_proposals(F(search="a_b"))[0]] == ["a_b"]
    assert rm.list_proposals(F(search="50%"))[1] == 0


def test_owner_precedence_and_steward_filter(pg):
    _seed(pg)
    pg.add_assignment("cat@x.com", "catalog", "c1")
    pg.add_assignment("sch@x.com", "schema", "c1", "s1")
    pg.add_assignment("tbl@x.com", "table", "c1", "s1", "t1")
    pg.add_assignment("aaa@x.com", "table", "c1", "s1", "t1")   # same level: smallest id wins
    owners = {i["column_key"]: i["owner"] for i in rm.list_proposals(F())[0]}
    assert owners == {"c1.s1.t1.email": "aaa@x.com", "c1.s1.t2.phone": "sch@x.com", "c2.s9.t9.ssn": "unknown"}
    items, total = rm.list_proposals(F(steward="sch@x.com"))
    assert total == 1 and items[0]["column_key"] == "c1.s1.t2.phone"
    assert rm.list_proposals(F(steward="unknown"))[1] == 1


def test_steward_prefilter_passes_but_owner_check_rejects(pg):
    """A steward whose catalog assignment is overridden by another principal at table level
    must NOT receive that table's rows, even though the prefilter EXISTS clause passes for it."""
    _seed(pg)
    pg.add_assignment("p0@x.com", "catalog", "c1")            # covers all of c1
    pg.add_assignment("other@x.com", "table", "c1", "s1", "t1")  # overrides p0 for t1
    # p0 should own only c1.s1.t2 (c1.s1.t1 is owned by other@x.com at table level)
    items, total = rm.list_proposals(F(steward="p0@x.com"))
    assert total == 1
    assert items[0]["column_key"] == "c1.s1.t2.phone"


def test_pagination(pg):
    for n in range(7):
        pg.add_result("c", "s", "t", f"col{n}", "class.name")
    items, total = rm.list_proposals(F(), page=2, page_size=3)
    assert total == 7 and [i["column"] for i in items] == ["col3", "col4", "col5"]
    items, total = rm.list_proposals(F(), page=9, page_size=3)
    assert items == [] and total == 7
    items, total = rm.list_proposals(F(), page_size=None)
    assert len(items) == 7 and total == 7


def test_catalog_filter_env_restricts_source(pg, monkeypatch):
    _seed(pg)
    monkeypatch.setenv("CLASSIFICATION_CATALOG_FILTER", "c2, other")
    assert [i["catalog"] for i in rm.list_proposals(F())[0]] == ["c2"]


def test_unset_env_raises_sync_pending(monkeypatch):
    monkeypatch.setattr(rm, "IS_MOCK", False)
    monkeypatch.delenv("CLASSIFICATION_SYNCED_TABLE", raising=False)
    with pytest.raises(rm.SyncPendingError):
        rm.list_proposals(F())


def test_missing_table_raises_sync_pending(pg):
    pg.query('DROP TABLE "default".classification_results')
    with pytest.raises(rm.SyncPendingError):
        rm.list_proposals(F())


def test_overview_stats(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved")         # 2 rows (two tags)
    pg.add_decision("c1.s1.t2.phone", "rejected")
    pg.add_decision("c9.s.t.x", "approved", modified_tag="class.ssn", user_added=True)
    pg.add_assignment("sch@x.com", "schema", "c1", "s1")
    st = rm.overview_stats(None)
    assert (st["total"], st["approved"], st["rejected"], st["modified"], st["pending"], st["applied"]) == (5, 3, 1, 0, 1, 0)
    assert st["approval_rate"] == 75 and st["table_count"] == 4
    by_cat = {c["catalog"]: c for c in st["by_catalog"]}
    assert by_cat["c1"]["tables"] == 2 and by_cat["c1"]["total"] == 3 and by_cat["c1"]["approved"] == 2
    assert {t["tag"]: t["total"] for t in st["by_tag"]}["class.ssn"] == 2
    by_owner = {o["owner"]: o for o in st["by_owner"]}
    assert by_owner["sch@x.com"]["total"] == 3 and by_owner["sch@x.com"]["rejected"] == 1
    assert by_owner["unknown"]["total"] == 2
    one = rm.overview_stats("c2")
    assert one["total"] == 1 and [c["catalog"] for c in one["by_catalog"]] == ["c2"]


def test_overview_stats_empty(pg):
    st = rm.overview_stats(None)
    assert st["total"] == 0 and st["approval_rate"] == 0
    assert st["by_catalog"] == [] and st["by_tag"] == [] and st["by_owner"] == []


def test_facets(pg):
    _seed(pg)
    pg.add_assignment("b@x.com", "catalog", "c1")
    pg.add_assignment("a@x.com", "catalog", "c2")
    f = rm.facets(None, None)
    assert f["catalogs"] == ["c1", "c2"] and f["schemas"] == ["s1", "s9"] and f["tables"] == []
    assert f["tags"] == ["class.email_address", "class.name", "class.phone_number", "class.ssn"]
    assert f["stewards"] == ["a@x.com", "b@x.com", "unknown"]
    f = rm.facets("c1", "s1")
    assert f["schemas"] == ["s1"] and f["tables"] == ["t1", "t2"]


def test_coverage(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved")
    cov = rm.coverage({"scope": "catalog", "catalog": "c1", "schema_name": None, "table_name": None})
    assert cov == {"table_count": 2, "proposal_count": 3, "pending": 1, "tables": ["c1.s1.t1", "c1.s1.t2"]}
    cov = rm.coverage({"scope": "table", "catalog": "c1", "schema_name": "s1", "table_name": "t2"})
    assert cov["table_count"] == 1 and cov["tables"] == ["c1.s1.t2"]
    cov = rm.coverage({"scope": "schema", "catalog": "nope", "schema_name": "x", "table_name": None})
    assert cov == {"table_count": 0, "proposal_count": 0, "pending": 0, "tables": []}
    cov = rm.coverage({"scope": "catalog", "catalog": "c1", "schema_name": None, "table_name": None}, limit=1)
    assert cov["table_count"] == 2 and cov["tables"] == ["c1.s1.t1"]


# ---------------------------------------------------------------------------
# Task 3: table_summaries + table_detail
# ---------------------------------------------------------------------------

def _cat(c):
    return {"scope": "catalog", "catalog": c, "schema_name": None, "table_name": None}


def test_table_summaries_scoped_to_assignments(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved")
    pg.add_assignment("tbl@x.com", "table", "c1", "s1", "t1")
    rows = rm.table_summaries([_cat("c1")])
    assert [r["key"] for r in rows] == ["c1.s1.t1", "c1.s1.t2"]
    t1 = rows[0]
    assert (t1["catalog"], t1["schema"], t1["table"]) == ("c1", "s1", "t1")
    assert t1["proposal_count"] == 2 and t1["approved"] == 2 and t1["pending"] == 0
    assert t1["high_conf"] == 1 and t1["low_conf"] == 1 and t1["total_cols"] == 2
    assert t1["tags"] == ["class.email_address", "class.name"]
    assert t1["owner"] == "tbl@x.com" and t1["last_scan"] == "2026-09-01" and t1["proposals"] == []
    assert rows[1]["owner"] == "unknown" and rows[1]["pending"] == 1


def test_table_summaries_without_assignments_is_empty(pg):
    _seed(pg)
    assert rm._cone([]) == ("FALSE", [])
    assert rm.table_summaries([]) == []


def test_table_summaries_search_keeps_full_counts(pg):
    _seed(pg)
    rows = rm.table_summaries([_cat("c1")], search="EMAIL")
    assert [r["key"] for r in rows] == ["c1.s1.t1"] and rows[0]["proposal_count"] == 2
    assert rm.table_summaries([_cat("c1")], search="e_mail") == []


def test_table_summaries_include_user_added_only_tables(pg):
    pg.add_decision("c1.s1.newt.col", "approved", modified_tag="class.ssn", user_added=True)
    rows = rm.table_summaries([_cat("c1")])
    assert [r["key"] for r in rows] == ["c1.s1.newt"]
    assert rows[0]["approved"] == 1 and rows[0]["last_scan"] == "—"


def test_table_detail(pg):
    _seed(pg)
    d = rm.table_detail("c1", "s1", "t1")
    assert d["key"] == "c1.s1.t1" and d["proposal_count"] == 2
    assert [p["class_tag"] for p in d["proposals"]] == ["class.email_address", "class.name"]
    assert rm.table_detail("c1", "s1", "missing") is None


# ---------------------------------------------------------------------------
# Per-(column, tag) decisions + proposal_state
# ---------------------------------------------------------------------------

def test_proposal_keys_are_unique_per_column_and_tag(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved", modified_tag="class.email_address", user_added=True)
    items, _ = rm.list_proposals(F())
    keys = [i["key"] for i in items]
    assert len(keys) == len(set(keys)) == 5
    assert "c1.s1.t1.email|class.email_address" in keys
    assert "c1.s1.t1.email|class.email_address|user" in keys


def test_decision_applies_only_to_its_tag(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved", class_tag="class.email_address")
    pg.add_decision("c1.s1.t1.email", "modified", modified_tag="class.ssn", class_tag="class.name",
                    decided_at="2026-09-03 00:00:00+00")
    by_tag = {i["class_tag"]: i for i in rm.list_proposals(F(table="t1"))[0]}
    assert by_tag["class.email_address"]["status"] == "approved"
    assert by_tag["class.email_address"]["modified_tag"] is None
    assert by_tag["class.name"]["status"] == "modified"
    assert by_tag["class.name"]["modified_tag"] == "class.ssn"


def test_tagged_decision_overrides_legacy_whole_column_decision(pg):
    _seed(pg)
    pg.add_decision("c1.s1.t1.email", "approved", decided_at="2026-09-01 00:00:00+00")
    # Older than the legacy row, but specific to one tag: still wins for that tag.
    pg.add_decision("c1.s1.t1.email", "rejected", class_tag="class.name",
                    decided_at="2026-08-01 00:00:00+00")
    by_tag = {i["class_tag"]: i["status"] for i in rm.list_proposals(F(table="t1"))[0]}
    assert by_tag == {"class.email_address": "approved", "class.name": "rejected"}


def test_state_keeps_latest_decision_when_older_rows_arrive_later(pg):
    """The legacy-copy notebook inserts history in any order; the newest decision must win."""
    _seed(pg)
    pg.add_decision("c1.s1.t2.phone", "approved", class_tag="class.phone_number",
                    decided_at="2026-09-05 00:00:00+00")
    pg.add_decision("c1.s1.t2.phone", "rejected", class_tag="class.phone_number",
                    decided_at="2026-09-01 00:00:00+00")
    [item] = rm.list_proposals(F(table="t2"))[0]
    assert item["status"] == "approved" and item["decided_at"].startswith("2026-09-05")


def test_admin_audit_rows_do_not_become_proposal_state(pg):
    pg.add_decision("steward:first.middle.last.name@x.com", "steward_added")
    pg.add_decision("assignment:table:c1.s1.t1", "scope_added")
    assert pg.query("SELECT * FROM proposal_state") == []
    row = pg.query("SELECT catalog_name FROM decisions WHERE status = 'steward_added'")[0]
    assert row["catalog_name"] is None


def test_decisions_expose_split_key_columns(pg):
    pg.add_decision("c1.s1.t1.col.with.dots", "approved", class_tag="class.name")
    row = pg.query("SELECT catalog_name, schema_name, table_name, column_name FROM decisions")[0]
    assert row == {"catalog_name": "c1", "schema_name": "s1", "table_name": "t1",
                   "column_name": "col.with.dots"}


def test_user_added_tags_on_one_column_are_independent(pg):
    pg.add_decision("c1.s1.t1.col", "approved", modified_tag="class.ssn", user_added=True)
    pg.add_decision("c1.s1.t1.col", "approved", modified_tag="class.name", user_added=True)
    pg.add_decision("c1.s1.t1.col", "rejected", modified_tag="class.name", user_added=True,
                    decided_at="2026-09-03 00:00:00+00")
    by_tag = {i["class_tag"]: i["status"] for i in rm.list_proposals(F())[0]}
    assert by_tag == {"class.ssn": "approved", "class.name": "rejected"}

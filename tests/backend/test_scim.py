from __future__ import annotations
from unittest.mock import MagicMock
import pytest


def _user(user_name: str, group_ids: list[str]):
    u = MagicMock()
    u.user_name = user_name
    u.display_name = user_name.split("@")[0].replace(".", " ").title()
    u.id = "scim-" + user_name
    email = MagicMock()
    email.value = user_name
    email.primary = True
    u.emails = [email]
    u.groups = [MagicMock(value=gid) for gid in group_ids]
    return u


def _group(gid: str, display_name: str, member_count: int = 0):
    g = MagicMock()
    g.id = gid
    g.display_name = display_name
    g.members = [MagicMock() for _ in range(member_count)]
    return g


# ── get_user_registered_group_ids ────────────────────────────────────────────

def test_returns_intersection_of_user_scim_groups_and_registered_groups():
    from data_classification_review_app.backend.core._scim import get_user_registered_group_ids
    ws = MagicMock()
    ws.users.list.return_value = [_user("alice@ex.com", ["g1", "g4"])]
    result = get_user_registered_group_ids(ws, "alice@ex.com", ["g1", "g2", "g3"])
    assert set(result) == {"g1"}
    ws.users.list.assert_called_once_with(
        filter='userName eq "alice@ex.com"', attributes="id,userName,groups"
    )


def test_returns_empty_when_no_registered_groups():
    from data_classification_review_app.backend.core._scim import get_user_registered_group_ids
    ws = MagicMock()
    result = get_user_registered_group_ids(ws, "alice@ex.com", [])
    ws.users.list.assert_not_called()
    assert result == []


def test_returns_empty_on_scim_error():
    from data_classification_review_app.backend.core._scim import get_user_registered_group_ids
    ws = MagicMock()
    ws.users.list.side_effect = Exception("SCIM unavailable")
    result = get_user_registered_group_ids(ws, "alice@ex.com", ["g1"])
    assert result == []


def test_returns_empty_when_user_not_found_in_scim():
    from data_classification_review_app.backend.core._scim import get_user_registered_group_ids
    ws = MagicMock()
    ws.users.list.return_value = []
    result = get_user_registered_group_ids(ws, "ghost@ex.com", ["g1"])
    assert result == []


# ── search_principals ─────────────────────────────────────────────────────────

def test_search_users_returns_results_with_email_as_id():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("alice@ex.com", [])]
    ws.groups.list.return_value = []
    results = search_principals(ws, "alice", "user", existing_ids=set())
    assert len(results) == 1
    assert results[0].id == "alice@ex.com"
    assert results[0].kind == "user"
    assert results[0].name == "Alice Ex"


def test_search_filters_out_existing_ids():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("alice@ex.com", [])]
    ws.groups.list.return_value = []
    results = search_principals(ws, "alice", "user", existing_ids={"alice@ex.com"})
    assert results == []


def test_search_groups_returns_results_with_scim_id():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = []
    ws.groups.list.return_value = [_group("12345", "Finance Stewards", member_count=3)]
    results = search_principals(ws, "finance", "group", existing_ids=set())
    assert len(results) == 1
    assert results[0].id == "12345"
    assert results[0].kind == "group"
    assert results[0].members == 3


def test_search_all_returns_both_users_and_groups():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("bob@ex.com", [])]
    ws.groups.list.return_value = [_group("g99", "Bob's Group")]
    results = search_principals(ws, "bob", "all", existing_ids=set())
    kinds = {r.kind for r in results}
    assert kinds == {"user", "group"}


def test_search_escapes_single_quotes_in_query():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = []
    ws.groups.list.return_value = []
    search_principals(ws, "O'Brien", "user", existing_ids=set())
    call_kwargs = ws.users.list.call_args
    assert "O\\'Brien" in call_kwargs.kwargs.get("filter", "") or "O\\'Brien" in str(call_kwargs)


def test_search_filter_includes_emails_value():
    """A full email address must match via emails.value, not just displayName/userName."""
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = []
    ws.groups.list.return_value = []
    search_principals(ws, "xiao.zhu@example.com", "user", existing_ids=set())
    filter_arg = ws.users.list.call_args.kwargs.get("filter", "")
    assert "emails.value co 'xiao.zhu@example.com'" in filter_arg

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
    results = search_principals(ws, "alice", "user", existing_ids=set()).results
    assert len(results) == 1
    assert results[0].id == "alice@ex.com"
    assert results[0].kind == "user"
    assert results[0].name == "Alice Ex"


def test_search_filters_out_existing_ids():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("alice@ex.com", [])]
    ws.groups.list.return_value = []
    results = search_principals(ws, "alice", "user", existing_ids={"alice@ex.com"}).results
    assert results == []


def test_search_groups_returns_results_with_scim_id():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = []
    ws.groups.list.return_value = [_group("12345", "Finance Stewards", member_count=3)]
    results = search_principals(ws, "finance", "group", existing_ids=set()).results
    assert len(results) == 1
    assert results[0].id == "12345"
    assert results[0].kind == "group"
    assert results[0].members == 3


def test_search_all_returns_both_users_and_groups():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("bob@ex.com", [])]
    ws.groups.list.return_value = [_group("g99", "Bob's Group")]
    results = search_principals(ws, "bob", "all", existing_ids=set()).results
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


# ── search_principals: throttled / unsupported SCIM user search (issue #16) ──
# On large workspaces every Users list/substring filter can return 429 (GetAllUsers global rate
# limit) and only `userName eq` works; some workspaces also reject emails.value.

def _throttled():
    from databricks.sdk.errors import TooManyRequests
    return TooManyRequests("REQUEST_LIMIT_EXCEEDED: GetAllUsers ... global rate limit")


def test_search_reports_ok_statuses_on_success():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("bob@ex.com", [])]
    ws.groups.list.return_value = [_group("g99", "Bob's Group")]
    resp = search_principals(ws, "bob", "all", existing_ids=set())
    assert (resp.users_status, resp.groups_status) == ("ok", "ok")


def test_search_marks_unrequested_kind_as_skipped():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.groups.list.return_value = []
    resp = search_principals(ws, "fin", "group", existing_ids=set())
    assert resp.users_status == "skipped"
    ws.users.list.assert_not_called()


def test_throttled_user_search_falls_back_to_exact_username_lookup_for_emails():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    alice = _user("alice@ex.com", [])

    def users_list(filter, attributes):
        if filter == "userName eq 'alice@ex.com'":
            return [alice]
        raise _throttled()

    ws.users.list.side_effect = users_list
    resp = search_principals(ws, "alice@ex.com", "user", existing_ids=set())
    assert resp.users_status == "exact_only"
    assert [r.id for r in resp.results] == ["alice@ex.com"]


def test_throttled_user_search_without_email_returns_no_users_and_exact_only():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.side_effect = _throttled()
    ws.groups.list.return_value = []
    resp = search_principals(ws, "alice", "user", existing_ids=set())
    assert resp.users_status == "exact_only"
    assert resp.results == []
    # Only the substring attempt; no exact lookup for a non-email query.
    assert ws.users.list.call_count == 1


def test_sdk_retry_timeout_on_users_is_treated_as_throttled():
    """The SDK wraps a persistent 429 in TimeoutError once its retry budget runs out."""
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    alice = _user("alice@ex.com", [])

    def users_list(filter, attributes):
        if filter.startswith("userName eq"):
            return [alice]
        raise TimeoutError("Timed out after 0:00:01")

    ws.users.list.side_effect = users_list
    resp = search_principals(ws, "alice@ex.com", "user", existing_ids=set())
    assert resp.users_status == "exact_only"
    assert [r.id for r in resp.results] == ["alice@ex.com"]


def test_throttled_users_still_return_groups():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.side_effect = _throttled()
    ws.groups.list.return_value = [_group("g1", "Data Stewards", member_count=2)]
    resp = search_principals(ws, "data", "all", existing_ids=set())
    assert resp.users_status == "exact_only"
    assert resp.groups_status == "ok"
    assert [r.id for r in resp.results] == ["g1"]


def test_user_search_error_still_returns_groups():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.side_effect = RuntimeError("boom")
    ws.groups.list.return_value = [_group("g1", "Data Stewards")]
    resp = search_principals(ws, "data", "all", existing_ids=set())
    assert resp.users_status == "error"
    assert resp.groups_status == "ok"
    assert [r.id for r in resp.results] == ["g1"]


def test_group_search_error_still_returns_users():
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = [_user("bob@ex.com", [])]
    ws.groups.list.side_effect = RuntimeError("boom")
    resp = search_principals(ws, "bob", "all", existing_ids=set())
    assert (resp.users_status, resp.groups_status) == ("ok", "error")
    assert [r.id for r in resp.results] == ["bob@ex.com"]


def test_rejected_emails_value_filter_retries_without_it():
    from databricks.sdk.errors import BadRequest
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    bob = _user("bob@ex.com", [])

    def users_list(filter, attributes):
        if "emails.value" in filter:
            raise BadRequest("Attribute ...:emails.value is not supported.")
        return [bob]

    ws.users.list.side_effect = users_list
    resp = search_principals(ws, "bob", "user", existing_ids=set())
    assert resp.users_status == "ok"
    assert [r.id for r in resp.results] == ["bob@ex.com"]
    assert "emails.value" not in ws.users.list.call_args.kwargs["filter"]


# ── fail_fast_client ──────────────────────────────────────────────────────────

def test_fail_fast_client_keeps_credentials_and_shortens_retry_budget(monkeypatch):
    import databricks.sdk.config as sdk_config
    from databricks.sdk import WorkspaceClient
    from data_classification_review_app.backend.core._scim import fail_fast_client

    # Building the base client would fetch /.well-known/databricks-config from the fake host.
    def _no_metadata(host):
        raise RuntimeError("offline")

    monkeypatch.setattr(sdk_config, "get_host_metadata", _no_metadata)
    ws = WorkspaceClient(host="https://example.cloud.databricks.com", token="tok")
    fast = fail_fast_client(ws)
    assert fast.config.host == ws.config.host
    assert fast.config.token == ws.config.token
    assert fast.config.retry_timeout_seconds == 1
    # The original client keeps the SDK default.
    assert ws.config.retry_timeout_seconds != 1


# ── search route ──────────────────────────────────────────────────────────────

def _search_resp(users_status, groups_status):
    from data_classification_review_app.backend.models import PrincipalSearchResponse
    return PrincipalSearchResponse(results=[], users_status=users_status, groups_status=groups_status)


@pytest.mark.parametrize("users_status,groups_status", [
    ("exact_only", "skipped"), ("error", "ok"), ("ok", "error"), ("exact_only", "error"),
])
def test_search_route_returns_partial_results(monkeypatch, users_status, groups_status):
    from data_classification_review_app.backend.routes import stewards as mod
    from data_classification_review_app.backend.core import _scim
    monkeypatch.setattr(mod, "IS_MOCK", False)
    monkeypatch.setattr(mod, "db_query", lambda *a, **k: [])
    monkeypatch.setattr(_scim, "fail_fast_client", lambda ws: ws)
    monkeypatch.setattr(_scim, "search_principals",
                        lambda *a, **k: _search_resp(users_status, groups_status))
    resp = mod.search_stewards(q="da", kind="all", headers=None, ws=MagicMock())
    assert (resp.users_status, resp.groups_status) == (users_status, groups_status)


@pytest.mark.parametrize("users_status,groups_status", [
    ("error", "error"), ("error", "skipped"), ("skipped", "error"),
])
def test_search_route_502_when_every_requested_kind_failed(monkeypatch, users_status, groups_status):
    from fastapi import HTTPException
    from data_classification_review_app.backend.routes import stewards as mod
    from data_classification_review_app.backend.core import _scim
    monkeypatch.setattr(mod, "IS_MOCK", False)
    monkeypatch.setattr(mod, "db_query", lambda *a, **k: [])
    monkeypatch.setattr(_scim, "fail_fast_client", lambda ws: ws)
    monkeypatch.setattr(_scim, "search_principals",
                        lambda *a, **k: _search_resp(users_status, groups_status))
    with pytest.raises(HTTPException) as exc:
        mod.search_stewards(q="da", kind="all", headers=None, ws=MagicMock())
    assert exc.value.status_code == 502


def test_user_filter_uses_lowercase_or():
    """Databricks SCIM only honours lowercase `or`; with `OR` it evaluates just the first
    clause, so a full-email query matched nothing (issue #16)."""
    from data_classification_review_app.backend.core._scim import search_principals
    ws = MagicMock()
    ws.users.list.return_value = []
    search_principals(ws, "alice@ex.com", "user", existing_ids=set())
    filter_arg = ws.users.list.call_args.kwargs["filter"]
    assert " or " in filter_arg
    assert " OR " not in filter_arg

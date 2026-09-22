from __future__ import annotations
import pytest
from pydantic import SecretStr
from fastapi import HTTPException


def _headers(email="nonadmin@example.com"):
    from data_classification_review_app.backend.core._headers import DatabricksAppsHeaders
    return DatabricksAppsHeaders(
        host=None, user_name=None, user_id=None, user_email=email,
        request_id=None, token=SecretStr("tok"),
    )


def test_create_assignment_requires_admin(monkeypatch):
    """A non-admin must not be able to create steward assignments; the admin guard
    must run before any DB mutation."""
    from data_classification_review_app.backend.routes import stewards as mod
    from data_classification_review_app.backend.models import StewardAssignmentIn

    monkeypatch.setattr(mod, "IS_MOCK", False)
    # _assert_admin looks the caller up in the DB; return no admin row → non-admin.
    monkeypatch.setattr(mod, "db_query", lambda *a, **k: [])

    def _fail(*a, **k):
        raise AssertionError("DB mutation must not run for a non-admin caller")

    monkeypatch.setattr(mod, "execute_returning", _fail)

    body = StewardAssignmentIn(
        principal="someone", principal_kind="user", scope="catalog",
        catalog="main", schema_name=None, table_name=None,
    )
    with pytest.raises(HTTPException) as exc:
        mod.create_assignment(body, headers=_headers())
    assert exc.value.status_code == 403


def test_delete_assignment_requires_admin(monkeypatch):
    """A non-admin must not be able to delete steward assignments; the admin guard
    must run before any DB read/mutation."""
    from data_classification_review_app.backend.routes import stewards as mod

    monkeypatch.setattr(mod, "IS_MOCK", False)
    # Ensure the ADMIN_EMAILS short-circuit doesn't apply, so admin status is resolved
    # via the DB lookup below.
    monkeypatch.setenv("ADMIN_EMAILS", "")
    # _assert_admin looks the caller up in the DB; return no admin row → non-admin.
    monkeypatch.setattr(mod, "db_query", lambda *a, **k: [])

    def _fail(*a, **k):
        raise AssertionError("DELETE must not run for a non-admin caller")

    # The guard must raise before the route body reaches the DELETE.
    monkeypatch.setattr(mod, "execute", _fail)

    with pytest.raises(HTTPException) as exc:
        mod.delete_assignment("some-id", headers=_headers())
    assert exc.value.status_code == 403

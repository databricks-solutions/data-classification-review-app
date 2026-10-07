from __future__ import annotations
import pytest
from fastapi import HTTPException


def _boom(*a, **k):
    from data_classification_review_app.backend.db.read_model import SyncPendingError
    raise SyncPendingError("no table")


def test_get_proposals_returns_503_when_pending(monkeypatch):
    from data_classification_review_app.backend.routes import proposals as mod
    monkeypatch.setattr(mod.rm, "list_proposals", _boom)
    with pytest.raises(HTTPException) as exc:
        mod.get_proposals(page=1, page_size=50)
    assert exc.value.status_code == 503
    assert exc.value.detail == "classification_sync_pending"


def test_get_tables_returns_503_when_pending(monkeypatch):
    from data_classification_review_app.backend.routes import tables as tmod
    from data_classification_review_app.backend.routes import stewards as smod
    monkeypatch.setattr(smod, "get_assignments", lambda pid, ws=None: [])
    monkeypatch.setattr(tmod.rm, "table_summaries", _boom)
    with pytest.raises(HTTPException) as exc:
        tmod.get_tables(steward="x", search=None, ws=None)
    assert exc.value.status_code == 503

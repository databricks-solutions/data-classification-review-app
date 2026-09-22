from __future__ import annotations
from unittest.mock import MagicMock, patch


def _make_assignment(principal: str, scope: str, catalog: str, schema_name=None, table_name=None):
    return {
        "id": "uuid-1",
        "principal": principal,
        "principal_kind": "group" if not "@" in principal else "user",
        "scope": scope,
        "catalog": catalog,
        "schema_name": schema_name,
        "table_name": table_name,
    }


def test_get_effective_group_ids_returns_empty_without_ws():
    from data_classification_review_app.backend.routes.stewards import _get_effective_group_ids
    result = _get_effective_group_ids(user_email="alice@ex.com", ws=None, registered_group_ids=["g1"])
    assert result == []


def test_get_effective_group_ids_delegates_to_scim():
    from data_classification_review_app.backend.routes.stewards import _get_effective_group_ids
    with patch("data_classification_review_app.backend.routes.stewards.get_user_registered_group_ids") as mock_fn:
        mock_fn.return_value = ["g1"]
        ws = MagicMock()
        result = _get_effective_group_ids("alice@ex.com", ws=ws, registered_group_ids=["g1", "g2"])
        assert result == ["g1"]
        mock_fn.assert_called_once()

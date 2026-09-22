from __future__ import annotations


def test_build_assignment_key_catalog():
    from data_classification_review_app.backend.routes.stewards import _build_assignment_key
    assert _build_assignment_key("catalog", "main", None, None) == "assignment:catalog:main"


def test_build_assignment_key_schema():
    from data_classification_review_app.backend.routes.stewards import _build_assignment_key
    assert _build_assignment_key("schema", "main", "finance", None) == "assignment:schema:main.finance"


def test_build_assignment_key_table():
    from data_classification_review_app.backend.routes.stewards import _build_assignment_key
    assert _build_assignment_key("table", "main", "finance", "orders") == "assignment:table:main.finance.orders"

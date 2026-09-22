from __future__ import annotations


def test_column_detail_out_has_column_description_field():
    from data_classification_review_app.backend.models import ColumnDetailOut
    assert "column_description" in ColumnDetailOut.model_fields


def test_columns_response_has_metadata_fields():
    from data_classification_review_app.backend.models import ColumnsResponse
    fields = ColumnsResponse.model_fields
    for name in ("table_description", "table_tags", "metadata_denied",
                 "table_tags_denied", "column_tags_denied"):
        assert name in fields


def test_columns_response_defaults():
    from data_classification_review_app.backend.models import ColumnsResponse
    out = ColumnsResponse(columns=[])
    assert out.table_description is None
    assert out.table_tags == []
    assert out.metadata_denied is False
    assert out.table_tags_denied is False
    assert out.column_tags_denied is False

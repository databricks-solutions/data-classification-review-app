from __future__ import annotations


def test_table_samples_out_shape():
    from data_classification_review_app.backend.models import ColumnSamplesOut, TableSamplesOut

    out = TableSamplesOut(
        columns=[
            ColumnSamplesOut(column="national_id", samples=["123-45-6789"]),
            ColumnSamplesOut(column="status", samples=[]),
        ],
        denied=False,
    )
    assert out.denied is False
    assert out.columns[0].column == "national_id"
    assert out.columns[0].samples == ["123-45-6789"]
    assert out.columns[1].samples == []


def test_column_detail_out_has_no_samples_field():
    from data_classification_review_app.backend.models import ColumnDetailOut

    fields = ColumnDetailOut.model_fields
    assert "samples" not in fields


def test_columns_response_has_no_samples_denied_field():
    from data_classification_review_app.backend.models import ColumnsResponse

    fields = ColumnsResponse.model_fields
    assert "samples_denied" not in fields

from __future__ import annotations


def _row(table, column, tag, t, confidence="HIGH", frequency=1.0):
    return {
        "catalog_name": "corporate",
        "schema_name": "compliance",
        "table_name": table,
        "column_name": column,
        "data_type": "string",
        "class_tag": tag,
        "confidence": confidence,
        "frequency": frequency,
        "latest_detected_time": t,
    }


def test_dedupe_collapses_repeat_scans_of_same_column_tag():
    """Same (column, tag) detected across multiple scans collapses to one row."""
    from data_classification_review_app.backend.routes.proposals import _dedupe_latest
    rows = [
        _row("regulatory_filings", "document_url", "class.url", "2026-06-10 18:13:16.684737"),
        _row("regulatory_filings", "document_url", "class.url", "2026-06-26 08:35:27.122342"),
        _row("regulatory_filings", "document_url", "class.url", "2026-06-29 08:50:33.461705"),
    ]
    out = _dedupe_latest(rows)
    assert len(out) == 1
    # Keeps the most recent scan's row.
    assert out[0]["latest_detected_time"] == "2026-06-29 08:50:33.461705"


def test_dedupe_preserves_distinct_tags_on_same_column():
    """A column legitimately carrying two different tags keeps both."""
    from data_classification_review_app.backend.routes.proposals import _dedupe_latest
    rows = [
        _row("t", "email", "class.email_address", "2026-06-29 08:00:00"),
        _row("t", "email", "class.pii", "2026-06-29 08:00:00"),
    ]
    out = _dedupe_latest(rows)
    assert len(out) == 2
    assert {r["class_tag"] for r in out} == {"class.email_address", "class.pii"}


def test_dedupe_keeps_latest_confidence_and_frequency():
    """The retained row reflects the most recent scan's metadata."""
    from data_classification_review_app.backend.routes.proposals import _dedupe_latest
    rows = [
        _row("t", "c", "class.url", "2026-06-10 00:00:00", confidence="LOW", frequency=0.5),
        _row("t", "c", "class.url", "2026-06-29 00:00:00", confidence="HIGH", frequency=1.0),
    ]
    out = _dedupe_latest(rows)
    assert len(out) == 1
    assert out[0]["confidence"] == "HIGH"
    assert out[0]["frequency"] == 1.0


def test_dedupe_handles_missing_timestamp():
    """Rows with a real timestamp win over rows missing one; no crash on None."""
    from data_classification_review_app.backend.routes.proposals import _dedupe_latest
    rows = [
        _row("t", "c", "class.url", None),
        _row("t", "c", "class.url", "2026-06-29 00:00:00"),
    ]
    out = _dedupe_latest(rows)
    assert len(out) == 1
    assert out[0]["latest_detected_time"] == "2026-06-29 00:00:00"


def test_dedupe_distinguishes_columns_across_tables():
    """Same column name in different tables stays separate."""
    from data_classification_review_app.backend.routes.proposals import _dedupe_latest
    rows = [
        _row("table_a", "document_url", "class.url", "2026-06-29 00:00:00"),
        _row("table_b", "document_url", "class.url", "2026-06-29 00:00:00"),
    ]
    out = _dedupe_latest(rows)
    assert len(out) == 2

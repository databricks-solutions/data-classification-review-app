from __future__ import annotations


def _decision(column_key, class_tag, status):
    return {"column_key": column_key, "class_tag": class_tag, "status": status}


def test_verdict_applies_only_to_the_tag_it_was_recorded_against():
    """Rejecting one class on a multi-class column leaves the other undecided."""
    from data_classification_review_app.backend.routes.proposals import _decision_for
    index = {
        (d["column_key"], d["class_tag"]): d
        for d in [_decision("c.s.t.email", "class.name", "rejected")]
    }
    assert _decision_for(index, "c.s.t.email", "class.name")["status"] == "rejected"
    assert _decision_for(index, "c.s.t.email", "class.email_address") == {}


def test_decision_without_a_class_tag_covers_every_tag_on_the_column():
    """Rows written before decisions recorded class_tag stay in force."""
    from data_classification_review_app.backend.routes.proposals import _decision_for
    index = {
        (d["column_key"], d["class_tag"]): d
        for d in [_decision("c.s.t.email", None, "rejected")]
    }
    assert _decision_for(index, "c.s.t.email", "class.name")["status"] == "rejected"
    assert _decision_for(index, "c.s.t.email", "class.email_address")["status"] == "rejected"


def test_tagged_decision_wins_over_an_untagged_one_for_the_same_column():
    from data_classification_review_app.backend.routes.proposals import _decision_for
    index = {
        (d["column_key"], d["class_tag"]): d
        for d in [
            _decision("c.s.t.email", None, "rejected"),
            _decision("c.s.t.email", "class.email_address", "approved"),
        ]
    }
    assert _decision_for(index, "c.s.t.email", "class.email_address")["status"] == "approved"
    assert _decision_for(index, "c.s.t.email", "class.name")["status"] == "rejected"

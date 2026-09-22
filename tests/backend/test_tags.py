from __future__ import annotations


def test_tag_config_out_fields():
    from data_classification_review_app.backend.models import TagConfigOut
    t = TagConfigOut(key="class.name", enabled=True)
    assert t.key == "class.name"
    assert t.enabled is True


def test_tag_refresh_out_fields():
    from data_classification_review_app.backend.models import TagRefreshOut
    r = TagRefreshOut(added=3, added_enabled=2, added_disabled=1, total=15)
    assert r.added == 3
    assert r.added_enabled == 2
    assert r.added_disabled == 1
    assert r.total == 15


def test_tag_patch_in_defaults():
    from data_classification_review_app.backend.models import TagPatchIn
    p = TagPatchIn(enabled=False)
    assert p.enabled is False
    assert p.force is False


def test_tag_patch_out_fields():
    from data_classification_review_app.backend.models import TagPatchOut
    out = TagPatchOut(key="class.ssn", enabled=False, active_proposals=5)
    assert out.key == "class.ssn"
    assert out.active_proposals == 5


def test_is_system_tag_true():
    from data_classification_review_app.backend.routes.tags import _is_system_tag
    assert _is_system_tag("class.name") is True
    assert _is_system_tag("class.email_address") is True
    assert _is_system_tag("class.ssn") is True


def test_is_system_tag_false():
    from data_classification_review_app.backend.routes.tags import _is_system_tag
    assert _is_system_tag("custom.my_tag") is False
    assert _is_system_tag("finance.sensitive") is False
    assert _is_system_tag("pii_flag") is False

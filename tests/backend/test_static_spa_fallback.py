from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_app(tmp_path, monkeypatch):
    """Minimal FastAPI app wired up like the real one: SPA static mount + 404 fallback."""
    from data_classification_review_app.backend.core import _static as mod

    dist_dir = tmp_path / "__dist__"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html>spa shell</html>")

    monkeypatch.setattr(mod, "dist_dir", dist_dir)

    app = FastAPI()
    app.mount("/", mod.CachedStaticFiles(directory=dist_dir, html=True))
    mod.add_not_found_handler(app)
    return app


def test_table_key_route_with_dots_falls_back_to_spa_shell(tmp_path, monkeypatch):
    """Refreshing a deep link like /inbox/corporate.compliance.safety_incidents must
    serve the SPA shell, not a 404 — the table key's dots aren't a file extension."""
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)

    resp = client.get(
        "/inbox/corporate.compliance.safety_incidents",
        headers={"accept": "text/html"},
    )

    assert resp.status_code == 200
    assert "spa shell" in resp.text


def test_missing_real_asset_still_returns_404(tmp_path, monkeypatch):
    """A genuinely missing static asset (real extension) should still 404, not
    silently serve the SPA shell."""
    app = _make_app(tmp_path, monkeypatch)
    client = TestClient(app)

    resp = client.get(
        "/assets/does-not-exist.js",
        headers={"accept": "text/html"},
    )

    assert resp.status_code == 404

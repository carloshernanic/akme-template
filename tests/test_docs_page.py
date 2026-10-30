from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_index_has_tabs_and_loads_review_js():
    html = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    for needle in ('id="tab-ontologia"', 'id="tab-revisao"', 'id="view-revisao"', 'id="gate-banner"', 'src="review.js"', 'src="ontology.js"'):
        assert needle in html, needle
    js = (ROOT / "docs" / "review.js").read_text(encoding="utf-8")
    assert "window.AkmeReview" in js and "/api/review" in js and "/api/propose" in js and "akme-reviewer" in js


def test_review_js_shows_stage2_pendings_read_only():
    js = (ROOT / "docs" / "review.js").read_text(encoding="utf-8")
    assert "Outros (aprovar pelo chat)" in js and '"p-readonly"' in js and "STAGE1.has(t)" in js

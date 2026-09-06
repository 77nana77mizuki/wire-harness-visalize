"""``html`` レンダラ。"""

from datapattern.model import load_model
from datapattern.render.base import RenderContext
from datapattern.render.html_renderer import HtmlRenderer
from datapattern.render.pipeline import render_patterns


def _ctx(tmp_path):
    d = tmp_path / "html"
    d.mkdir()
    return RenderContext(out_dir=d)


def test_supports():
    r = HtmlRenderer()
    assert r.supports("option_config")
    assert r.supports("circuit")
    assert r.supports("property_set")
    assert not r.supports("unknown")


def test_option_config_fragment(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    p = model.pattern_by_id("opt-cfg-all-false")
    asset = HtmlRenderer().render(p, _ctx(tmp_path))
    frag = (tmp_path / "html" / asset.path).read_text("utf-8")
    assert asset.kind == "html"
    assert '<table class="grid">' in frag
    assert "OPT_GND=1" in frag
    assert "X1, W1" in frag


def test_property_set_fragment(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    p = model.pattern_by_id("prop-wire-csa-lower-bound")
    asset = HtmlRenderer().render(p, _ctx(tmp_path))
    frag = (tmp_path / "html" / asset.path).read_text("utf-8")
    assert "0.35" in frag
    assert "0.34" in frag
    assert "csa" in frag


def test_circuit_fragment(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    p = model.pattern_by_id("circuit-switched-ground")
    asset = HtmlRenderer().render(p, _ctx(tmp_path))
    frag = (tmp_path / "html" / asset.path).read_text("utf-8")
    assert "D1.GND" in frag
    assert "<td>BK</td>" in frag
    # ノードは id 昇順
    assert frag.index(">D1<") < frag.index(">S1<") < frag.index(">X1<")


def test_escapes_html(tmp_path):
    from datapattern.model import Pattern, VariantRow

    p = Pattern(
        id="x",
        type="option_config",
        title="t",
        summary="s",
        rationale="r",
        option_expression="a & b",
        variant_matrix=(VariantRow(expr="<script>alert(1)</script>", resolves_to=("A & B",)),),
    )
    asset = HtmlRenderer().render(p, _ctx(tmp_path))
    frag = (tmp_path / "html" / asset.path).read_text("utf-8")
    assert "<script>" not in frag
    assert "&lt;script&gt;" in frag
    assert "&amp;" in frag


def test_render_patterns_is_deterministic(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    a = render_patterns(model, HtmlRenderer(), tmp_path / "a")
    b = render_patterns(model, HtmlRenderer(), tmp_path / "b")
    for asset in a.assets:
        assert a.path_of(asset).read_bytes() == b.path_of(asset).read_bytes()
    assert (a.out_root / "index.json").read_text() == (b.out_root / "index.json").read_text()


def test_index_json_shape(tmp_path, fixtures_dir):
    import json

    model = load_model(fixtures_dir / "valid_full.json")
    m = render_patterns(model, HtmlRenderer(), tmp_path)
    index = json.loads((m.out_root / "index.json").read_text("utf-8"))
    records = index["entries"]["opt-cfg-all-false"]
    assert isinstance(records, list) and len(records) == 1
    entry = records[0]
    assert entry["asset_path"] == "opt-cfg-all-false.html"
    assert entry["kind"] == "html"
    assert entry["method"] == "html"
    assert entry["warnings"] == []

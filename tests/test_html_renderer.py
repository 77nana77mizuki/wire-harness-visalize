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
    assert "<code>OPT_GND</code>" in frag
    assert "OPT_GND=1" in frag
    assert "X1, W1" in frag
    assert 'id="fig-opt-cfg-all-false"' in frag


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
    from datapattern.model import Pattern

    p = Pattern(
        id="x",
        type="option_config",
        title="<script>",
        summary="s",
        rationale="r",
        option_expression="a & <b>",
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
        fa = (a.method_dir / asset.path).read_bytes()
        fb = (b.method_dir / asset.path).read_bytes()
        assert fa == fb
    assert (a.method_dir / "index.json").read_text() == (b.method_dir / "index.json").read_text()


def test_index_json_shape(tmp_path, fixtures_dir):
    import json

    model = load_model(fixtures_dir / "valid_full.json")
    m = render_patterns(model, HtmlRenderer(), tmp_path)
    index = json.loads((m.method_dir / "index.json").read_text("utf-8"))
    assert index["method"] == "html"
    entry = index["entries"]["opt-cfg-all-false"]
    assert entry["asset_path"] == "opt-cfg-all-false.html"
    assert entry["kind"] == "html"
    assert entry["method"] == "html"
    assert entry["warnings"] == []

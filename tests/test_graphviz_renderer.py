"""graphviz レンダラ。DOT 生成は常にテスト、SVG 化は dot があるときだけ。"""

import shutil

import pytest

from datapattern.model import load_model
from datapattern.render.base import RenderContext
from datapattern.render.graphviz_renderer import (
    GraphvizRenderer,
    _dot_circuit,
    _dot_option_config,
)

HAS_DOT = shutil.which("dot") is not None


def _patterns(fixtures_dir):
    return load_model(fixtures_dir / "valid_full.json")


def test_supports():
    r = GraphvizRenderer()
    assert r.supports("circuit")
    assert r.supports("option_config")
    assert not r.supports("property_set")


def test_dot_circuit_is_deterministic(fixtures_dir):
    p = _patterns(fixtures_dir).pattern_by_id("circuit-switched-ground")
    a = _dot_circuit(p)
    b = _dot_circuit(p)
    assert a == b
    assert '"D1" -> "S1"' in a
    assert '"S1" -> "X1"' in a  # via 経由で 2 ホップに分解
    assert "digraph G" in a
    assert r'label="D1\n(device)"' in a  # DOT 改行エスケープ（\\n に潰れていない）
    assert r"\\n" not in a


def test_dot_option_config(fixtures_dir):
    p = _patterns(fixtures_dir).pattern_by_id("opt-cfg-all-false")
    dot = _dot_option_config(p)
    assert '"root"' in dot
    assert "OPT_GND=1" in dot
    assert "OPT_GND" in dot


@pytest.mark.skipif(not HAS_DOT, reason="graphviz (dot) 未インストール")
def test_render_svg(tmp_path, fixtures_dir):
    d = tmp_path / "graphviz"
    d.mkdir()
    p = _patterns(fixtures_dir).pattern_by_id("circuit-switched-ground")
    asset = GraphvizRenderer().render(p, RenderContext(out_dir=d))
    svg = (d / asset.path).read_text("utf-8")
    assert svg.startswith("<svg")
    assert asset.kind == "svg"
    # 2 回実行して一致
    d2 = tmp_path / "g2"
    d2.mkdir()
    asset2 = GraphvizRenderer().render(p, RenderContext(out_dir=d2))
    assert (d2 / asset2.path).read_text("utf-8") == svg

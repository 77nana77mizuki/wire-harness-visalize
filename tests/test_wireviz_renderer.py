"""wireviz レンダラ。YAML 生成は常にテスト、SVG 化は wireviz があるときだけ。"""

import shutil

import pytest

from datapattern.model import load_model
from datapattern.render.base import RenderContext
from datapattern.render.wireviz_renderer import WirevizRenderer, wireviz_yaml

HAS_WIREVIZ = shutil.which("wireviz") is not None


def _pattern(fixtures_dir):
    return load_model(fixtures_dir / "valid_full.json").pattern_by_id("circuit-switched-ground")


def test_supports():
    assert WirevizRenderer().supports("circuit")
    assert not WirevizRenderer().supports("option_config")


def test_yaml_is_deterministic(fixtures_dir):
    p = _pattern(fixtures_dir)
    a = wireviz_yaml(p)
    b = wireviz_yaml(p)
    assert a == b


def test_yaml_structure(fixtures_dir):
    yml = wireviz_yaml(_pattern(fixtures_dir))
    assert yml.startswith("connectors:")
    assert "'D1':" in yml
    assert "'S1':" in yml
    assert "style: simple" in yml  # splice
    assert "connections:" in yml
    assert "gauge: '0.5'" in yml
    assert "colors: ['BK']" in yml


def test_pin_label_resolves_to_index(fixtures_dir):
    # D1 は pinlabels ["VCC","GND"] を持つので D1.GND → ピン 2
    yml = wireviz_yaml(_pattern(fixtures_dir))
    assert "'D1': 2" in yml


@pytest.mark.skipif(not HAS_WIREVIZ, reason="wireviz 未インストール")
def test_render_svg(tmp_path, fixtures_dir):
    d = tmp_path / "wireviz"
    d.mkdir()
    asset = WirevizRenderer().render(_pattern(fixtures_dir), RenderContext(out_dir=d))
    svg = (d / asset.path).read_text("utf-8")
    assert svg.lstrip().startswith("<svg")
    assert asset.kind == "svg"

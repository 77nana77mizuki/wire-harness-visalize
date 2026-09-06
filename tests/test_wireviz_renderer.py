"""wireviz レンダラ。YAML 生成は常にテスト、SVG 化は wireviz があるときだけ。"""

import shutil

import pytest

from datapattern.model import load_model
from datapattern.render.base import RenderContext
from datapattern.render.wireviz_renderer import WirevizRenderer, wireviz_yaml

HAS_WIREVIZ = shutil.which("wireviz") is not None
EXAMPLE = "examples"


def _pattern(name):
    from pathlib import Path

    root = Path(__file__).parents[1]
    return load_model(root / "examples" / "capital-drawing-patterns.json").pattern_by_id(name)


def test_supports():
    assert WirevizRenderer().supports("circuit")
    assert not WirevizRenderer().supports("option_config")


def test_yaml_is_deterministic():
    p = _pattern("splice-branch-one-to-three")
    assert wireviz_yaml(p) == wireviz_yaml(p)


def test_yaml_structure_splice():
    yml = wireviz_yaml(_pattern("splice-branch-one-to-three"))
    assert yml.startswith("connectors:")
    assert "'SP1':" in yml
    assert "style: simple" in yml  # splice
    assert "connections:" in yml
    assert "gauge: 1.0 mm2" in yml  # 数値 + 単位（クォートしない）
    assert "colors: [RD]" in yml  # 色コードはクォートしない


def test_multicore_is_one_multiwire_cable():
    yml = wireviz_yaml(_pattern("multicore-three-core"))
    assert "'MC1':" in yml
    assert "wirecount: 3" in yml
    assert "colors: [BK, BN, BU]" in yml
    assert "- 'M1': [1, 2, 3]" in yml


def test_pin_label_resolves_to_index():
    # ground-earth: D1 の pinlabels ["GND"] → D1.GND はピン 1（リスト形式）
    yml = wireviz_yaml(_pattern("shielded-pair-with-drain"))
    # SENS pinlabels ["SIG+","SIG-","SHLD"] → SENS.SIG+ = 1, SENS.SHLD = 3
    assert "'SENS': [1]" in yml or "'SENS': [3]" in yml


@pytest.mark.skipif(not HAS_WIREVIZ, reason="wireviz 未インストール")
@pytest.mark.parametrize(
    "pid",
    [
        "wiring-point-to-point",
        "splice-branch-one-to-three",
        "multicore-three-core",
        "shielded-pair-with-drain",
        "daisy-chain-lamps",
        "ground-earth-star-point",
        "overbraid-bundle-protection",
    ],
)
def test_render_svg(tmp_path, pid):
    d = tmp_path / "wireviz"
    d.mkdir()
    asset = WirevizRenderer().render(_pattern(pid), RenderContext(out_dir=d))
    svg = (d / asset.path).read_text("utf-8")
    assert svg.startswith("<svg")
    assert asset.kind == "svg"
    # 中間物は残っていない
    assert sorted(p.suffix for p in d.iterdir()) == [".svg", ".yml"]

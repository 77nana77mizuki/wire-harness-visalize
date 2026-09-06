"""mermaid レンダラ。疎結合の実証枠。"""

import shutil

import pytest

from datapattern.model import load_model
from datapattern.render.base import RenderContext
from datapattern.render.mermaid_renderer import (
    MermaidRenderer,
    _mermaid_circuit,
    _mermaid_option_config,
)
from datapattern.render.registry import load_registry

HAS_MMDC = shutil.which("mmdc") is not None


def _model(fixtures_dir):
    return load_model(fixtures_dir / "valid_full.json")


def test_registered_and_gated():
    reg = load_registry()
    entry = next(e for e in reg.entries if e.name == "mermaid")
    assert entry.requires == ("mmdc",)
    assert entry.available is HAS_MMDC


def test_circuit_source_deterministic(fixtures_dir):
    p = _model(fixtures_dir).pattern_by_id("circuit-switched-ground")
    a = _mermaid_circuit(p)
    assert a == _mermaid_circuit(p)
    assert a.startswith("flowchart LR")
    assert "n_D1" in a and "n_S1" in a


def test_option_config_source(fixtures_dir):
    p = _model(fixtures_dir).pattern_by_id("opt-cfg-all-false")
    s = _mermaid_option_config(p)
    assert s.startswith("flowchart TD")
    assert "OPT_GND=1" in s


@pytest.mark.skipif(not HAS_MMDC, reason="mermaid-cli (mmdc) 未インストール")
def test_render_svg(tmp_path, fixtures_dir):
    d = tmp_path / "mermaid"
    d.mkdir()
    p = _model(fixtures_dir).pattern_by_id("circuit-switched-ground")
    asset = MermaidRenderer().render(p, RenderContext(out_dir=d))
    assert (d / asset.path).read_text("utf-8").lstrip().startswith("<svg")

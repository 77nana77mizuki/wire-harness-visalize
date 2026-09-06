"""svg / drawio / schemdraw レンダラ。"""

import shutil
from pathlib import Path

import pytest

from datapattern.model import load_model
from datapattern.render.base import RenderContext
from datapattern.render.drawio_renderer import DrawioRenderer
from datapattern.render.svg_renderer import SvgRenderer

EXAMPLE = Path(__file__).parents[1] / "examples" / "capital-drawing-patterns.json"


def _pat(name):
    return load_model(EXAMPLE).pattern_by_id(name)


def _ctx(tmp_path, sub):
    d = tmp_path / sub
    d.mkdir()
    return RenderContext(out_dir=d), d


# --- svg（ゼロ依存） ---


def test_svg_supports():
    r = SvgRenderer()
    assert r.supports("circuit") and r.supports("option_config")
    assert not r.supports("property_set")


def test_svg_circuit_deterministic(tmp_path):
    r = SvgRenderer()
    ctx, d = _ctx(tmp_path, "a")
    a = (d / r.render(_pat("multicore-three-core"), ctx).path).read_bytes()
    ctx2, d2 = _ctx(tmp_path, "b")
    b = (d2 / r.render(_pat("multicore-three-core"), ctx2).path).read_bytes()
    assert a == b
    assert a.startswith(b"<svg")
    assert b"MC1" in a


def test_svg_option_config(tmp_path):
    ctx, d = _ctx(tmp_path, "o")
    asset = SvgRenderer().render(_pat("opt-variant-steering-side"), ctx)
    svg = (d / asset.path).read_text("utf-8")
    assert "W_STEER_L" in svg
    assert asset.kind == "svg"


# --- drawio（編集可能 XML） ---


def test_drawio_kind_and_content(tmp_path):
    ctx, d = _ctx(tmp_path, "dr")
    asset = DrawioRenderer().render(_pat("splice-branch-one-to-three"), ctx)
    assert asset.kind == "xml"
    assert asset.path.suffix == ".drawio"
    xml = (d / asset.path).read_text("utf-8")
    assert xml.startswith("<mxfile")
    assert '<mxCell id="0"/>' in xml
    assert 'vertex="1"' in xml and 'edge="1"' in xml
    assert "n_SP1" in xml


def test_drawio_deterministic(tmp_path):
    ctx, d = _ctx(tmp_path, "a")
    a = (d / DrawioRenderer().render(_pat("multicore-three-core"), ctx).path).read_bytes()
    ctx2, d2 = _ctx(tmp_path, "b")
    b = (d2 / DrawioRenderer().render(_pat("multicore-three-core"), ctx2).path).read_bytes()
    assert a == b


# --- schemdraw（要 import できるとき） ---

_HAS_SCHEMDRAW = shutil.which("python") is not None
try:
    import schemdraw  # noqa: F401

    _HAS_SCHEMDRAW = True
except ImportError:
    _HAS_SCHEMDRAW = False


@pytest.mark.skipif(not _HAS_SCHEMDRAW, reason="schemdraw 未インストール")
def test_schemdraw_circuit(tmp_path):
    from datapattern.render.schemdraw_renderer import SchemdrawRenderer

    r = SchemdrawRenderer()
    assert r.supports("circuit") and not r.supports("option_config")
    ctx, d = _ctx(tmp_path, "s")
    asset = r.render(_pat("ground-earth-star-point"), ctx)
    svg = (d / asset.path).read_text("utf-8")
    assert svg.lstrip().startswith("<svg")
    assert "<metadata>" not in svg  # 日時メタは除去済み
    # 2 回で一致
    ctx2, d2 = _ctx(tmp_path, "s2")
    assert (d2 / r.render(_pat("ground-earth-star-point"), ctx2).path).read_text("utf-8") == svg

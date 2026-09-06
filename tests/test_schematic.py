"""_schematic.build_scene — 記号分類とリンク種別。"""

import base64
import zlib
from pathlib import Path

from datapattern.model import load_model
from datapattern.render._schematic import build_scene
from datapattern.report import _drawio_open_url

EXAMPLE = Path(__file__).parents[1] / "examples" / "capital-drawing-patterns.json"


def _scene(name):
    return build_scene(load_model(EXAMPLE).pattern_by_id(name))


def test_ground_and_splice_symbols():
    s = _scene("ground-earth-star-point")
    syms = {n.id: n.symbol for n in s.nodes}
    assert syms["GSP"] == "splice"
    assert syms["G100"] == "ground"
    assert syms["D1"] == "connector"


def test_multicore_is_one_link_with_conductors():
    s = _scene("multicore-three-core")
    assert len(s.links) == 1
    lk = s.links[0]
    assert lk.kind == "multicore"
    assert lk.conductors == 3
    assert lk.colors == ("BK", "BN", "BU")


def test_shield_and_overbraid_and_fuse():
    assert any(lk.kind == "shield" for lk in _scene("shielded-pair-with-drain").links)
    assert any(lk.kind == "overbraid" for lk in _scene("overbraid-bundle-protection").links)
    fuse = {n.id: n.symbol for n in _scene("power-distribution-fused-feed").nodes}
    assert fuse["F12"] == "fuse"
    assert fuse["BATT"] == "supply"


def test_deterministic():
    a = _scene("splice-branch-one-to-three")
    b = _scene("splice-branch-one-to-three")
    assert [(n.id, n.x, n.y) for n in a.nodes] == [(n.id, n.x, n.y) for n in b.nodes]
    assert [(lk.a, lk.b, lk.kind) for lk in a.links] == [(lk.a, lk.b, lk.kind) for lk in b.links]


def test_drawio_open_url_round_trips():
    xml = "<mxfile><diagram>hello</diagram></mxfile>"
    url = _drawio_open_url(xml)
    assert url.startswith("https://app.diagrams.net/#R")
    import urllib.parse

    packed = base64.b64decode(urllib.parse.unquote(url.split("#R", 1)[1]))
    assert zlib.decompress(packed, -15).decode("utf-8") == xml

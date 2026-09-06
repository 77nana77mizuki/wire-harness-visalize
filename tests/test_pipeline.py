"""render_all / registry.all_supporting — 複数方式まとめ描画。"""

import json

from datapattern.model import load_model
from datapattern.render.html_renderer import HtmlRenderer
from datapattern.render.pipeline import render_all
from datapattern.render.registry import Registry, RendererEntry


class _AltHtml(HtmlRenderer):
    name = "alt"


class _FakeRegistry(Registry):
    """html と alt の 2 レンダラを持つ人工レジストリ（動的 import を通さない）。"""

    def __init__(self) -> None:
        super().__init__(
            [
                RendererEntry("html", "x:x", (), True, ()),
                RendererEntry("alt", "x:x", (), True, ()),
            ]
        )
        self._instances = {"html": HtmlRenderer(), "alt": _AltHtml()}

    def _load(self, name):  # type: ignore[override]
        return self._instances.get(name)


def test_all_supporting_returns_every_available():
    reg = _FakeRegistry()
    assert [r.name for r in reg.all_supporting("option_config")] == ["html", "alt"]
    assert reg.all_supporting("no-such-type") == []


def test_render_all_produces_multiple_assets_per_pattern(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    manifest = render_all(model, _FakeRegistry(), tmp_path)
    for p in model.patterns:
        assert {a.method for a in manifest.assets_for(p.id)} == {"html", "alt"}
    index = json.loads((tmp_path / "index.json").read_text("utf-8"))
    assert len(index["entries"]["opt-cfg-all-false"]) == 2
    assert manifest.methods() == ["html", "alt"]


def test_render_all_is_deterministic(tmp_path, fixtures_dir):
    model = load_model(fixtures_dir / "valid_full.json")
    a = render_all(model, _FakeRegistry(), tmp_path / "a")
    b = render_all(model, _FakeRegistry(), tmp_path / "b")
    assert (a.out_root / "index.json").read_text() == (b.out_root / "index.json").read_text()

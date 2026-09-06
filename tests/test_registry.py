"""render/registry.py — レンダラの発見・選択・フォールバック。"""

from datapattern.render.registry import load_registry

_TOML = """
[[renderer]]
name = "html"
module = "datapattern.render.html_renderer:HtmlRenderer"
requires = []

[[renderer]]
name = "needs_missing_tool"
module = "datapattern.render.graphviz_renderer:GraphvizRenderer"
requires = ["definitely-not-a-real-binary-xyz"]
"""


def test_bundled_registry_loads():
    reg = load_registry()
    names = {e.name for e in reg.entries}
    assert {"html", "graphviz", "wireviz"} <= names
    html = next(e for e in reg.entries if e.name == "html")
    assert html.available is True
    assert html.requires == ()


def test_missing_tool_marks_unavailable():
    reg = load_registry(_TOML)
    entry = next(e for e in reg.entries if e.name == "needs_missing_tool")
    assert entry.available is False
    assert entry.missing == ("definitely-not-a-real-binary-xyz",)
    assert reg.get("needs_missing_tool") is None


def test_select_falls_back_to_html():
    reg = load_registry(_TOML)
    # preferred が全滅でも html が拾える
    r = reg.select("option_config", preferred=("needs_missing_tool", "nonexistent"))
    assert r is not None
    assert r.name == "html"


def test_select_prefers_available_preferred():
    reg = load_registry(_TOML)
    r = reg.select("option_config", preferred=("html",))
    assert r.name == "html"


def test_select_returns_none_when_nothing_supports():
    reg = load_registry(_TOML)
    assert reg.select("no-such-type") is None


def test_bundled_select_circuit_available_only():
    reg = load_registry()
    r = reg.select("circuit", preferred=("wireviz", "graphviz"))
    # wireviz / graphviz は環境次第。少なくとも何かは返る（html まで落ちる）
    assert r is not None
    assert r.supports("circuit")

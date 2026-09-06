"""``svg`` レンダラ — 外部ツールなしで決定論的に SVG を組む（ゼロ依存）。

circuit は Capital Logic 風の記号（アース / スプライス / コネクタ / マルチコア束 /
シールド）で描く。共有シーンは ``_schematic.py``。option_config は簡易な決定木。
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render._schematic import Scene, SNode, build_scene
from datapattern.render.base import Asset, RenderContext, Renderer

_PAD = 20
_IEC = {
    "BK": "#1b1b1b",
    "BN": "#6b4423",
    "RD": "#d62828",
    "OG": "#e8791a",
    "YE": "#e0b400",
    "GN": "#1a9e3a",
    "BU": "#1a5fd2",
    "VT": "#7a3aa8",
    "GY": "#8a8a8a",
    "WH": "#cfcfcf",
    "PK": "#e07a9c",
    "BG": "#c9b48a",
    "GNYE": "#1a9e3a",
    "SL": "#9aa0a6",
    "TQ": "#1aa5a5",
}


def _wire_color(colors: tuple[str, ...]) -> str:
    return _IEC.get(colors[0].upper(), "#666") if colors else "#666"


def _line(x1: float, y1: float, x2: float, y2: float, cls: str = "sym", extra: str = "") -> str:
    return f'<line class="{cls}" x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" {extra}/>'


def _txt(
    x: float, y: float, s: str, *, anchor: str = "middle", size: int = 10, cls: str = "t"
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-size="{size}" class="{cls}">{escape(s)}</text>'
    )


def _svg(w: float, h: float, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}" font-family="Helvetica, Arial, sans-serif">'
        "<style>"
        ".box{fill:#fbfbfb;stroke:#444;stroke-width:1.2}"
        ".dev{fill:#eef4fb;stroke:#3a6ea5;stroke-width:1.2}"
        ".pin{stroke:#444;stroke-width:1}"
        ".sym{fill:none;stroke:#222;stroke-width:1.4}"
        ".splice{fill:#222}"
        ".t{fill:#222}.lbl{fill:#555}"
        "</style>"
        f"{body}</svg>"
    )


# --- ノード記号 -------------------------------------------------------------- #

_NW, _NH = 130, 46


def _anchor(n: SNode) -> tuple[float, float]:
    if n.symbol in {"connector", "device", "fuse", "supply"}:
        return n.x + _NW / 2, n.y + _NH
    if n.symbol == "ground":
        return n.x, n.y  # 接続点は上端
    return n.x, n.y  # splice: 中心


def _node_svg(n: SNode) -> str:
    p: list[str] = []
    if n.symbol in {"connector", "device", "fuse"}:
        cls = "dev" if n.symbol == "device" else "box"
        rx = 6 if n.symbol == "device" else 2
        p.append(
            f'<rect class="{cls}" x="{n.x:.0f}" y="{n.y:.0f}" '
            f'width="{_NW}" height="{_NH}" rx="{rx}"/>'
        )
        p.append(_txt(n.x + _NW / 2, n.y + _NH / 2 + 4, n.id, size=11))
        if n.symbol == "fuse":
            p.append(_line(n.x + 12, n.y + _NH - 8, n.x + _NW - 12, n.y + 8))
        n_pins = len(n.pins)
        for i, pl in enumerate(n.pins[:8]):
            px = n.x + 14 + i * ((_NW - 28) / max(n_pins - 1, 1) if n_pins > 1 else 0)
            p.append(_line(px, n.y + _NH, px, n.y + _NH + 7, cls="pin"))
            p.append(_txt(px, n.y + _NH + 17, pl, size=7, cls="lbl"))
    elif n.symbol == "supply":
        cx, cy = n.x + _NW / 2, n.y + _NH / 2
        p.append(f'<circle class="box" cx="{cx:.0f}" cy="{cy:.0f}" r="18"/>')
        p.append(_txt(cx, cy - 2, "+", size=13))
        p.append(_txt(cx, cy + 14, n.id, size=8, cls="lbl"))
        p.append(_line(cx, cy + 18, cx, n.y + _NH, cls="pin"))
    elif n.symbol == "splice":
        p.append(f'<circle class="splice" cx="{n.x:.0f}" cy="{n.y:.0f}" r="5"/>')
        p.append(_txt(n.x + 9, n.y + 3, n.id, anchor="start", size=8, cls="lbl"))
    elif n.symbol == "ground":
        x, y = n.x, n.y
        p.append(_line(x, y, x, y + 14))
        for i, half in enumerate((11, 7, 3)):
            yy = y + 14 + i * 5
            p.append(_line(x - half, yy, x + half, yy))
        p.append(_txt(x, y + 42, n.id, size=8, cls="lbl"))
    return "".join(p)


# --- リンク ---------------------------------------------------------------- #


def _link_svg(scene: Scene, link, idx: int) -> str:
    a, b = scene.node(link.a), scene.node(link.b)
    if a is None or b is None:
        return ""
    ax, ay = _anchor(a)
    bx, by = _anchor(b)
    mx, my = (ax + bx) / 2, max(ay, by) + 46 + (idx % 4) * 8
    color = _wire_color(link.colors)
    p: list[str] = []

    def curve(off: float, stroke: str, extra: str = "") -> str:
        return (
            f'<path d="M{ax + off:.1f},{ay:.1f} C{ax + off:.1f},{my:.1f} '
            f'{bx + off:.1f},{my:.1f} {bx + off:.1f},{by:.1f}" '
            f'fill="none" stroke="{stroke}" stroke-width="1.6" {extra}/>'
        )

    if link.kind == "multicore":
        for k in range(min(link.conductors, 5)):
            off = (k - (min(link.conductors, 5) - 1) / 2) * 3
            c = _IEC.get(link.colors[k].upper(), "#666") if k < len(link.colors) else "#666"
            p.append(curve(off, c))
        p.append(
            f'<ellipse cx="{mx:.0f}" cy="{my:.0f}" rx="16" ry="9" '
            f'fill="none" stroke="#555" stroke-dasharray="1 2"/>'
        )
    elif link.kind == "shield":
        p.append(curve(0, color))
        p.append(curve(-6, "#888", 'stroke-dasharray="4 2"'))
        p.append(_txt(mx, my - 12, "shield", size=8, cls="lbl"))
    elif link.kind == "overbraid":
        p.append(curve(0, color))
        p.append(curve(-5, "#999", 'stroke-dasharray="2 2"'))
        p.append(curve(5, "#999", 'stroke-dasharray="2 2"'))
    else:
        p.append(curve(0, color))

    lbl = link.label or (link.gauge or "")
    if link.colors and link.kind != "multicore":
        lbl = f"{link.gauge or ''} {link.colors[0]}".strip()
    if lbl:
        p.append(_txt(mx, my + 4, lbl, size=8, cls="lbl"))
    return "".join(p)


def _circuit(pattern: Pattern) -> str:
    scene = build_scene(pattern)
    body = "".join(_link_svg(scene, lk, i) for i, lk in enumerate(scene.links))
    body += "".join(_node_svg(n) for n in scene.nodes)
    return _svg(scene.width, scene.height + 30, body)


# --- option_config（決定木） ---------------------------------------------- #


def _option_config(pattern: Pattern) -> str:
    rows = pattern.variant_matrix
    root = pattern.option_expression or "option expression"
    row_h, width, left_w, gap = 34, 640, 200, 60
    cy0 = _PAD + 20
    height = _PAD * 2 + 40 + max(len(rows), 1) * row_h
    parts = [
        f'<rect class="box" x="{_PAD}" y="{cy0}" width="{left_w}" height="{row_h}" rx="4"/>',
        _txt(_PAD + left_w / 2, cy0 + row_h / 2 + 4, root, size=10),
    ]
    for i, r in enumerate(rows):
        y = cy0 + 60 + i * row_h
        rx = _PAD + left_w + gap
        rw = width - rx - _PAD
        parts.append(
            f'<rect class="box" x="{rx:.0f}" y="{y:.0f}" '
            f'width="{rw:.0f}" height="{row_h - 6}" rx="4"/>'
        )
        resolved = ", ".join(r.resolves_to) if r.resolves_to else "（空）"
        parts.append(_txt(rx + rw / 2, y + row_h / 2, resolved, size=9))
        parts.append(
            f'<path d="M{_PAD + left_w},{cy0 + row_h / 2} '
            f"C{_PAD + left_w + gap / 2:.0f},{cy0 + row_h / 2} "
            f'{rx - gap / 2:.0f},{y + row_h / 2:.0f} {rx:.0f},{y + row_h / 2:.0f}" '
            f'fill="none" stroke="#777"/>'
        )
        parts.append(_txt((_PAD + left_w + rx) / 2, y + row_h / 2 - 6, r.expr, size=8, cls="lbl"))
    return _svg(width, height + 30, "".join(parts))


_BUILDERS = {"circuit": _circuit, "option_config": _option_config}


class SvgRenderer(Renderer):
    name: ClassVar[str] = "svg"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset(_BUILDERS)

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        svg = _BUILDERS[pattern.type](pattern)
        rel = Path(f"{pattern.id}.svg")
        (ctx.out_dir / rel).write_text(svg + "\n", encoding="utf-8")
        return Asset(
            pattern_id=pattern.id,
            method=self.name,
            path=rel,
            kind="svg",
            title=pattern.title,
            caption=pattern.summary,
        )

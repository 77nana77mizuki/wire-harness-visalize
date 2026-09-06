"""``svg`` レンダラ — 外部ツール無しで、配線設計に耐える体裁の SVG を組む（決定論）。

方針: 回路は左 → 右に流す。プロパティ値（CSA/色コード/長さ/部品番号…）は図に書かず、
レポートの表に任せる。共有シーンは ``_schematic.py``。option_config は簡潔な決定表。
"""

from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render._schematic import Scene, SLink, SNode, SPin, build_scene
from datapattern.render.base import Asset, RenderContext, Renderer

# IEC 60757 → 落ち着いた実寸色
_IEC = {
    "BK": "#3a3f4a",
    "BN": "#7a5230",
    "RD": "#c0392b",
    "OG": "#d9822b",
    "YE": "#c9a227",
    "GN": "#2e8b57",
    "BU": "#2f6fb3",
    "VT": "#7d5ba6",
    "GY": "#8b929c",
    "WH": "#aeb4bf",
    "PK": "#c97b98",
    "BG": "#c4ad86",
    "GNYE": "#2e8b57",
    "SL": "#9aa0a6",
    "TQ": "#2aa5a0",
}
_STUB = 14
_WIRE_FALLBACK = "#4c7bd0"

_STYLE = (
    "<style>"
    "text{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}"
    ".nm{font-weight:600;fill:#0a4b3c}"
    ".sub{fill:#3f7d6c}"
    ".pin{fill:#9198a3}"
    ".conn{fill:#e6f6f0;stroke:#159e79;stroke-width:1}"
    ".dev{fill:#eef3fb;stroke:#5b82b8;stroke-width:1}"
    ".nub{fill:#e6f6f0;stroke:#159e79;stroke-width:1}"
    ".pindot{fill:#e6f6f0;stroke:#159e79;stroke-width:1}"
    ".wire{fill:none;stroke-width:2;stroke-linecap:round}"
    ".sym{fill:none;stroke:#3a3f4a;stroke-width:1.6}"
    ".splice{fill:#fbeee8;stroke:#b4693f;stroke-width:1;stroke-dasharray:3 2}"
    ".splicetx{fill:#8a4a2a;font-weight:600}"
    ".enc{fill:none;stroke:#a7abb2;stroke-width:1;stroke-dasharray:4 3}"
    ".frame{fill:none;stroke:#d3d7de;stroke-width:1}"
    ".tblk{fill:#fbfcfe;stroke:#d3d7de;stroke-width:1}"
    "</style>"
)


def _c(colors: tuple[str, ...], i: int = 0) -> str:
    if i < len(colors):
        return _IEC.get(colors[i].upper(), _WIRE_FALLBACK)
    return _WIRE_FALLBACK


def _t(x: float, y: float, s: str, *, a: str = "middle", size: float = 10, cls: str = "nm") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{a}" '
        f'font-size="{size}" class="{cls}">{escape(s)}</text>'
    )


def _grid(w: float, h: float) -> str:
    return (
        '<defs><pattern id="g" width="18" height="18" patternUnits="userSpaceOnUse">'
        '<circle cx="1" cy="1" r="0.6" fill="#e9ecf1"/></pattern></defs>'
        f'<rect width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>'
        f'<rect x="6" y="6" width="{w - 12:.0f}" height="{h - 12:.0f}" fill="url(#g)"/>'
        f'<rect class="frame" x="6" y="6" width="{w - 12:.0f}" height="{h - 12:.0f}"/>'
    )


def _titleblock(w: float, h: float, title: str) -> str:
    tw, th = 200, 26
    x, y = w - 6 - tw, h - 6 - th
    return f'<rect class="tblk" x="{x:.0f}" y="{y:.0f}" width="{tw}" height="{th}"/>' + _t(
        x + tw / 2, y + th / 2 + 3.5, title, size=9, cls="pin"
    )


def _frame(w: float, h: float, body: str, title: str = "") -> str:
    tb = _titleblock(w, h, title) if title else ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}">{_STYLE}{_grid(w, h)}{body}{tb}</svg>'
    )


# --- 記号 ----------------------------------------------------------------- #


def _ground_sym(x: float, y: float) -> str:
    p = [f'<line class="sym" x1="{x:.1f}" y1="{y:.1f}" x2="{x:.1f}" y2="{y + 12:.1f}"/>']
    for i, half in enumerate((9, 6, 3)):
        yy = y + 12 + i * 4.5
        p.append(
            f'<line class="sym" x1="{x - half:.1f}" y1="{yy:.1f}" x2="{x + half:.1f}" y2="{yy:.1f}"/>'
        )
    return "".join(p)


def _node_svg(n: SNode) -> str:
    if n.symbol == "splice":
        s = 42
        x, y = n.cx - s / 2, n.cy - s / 2
        return (
            f'<rect class="splice" x="{x:.1f}" y="{y:.1f}" width="{s}" height="{s}" rx="9"/>'
            + _t(n.cx, n.cy + 4, n.id, size=12, cls="splicetx")
        )
    if n.symbol == "ground":
        px, py = n.pins["*"].x, n.pins["*"].y
        return _ground_sym(px, py) + _t(px, py + 38, n.id, size=8, cls="pin")
    if n.symbol == "supply":
        r = n.w / 2
        return (
            f'<circle class="conn" cx="{n.cx:.1f}" cy="{n.cy:.1f}" r="{r:.1f}"/>'
            + _t(n.cx, n.cy + 1, "＋", size=13, cls="nm")
            + _t(n.cx, n.cy + r + 12, n.id, size=8, cls="pin")
        )

    cls = "dev" if n.symbol == "device" else "conn"
    p: list[str] = []
    # 上部のタブ
    p.append(
        f'<rect class="nub" x="{n.cx - 11:.1f}" y="{n.y - 7:.1f}" width="22" height="9" rx="2"/>'
    )
    p.append(
        f'<rect class="{cls}" x="{n.x:.1f}" y="{n.y:.1f}" width="{n.w:.1f}" height="{n.h:.1f}" rx="12"/>'
    )
    if n.symbol == "fuse":
        my = n.y + n.h / 2
        p.append(
            f'<line class="sym" x1="{n.x + 12:.1f}" y1="{my:.1f}" x2="{n.x + n.w - 12:.1f}" y2="{my:.1f}"/>'
        )
        p.append(_t(n.cx, n.y - 6, n.id, size=11, cls="nm"))
    else:
        ty = n.y + 22 if n.sub else n.y + n.h / 2 + 4
        p.append(_t(n.cx, ty, n.id, size=12, cls="nm"))
        if n.sub:
            p.append(_t(n.cx, ty + 15, n.sub, size=9, cls="sub"))
    # 接続ピンを丸で
    for name, pin in sorted(n.pins.items(), key=lambda kv: (kv[1].side, kv[1].y)):
        if pin.side == "C":
            continue
        p.append(f'<circle class="pindot" cx="{pin.x:.1f}" cy="{pin.y:.1f}" r="3.4"/>')
        auto = len(name) >= 2 and name[0] in "LR" and name[1:].isdigit()
        if name and not auto and n.symbol != "fuse":
            lx = pin.x + (-8 if pin.side == "R" else 8)
            p.append(
                _t(lx, pin.y + 3, name, a="end" if pin.side == "R" else "start", size=7, cls="pin")
            )
    return "".join(p)


# --- ベジェ配線（左 → 右の流れ） ---------------------------------------- #


def _pin_of(node: SNode, name: str) -> SPin:
    return node.pins.get(name) or next(iter(node.pins.values()))


def _bez(ax: float, ay: float, bx: float, by: float, mx: float | None = None) -> str:
    mx = mx if mx is not None else (ax + bx) / 2
    return f"M{ax:.1f},{ay:.1f} C{mx:.1f},{ay:.1f} {mx:.1f},{by:.1f} {bx:.1f},{by:.1f}"


def _links_svg(scene: Scene) -> str:
    by_channel: dict[float, list[SLink]] = defaultdict(list)
    for lk in scene.links:
        na, nb = scene.node(lk.a), scene.node(lk.b)
        if na is None or nb is None:
            continue
        left = na if na.col <= nb.col else nb
        by_channel[left.x + left.w].append(lk)

    out: list[str] = []
    for base_x, lks in sorted(by_channel.items()):
        lane = sorted(lks, key=lambda lk: scene.node(lk.a).cy + scene.node(lk.b).cy)
        for j, lk in enumerate(lane):
            na, nb = scene.node(lk.a), scene.node(lk.b)
            a_node, b_node = (na, nb) if na.col <= nb.col else (nb, na)
            a_pin = lk.a_pin if a_node is na else lk.b_pin
            b_pin = lk.b_pin if a_node is na else lk.a_pin
            pa, pb = _pin_of(a_node, a_pin), _pin_of(b_node, b_pin)
            mx = base_x + 44 + (j - (len(lane) - 1) / 2) * 10
            out.append(_link_svg(lk, pa, pb, mx))
    return "".join(out)


def _link_svg(lk: SLink, pa: SPin, pb: SPin, mx: float) -> str:
    ax = pa.x + (_STUB if pa.side == "R" else -_STUB if pa.side == "L" else 0)
    bx = pb.x + (-_STUB if pb.side == "L" else _STUB if pb.side == "R" else 0)
    ay, by = pa.y, pb.y
    parts = [
        f'<line class="wire" x1="{pa.x:.1f}" y1="{ay:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" stroke="{_c(lk.colors)}"/>',
        f'<line class="wire" x1="{pb.x:.1f}" y1="{by:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{_c(lk.colors)}"/>',
    ]

    if lk.kind in {"multicore", "shield"}:
        n = min(lk.conductors, 6)
        for k in range(n):
            off = (k - (n - 1) / 2) * 3
            parts.append(
                f'<path class="wire" d="{_bez(ax, ay + off, bx, by + off, mx + off)}" '
                f'stroke="{_c(lk.colors, k)}" stroke-width="1.5"/>'
            )
        if lk.kind == "multicore":
            my = (ay + by) / 2
            parts.append(
                f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="9" fill="#fff" stroke="#8b929c"/>'
            )
            parts.append(_t(mx, my + 3, f"{lk.conductors}", size=8, cls="pin"))
        else:
            pad = (n - 1) / 2 * 3 + 5
            parts.append(f'<path class="enc" d="{_bez(ax, ay - pad, bx, by - pad, mx - pad)}"/>')
            parts.append(f'<path class="enc" d="{_bez(ax, ay + pad, bx, by + pad, mx + pad)}"/>')
    elif lk.kind == "overbraid":
        parts.append(
            f'<path class="wire" d="{_bez(ax, ay, bx, by, mx)}" stroke="{_c(lk.colors)}" stroke-width="4" stroke-opacity="0.3"/>'
        )
        parts.append(
            f'<path class="wire" d="{_bez(ax, ay, bx, by, mx)}" stroke="{_c(lk.colors)}"/>'
        )
    else:
        parts.append(
            f'<path class="wire" d="{_bez(ax, ay, bx, by, mx)}" stroke="{_c(lk.colors)}"/>'
        )
    return "".join(parts)


def _circuit(pattern: Pattern) -> str:
    scene = build_scene(pattern)
    body = _links_svg(scene) + "".join(_node_svg(n) for n in scene.nodes)
    return _frame(scene.width, scene.height, body, title=pattern.id)


# --- option_config（決定表） --------------------------------------------- #


def _option_config(pattern: Pattern) -> str:
    rows = pattern.variant_matrix
    root = pattern.option_expression or "option expression"
    rh, w, lw, gap, m = 32, 680, 230, 76, 28
    h = m * 2 + 40 + max(len(rows), 1) * (rh + 8)
    y0 = m + 16
    p = [
        f'<rect class="conn" x="{m}" y="{y0}" width="{lw}" height="{rh}" rx="7"/>',
        _t(m + lw / 2, y0 + rh / 2 + 4, root, size=10, cls="nm"),
    ]
    for i, r in enumerate(rows):
        y = y0 + 54 + i * (rh + 8)
        rx = m + lw + gap
        rw = w - rx - m
        p.append(
            f'<rect class="conn" x="{rx:.0f}" y="{y:.0f}" width="{rw:.0f}" height="{rh}" rx="7"/>'
        )
        resolved = ", ".join(r.resolves_to) if r.resolves_to else "（空）"
        p.append(_t(rx + rw / 2, y + rh / 2 + 4, resolved, size=9, cls="nm"))
        p.append(
            f'<path class="wire" stroke="{_WIRE_FALLBACK}" d="'
            f'{_bez(m + lw, y0 + rh / 2, rx, y + rh / 2)}"/>'
        )
        p.append(_t((m + lw + rx) / 2, y + rh / 2 - 7, r.expr, size=8, cls="pin"))
    return _frame(w, h, "".join(p))


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

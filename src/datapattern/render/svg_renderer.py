"""``svg`` レンダラ — 外部ツール無しで、配線設計に耐える体裁の SVG を組む（決定論）。

方針: プロパティ値（CSA/色コード/長さ/部品番号…）は図に書かず、レポートの表に任せる。
図はレイアウトと記号だけ — ランク付きの列配置・直交配線・IEC 記号。共有シーンは
``_schematic.py``。option_config は簡潔な決定表。
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render._schematic import Scene, SLink, SNode, SPin, build_scene
from datapattern.render.base import Asset, RenderContext, Renderer

# IEC 60757 → 落ち着いた実寸色
_IEC = {
    "BK": "#20242c",
    "BN": "#7a5230",
    "RD": "#c0392b",
    "OG": "#d9822b",
    "YE": "#c9a227",
    "GN": "#2e8b57",
    "BU": "#2f6fb3",
    "VT": "#7d5ba6",
    "GY": "#8b929c",
    "WH": "#b9bec6",
    "PK": "#c97b98",
    "BG": "#c4ad86",
    "GNYE": "#2e8b57",
    "SL": "#9aa0a6",
    "TQ": "#2aa5a0",
}
_STUB = 12
_CORNER = 4


def _c(colors: tuple[str, ...], i: int = 0) -> str:
    if i < len(colors):
        return _IEC.get(colors[i].upper(), "#4b5563")
    return "#4b5563"


def _t(x: float, y: float, s: str, *, a: str = "middle", size: int = 10, cls: str = "id") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{a}" '
        f'font-size="{size}" class="{cls}">{escape(s)}</text>'
    )


_STYLE = (
    "<style>"
    "text{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;fill:#2b303b}"
    ".id{font-weight:600;fill:#1f2430}"
    ".pin{fill:#9198a3}"
    ".node{fill:#ffffff;stroke:#9aa1ac;stroke-width:1.1}"
    ".dev{fill:#f5f8fc;stroke:#8199b6;stroke-width:1.1}"
    ".stub{stroke:#8b929c;stroke-width:1}"
    ".wire{fill:none;stroke-width:1.5;stroke-linejoin:round;stroke-linecap:round}"
    ".sym{fill:none;stroke:#2b303b;stroke-width:1.5}"
    ".splice{fill:#ffffff;stroke:#1f2430;stroke-width:1.4}"
    ".enc{fill:none;stroke:#9aa0a6;stroke-width:1;stroke-dasharray:4 3}"
    ".frame{fill:none;stroke:#c7ccd6;stroke-width:1}"
    ".tblk{fill:#fbfcfe;stroke:#c7ccd6;stroke-width:1}"
    "</style>"
)


def _grid(w: float, h: float) -> str:
    return (
        '<defs><pattern id="g" width="16" height="16" patternUnits="userSpaceOnUse">'
        '<circle cx="1" cy="1" r="0.6" fill="#e7eaf0"/></pattern></defs>'
        f'<rect width="{w:.0f}" height="{h:.0f}" fill="#ffffff"/>'
        f'<rect x="6" y="6" width="{w - 12:.0f}" height="{h - 12:.0f}" fill="url(#g)"/>'
        f'<rect class="frame" x="6" y="6" width="{w - 12:.0f}" height="{h - 12:.0f}"/>'
    )


def _titleblock(w: float, h: float, title: str) -> str:
    tw, th = 190, 30
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
        r = 5
        d = (
            f"M{n.cx:.1f},{n.cy - r:.1f} L{n.cx + r:.1f},{n.cy:.1f} "
            f"L{n.cx:.1f},{n.cy + r:.1f} L{n.cx - r:.1f},{n.cy:.1f} Z"
        )
        return f'<path class="splice" d="{d}"/>' + _t(n.cx, n.cy - r - 4, n.id, size=8, cls="pin")
    if n.symbol == "ground":
        px, py = n.pins["*"].x, n.pins["*"].y
        return _ground_sym(px, py) + _t(px, py + 38, n.id, size=8, cls="pin")
    if n.symbol == "supply":
        r = n.w / 2
        return (
            f'<circle class="node" cx="{n.cx:.1f}" cy="{n.cy:.1f}" r="{r:.1f}"/>'
            + _t(n.cx, n.cy + 1, "＋", size=12)
            + _t(n.cx, n.cy + r + 11, n.id, size=8, cls="pin")
        )

    cls = "dev" if n.symbol == "device" else "node"
    rx = 6 if n.symbol == "device" else 2
    p = [
        f'<rect class="{cls}" x="{n.x:.1f}" y="{n.y:.1f}" '
        f'width="{n.w:.1f}" height="{n.h:.1f}" rx="{rx}"/>',
    ]
    if n.symbol == "fuse":
        my = n.y + n.h / 2
        p.append(
            f'<line class="sym" x1="{n.x + 10:.1f}" y1="{my:.1f}" '
            f'x2="{n.x + n.w - 10:.1f}" y2="{my:.1f}"/>'
        )
        p.append(_t(n.cx, n.y - 5, n.id, size=10))
    else:
        p.append(_t(n.cx, n.y + n.h / 2 + 4, n.id, size=10.5))
    for name, pin in sorted(n.pins.items(), key=lambda kv: (kv[1].side, kv[1].y)):
        if pin.side == "C":
            continue
        dx = _STUB if pin.side == "R" else -_STUB
        p.append(
            f'<line class="stub" x1="{pin.x:.1f}" y1="{pin.y:.1f}" '
            f'x2="{pin.x + dx:.1f}" y2="{pin.y:.1f}"/>'
        )
        auto = len(name) >= 2 and name[0] in "LR" and name[1:].isdigit()
        if name and not auto and n.symbol != "fuse":
            lx = pin.x + (-6 if pin.side == "R" else 6)
            p.append(
                _t(lx, pin.y + 3, name, a="end" if pin.side == "R" else "start", size=7, cls="pin")
            )
    return "".join(p)


# --- 直交配線 ------------------------------------------------------------- #


def _pin_of(node: SNode, name: str) -> SPin:
    return node.pins.get(name) or next(iter(node.pins.values()))


def _ortho(ax: float, ay: float, bx: float, by: float, chx: float, r: float = _CORNER) -> str:
    """A(右向き) → 縦チャネル chx → B(左向き) を角丸で。"""
    sx = ax + _STUB
    ex = bx - _STUB
    if abs(ay - by) < 1:
        return f"M{ax:.1f},{ay:.1f} H{bx:.1f}"
    dy = 1 if by > ay else -1
    return (
        (
            f"M{ax:.1f},{ay:.1f} H{chx - r:.1f} "
            f"Q{chx:.1f},{ay:.1f} {chx:.1f},{ay + dy * r:.1f} "
            f"V{by - dy * r:.1f} "
            f"Q{chx:.1f},{by:.1f} {chx + r:.1f},{by:.1f} "
            f"H{bx:.1f}"
        )
        if sx <= ex
        else (f"M{ax:.1f},{ay:.1f} H{max(sx, chx):.1f} V{by:.1f} H{bx:.1f}")
    )


def _links_svg(scene: Scene) -> str:
    from collections import defaultdict

    by_channel: dict[float, list[SLink]] = defaultdict(list)
    for lk in scene.links:
        na, nb = scene.node(lk.a), scene.node(lk.b)
        if na is None or nb is None:
            continue
        left = na if na.col <= nb.col else nb
        by_channel[left.x + left.w].append(lk)

    out: list[str] = []
    for base_x, lks in sorted(by_channel.items()):
        gap = 60
        lane_lks = sorted(lks, key=lambda lk: scene.node(lk.a).cy + scene.node(lk.b).cy)
        for j, lk in enumerate(lane_lks):
            na, nb = scene.node(lk.a), scene.node(lk.b)
            a_node, b_node = (na, nb) if na.col <= nb.col else (nb, na)
            a_pin_name = lk.a_pin if a_node is na else lk.b_pin
            b_pin_name = lk.b_pin if a_node is na else lk.a_pin
            pa = _pin_of(a_node, a_pin_name)
            pb = _pin_of(b_node, b_pin_name)
            chx = base_x + gap / 2 + (j - (len(lane_lks) - 1) / 2) * 7
            out.append(_link_svg(lk, pa, pb, chx))
    return "".join(out)


def _link_svg(lk: SLink, pa: SPin, pb: SPin, chx: float) -> str:
    ax = pa.x + (_STUB if pa.side == "R" else -_STUB if pa.side == "L" else 0)
    bx = pb.x + (-_STUB if pb.side == "L" else _STUB if pb.side == "R" else 0)
    ay, by = pa.y, pb.y
    parts: list[str] = []

    if lk.kind in {"multicore", "shield"}:
        n = min(lk.conductors, 6)
        for k in range(n):
            off = (k - (n - 1) / 2) * 3
            d = _ortho(ax, ay + off, bx, by + off, chx + off)
            parts.append(
                f'<path class="wire" d="{d}" stroke="{_c(lk.colors, k)}" stroke-width="1.3"/>'
            )
        if lk.kind == "multicore":
            mx, my = chx, (ay + by) / 2
            parts.append(
                f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="8" fill="#fff" stroke="#8b929c"/>'
            )
            parts.append(_t(mx, my + 3, f"{lk.conductors}", size=8, cls="pin"))
        else:  # shield: 導体を囲う破線
            pad = (n - 1) / 2 * 3 + 4
            parts.append(f'<path class="enc" d="{_ortho(ax, ay - pad, bx, by - pad, chx - pad)}"/>')
            parts.append(f'<path class="enc" d="{_ortho(ax, ay + pad, bx, by + pad, chx + pad)}"/>')
    elif lk.kind == "overbraid":
        d = _ortho(ax, ay, bx, by, chx)
        parts.append(
            f'<path class="wire" d="{d}" stroke="{_c(lk.colors)}" stroke-width="3.4" '
            f'stroke-opacity="0.35"/>'
        )
        parts.append(f'<path class="wire" d="{d}" stroke="{_c(lk.colors)}"/>')
    else:
        d = _ortho(ax, ay, bx, by, chx)
        parts.append(f'<path class="wire" d="{d}" stroke="{_c(lk.colors)}"/>')

    # ピンとスタブ端をつなぐ短い線
    parts.append(
        f'<line class="wire" x1="{pa.x:.1f}" y1="{ay:.1f}" x2="{ax:.1f}" y2="{ay:.1f}" '
        f'stroke="{_c(lk.colors)}"/>'
    )
    parts.append(
        f'<line class="wire" x1="{pb.x:.1f}" y1="{by:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
        f'stroke="{_c(lk.colors)}"/>'
    )
    return "".join(parts)


def _circuit(pattern: Pattern) -> str:
    scene = build_scene(pattern)
    body = _links_svg(scene) + "".join(_node_svg(n) for n in scene.nodes)
    return _frame(scene.width, scene.height + 44, body, title=pattern.id)


# --- option_config（決定表） --------------------------------------------- #


def _option_config(pattern: Pattern) -> str:
    rows = pattern.variant_matrix
    root = pattern.option_expression or "option expression"
    rh, w, lw, gap, m = 32, 660, 220, 70, 24
    h = m * 2 + 40 + max(len(rows), 1) * (rh + 6)
    y0 = m + 16
    p = [
        f'<rect class="node" x="{m}" y="{y0}" width="{lw}" height="{rh}" rx="4"/>',
        _t(m + lw / 2, y0 + rh / 2 + 4, root, size=10),
    ]
    for i, r in enumerate(rows):
        y = y0 + 54 + i * (rh + 6)
        rx = m + lw + gap
        rw = w - rx - m
        p.append(
            f'<rect class="node" x="{rx:.0f}" y="{y:.0f}" width="{rw:.0f}" height="{rh}" rx="4"/>'
        )
        resolved = ", ".join(r.resolves_to) if r.resolves_to else "（空）"
        p.append(_t(rx + rw / 2, y + rh / 2 + 4, resolved, size=9))
        p.append(
            f'<path class="wire" stroke="#8b929c" d="M{m + lw},{y0 + rh / 2} '
            f'H{m + lw + gap / 2:.0f} V{y + rh / 2:.0f} H{rx:.0f}"/>'
        )
        p.append(_t(m + lw + gap / 2, y + rh / 2 - 6, r.expr, size=8, cls="pin"))
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

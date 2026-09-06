"""``svg`` レンダラ — 外部ツールなしで決定論的に SVG を組む（ゼロ依存）。

レイアウトは素朴（ノードを 1 行に並べ、エッジは下側に弧を描く）。graphviz ほど賢くないが
CI でも必ず動く。分類 circuit / option_config。
"""

from __future__ import annotations

from html import escape
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render.base import Asset, RenderContext, Renderer

_NW, _NH, _GAP = 120, 40, 40
_PAD = 20


def _text(
    x: float, y: float, s: str, *, anchor: str = "middle", size: int = 11, cls: str = ""
) -> str:
    c = f' class="{cls}"' if cls else ""
    return (
        f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" '
        f'font-size="{size}"{c}>{escape(s)}</text>'
    )


def _svg(width: float, height: float, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" font-family="Helvetica, Arial, sans-serif">'
        f"<style>.n{{fill:#f4f4f4;stroke:#555}}.s{{fill:#555}}.e{{stroke:#777;fill:none}}"
        f".lbl{{fill:#555}}.t{{fill:#111}}</style>{body}</svg>"
    )


def _circuit(pattern: Pattern) -> str:
    conn = pattern.connectivity
    assert conn is not None
    ids: list[str] = [n.id for n in sorted(conn.nodes, key=lambda n: n.id)]
    kinds = {n.id: n.kind for n in conn.nodes}
    for e in conn.edges:  # via ノードも並べる
        if e.via and e.via not in ids:
            ids.append(e.via)

    x_of = {nid: _PAD + i * (_NW + _GAP) for i, nid in enumerate(ids)}
    top = _PAD + 20
    width = _PAD * 2 + len(ids) * (_NW + _GAP) - _GAP
    edges = sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or ""))
    depth = max((i for i, _ in enumerate(edges)), default=0)
    height = top + _NH + 40 + depth * 22 + _PAD

    parts: list[str] = []
    for nid in ids:
        x = x_of[nid]
        if kinds.get(nid) == "splice":
            parts.append(
                f'<circle class="s" cx="{x + _NW / 2:.0f}" cy="{top + _NH / 2:.0f}" r="6"/>'
            )
            parts.append(_text(x + _NW / 2, top - 4, nid, size=10, cls="lbl"))
        else:
            parts.append(
                f'<rect class="n" x="{x:.0f}" y="{top}" width="{_NW}" height="{_NH}" rx="4"/>'
            )
            label = nid if kinds.get(nid) is None else f"{nid} ({kinds[nid]})"
            parts.append(_text(x + _NW / 2, top + _NH / 2 + 4, label, cls="t"))

    base_y = top + _NH
    for i, e in enumerate(edges):
        a = e.source.split(".")[0]
        b = e.target.split(".")[0]
        hops = [a, e.via, b] if e.via else [a, b]
        dip = base_y + 24 + i * 22
        for p, q in pairwise(hops):
            x1, x2 = x_of[p] + _NW / 2, x_of[q] + _NW / 2
            parts.append(
                f'<path class="e" d="M{x1:.0f},{base_y} C{x1:.0f},{dip:.0f} '
                f'{x2:.0f},{dip:.0f} {x2:.0f},{base_y}"/>'
            )
        tags = " ".join(t for t in (e.gauge, e.color, "shield" if e.shield else None) if t)
        if tags:
            parts.append(
                _text(
                    (x_of[hops[0]] + x_of[hops[-1]]) / 2 + _NW / 2, dip + 4, tags, size=9, cls="lbl"
                )
            )

    return _svg(width, height, "".join(parts))


def _option_config(pattern: Pattern) -> str:
    rows = pattern.variant_matrix
    root = pattern.option_expression or "option expression"
    row_h = 34
    width = 640
    height = _PAD * 2 + 30 + max(len(rows), 1) * row_h
    left_w, gap = 200, 60
    cy0 = _PAD + 20
    parts = [
        f'<rect class="n" x="{_PAD}" y="{cy0}" width="{left_w}" height="{row_h}" rx="4"/>',
        _text(_PAD + left_w / 2, cy0 + row_h / 2 + 4, root, size=10, cls="t"),
    ]
    for i, r in enumerate(rows):
        y = cy0 + 60 + i * row_h
        rx = _PAD + left_w + gap
        rw = width - rx - _PAD
        parts.append(
            f'<rect class="n" x="{rx:.0f}" y="{y:.0f}" '
            f'width="{rw:.0f}" height="{row_h - 6}" rx="4"/>'
        )
        resolved = ", ".join(r.resolves_to) if r.resolves_to else "（空）"
        parts.append(_text(rx + rw / 2, y + row_h / 2, resolved, size=9, cls="t"))
        parts.append(
            f'<path class="e" d="M{_PAD + left_w},{cy0 + row_h / 2} '
            f"C{_PAD + left_w + gap / 2:.0f},{cy0 + row_h / 2} "
            f'{rx - gap / 2:.0f},{y + row_h / 2:.0f} {rx:.0f},{y + row_h / 2:.0f}"/>'
        )
        parts.append(_text((_PAD + left_w + rx) / 2, y + row_h / 2 - 6, r.expr, size=8, cls="lbl"))
    return _svg(width, height + 40, "".join(parts))


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

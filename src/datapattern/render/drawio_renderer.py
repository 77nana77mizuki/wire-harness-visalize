"""``drawio`` レンダラ — 編集可能な .drawio（mxGraph XML）を手書き生成（ゼロ依存）。

共有シーン（``_schematic.py``）の配置をそのまま使い、draw.io にエッジ経路は任せる。
記号は Capital 風（アース ⏚ / スプライスのドット / 多芯太線 / シールド破線）。
出力は「画像」でなく編集可能ファイル。circuit / option_config。
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar
from xml.sax.saxutils import quoteattr

from datapattern.model import Pattern
from datapattern.render._schematic import SLink, SNode, build_scene
from datapattern.render.base import Asset, RenderContext, Renderer

_STYLE = {
    "connector": "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#333333;",
    "device": "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;",
    "fuse": "rounded=0;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;",
    "supply": "ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;",
    "splice": "ellipse;whiteSpace=wrap;html=1;fillColor=#000000;strokeColor=#000000;",
    "ground": "text;html=1;align=center;verticalAlign=middle;fontSize=22;strokeColor=none;fillColor=none;",
}
_LINK = {
    "wire": "endArrow=none;html=1;strokeColor=#555555;",
    "multicore": "endArrow=none;html=1;strokeWidth=3;strokeColor=#333333;",
    "shield": "endArrow=none;html=1;dashed=1;strokeColor=#777777;",
    "overbraid": "endArrow=none;html=1;strokeWidth=4;dashed=1;strokeColor=#999999;",
}


def _vertex(cid: str, label: str, x: float, y: float, w: float, h: float, style: str) -> str:
    return (
        f"<mxCell id={quoteattr(cid)} value={quoteattr(label)} style={quoteattr(style)} "
        'vertex="1" parent="1">'
        f'<mxGeometry x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" as="geometry"/></mxCell>'
    )


def _edge(cid: str, src: str, tgt: str, label: str, style: str) -> str:
    return (
        f"<mxCell id={quoteattr(cid)} value={quoteattr(label)} style={quoteattr(style)} "
        f'edge="1" parent="1" source={quoteattr(src)} target={quoteattr(tgt)}>'
        '<mxGeometry relative="1" as="geometry"/></mxCell>'
    )


def _wrap(cells: list[str]) -> str:
    inner = "".join(cells)
    return (
        '<mxfile host="datapattern"><diagram name="pattern">'
        '<mxGraphModel dx="900" dy="640" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        'pageWidth="900" pageHeight="700" math="0" shadow="0">'
        f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{inner}</root>'
        "</mxGraphModel></diagram></mxfile>"
    )


def _node_cell(n: SNode) -> str:
    label = f"⏚&#10;{n.id}" if n.symbol == "ground" else n.id
    return _vertex(
        f"n_{n.id}", label, n.x, n.y, n.w, n.h, _STYLE.get(n.symbol, _STYLE["connector"])
    )


def _link_cell(idx: int, lk: SLink) -> str:
    style = _LINK.get(lk.kind, _LINK["wire"])
    if lk.kind == "multicore":
        label = f"{lk.conductors}C"
    elif lk.colors:
        label = f"{lk.gauge or ''} {lk.colors[0]}".strip()
    else:
        label = lk.gauge or ""
    return _edge(f"e_{idx}", f"n_{lk.a}", f"n_{lk.b}", label, style)


def _circuit_xml(pattern: Pattern) -> str:
    scene = build_scene(pattern)
    cells = [_node_cell(n) for n in scene.nodes]
    cells += [_link_cell(i, lk) for i, lk in enumerate(scene.links)]
    return _wrap(cells)


def _option_config_xml(pattern: Pattern) -> str:
    root = pattern.option_expression or "option expression"
    cells = [_vertex("root", root, 40, 40, 240, 50, _STYLE["connector"])]
    for i, r in enumerate(pattern.variant_matrix):
        resolved = ", ".join(r.resolves_to) if r.resolves_to else "（空）"
        cells.append(_vertex(f"v{i}", resolved, 380, 40 + i * 80, 260, 50, _STYLE["connector"]))
        cells.append(_edge(f"e{i}", "root", f"v{i}", r.expr, _LINK["wire"]))
    return _wrap(cells)


_BUILDERS = {"circuit": _circuit_xml, "option_config": _option_config_xml}


class DrawioRenderer(Renderer):
    name: ClassVar[str] = "drawio"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset(_BUILDERS)

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        xml = _BUILDERS[pattern.type](pattern)
        rel = Path(f"{pattern.id}.drawio")
        (ctx.out_dir / rel).write_text(xml + "\n", encoding="utf-8")
        return Asset(
            pattern_id=pattern.id,
            method=self.name,
            path=rel,
            kind="xml",
            title=pattern.title,
            caption=pattern.summary,
        )

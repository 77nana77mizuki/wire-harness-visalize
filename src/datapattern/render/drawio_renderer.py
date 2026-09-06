"""``drawio`` レンダラ — 編集可能な .drawio（mxGraph XML）を手書き生成する（ゼロ依存）。

drawpyo は GPLv3 なので使わず、XML を直接組む。出力は「画像」ではなく編集可能ファイル。
レポートには XML を載せる（app.diagrams.net に貼り付け）。分類 circuit / option_config。
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path
from typing import ClassVar
from xml.sax.saxutils import quoteattr

from datapattern.model import Pattern
from datapattern.render.base import Asset, RenderContext, Renderer

_VS = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
_SS = "ellipse;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;"
_ES = "endArrow=none;html=1;"


def _cell_vertex(cid: str, label: str, x: int, y: int, w: int, h: int, style: str) -> str:
    return (
        f"<mxCell id={quoteattr(cid)} value={quoteattr(label)} style={quoteattr(style)} "
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def _cell_edge(cid: str, src: str, tgt: str, label: str) -> str:
    return (
        f"<mxCell id={quoteattr(cid)} value={quoteattr(label)} style={quoteattr(_ES)} "
        f'edge="1" parent="1" source={quoteattr(src)} target={quoteattr(tgt)}>'
        f'<mxGeometry relative="1" as="geometry"/></mxCell>'
    )


def _wrap(cells: list[str]) -> str:
    inner = "".join(cells)
    return (
        '<mxfile host="datapattern"><diagram name="pattern">'
        '<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" guides="1" '
        'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        'pageWidth="850" pageHeight="1100" math="0" shadow="0">'
        f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{inner}</root>'
        "</mxGraphModel></diagram></mxfile>"
    )


def _circuit_xml(pattern: Pattern) -> str:
    conn = pattern.connectivity
    assert conn is not None
    kinds = {n.id: n.kind for n in conn.nodes}
    ids = [n.id for n in sorted(conn.nodes, key=lambda n: n.id)]
    for e in conn.edges:
        if e.via and e.via not in ids:
            ids.append(e.via)

    cells: list[str] = []
    for i, nid in enumerate(ids):
        x, y = 40 + (i % 4) * 200, 40 + (i // 4) * 140
        if kinds.get(nid) == "splice":
            cells.append(_cell_vertex(f"n_{nid}", nid, x + 60, y + 20, 40, 40, _SS))
        else:
            label = nid if kinds.get(nid) is None else f"{nid}&#10;({kinds[nid]})"
            cells.append(_cell_vertex(f"n_{nid}", label, x, y, 160, 60, _VS))

    for j, e in enumerate(sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or ""))):
        a, b = e.source.split(".")[0], e.target.split(".")[0]
        tags = " ".join(t for t in (e.gauge, e.color, "shield" if e.shield else None) if t)
        hops = [a, e.via, b] if e.via else [a, b]
        for k, (p, q) in enumerate(pairwise(hops)):
            cells.append(_cell_edge(f"e_{j}_{k}", f"n_{p}", f"n_{q}", tags if k == 0 else ""))
    return _wrap(cells)


def _option_config_xml(pattern: Pattern) -> str:
    root = pattern.option_expression or "option expression"
    cells = [_cell_vertex("root", root, 40, 40, 220, 50, _VS)]
    for i, r in enumerate(pattern.variant_matrix):
        rid = f"v{i}"
        resolved = ", ".join(r.resolves_to) if r.resolves_to else "（空）"
        cells.append(_cell_vertex(rid, resolved, 360, 40 + i * 80, 240, 50, _VS))
        cells.append(_cell_edge(f"e{i}", "root", rid, r.expr))
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

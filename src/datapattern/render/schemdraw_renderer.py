"""``schemdraw`` レンダラ — connectivity を回路図風に描く（MIT、``import`` 利用）。

matplotlib の SVG 出力はメタデータに日時を含むため、``<metadata>`` とコメントを除去して
決定論性を確保する。分類 circuit 専用。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render.base import Asset, RenderContext, Renderer

_COLS = 4
_DX, _DY = 6.0, -3.5


def _strip(svg: str) -> str:
    svg = re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.S)
    svg = re.sub(r"<!--.*?-->", "", svg, flags=re.S)
    i = svg.find("<svg")
    return svg[i:] if i != -1 else svg


def _draw(pattern: Pattern) -> str:
    import matplotlib

    matplotlib.rcParams["svg.hashsalt"] = "datapattern"
    import schemdraw
    import schemdraw.elements as elm

    conn = pattern.connectivity
    assert conn is not None
    kinds = {n.id: n.kind for n in conn.nodes}
    ids = [n.id for n in sorted(conn.nodes, key=lambda n: n.id)]
    for e in conn.edges:
        if e.via and e.via not in ids:
            ids.append(e.via)

    pos = {nid: (col * _DX, (i // _COLS) * _DY) for i, nid in enumerate(ids) for col in [i % _COLS]}

    with schemdraw.Drawing(show=False) as d:
        elements: dict[str, object] = {}
        for nid in ids:
            x, y = pos[nid]
            if kinds.get(nid) == "splice":
                elements[nid] = d.add(elm.Dot(radius=0.12).at((x, y)).label(nid, fontsize=9))
            else:
                lbl = nid if kinds.get(nid) is None else f"{nid}\n({kinds[nid]})"
                elements[nid] = d.add(elm.RBox(w=3.2, h=1.4).at((x, y)).label(lbl, fontsize=9))

        def _xy(nid: str) -> tuple[float, float]:
            el = elements[nid]
            return tuple(getattr(el, "center", pos[nid]))

        for e in sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or "")):
            a, b = e.source.split(".")[0], e.target.split(".")[0]
            hops = [a, e.via, b] if e.via else [a, b]
            tags = " ".join(t for t in (e.gauge, e.color, "shield" if e.shield else None) if t)
            for k in range(len(hops) - 1):
                line = elm.Line().at(_xy(hops[k])).to(_xy(hops[k + 1]))
                if k == 0 and tags:
                    line = line.label(tags, fontsize=8, ofst=0.2)
                d.add(line)

        return _strip(d.get_imagedata("svg").decode("utf-8"))


class SchemdrawRenderer(Renderer):
    name: ClassVar[str] = "schemdraw"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset({"circuit"})

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        svg = _draw(pattern)
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

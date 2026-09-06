"""``graphviz`` レンダラ — DOT を生成し ``dot`` CLI（サブプロセス）で SVG 化。

分類 circuit（接続グラフ）と option_config（決定木）。`dot` が PATH に無い場合、
レジストリがこのレンダラをスキップする（``html`` にフォールバック）。
"""

from __future__ import annotations

import subprocess
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render.base import Asset, RenderContext, Renderer

_NODE_SHAPE = {
    "device": "box",
    "connector": "box",
    "splice": "point",
    "terminal": "box",
    "component": "box",
}
_HEADER = (
    "digraph G {\n"
    '  graph [ordering=out, rankdir=LR, bgcolor="transparent", fontname="Helvetica"];\n'
    '  node [fontname="Helvetica", fontsize=10];\n'
    '  edge [fontname="Helvetica", fontsize=9];\n'
)


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _dot_circuit(pattern: Pattern) -> str:
    conn = pattern.connectivity
    assert conn is not None
    lines = [_HEADER]
    for node in sorted(conn.nodes, key=lambda n: n.id):
        shape = _NODE_SHAPE.get(node.kind, "box")
        # \n は DOT の改行エスケープ。_esc の後に足す（_esc に通すと \\n に潰れる）。
        label = _esc(node.id) if node.kind == "splice" else f"{_esc(node.id)}\\n({_esc(node.kind)})"
        lines.append(f'  "{_esc(node.id)}" [label="{label}", shape={shape}];\n')
    for edge in sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or "")):
        tags = [t for t in (edge.gauge, edge.color, "shield" if edge.shield else None) if t]
        elabel = " ".join(tags)
        src = edge.source.split(".")[0]
        dst = edge.target.split(".")[0]
        hops = [src, edge.via, dst] if edge.via else [src, dst]
        for a, b in pairwise(hops):
            lines.append(f'  "{_esc(a)}" -> "{_esc(b)}" [label="{_esc(elabel)}", dir=none];\n')
    lines.append("}\n")
    return "".join(lines)


def _dot_option_config(pattern: Pattern) -> str:
    root = pattern.option_expression or "option expression"
    lines = [_HEADER, f'  "root" [label="{_esc(root)}", shape=oval];\n']
    for i, row in enumerate(pattern.variant_matrix):
        leaf = f"v{i}"
        resolved = ", ".join(row.resolves_to) if row.resolves_to else "（空）"
        lines.append(
            f'  "{leaf}" [label="{_esc(resolved)}", shape=box];\n'
            f'  "root" -> "{leaf}" [label="{_esc(row.expr)}"];\n'
        )
    lines.append("}\n")
    return "".join(lines)


def _strip_svg_preamble(svg: str) -> str:
    """XML 宣言・DOCTYPE・graphviz バージョンコメントを落として ``<svg`` から返す。"""
    idx = svg.find("<svg")
    return svg[idx:] if idx != -1 else svg


class GraphvizRenderer(Renderer):
    name: ClassVar[str] = "graphviz"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset({"circuit", "option_config"})

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        dot_source = (
            _dot_circuit(pattern) if pattern.type == "circuit" else _dot_option_config(pattern)
        )
        dot_path = ctx.out_dir / f"{pattern.id}.dot"
        dot_path.write_text(dot_source, encoding="utf-8")

        proc = subprocess.run(
            ["dot", "-Tsvg", str(dot_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        svg_rel = Path(f"{pattern.id}.svg")
        (ctx.out_dir / svg_rel).write_text(_strip_svg_preamble(proc.stdout), encoding="utf-8")
        return Asset(
            pattern_id=pattern.id,
            method=self.name,
            path=svg_rel,
            kind="svg",
            title=pattern.title,
            caption=pattern.summary,
        )

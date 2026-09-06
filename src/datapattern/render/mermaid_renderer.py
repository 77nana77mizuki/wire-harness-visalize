"""``mermaid`` レンダラ — Mermaid 記法を生成し ``mmdc``（mermaid-cli）で SVG 化。

これは「疎結合の実証」枠。`DataPatternModel` 契約・パイプライン・レポート組立には一切触れず、
このファイル ＋ ``renderers/registry.toml`` の 1 エントリ ＋ skill ＋ テスト だけで足りる。
``mmdc`` 未導入ならレジストリがスキップする（`html` にフォールバック）。
"""

from __future__ import annotations

import re
import subprocess
from itertools import pairwise
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render.base import Asset, RenderContext, Renderer

_ID_SAFE = re.compile(r"[^A-Za-z0-9_]")


def _nid(raw: str) -> str:
    return "n_" + _ID_SAFE.sub("_", raw)


def _label(text: str) -> str:
    return text.replace('"', "&quot;").replace("\n", " ")


def _mermaid_circuit(pattern: Pattern) -> str:
    conn = pattern.connectivity
    assert conn is not None
    lines = ["flowchart LR"]
    for node in sorted(conn.nodes, key=lambda n: n.id):
        shape = ("((", "))") if node.kind == "splice" else ("[", "]")
        lines.append(f'  {_nid(node.id)}{shape[0]}"{_label(node.id)}"{shape[1]}')
    for edge in sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or "")):
        tags = " ".join(t for t in (edge.gauge, edge.color, "shield" if edge.shield else None) if t)
        a = _nid(edge.source.split(".")[0])
        b = _nid(edge.target.split(".")[0])
        hops = [a, _nid(edge.via), b] if edge.via else [a, b]
        link = f'-- "{_label(tags)}" ---' if tags else "---"
        for x, y in pairwise(hops):
            lines.append(f"  {x} {link} {y}")
    return "\n".join(lines) + "\n"


def _mermaid_option_config(pattern: Pattern) -> str:
    root = pattern.option_expression or "option expression"
    lines = ["flowchart TD", f'  root["{_label(root)}"]']
    for i, row in enumerate(pattern.variant_matrix):
        resolved = ", ".join(row.resolves_to) if row.resolves_to else "（空）"
        lines.append(f'  v{i}["{_label(resolved)}"]')
        lines.append(f'  root -- "{_label(row.expr)}" --> v{i}')
    return "\n".join(lines) + "\n"


def _strip_svg_preamble(svg: str) -> str:
    idx = svg.find("<svg")
    return svg[idx:] if idx != -1 else svg


class MermaidRenderer(Renderer):
    name: ClassVar[str] = "mermaid"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset({"circuit", "option_config"})

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        source = (
            _mermaid_circuit(pattern)
            if pattern.type == "circuit"
            else _mermaid_option_config(pattern)
        )
        mmd = ctx.out_dir / f"{pattern.id}.mmd"
        mmd.write_text(source, encoding="utf-8")

        svg_rel = Path(f"{pattern.id}.svg")
        subprocess.run(
            ["mmdc", "-i", str(mmd), "-o", str(ctx.out_dir / svg_rel)],
            capture_output=True,
            text=True,
            check=True,
        )
        produced = ctx.out_dir / svg_rel
        produced.write_text(_strip_svg_preamble(produced.read_text("utf-8")), encoding="utf-8")
        return Asset(
            pattern_id=pattern.id,
            method=self.name,
            path=svg_rel,
            kind="svg",
            title=pattern.title,
            caption=pattern.summary,
        )

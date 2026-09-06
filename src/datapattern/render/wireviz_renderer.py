"""``wireviz`` レンダラ — connectivity を WireViz YAML に写像し ``wireviz`` CLI で SVG 化。

WireViz は GPLv3。**import せず** CLI をサブプロセス起動する。PATH に無ければレジストリが
このレンダラをスキップする。分類 circuit 専用（ハーネス / 接続トポロジ）。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import ClassVar

from datapattern.model import Node, Pattern
from datapattern.render.base import Asset, RenderContext, Renderer


def _q(text: object) -> str:
    """YAML 用にシングルクォートする（内部の ' はエスケープ）。"""
    return "'" + str(text).replace("'", "''") + "'"


def _pin_ref(node: Node | None, raw: str | None) -> str:
    """'X1.GND' の 'GND' 部分を WireViz のピン参照へ。ラベル→1始まり番号、無ければ 1。"""
    if raw is None or raw == "":
        return "1"
    if raw.isdigit():
        return raw
    if node is not None and raw in node.pinlabels:
        return str(node.pinlabels.index(raw) + 1)
    return "1"


def wireviz_yaml(pattern: Pattern) -> str:
    conn = pattern.connectivity
    assert conn is not None
    nodes = {n.id: n for n in conn.nodes}
    ordered = sorted(conn.nodes, key=lambda n: n.id)

    lines: list[str] = ["connectors:"]
    for n in ordered:
        lines.append(f"  {_q(n.id)}:")
        lines.append(f"    type: {_q(n.kind)}")
        if n.kind == "splice":
            lines.append("    style: simple")
            lines.append("    pincount: 1")
        else:
            lines.append(f"    pincount: {n.pincount or max(1, len(n.pinlabels)) or 1}")
            if n.pinlabels:
                inner = ", ".join(_q(pl) for pl in n.pinlabels)
                lines.append(f"    pinlabels: [{inner}]")

    edges = sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or ""))
    lines.append("cables:")
    for i, e in enumerate(edges):
        seg = 2 if e.via else 1
        for s in range(seg):
            lines.append(f"  W{i}_{s}:")
            lines.append("    wirecount: 1")
            if e.gauge:
                lines.append(f"    gauge: {_q(e.gauge)}")
            if e.color:
                lines.append(f"    colors: [{_q(e.color)}]")
            if e.shield:
                lines.append("    shield: true")

    lines.append("connections:")
    for i, e in enumerate(edges):
        a_id, _, a_pin = e.source.partition(".")
        b_id, _, b_pin = e.target.partition(".")
        a = (a_id, _pin_ref(nodes.get(a_id), a_pin or None))
        b = (b_id, _pin_ref(nodes.get(b_id), b_pin or None))
        if e.via:
            mid = (e.via, "1")
            lines.append(
                f"  -\n    - {_q(a[0])}: {a[1]}\n    - W{i}_0: 1\n    - {_q(mid[0])}: {mid[1]}"
            )
            lines.append(
                f"  -\n    - {_q(mid[0])}: {mid[1]}\n    - W{i}_1: 1\n    - {_q(b[0])}: {b[1]}"
            )
        else:
            lines.append(
                f"  -\n    - {_q(a[0])}: {a[1]}\n    - W{i}_0: 1\n    - {_q(b[0])}: {b[1]}"
            )

    return "\n".join(lines) + "\n"


def _strip_svg_preamble(svg: str) -> str:
    idx = svg.find("<svg")
    return svg[idx:] if idx != -1 else svg


class WirevizRenderer(Renderer):
    name: ClassVar[str] = "wireviz"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset({"circuit"})

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        yml = ctx.out_dir / f"{pattern.id}.yml"
        yml.write_text(wireviz_yaml(pattern), encoding="utf-8")

        subprocess.run(
            ["wireviz", "-f", "s", "-o", str(ctx.out_dir / pattern.id), str(yml)],
            capture_output=True,
            text=True,
            check=True,
        )
        svg_rel = Path(f"{pattern.id}.svg")
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

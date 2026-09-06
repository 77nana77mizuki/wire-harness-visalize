"""``wireviz`` レンダラ — connectivity を WireViz YAML に写像し ``wireviz`` CLI で SVG 化。

WireViz は GPLv3。**import せず** CLI をサブプロセス起動する。PATH に無ければレジストリが
このレンダラをスキップする。分類 circuit 専用（ハーネス / 接続トポロジ）。
"""

from __future__ import annotations

import re
import subprocess
from collections import OrderedDict
from pathlib import Path
from typing import ClassVar

from datapattern.model import Connectivity, Node, Pattern
from datapattern.render.base import Asset, RenderContext, Renderer

_NUM = re.compile(r"^\d+(?:\.\d+)?$")
_AWG = re.compile(r"^AWG\s*(\d+)$", re.IGNORECASE)


def _q(text: object) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def _gauge(raw: str | None) -> str | None:
    """WireViz は数値 or '数値 単位' を要求する。Capital の CSA は mm2。"""
    if not raw:
        return None
    if _NUM.match(raw):
        return f"{raw} mm2"
    m = _AWG.match(raw)
    if m:
        return f"{m.group(1)} AWG"
    return raw


def _pin_ref(node: Node | None, raw: str) -> str:
    if raw == "":
        return "1"
    if raw.isdigit():
        return raw
    if node is not None and raw in node.pinlabels:
        return str(node.pinlabels.index(raw) + 1)
    return "1"


def _endpoint(spec: str) -> tuple[str, str]:
    node_id, _, pin = spec.partition(".")
    return node_id, pin


def _classify(conn: Connectivity) -> tuple[list[str], set[str]]:
    """connector になる id と、cable になる via 名（＝一度も端点にならない via）を返す。"""
    endpoints: set[str] = set()
    for e in conn.edges:
        endpoints.add(_endpoint(e.source)[0])
        endpoints.add(_endpoint(e.target)[0])
    vias = {e.via for e in conn.edges if e.via}
    cable_vias = vias - endpoints
    connector_ids = sorted({n.id for n in conn.nodes} | (endpoints - cable_vias))
    return connector_ids, cable_vias


def wireviz_yaml(pattern: Pattern) -> str:
    conn = pattern.connectivity
    assert conn is not None
    nodes = {n.id: n for n in conn.nodes}
    connector_ids, cable_vias = _classify(conn)

    lines: list[str] = ["connectors:"]
    for cid in connector_ids:
        node = nodes.get(cid)
        kind = node.kind if node else "connector"
        lines.append(f"  {_q(cid)}:")
        if kind == "splice":
            lines.append("    style: simple")
            lines.append("    pincount: 1")
        else:
            pincount = (
                (node.pincount if node and node.pincount else 0)
                or (len(node.pinlabels) if node and node.pinlabels else 0)
                or 1
            )
            lines.append(f"    pincount: {pincount}")
            if node and node.pinlabels:
                lines.append(f"    pinlabels: [{', '.join(_q(p) for p in node.pinlabels)}]")

    # via 共有かつ端点ペアが同じエッジは 1 本の多芯ケーブルにまとめる（マルチコア等）。
    groups: OrderedDict[tuple[str, tuple[str, str]], list] = OrderedDict()
    for i, e in enumerate(sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or ""))):
        a, _ = _endpoint(e.source)
        b, _ = _endpoint(e.target)
        pair = tuple(sorted((a, b)))
        key = (e.via, pair) if (e.via and e.via in cable_vias) else (f"__solo{i}", pair)
        groups.setdefault(key, []).append(e)

    cable_names: dict[tuple[str, tuple[str, str]], str] = {}
    lines.append("cables:")
    for idx, (key, edges) in enumerate(groups.items()):
        via, _pair = key
        name = via if (via and not via.startswith("__solo")) else f"W{idx}"
        cable_names[key] = name
        gauges = [g for g in (_gauge(e.gauge) for e in edges) if g]
        colors = [e.color for e in edges if e.color]
        lines.append(f"  {_q(name)}:")
        lines.append(f"    wirecount: {len(edges)}")
        if gauges:
            lines.append(f"    gauge: {gauges[0]}")
        if colors and len(colors) == len(edges):
            lines.append(f"    colors: [{', '.join(colors)}]")
        if any(e.shield for e in edges):
            lines.append("    shield: true")

    lines.append("connections:")
    for key, edges in groups.items():
        _via, pair = key
        first, second = pair
        name = cable_names[key]
        first_pins, second_pins, wires = [], [], []
        for w, e in enumerate(edges, start=1):
            (na, pa), (nb, pb) = _endpoint(e.source), _endpoint(e.target)
            if na != first:  # 向きを first/second に正規化
                na, pa, nb, pb = nb, pb, na, pa
            first_pins.append(_pin_ref(nodes.get(na), pa))
            second_pins.append(_pin_ref(nodes.get(nb), pb))
            wires.append(str(w))
        lines.append(
            f"  -\n"
            f"    - {_q(first)}: [{', '.join(first_pins)}]\n"
            f"    - {_q(name)}: [{', '.join(wires)}]\n"
            f"    - {_q(second)}: [{', '.join(second_pins)}]"
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
            ["wireviz", "-f", "s", "-o", str(ctx.out_dir), "-O", pattern.id, str(yml)],
            capture_output=True,
            text=True,
            check=True,
        )
        svg_rel = Path(f"{pattern.id}.svg")
        produced = ctx.out_dir / svg_rel
        produced.write_text(_strip_svg_preamble(produced.read_text("utf-8")), encoding="utf-8")
        # WireViz が追加で吐く中間物を片付ける（.gv / .bom.tsv など）。SVG のみ残す。
        for extra in ctx.out_dir.glob(f"{pattern.id}.*"):
            if extra.suffix not in {".svg", ".yml"}:
                extra.unlink()
        return Asset(
            pattern_id=pattern.id,
            method=self.name,
            path=svg_rel,
            kind="svg",
            title=pattern.title,
            caption=pattern.summary,
        )

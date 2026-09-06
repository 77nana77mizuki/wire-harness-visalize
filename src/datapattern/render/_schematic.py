"""circuit パターン → 配線図の「シーン」（配置済みノード + リンク）。

svg / drawio レンダラが共有する。Capital Logic で見る記号（アース、スプライス、
コネクタ、マルチコア束、シールド、ヒューズ…）に寄せる。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from datapattern.model import Connectivity, Pattern

_GROUND_RE = re.compile(r"(?:^g\d{2,}$|gnd|ground|earth|chassis|masse)", re.IGNORECASE)
_SUPPLY_RE = re.compile(r"(?:batt|^b\+|kl30|^bat$|power)", re.IGNORECASE)
_FUSE_RE = re.compile(r"(?:^f\d|fuse|fusible)", re.IGNORECASE)
_OVERBRAID_RE = re.compile(r"(?:ob\d*|braid|overbraid)", re.IGNORECASE)

COL_W, ROW_H, PAD = 190, 150, 24


@dataclass(frozen=True, slots=True)
class SNode:
    id: str
    symbol: str  # connector | device | splice | ground | supply | fuse
    x: float
    y: float
    pins: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SLink:
    a: str
    b: str
    kind: str  # wire | multicore | shield | overbraid
    conductors: int
    gauge: str | None
    colors: tuple[str, ...]
    label: str


@dataclass(slots=True)
class Scene:
    nodes: list[SNode] = field(default_factory=list)
    links: list[SLink] = field(default_factory=list)
    width: float = 0
    height: float = 0

    def node(self, nid: str) -> SNode | None:
        return next((n for n in self.nodes if n.id == nid), None)


def _symbol_for(kind: str | None, nid: str) -> str:
    if kind == "splice":
        return "splice"
    if kind == "terminal" or (kind is None and _GROUND_RE.search(nid)):
        if _SUPPLY_RE.search(nid):
            return "supply"
        return "ground"
    if _GROUND_RE.search(nid):
        return "ground"
    if _FUSE_RE.search(nid) or (kind == "component" and _FUSE_RE.search(nid)):
        return "fuse"
    if kind in {"device", "component"}:
        return "device"
    return "connector"


def build_scene(pattern: Pattern) -> Scene:
    conn: Connectivity | None = pattern.connectivity
    assert conn is not None
    node_kinds = {n.id: n.kind for n in conn.nodes}
    node_pins = {n.id: n.pinlabels for n in conn.nodes}

    endpoints: list[str] = []
    for e in conn.edges:
        for spec in (e.source, e.target):
            nid = spec.split(".")[0]
            if nid not in endpoints:
                endpoints.append(nid)
    vias = {e.via for e in conn.edges if e.via}
    cable_vias = vias - set(endpoints)

    ids = sorted({n.id for n in conn.nodes} | (set(endpoints) - cable_vias))

    # --- リンクをまとめる（端点ペア単位。マルチコアは 1 リンクに複数導体） ---
    groups: dict[tuple[str, str], list] = {}
    order: list[tuple[str, str]] = []
    for e in sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or "")):
        a, b = e.source.split(".")[0], e.target.split(".")[0]
        key = (a, b) if a <= b else (b, a)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(e)

    links: list[SLink] = []
    for key in order:
        es = groups[key]
        via = next((e.via for e in es if e.via), None)
        colors = tuple(e.color for e in es if e.color)
        gauge = next((e.gauge for e in es if e.gauge), None)
        if via and _OVERBRAID_RE.search(via):
            kind = "overbraid"
        elif any(e.shield for e in es):
            kind = "shield"
        elif via and via in cable_vias and len(es) > 1:
            kind = "multicore"
        else:
            kind = "wire"
        label = via or (gauge or "")
        if kind == "multicore":
            label = f"{via} · {len(es)}C"
        links.append(SLink(key[0], key[1], kind, len(es), gauge, colors, label))

    # --- 配置: 上段にコネクタ/デバイス、スプライスは中段、アース類は下段 ---
    upper = [
        i
        for i in ids
        if _symbol_for(node_kinds.get(i), i) in {"connector", "device", "fuse", "supply"}
    ]
    mid = [i for i in ids if _symbol_for(node_kinds.get(i), i) == "splice"]
    lower = [i for i in ids if _symbol_for(node_kinds.get(i), i) == "ground"]

    scene = Scene(links=links)
    max_cols = max(len(upper), 1)
    for col, nid in enumerate(upper):
        scene.nodes.append(
            SNode(
                nid,
                _symbol_for(node_kinds.get(nid), nid),
                PAD + col * COL_W,
                PAD,
                tuple(node_pins.get(nid, ())),
            )
        )
    for k, nid in enumerate(mid):
        step = max(1, len(mid))
        scene.nodes.append(
            SNode(nid, "splice", PAD + (k + 0.5) * (max_cols * COL_W) / step, PAD + ROW_H)
        )
    for k, nid in enumerate(lower):
        step = max(1, len(lower))
        scene.nodes.append(
            SNode(
                nid,
                _symbol_for(node_kinds.get(nid), nid),
                PAD + (k + 0.5) * (max_cols * COL_W) / step,
                PAD + 2 * ROW_H,
            )
        )

    scene.width = PAD * 2 + max(max_cols, len(lower), 1) * COL_W
    scene.height = PAD * 2 + (2 if (mid or lower) else 0) * ROW_H + 90
    return scene

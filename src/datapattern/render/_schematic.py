"""circuit パターン → 配線図の「シーン」（ランク付け・整列・ピン配置済み）。

svg / drawio レンダラが共有する。プロパティ値は図に描かず（レポートの表が担う）、
レイアウトと記号だけを持つ。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from datapattern.model import Connectivity, Pattern

_GROUND_RE = re.compile(r"(?:^g\d{2,}$|gnd|ground|earth|chassis|masse)", re.IGNORECASE)
_SUPPLY_RE = re.compile(r"(?:batt|^b\+|kl30|^bat$|power|^pwr$|feed|source|^src$)", re.IGNORECASE)
_FUSE_RE = re.compile(r"(?:^f\d|fuse|fusible|relay|^k\d)", re.IGNORECASE)
_OVERBRAID_RE = re.compile(r"(?:ob\d*|braid|overbraid)", re.IGNORECASE)

COL_PITCH = 210
ROW_PITCH = 96
MARGIN = 44
NODE_W = 124
NODE_H = 44


@dataclass(frozen=True, slots=True)
class SPin:
    name: str
    x: float
    y: float
    side: str  # L | R | C


@dataclass(slots=True)
class SNode:
    id: str
    symbol: str  # connector | device | splice | ground | supply | fuse
    col: int
    row: int
    x: float = 0
    y: float = 0
    w: float = NODE_W
    h: float = NODE_H
    pins: dict[str, SPin] = field(default_factory=dict)

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


@dataclass(frozen=True, slots=True)
class SLink:
    a: str
    b: str
    a_pin: str
    b_pin: str
    kind: str  # wire | multicore | shield | overbraid
    conductors: int
    colors: tuple[str, ...]
    gauge: str | None


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
    if _SUPPLY_RE.search(nid):
        return "supply"
    if kind == "terminal" or _GROUND_RE.search(nid):
        return "ground"
    if _FUSE_RE.search(nid):
        return "fuse"
    if kind in {"device", "component"}:
        return "device"
    return "connector"


def _node_size(symbol: str) -> tuple[float, float]:
    if symbol == "splice":
        return 12, 12
    if symbol == "ground":
        return 30, 34
    if symbol == "supply":
        return 52, 52
    if symbol == "fuse":
        return 108, 40
    return NODE_W, NODE_H


# --------------------------------------------------------------------------- #
# ランク付け（列）と整列（行）
# --------------------------------------------------------------------------- #


def _build_links(conn: Connectivity) -> tuple[list[SLink], set[str], dict[str, str]]:
    endpoints: list[str] = []
    for e in conn.edges:
        for spec in (e.source, e.target):
            nid = spec.split(".")[0]
            if nid not in endpoints:
                endpoints.append(nid)
    vias = {e.via for e in conn.edges if e.via}
    cable_vias = vias - set(endpoints)

    groups: dict[tuple[str, str], list] = {}
    order: list[tuple[str, str]] = []
    ep_pins: dict[tuple[str, str], tuple[str, str]] = {}
    for e in sorted(conn.edges, key=lambda e: (e.source, e.target, e.via or "")):
        an, _, ap = e.source.partition(".")
        bn, _, bp = e.target.partition(".")
        key = (an, bn) if an <= bn else (bn, an)
        if key not in groups:
            groups[key] = []
            order.append(key)
            ep_pins[key] = (ap, bp) if an <= bn else (bp, ap)
        groups[key].append(e)

    links: list[SLink] = []
    for key in order:
        es = groups[key]
        via = next((x.via for x in es if x.via), None)
        colors = tuple(x.color for x in es if x.color)
        gauge = next((x.gauge for x in es if x.gauge), None)
        if via and _OVERBRAID_RE.search(via):
            kind = "overbraid"
        elif any(x.shield for x in es):
            kind = "shield"
        elif via and via in cable_vias and len(es) > 1:
            kind = "multicore"
        else:
            kind = "wire"
        ap, bp = ep_pins[key]
        links.append(SLink(key[0], key[1], ap, bp, kind, len(es), colors, gauge))
    return links, cable_vias, {}


def _rank(ids: list[str], links: list[SLink], symbols: dict[str, str]) -> dict[str, int]:
    adj: dict[str, set[str]] = {i: set() for i in ids}
    for lk in links:
        if lk.a in adj and lk.b in adj:
            adj[lk.a].add(lk.b)
            adj[lk.b].add(lk.a)

    # ルート: supply → 次数 1 の最小 id → 最小 id
    roots = [i for i in ids if symbols[i] == "supply"]
    if not roots:
        roots = [i for i in sorted(ids) if len(adj[i]) <= 1]
    root = roots[0] if roots else sorted(ids)[0]

    col: dict[str, int] = {root: 0}
    frontier = [root]
    while frontier:
        nxt: list[str] = []
        for u in frontier:
            for v in sorted(adj[u]):
                if v not in col:
                    col[v] = col[u] + 1
                    nxt.append(v)
        frontier = nxt
    for i in ids:  # 孤立ノード
        col.setdefault(i, 0)

    # アース類はいちばん右へ寄せる（隣接ノードの右）
    for i in ids:
        if symbols[i] == "ground" and adj[i]:
            col[i] = max(col[n] for n in adj[i]) + 1
    return col


def _order_rows(ids: list[str], col: dict[str, int], links: list[SLink]) -> dict[str, int]:
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for lk in links:
        if lk.a in adj and lk.b in adj:
            adj[lk.a].append(lk.b)
            adj[lk.b].append(lk.a)

    by_col: dict[int, list[str]] = {}
    for i in sorted(ids):
        by_col.setdefault(col[i], []).append(i)

    row: dict[str, int] = {}
    for c in sorted(by_col):
        by_col[c].sort()
        for r, i in enumerate(by_col[c]):
            row[i] = r

    # 隣接列の重心で 2 回ならす
    cols_sorted = sorted(by_col)
    for _ in range(2):
        for c in cols_sorted:
            prev = [i for i in ids if col[i] == c - 1]
            if not prev:
                continue

            def bary(node: str) -> float:
                ns = [n for n in adj[node] if col[n] == c - 1]  # noqa: B023
                return sum(row[n] for n in ns) / len(ns) if ns else row[node]

            by_col[c].sort(key=lambda n: (bary(n), n))
            for r, i in enumerate(by_col[c]):
                row[i] = r
    return row


# --------------------------------------------------------------------------- #
# ピン配置
# --------------------------------------------------------------------------- #


def _place_pins(scene: Scene, links: list[SLink]) -> None:
    # ノードごとに「右へ出る接続」「左へ出る接続」を集める
    want: dict[str, list[tuple[str, str, float]]] = {n.id: [] for n in scene.nodes}
    for lk in links:
        na, nb = scene.node(lk.a), scene.node(lk.b)
        if na is None or nb is None:
            continue
        a_side = "R" if nb.col >= na.col else "L"
        b_side = "L" if nb.col >= na.col else "R"
        want[lk.a].append((lk.a_pin, a_side, nb.cy))
        want[lk.b].append((lk.b_pin, b_side, na.cy))

    for n in scene.nodes:
        if n.symbol in {"splice", "ground", "supply"}:
            px = n.cx
            py = n.y if n.symbol == "ground" else n.cy
            n.pins = {"*": SPin("*", px, py, "C")}
            continue
        left = sorted((w for w in want[n.id] if w[1] == "L"), key=lambda w: w[2])
        right = sorted((w for w in want[n.id] if w[1] == "R"), key=lambda w: w[2])
        for side, group, sx in (("L", left, n.x), ("R", right, n.x + n.w)):
            k = len(group)
            for idx, (pin, _s, _y) in enumerate(group):
                py = n.y + n.h * (idx + 1) / (k + 1)
                n.pins[pin or f"{side}{idx}"] = SPin(pin or f"{side}{idx}", sx, py, side)


def build_scene(pattern: Pattern) -> Scene:
    conn: Connectivity | None = pattern.connectivity
    assert conn is not None
    node_kinds = {n.id: n.kind for n in conn.nodes}

    links, _cable_vias, _ = _build_links(conn)
    endpoints = {p for lk in links for p in (lk.a, lk.b)}
    ids = sorted({n.id for n in conn.nodes} | endpoints)
    symbols = {i: _symbol_for(node_kinds.get(i), i) for i in ids}

    col = _rank(ids, links, symbols)
    row = _order_rows(ids, col, links)
    rows_in_col = {
        c: max((row[i] for i in ids if col[i] == c), default=0) + 1 for c in col.values()
    }
    max_rows = max(rows_in_col.values(), default=1)

    scene = Scene(links=links)
    for i in sorted(ids):
        w, h = _node_size(symbols[i])
        c, r = col[i], row[i]
        n_rows = rows_in_col.get(c, 1)
        x = MARGIN + c * COL_PITCH
        # 列内で縦中央寄せ
        y = MARGIN + (r + (max_rows - n_rows) / 2) * ROW_PITCH
        scene.nodes.append(SNode(i, symbols[i], c, r, x + (NODE_W - w) / 2, y, w, h))

    _place_pins(scene, links)

    ncols = max(col.values(), default=0) + 1
    scene.width = MARGIN * 2 + (ncols - 1) * COL_PITCH + NODE_W
    bottom = max((n.y + n.h for n in scene.nodes), default=MARGIN)
    scene.height = bottom + MARGIN + 24  # 24 = アース記号や下ラベルの余白
    return scene

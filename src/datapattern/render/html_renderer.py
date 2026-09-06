"""``html`` レンダラ — Jinja2 も外部ツールも使わず、決定論的に HTML 断片を組む。

分類 A/C（表）が主対象。分類 B も接続表として簡易に描ける（既定のフォールバック）。
出力はスタイルなしの ``<table class="grid">`` 等の断片で、``report.py`` の CSS が装飾する。
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import ClassVar

from datapattern.model import Pattern
from datapattern.render.base import Asset, RenderContext, Renderer


def _cell(value: object) -> str:
    if value is None:
        return '<td class="dp-empty">—</td>'
    if isinstance(value, bool):
        return f"<td>{'true' if value else 'false'}</td>"
    return f"<td>{escape(str(value))}</td>"


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    out = ['<table class="grid">', "  <thead><tr>"]
    out += [f"    <th>{escape(h)}</th>" for h in headers]
    out += ["  </tr></thead>", "  <tbody>"]
    if not rows:
        out.append(
            f'    <tr><td class="dp-empty" colspan="{len(headers)}">（データなし）</td></tr>'
        )
    for row in rows:
        out.append("    <tr>" + "".join(_cell(c) for c in row) + "</tr>")
    out += ["  </tbody>", "</table>"]
    return out


def _subhead(text: str) -> str:
    style = "font-weight:600;color:var(--muted);margin:.6rem 0 .2rem"
    return f'<p class="subhead" style="{style}">{escape(text)}</p>'


def _option_config(pattern: Pattern) -> list[str]:
    rows = [
        [row.expr, ", ".join(row.resolves_to) if row.resolves_to else None]
        for row in pattern.variant_matrix
    ]
    return _table(["option 値の組", "解決後に残るオブジェクト"], rows)


def _property_set(pattern: Pattern) -> list[str]:
    body = _table(
        ["対象", "プロパティ", "期待値", "理由（同値クラス / 境界）"],
        [[e.object, e.property, e.value, e.why] for e in pattern.property_expectations],
    )
    obj_rows = [
        [o.ref or "—", o.kind, ", ".join(f"{k}={v}" for k, v in sorted(o.properties.items()))]
        for o in pattern.capital_objects
        if o.properties
    ]
    if obj_rows:
        body.append(_subhead("オブジェクトのプロパティ"))
        body += _table(["参照", "種別", "プロパティ"], obj_rows)
    return body


def _circuit(pattern: Pattern) -> list[str]:
    conn = pattern.connectivity
    if conn is None:  # スキーマ上は circuit なら必ずあるが、防御的に
        return ['<p class="dp-empty">connectivity なし</p>']
    node_rows = [
        [n.id, n.kind, n.pincount, ", ".join(n.pinlabels) if n.pinlabels else None]
        for n in sorted(conn.nodes, key=lambda n: n.id)
    ]
    edge_rows = [[e.source, e.target, e.via, e.gauge, e.color, e.shield] for e in conn.edges]
    body = [_subhead("ノード")]
    body += _table(["id", "種別", "ピン数", "ピン名"], node_rows)
    body.append(_subhead("接続"))
    body += _table(["from", "to", "経由", "断面積", "色", "シールド"], edge_rows)
    return body


_BUILDERS = {
    "option_config": _option_config,
    "property_set": _property_set,
    "circuit": _circuit,
}


class HtmlRenderer(Renderer):
    name: ClassVar[str] = "html"
    deterministic: ClassVar[bool] = True
    supported_types: ClassVar[frozenset[str]] = frozenset(_BUILDERS)

    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        builder = _BUILDERS[pattern.type]
        fragment = "\n".join(builder(pattern)) + "\n"

        rel = Path(f"{pattern.id}.html")
        (ctx.out_dir / rel).write_text(fragment, encoding="utf-8")
        return Asset(
            pattern_id=pattern.id,
            method=self.name,
            path=rel,
            kind="html",
            title=pattern.title,
            caption=pattern.summary,
        )

"""``DataPatternModel`` + レンダマニフェスト → 自己完結 ``report.html``（決定論的）。

- 一覧テーブル ＋ パターンごとの詳細テーブル
- 図は「実現方式ごとのタブ」で並べる（1 方式なら 1 タブ）
- タイムスタンプなど実行ごとに変わる値は出さない
"""

from __future__ import annotations

from html import escape
from importlib import resources
from pathlib import Path

from jinja2 import Environment

from datapattern.model import DataPatternModel, Pattern
from datapattern.render.pipeline import RenderManifest

_TYPE_LABELS = {
    "option_config": "オプション / バリアント構成",
    "circuit": "回路 / サブ回路の設計",
    "property_set": "部品・回路のプロパティ設定",
}
_TYPE_ORDER = ["option_config", "circuit", "property_set"]


def _environment() -> Environment:
    # autoescape=True。図の断片だけ ``| safe`` で通す（各レンダラが escape 済み）。
    return Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)


def _load_template_source() -> str:
    return resources.files("datapattern.templates").joinpath("report.html.j2").read_text("utf-8")


def _figures_for(pattern: Pattern, manifest: RenderManifest) -> list[dict[str, str]]:
    figs: list[dict[str, str]] = []
    for asset in manifest.assets_for(pattern.id):
        raw = manifest.path_of(asset).read_text("utf-8").rstrip("\n")
        if asset.kind == "svg":
            content = f'<div class="svg-wrap">{raw}</div>'
        elif asset.kind == "xml":
            link = (
                '<a href="https://app.diagrams.net/" target="_blank" '
                'rel="noopener">app.diagrams.net</a>'
            )
            content = (
                f'<p class="xml-note">編集可能ファイル。下の XML を {link} に貼り付け'
                "（Extras → Edit Diagram）。</p>"
                f'<pre class="xml">{escape(raw)}</pre>'
            )
        else:
            content = raw
        figs.append({"method": asset.method, "content": content})
    return figs


def render_report_html(model: DataPatternModel, manifest: RenderManifest) -> str:
    """``report.html`` の中身を文字列で返す。"""
    figures: dict[str, list[dict[str, str]]] = {}
    missing: list[str] = []
    for pattern in model.patterns:
        figs = _figures_for(pattern, manifest)
        if not figs:
            missing.append(pattern.id)
        figures[pattern.id] = figs

    counts = dict.fromkeys(_TYPE_ORDER, 0)
    for p in model.patterns:
        counts[p.type] = counts.get(p.type, 0) + 1
    type_summary = [
        {"type": t, "count": counts.get(t, 0), "label": _TYPE_LABELS.get(t, t)} for t in _TYPE_ORDER
    ]

    patterns = sorted(model.patterns, key=lambda p: p.id)
    overview = [
        {
            "id": p.id,
            "type": p.type,
            "title": p.title,
            "summary": p.summary,
            "methods": ", ".join(f["method"] for f in figures[p.id]) or "—",
        }
        for p in patterns
    ]

    template = _environment().from_string(_load_template_source())
    html = template.render(
        addon=model.addon,
        schema_version=model.schema_version,
        generator=(model.generated_from.generator if model.generated_from else None),
        patterns=patterns,
        overview=overview,
        figures=figures,
        type_summary=type_summary,
        methods_used=manifest.methods(),
        skipped=sorted(set(manifest.skipped) | set(missing)),
    )
    return html if html.endswith("\n") else html + "\n"


def write_report(model: DataPatternModel, manifest: RenderManifest, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report_html(model, manifest), encoding="utf-8")
    return out_path

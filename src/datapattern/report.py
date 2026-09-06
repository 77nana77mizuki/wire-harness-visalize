"""``DataPatternModel`` + レンダマニフェスト → 自己完結 ``report.html``（決定論的）。

タイムスタンプなど実行ごとに変わる値は出力しない（スナップショットテスト可能に保つ）。
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from jinja2 import Environment

from datapattern.model import DataPatternModel
from datapattern.render.pipeline import RenderManifest

_TYPE_LABELS = {
    "option_config": "オプション / バリアント構成",
    "circuit": "回路 / サブ回路の設計",
    "property_set": "部品・回路のプロパティ設定",
}
_TYPE_ORDER = ["option_config", "circuit", "property_set"]


def _load_template_source() -> str:
    return resources.files("datapattern.templates").joinpath("report.html.j2").read_text("utf-8")


def _environment() -> Environment:
    # autoescape=True。図の断片だけ ``| safe`` で通す（html_renderer が escape 済み）。
    return Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)


def render_report_html(model: DataPatternModel, manifest: RenderManifest) -> str:
    """``report.html`` の中身を文字列で返す。"""
    figures: dict[str, str] = {}
    missing: list[str] = []
    for pattern in model.patterns:
        asset = manifest.asset_for(pattern.id)
        if asset is None:
            missing.append(pattern.id)
            figures[pattern.id] = (
                '<figure class="dp-figure"><p class="dp-empty">'
                "利用可能なレンダラで描画できませんでした。</p></figure>"
            )
            continue
        content = manifest.path_of(asset).read_text("utf-8").rstrip("\n")
        if asset.kind == "svg":
            content = f'<figure class="dp-figure">{content}</figure>'
        figures[pattern.id] = content

    counts = {t: 0 for t in _TYPE_ORDER}
    for p in model.patterns:
        counts[p.type] = counts.get(p.type, 0) + 1
    type_summary = [
        {"type": t, "count": counts.get(t, 0), "label": _TYPE_LABELS.get(t, t)} for t in _TYPE_ORDER
    ]

    template = _environment().from_string(_load_template_source())
    html = template.render(
        addon=model.addon,
        schema_version=model.schema_version,
        generator=(model.generated_from.generator if model.generated_from else None),
        patterns=sorted(model.patterns, key=lambda p: p.id),
        figures=figures,
        type_summary=type_summary,
        skipped=sorted(set(manifest.skipped) | set(missing)),
    )
    return html if html.endswith("\n") else html + "\n"


def write_report(model: DataPatternModel, manifest: RenderManifest, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_report_html(model, manifest), encoding="utf-8")
    return out_path

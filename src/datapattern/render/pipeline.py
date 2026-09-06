"""1 つのレンダラで ``DataPatternModel`` の全パターンを描画し、``index.json`` を書く。

契約は ``docs/03-architecture.md`` §B。レンダラ選択（レジストリ）は第5弾。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from datapattern.model import DataPatternModel
from datapattern.render.base import Asset, RenderContext, Renderer


@dataclass(frozen=True, slots=True)
class RenderManifest:
    """``renders/<method>/index.json`` に対応。"""

    method: str
    method_dir: Path
    assets: tuple[Asset, ...]
    skipped: tuple[str, ...]
    """このレンダラが ``supports`` しなかったパターン id。"""

    def asset_for(self, pattern_id: str) -> Asset | None:
        return next((a for a in self.assets if a.pattern_id == pattern_id), None)

    def to_index(self) -> dict[str, object]:
        return {
            "method": self.method,
            "entries": {a.pattern_id: a.as_record() for a in self.assets},
            "skipped": list(self.skipped),
        }


def render_patterns(
    model: DataPatternModel,
    renderer: Renderer,
    out_root: Path,
) -> RenderManifest:
    """``out_root/<method>/`` に各パターンのアセットと ``index.json`` を書き出す。"""
    method_dir = out_root / renderer.name
    method_dir.mkdir(parents=True, exist_ok=True)
    ctx = RenderContext(out_dir=method_dir)

    assets: list[Asset] = []
    skipped: list[str] = []
    for pattern in sorted(model.patterns, key=lambda p: p.id):
        if renderer.supports(pattern.type):
            assets.append(renderer.render(pattern, ctx))
        else:
            skipped.append(pattern.id)

    manifest = RenderManifest(
        method=renderer.name,
        method_dir=method_dir,
        assets=tuple(assets),
        skipped=tuple(skipped),
    )
    (method_dir / "index.json").write_text(
        json.dumps(manifest.to_index(), ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return manifest

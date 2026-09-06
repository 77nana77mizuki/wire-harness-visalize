"""パターン群を描画し ``index.json`` を書く。

- :func:`render_patterns` … 単一レンダラで全パターン
- :func:`render_auto` … レジストリでパターンごとに最適なレンダラを 1 つ選ぶ
- :func:`render_all` … パターンごとに対応レンダラ**全部**で描く（レポートのタブ比較用）

契約は ``docs/03-architecture.md`` §B。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from datapattern.model import DataPatternModel
from datapattern.render.base import Asset, RenderContext, Renderer


@dataclass(frozen=True, slots=True)
class RenderManifest:
    """``renders/index.json`` に対応。アセットは ``out_root/<method>/<path>``。"""

    out_root: Path
    assets: tuple[Asset, ...]
    skipped: tuple[str, ...]
    """どのレンダラでも描けなかったパターン id。"""

    def asset_for(self, pattern_id: str) -> Asset | None:
        return next((a for a in self.assets if a.pattern_id == pattern_id), None)

    def assets_for(self, pattern_id: str) -> tuple[Asset, ...]:
        return tuple(a for a in self.assets if a.pattern_id == pattern_id)

    def methods(self) -> list[str]:
        seen: list[str] = []
        for a in self.assets:
            if a.method not in seen:
                seen.append(a.method)
        return seen

    def path_of(self, asset: Asset) -> Path:
        return self.out_root / asset.method / asset.path

    def to_index(self) -> dict[str, object]:
        entries: dict[str, list[dict[str, object]]] = {}
        for a in self.assets:
            entries.setdefault(a.pattern_id, []).append(a.as_record())
        return {"entries": entries, "skipped": list(self.skipped)}


def _write_index(manifest: RenderManifest) -> None:
    manifest.out_root.mkdir(parents=True, exist_ok=True)
    (manifest.out_root / "index.json").write_text(
        json.dumps(manifest.to_index(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _render_one(renderer: Renderer, pattern, out_root: Path) -> Asset:
    method_dir = out_root / renderer.name
    method_dir.mkdir(parents=True, exist_ok=True)
    return renderer.render(pattern, RenderContext(out_dir=method_dir))


def render_patterns(model: DataPatternModel, renderer: Renderer, out_root: Path) -> RenderManifest:
    """``renderer`` 一本で全パターンを描画する。"""
    assets: list[Asset] = []
    skipped: list[str] = []
    for pattern in sorted(model.patterns, key=lambda p: p.id):
        if renderer.supports(pattern.type):
            assets.append(_render_one(renderer, pattern, out_root))
        else:
            skipped.append(pattern.id)
    manifest = RenderManifest(Path(out_root), tuple(assets), tuple(skipped))
    _write_index(manifest)
    return manifest


def render_auto(model: DataPatternModel, registry, out_root: Path) -> RenderManifest:
    """パターンごとに ``registry`` が選んだレンダラで描画する。"""
    assets: list[Asset] = []
    skipped: list[str] = []
    for pattern in sorted(model.patterns, key=lambda p: p.id):
        renderer = registry.select(pattern.type, pattern.preferred_methods)
        if renderer is None:
            skipped.append(pattern.id)
            continue
        assets.append(_render_one(renderer, pattern, out_root))
    manifest = RenderManifest(Path(out_root), tuple(assets), tuple(skipped))
    _write_index(manifest)
    return manifest


def render_all(model: DataPatternModel, registry, out_root: Path) -> RenderManifest:
    """パターンごとに、対応する利用可能レンダラ全部で描画する。"""
    assets: list[Asset] = []
    skipped: list[str] = []
    for pattern in sorted(model.patterns, key=lambda p: p.id):
        renderers = registry.all_supporting(pattern.type, pattern.preferred_methods)
        if not renderers:
            skipped.append(pattern.id)
            continue
        assets.extend(_render_one(r, pattern, out_root) for r in renderers)
    manifest = RenderManifest(Path(out_root), tuple(assets), tuple(skipped))
    _write_index(manifest)
    return manifest

"""``renderers/registry.toml`` を読み、使えるレンダラだけを提供する。

- ``requires`` の外部コマンドが `PATH` に無いエントリは自動スキップ
- ``select()`` は preferred → 任意の対応レンダラ → ``html`` の順にフォールバック
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from importlib import import_module, resources

from datapattern.render.base import Renderer

_FALLBACK = "html"


@dataclass(frozen=True, slots=True)
class RendererEntry:
    name: str
    module: str
    requires: tuple[str, ...]
    available: bool
    missing: tuple[str, ...]


class Registry:
    def __init__(self, entries: list[RendererEntry]) -> None:
        self._entries = entries
        self._cache: dict[str, Renderer] = {}

    @property
    def entries(self) -> list[RendererEntry]:
        return list(self._entries)

    def names(self, *, available_only: bool = True) -> list[str]:
        return [e.name for e in self._entries if e.available or not available_only]

    def _load(self, name: str) -> Renderer | None:
        if name in self._cache:
            return self._cache[name]
        entry = next((e for e in self._entries if e.name == name), None)
        if entry is None or not entry.available:
            return None
        mod_name, _, cls_name = entry.module.partition(":")
        cls = getattr(import_module(mod_name), cls_name)
        renderer = cls()
        self._cache[name] = renderer
        return renderer

    def get(self, name: str) -> Renderer | None:
        return self._load(name)

    def select(self, pattern_type: str, preferred: tuple[str, ...] = ()) -> Renderer | None:
        """このパターン種別に使うレンダラを 1 つ選ぶ。"""
        for name in (*preferred, *self.names(), _FALLBACK):
            renderer = self._load(name)
            if renderer is not None and renderer.supports(pattern_type):
                return renderer
        return None

    def all_supporting(self, pattern_type: str, preferred: tuple[str, ...] = ()) -> list[Renderer]:
        """このパターン種別を扱える利用可能レンダラを全部返す（preferred を先頭に）。"""
        ordered: list[str] = []
        for name in (*preferred, *self.names(), _FALLBACK):
            if name not in ordered:
                ordered.append(name)
        out: list[Renderer] = []
        for name in ordered:
            renderer = self._load(name)
            if renderer is not None and renderer.supports(pattern_type):
                out.append(renderer)
        return out


def _entry_from_toml(raw: dict[str, object]) -> RendererEntry:
    requires = tuple(str(r) for r in raw.get("requires", ()))
    missing = tuple(r for r in requires if shutil.which(r) is None)
    return RendererEntry(
        name=str(raw["name"]),
        module=str(raw["module"]),
        requires=requires,
        available=not missing,
        missing=missing,
    )


def load_registry(text: str | None = None) -> Registry:
    if text is None:
        text = resources.files("datapattern.renderers").joinpath("registry.toml").read_text("utf-8")
    data = tomllib.loads(text)
    entries = [_entry_from_toml(r) for r in data.get("renderer", [])]
    return Registry(entries)

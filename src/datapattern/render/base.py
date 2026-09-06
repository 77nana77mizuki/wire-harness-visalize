"""レンダラ契約（プラグイン化の肝）。

- 入力: 1 つの :class:`~datapattern.model.Pattern` + :class:`RenderContext`
- 出力: :class:`Asset`（生成した図ファイルへの相対パスとメタデータ）

決定論化のルールは ``docs/02-datapattern-and-rendering.md`` §B-6 を参照。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Literal

from datapattern.model import Pattern

AssetKind = Literal["svg", "html", "xml"]


@dataclass(frozen=True, slots=True)
class RenderContext:
    """1 回のレンダリング実行に共通の設定。"""

    out_dir: Path
    """アセットの出力先ディレクトリ（``renders/<method>/``）。"""

    options: Mapping[str, object] = field(default_factory=dict)
    """方式固有のオプション（``renderers/registry.yaml`` の ``options`` 由来）。"""


@dataclass(frozen=True, slots=True)
class Asset:
    """レンダラが生成した 1 つの図。``renders/<method>/index.json`` に集約される。"""

    pattern_id: str
    method: str
    path: Path
    """``out_dir`` からの相対パス。"""
    title: str
    kind: AssetKind = "svg"
    """``report.html`` への埋め込み方。``svg`` は inline SVG、``html`` はそのまま HTML 断片。"""
    caption: str = ""
    width: int | None = None
    height: int | None = None
    warnings: tuple[str, ...] = ()

    def as_record(self) -> dict[str, object]:
        """``index.json`` に書く 1 エントリ分の辞書（決定論的なキー順）。"""
        return {
            "asset_path": self.path.as_posix(),
            "kind": self.kind,
            "title": self.title,
            "caption": self.caption,
            "width": self.width,
            "height": self.height,
            "method": self.method,
            "warnings": list(self.warnings),
        }


class Renderer(ABC):
    """描画方式 1 つ分の実装。"""

    name: ClassVar[str]
    """レジストリ・CLI で使う一意名（例: ``"html"``、``"wireviz"``）。"""

    deterministic: ClassVar[bool] = True
    """同一入力で同一バイト出力を保証できるか。"""

    #: この方式が扱える ``Pattern.type`` の集合。
    supported_types: ClassVar[frozenset[str]] = frozenset()

    def supports(self, pattern_type: str) -> bool:
        """``pattern_type`` をこのレンダラが扱えるか。"""
        return pattern_type in self.supported_types

    @abstractmethod
    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset:
        """``pattern`` を図に変換し、生成したアセットのメタデータを返す。

        実装は ``ctx.out_dir`` 配下にファイルを書き、``Asset.path`` を相対パスで返すこと。
        """
        raise NotImplementedError

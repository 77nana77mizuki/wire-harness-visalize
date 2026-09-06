"""レンダラ層。``DataPatternModel`` の各 ``Pattern`` を図アセットへ純変換する。

新しい描画方式は ``Renderer`` を実装し ``renderers/registry.yaml`` に登録するだけで足せる
（コア無改修）。詳細は ``docs/03-architecture.md`` §B。
"""

from datapattern.render.base import Asset, RenderContext, Renderer

__all__ = ["Asset", "RenderContext", "Renderer"]

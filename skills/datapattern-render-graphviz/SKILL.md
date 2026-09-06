---
name: datapattern-render-graphviz
description: >-
  DataPatternModel の circuit / option_config パターンを Graphviz DOT に変換し、
  `dot` CLI で SVG 化するレンダラ。接続グラフや option 決定木を描きたいとき、
  または graphviz レンダラを直したいときに参照する。
---

# datapattern-render-graphviz

- 実体: `src/datapattern/render/graphviz_renderer.py`
- 対応: `circuit`（接続グラフ）/ `option_config`（決定木）
- 依存: `dot`（Graphviz バイナリ）。**Python の `graphviz` パッケージは使わない**（`dot` を subprocess 起動）
- 未導入なら `renderers/registry.toml` の `requires=["dot"]` によりレジストリがスキップ → `html` にフォールバック

## 変換

| pattern | DOT |
|---------|-----|
| `circuit` | connectivity のノード（device/connector=box, splice=point）＋ 無向エッジ（`dir=none`）。`via` 経由は 2 ホップに分解。ラベル = gauge / color / shield |
| `option_config` | root（option expression, oval）→ variantMatrix の各行を leaf（resolvesTo）に。エッジラベル = 行の expr |

## 決定論

- ノード・エッジは `id` / `(source,target,via)` で安定ソート
- `graph [ordering=out]`、engine は `dot` 固定
- 出力 SVG は `<svg` より前（XML 宣言・DOCTYPE・graphviz バージョンコメント）を落とす
- 同一マシンでは 2 回実行してバイト一致（`tests/test_graphviz_renderer.py::test_render_svg`）
- クロスマシンのゴールデンは Graphviz バージョン差で揺れるので取らない（構造 assert のみ）

## テスト

`tests/test_graphviz_renderer.py`。`_dot_circuit` / `_dot_option_config` の生成は常時テスト、
SVG 化は `shutil.which("dot")` があるときだけ（`pytest.mark.skipif`）。

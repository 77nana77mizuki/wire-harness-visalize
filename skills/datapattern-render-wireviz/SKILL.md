---
name: datapattern-render-wireviz
description: >-
  DataPatternModel の circuit パターンを WireViz YAML に変換し、`wireviz` CLI で
  ハーネス風の接続図（SVG）を生成するレンダラ。回路トポロジをハーネス図で見せたいとき、
  または wireviz レンダラを直したいときに参照する。
---

# datapattern-render-wireviz

- 実体: `src/datapattern/render/wireviz_renderer.py`
- 対応: `circuit` 専用
- 依存: `wireviz`（**GPLv3。import せず** CLI を subprocess 起動）。未導入ならレジストリがスキップ
- ライセンス方針は `docs/02` §B-7

## 変換（`wireviz_yaml(pattern)`）

- connectivity の各ノード → `connectors:` エントリ
  - device / connector: `pincount`（`pincount` or `len(pinlabels)` or 1）、`pinlabels`
  - splice: `style: simple`, `pincount: 1`
- 各エッジ → `cables:` の 1 芯ケーブル（`gauge` / `colors` / `shield`）。`via` 経由は 2 本に分割
- `connections:` はエッジごとに `connector — cable — connector`（`via` は間に splice）
- ピン参照: `X1.GND` の `GND` は、そのノードの `pinlabels` にあれば 1 始まり番号に解決、無ければ `1`

## 決定論

- ノード `id` 昇順、エッジ `(source,target,via)` 昇順
- ケーブル名は `W<edge index>_<segment>` で固定
- YAML 文字列スカラーは全てシングルクォート（`_q`）
- SVG は `<svg` 前を落とす

## 制約 / 注意

- WireViz は条件分岐・150% を扱えない（`docs/02` §B-3-1）。本ツールは 100% 解決済みを渡すので問題なし
- 3-way 以上のスプライスは WireViz 側で名前付きテンプレートが要る。複雑なトポロジは `graphviz` にフォールバックする方が無難（`renderHints.preferredMethods` で `["graphviz","wireviz"]` の順にするなど）

## テスト

`tests/test_wireviz_renderer.py`。YAML 生成は常時テスト、`wireviz` CLI 呼び出しは
インストール時のみ（`skipif`）。

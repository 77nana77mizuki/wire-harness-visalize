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
- 依存: `wireviz`（**GPLv3。import せず** CLI を subprocess 起動）。pyproject には入れない
  （arms-length を保つ）。使いたい人が各自入れる: `pipx install wireviz` もしくは `uv pip install wireviz`
- 未導入ならレジストリがスキップ → `--method auto` は `graphviz` / `html` を選ぶ
- CLI 呼び出し: `wireviz -f s -o <dir> -O <name> <yml>`（`-o` は出力ディレクトリ、`-O` は拡張子なしのファイル名）
- ライセンス方針は `docs/02` §B-7

## 変換（`wireviz_yaml(pattern)`）

- connectivity の各ノード → `connectors:` エントリ（splice は `style: simple` / `pincount: 1`）
- **cable のグルーピング**: `via` を共有し端点ペアが同じエッジ群は **1 本の多芯ケーブル**に
  （マルチコアが `wirecount: 3` / `colors: [BK, BN, BU]` になる）。それ以外は 1 芯ケーブル
- 一度も端点にならない `via` 名だけがケーブル扱い。端点にもなる名前（例: overbraid のドレン元）は connector
- `gauge`: 数値は `0.5 mm2`、`AWG20` は `20 AWG`（WireViz は裸の文字列を受け付けない）
- `colors`: IEC 略号はクォートしない（`[BK, RD]`）
- ピン参照: `X1.GND` の `GND` は pinlabels にあれば 1 始まり番号、数字ならそのまま、無ければ `1`
- `connections` は `- connector: [pins]` / `- cable: [wires]` / `- connector: [pins]` のリスト形式

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

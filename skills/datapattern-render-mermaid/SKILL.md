---
name: datapattern-render-mermaid
description: >-
  DataPatternModel の circuit / option_config を Mermaid 記法に変換し mermaid-cli (mmdc) で
  SVG 化するレンダラ。軽量な図が欲しいとき、または「疎結合の実証」として新レンダラの
  追加手順を確認したいときに参照する。
---

# datapattern-render-mermaid

**疎結合の実証枠**。この方式を足すのに変更したのは 4 ファイルだけ:

1. `src/datapattern/render/mermaid_renderer.py`（このレンダラ）
2. `src/datapattern/renderers/registry.toml`（`[[renderer]]` を 1 個）
3. `skills/datapattern-render-mermaid/SKILL.md`（これ）
4. `tests/test_mermaid_renderer.py`

`DataPatternModel` / JSON Schema / `report.py` / `render/pipeline.py` / `render/registry.py` /
既存レンダラは **一切触っていない**。同じ手順で `schemdraw`（MIT、`import` 可）や
`drawio`（`drawpyo`）も足せる。

## 変換

| pattern | Mermaid |
|---------|---------|
| `circuit` | `flowchart LR`。ノード（splice は `((..))`）＋ リンク（ラベル = gauge/color/shield）。`via` は 2 ホップ |
| `option_config` | `flowchart TD`。`root` → 各 variantMatrix 行を leaf に。矢印ラベル = expr |

## 依存 / フォールバック

- `mmdc`（`npm i -g @mermaid-js/mermaid-cli`）。`requires = ["mmdc"]`
- 未導入なら `Registry` がスキップ → `--method auto` は `graphviz` か `html` を選ぶ

## 決定論

- ノード / エッジは安定ソート、ノード id は `n_<sanitized>` で固定
- 出力 SVG は `<svg` 前を落とす

## 補足

自己完結 `report.html` に mermaid をそのまま埋める（`<pre class="mermaid">` ＋ mermaid.js）案もあるが、
それはテンプレート（コア）側の変更になる。ここでは他レンダラと同じ「記法 → CLI → SVG」に揃えた。

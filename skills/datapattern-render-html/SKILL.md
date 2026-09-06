---
name: datapattern-render-html
description: >-
  DataPatternModel の各パターンを、外部ツール不要・完全決定論的に HTML 断片（表・カード）へ
  変換する既定レンダラ。option_config / property_set / circuit の 3 分類すべてに対応。
  レンダラを新設・改修するとき、または report.html の図の見た目を変えるときに参照する。
---

# datapattern-render-html

## 位置づけ

- レンダラ契約（`docs/03-architecture.md` §B）の実装。実体は `src/datapattern/render/html_renderer.py`。
- **既定 / フォールバック**。依存ゼロ（Python 標準ライブラリの `html.escape` のみ）、完全決定論。
- `wireviz` / `graphviz` 等が使えない環境でも必ず動く土台。

## 入出力

- 入力: 1 つの `datapattern.model.Pattern` + `RenderContext(out_dir=...)`
- 出力: `out_dir/<pattern-id>.html`（`<figure class="dp-figure dp-<type>">` 断片）と、
  `render_patterns()` 経由で `out_dir/index.json`
- `Asset.kind == "html"`。`report.py` は `| safe` でそのまま埋め込む（断片側で escape 済み）

## 分類ごとの描画

| type | 生成物 |
|------|--------|
| `option_config` | option expression の表示 + variantMatrix の表（option 値の組 → 解決後オブジェクト） |
| `property_set` | propertyExpectations の表（対象 / プロパティ / 期待値 / 理由）+ capitalObjects のプロパティ表 |
| `circuit` | connectivity のノード表・接続表（from / to / 経由 / 断面積 / 色 / シールド）※簡易フォールバック |

## 決定論のルール（守ること）

- コレクションは安定ソート（ノードは `id` 昇順、プロパティは `sorted(items())`）
- 乱数・時刻・絶対パスを出力に入れない
- 変更したら `UPDATE_GOLDEN=1 uv run pytest tests/test_report.py` でゴールデン更新し、差分をレビュー

## よくある変更

- 表の列を足す → `_table(headers, rows)` の呼び出しを直す
- 新しい `type` を足す → `_BUILDERS` にビルダ関数を追加し `supported_types` は自動反映
- 見た目（CSS）は `src/datapattern/templates/report.html.j2` の `<style>` 側（断片は class のみ持つ）

## テスト

`tests/test_html_renderer.py`（断片の内容・エスケープ・決定論・index.json 形状）、
`tests/test_report.py`（組立・ゴールデン）。

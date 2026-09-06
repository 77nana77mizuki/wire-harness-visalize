---
name: capital-datapattern-report
description: >-
  Capital Logic の Java アドオンから、テスト用データパターンの図つき HTML レポートを
  端から端まで作る。アドオンのソースを渡されて「テストのデータパターンを洗い出してレポートに
  して」と言われたらこれを使う。内部で capital-addon-analysis と各レンダラ skill を呼ぶ。
---

# capital-datapattern-report

アドオンソース ＋ 前提情報 → `out/report.html`。

## パイプライン（`docs/03-architecture.md` §A）

```
[1] datapattern run --addon <src> --out out/     ← 決定論（ingest + scan）
        → out/workspace/{manifest.json, evidence.json, datapatterns.template.json}
[2] capital-addon-analysis skill                  ← LLM（唯一の非決定論パート）
        evidence.json + ソース + 前提メモ → out/workspace/datapatterns.json
        （template.json を出発点に patterns[] を埋める。datapattern validate を通す）
[3] datapattern run --patterns out/workspace/datapatterns.json --out out/   ← 決定論（render + report）
        → out/report.html
```

## 手順

1. アドオンのソースディレクトリと前提メモを確認する。
2. `[1]` を実行。`evidence.json` の `pluginTypeGuess` と findings に目を通す。
3. `capital-addon-analysis` skill を起動して `datapatterns.json` を作る。
   - `addon.name` を正しい名前に、`generatedFrom.evidenceHash` は `[1]` の出力（`prepare` ログ）に合わせる。
   - `datapattern validate out/workspace/datapatterns.json` が通ることを必ず確認。
4. `[3]` を実行。`--method` は既定 `html`（依存ゼロ・決定論）。
   図の方式を増やしたい場合は `renderers/registry.yaml` を見て、対応する
   `datapattern-render-*` skill を参照（`wireviz` / `graphviz` など。未導入なら `html` に自動フォールバック）。
5. `out/report.html` をユーザーに渡す。レビュアー向けにサマリと網羅範囲が入っているか確認する。

## 判断のポイント

- パターン方式の選択は `renderHints.preferredMethods` に載せる（分類 B → `["wireviz","graphviz","html"]` など）。
  最終的にどれで描かれたかは `out/renders/*/index.json` と `report.html` フッターで確認できる。
- `datapatterns.json` は成果物。`out/workspace/` に残し、レポートと一緒に扱う。
- 決定論チェック: `[1]` `[3]` を 2 回流して差分が無いこと（テスト `test_orchestrate.py::test_run_is_deterministic` と同じ考え方）。

## 関連 skill

- `capital-addon-analysis` — `[2]` の中身
- `datapattern-render-html` / `datapattern-render-wireviz` / `datapattern-render-graphviz` — `[3]` の描画

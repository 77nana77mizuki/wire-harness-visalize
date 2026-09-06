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
[3] datapattern run --patterns <datapatterns.json> --out out/ --method <選択>   ← 決定論（render + report）
        → out/report.html
```

## 手順

1. アドオンのソースディレクトリと前提メモを確認する。
2. `[1]` を実行。`evidence.json` の `pluginTypeGuess` と findings に目を通す。
3. `capital-addon-analysis` skill を起動して `datapatterns.json` を作る。
   - `addon.name` を正しい名前に、`generatedFrom.evidenceHash` は `[1]` の `prepare` ログに合わせる。
   - `datapattern validate out/workspace/datapatterns.json` が通ることを必ず確認。
4. **どの描画方式を使うかユーザーに確認する**（次節）。決めた値を `[3]` の `--method` に渡す。
5. `[3]` を実行。`out/report.html` をユーザーに渡す。サマリと網羅範囲が入っているか確認する。

## 描画方式の選択（手順 4）

`datapattern` に登録済みの方式を `datapattern schema` ではなく次で確認できる:

```sh
datapattern render --help          # 説明
python -c "from datapattern.render.registry import load_registry; \
  print([(e.name, e.available) for e in load_registry().entries])"
```

| 方式 | 内容 | 依存 |
|------|------|------|
| `html` | 表（既定・常時） | なし |
| `svg` | ゼロ依存の簡易 SVG | なし |
| `graphviz` | 抽象接続グラフ / option 決定木 | `dot` |
| `wireviz` | ハーネス図（色つき電線・ピンアウト） | `wireviz`（GPLv3） |
| `mermaid` | Mermaid フローチャート | `mmdc` |
| `schemdraw` | IEC 回路図シンボル | `schemdraw`（py） |
| `drawio` | 編集可能 .drawio（画像でなくファイル） | なし |

ユーザーに提示して選んでもらい、`--method` に渡す:

- `--method all` … 使える方式を**全部**（レポートで方式タブ比較）
- `--method auto` … パターンごとに 1 つ自動選択（`renderHints.preferredMethods` 優先）
- `--method wireviz,graphviz,html` … カンマ区切りで指定

`renderHints.preferredMethods`（`datapatterns.json` 側）は `auto` / タブ順の優先度に効く。
未導入の方式は自動スキップされ `html` に落ちる。

## 判断のポイント

- `datapatterns.json` は成果物。`out/workspace/` に残し、レポートと一緒に扱う。
- どれで描かれたかは `out/renders/index.json`（`entries[pattern-id]` は配列）で確認。
- 決定論チェック: `[1]` `[3]` を 2 回流して差分が無いこと。

## 関連 skill

- `capital-addon-analysis` — `[2]` の中身
- `datapattern-render-{html,svg,graphviz,wireviz,mermaid,schemdraw,drawio}` — `[3]` の描画

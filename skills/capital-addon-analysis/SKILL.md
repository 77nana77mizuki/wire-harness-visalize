---
name: capital-addon-analysis
description: >-
  Capital Logic の Java アドオンのソースと static_scan の evidence.json から、
  そのアドオンをテストするために必要なデータパターン（DataPatternModel / datapatterns.json）を
  洗い出す。アドオンのテスト設計・データパターン洗い出しを頼まれたら使う。
---

# capital-addon-analysis

Java アドオンソース ＋ 前提情報 → **`datapatterns.json`（DataPatternModel）** を作る。
ドメイン知識は `docs/01-capital-logic-research.md`、分類は `docs/02` §A、契約は `docs/03` §E。

## 手順

1. **決定論パートを先に回す**（LLM がやり直す必要がないように）:
   ```sh
   uv run datapattern scan <アドオンのソースdir> --out out/
   # → out/workspace/manifest.json, out/workspace/evidence.json
   ```
2. `evidence.json` と、必要なら該当ソース本文を読む。前提メモ（仕様書等）も読む。
3. 下の「evidence → パターン」表に従ってパターン候補を出す。
4. option コードが絡むなら組合せは自分で書かず生成させる:
   ```sh
   uv run datapattern combos --codes OPT_A,OPT_B,OPT_C --exclusive OPT_A:OPT_B
   ```
   出力の `expr` を `variantMatrix[].expr` に使う。
5. `datapatterns.json` を書く。**必ず**:
   ```sh
   uv run datapattern validate datapatterns.json
   ```
6. レポート生成まで一気にやるなら `capital-datapattern-report` skill へ。

## evidence → パターンの対応

| evidence の signal | 出すべきパターン |
|--------------------|------------------|
| `pluginTypeGuess=check` ＋ `verdictBranches` | 各分岐の合格側 / 違反側 / 境界（`property_set` 主体） |
| `optionApiCalls` あり | `option_config`: `combos` で全 false / 全 true / 単独 / ペアワイズ / 排他違反 |
| `collectionsIterated`（connectors, wires, splices…） | `circuit`: そのオブジェクトが 0 個 / 1 個 / 複数 / スプライス経由 / マルチコア |
| `propertyKeys`（CSA, PART_NUMBER…） | `property_set`: 未設定 / 型不一致 / 範囲外（下限・上限）/ 参照切れ / 正常テンプレート |
| `ixTypes` に `IXSplice` / `IXMulticore` / `IXShield` | `circuit`: その要素を含む / 含まない構成 |
| `pluginTypeGuess=report` | `option_config`（全構成網羅）＋ `property_set`（全属性）＋ 空設計 / 大規模 |

## 必須ルール

- `patterns[].id` はケバブケース。`type` ごとの必須項目（`docs/03` §E、スキーマの `if/then`）を満たす。
- `sourceRefs` は evidence の `refs`（`path#Lx-Ly`）をそのまま使い、根拠を追えるようにする。
- 各 `rationale` に「なぜこのパターンが必要か」、`testHints` に「境界の具体値」と
  **「何を対象外にしたか（カバレッジの外側）」**を書く。レビュアーが網羅性を判断できること。
- `connectivity` は WireViz へ写像しやすい形（`docs/03` §B-5）。
- 事実にないことを書かない。ソースから確度が低いものは `testHints` に「要確認」と明記。
- Capital Java API の正確な仕様は不明な部分がある（`docs/01` §D）。推測はそのラベルを付ける。

## 出力しないもの

- 実行時刻・環境依存パス
- `evidence.json` に無い IX 型やプロパティキーの捏造

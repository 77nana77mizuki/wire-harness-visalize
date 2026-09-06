# wire-harness-visalize

Capital Logic（Siemens Capital）の Java 製アドオン開発において、
**設計時にテスト用のデータパターンを洗い出し、図つき HTML レポートを出力する**ための基盤。

現在フェーズ: **縦串（最小 e2e）完了**（[docs/03 §H](docs/03-architecture.md#h-実装ロードマップ)）。
`datapatterns.json` → HTML レンダラ → 単一 `report.html` が生成できる。次は解析（Java 静的スキャン）。

## セットアップ / 開発

```sh
uv sync                        # 依存 + venv（Python 3.12 は uv が管理）
uv run pytest                  # テスト
uv run ruff check . && uv run ruff format --check .
uv run datapattern --help
uv run datapattern validate <datapatterns.json>          # JSON Schema 検証
uv run datapattern report <datapatterns.json> --out out/ # out/report.html を生成
uv run datapattern schema                                # 同梱 JSON Schema を出力
```

`validate` / `schema` / `render` / `report` が実働。`ingest` / `scan` / `run` は骨組み。

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [docs/01-capital-logic-research.md](docs/01-capital-logic-research.md) | Capital Logic のドメインモデル（図面 / オブジェクト / プロパティ / 150% 構成機構）と Java 拡張 API（`IX*` インターフェース、プラグイン種別）の調査。要検証事項つき |
| [docs/02-datapattern-and-rendering.md](docs/02-datapattern-and-rendering.md) | データパターン3分類（オプション構成 / 回路パターン / プロパティ設定）と、図の描画方式の評価・skill 化方針 |
| [docs/03-architecture.md](docs/03-architecture.md) | 疎結合アーキテクチャ（`DataPatternModel` を結合点にしたパイプライン、skill 構成、決定論 / LLM の切り分け、レポート要件、ロードマップ、開発環境） |

## 方針

- **疎結合**: 描画方式は `DataPatternModel`（JSON Schema）契約にぶら下がるだけ。
  skill とレンダラモジュールの追加のみで新方式を導入でき、コアは無改修。
- **決定論はスクリプト、判断は LLM**: ソース収集・静的解析・図生成・レポート組立は Python。
  ソースの意味解釈とパターン導出のみ LLM（skill）。
- **描画方式（調査結果）**: 分類 B（回路/接続トポロジ）は **WireViz**（`wireviz` CLI を
  サブプロセス起動。GPLv3 なので import しない）、分類 A/C は HTML 表 + Graphviz。
  Splice CAD は図生成にクラウド送信が必要なため不採用（データモデルのみ参考）。
  詳細は [docs/02](docs/02-datapattern-and-rendering.md#b-図の描画方式の評価)。

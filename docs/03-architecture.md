# 03. アーキテクチャ（将来実装の設計）

> 前提: [01-capital-logic-research.md](01-capital-logic-research.md) /
> [02-datapattern-and-rendering.md](02-datapattern-and-rendering.md)
>
> 本書は「第2弾以降で実装する」ための設計であり、第1弾ではコードは作らない。

---

## A. 疎結合パイプライン

### A-1. 全体像

**唯一の結合点 = `DataPatternModel`**（バージョン付き JSON、JSON Schema で定義）。
解析・描画・レポート組立は、この契約だけを介してやり取りする。

```text
アドオン Java ソース + 前提メモ
      │  ingest          [決定論 / Python]   作業ディレクトリを正規化しマニフェスト化
      ▼
  workspace/manifest.json
      │  static_scan     [決定論 / Python]   import / IX* 使用 / プラグイン種別 /
      ▼                                      プロパティキー / option 式呼び出し を抽出
  workspace/evidence.json
      │  capital-addon-analysis (skill)  [LLM]  同値クラス・境界値・パターンカタログを導出
      ▼                                        出力は JSON Schema 検証を必ず通す
  datapatterns.json  ◄────────────── DataPatternModel（契約）
      │  render/<method> [決定論 / Python]  model → 図アセット（SVG 等）への純変換
      ▼
  renders/<method>/index.json + renders/<method>/*.svg
      │  assemble-report [決定論 / Python]  model + renders → 自己完結 report.html（Jinja2）
      ▼
  report.html
```

### A-2. 各ステップの責務

| ステップ | 実装 | 入力 | 出力 | 決定論 |
|----------|------|------|------|:------:|
| `ingest` | Python | ソースツリー + 前提メモ | `manifest.json`（ファイル一覧・ハッシュ・メタ） | ✅ |
| `static_scan` | Python（tree-sitter-java） | `manifest.json` | `evidence.json`（機械抽出した事実） | ✅ |
| `capital-addon-analysis` | LLM skill | `evidence.json` + ソース本文 | `datapatterns.json` | ❌（要 schema 検証） |
| `render` | Python（方式別モジュール） | `datapatterns.json` | `renders/<method>/` | ✅ |
| `assemble-report` | Python（Jinja2） | `datapatterns.json` + `renders/` | `report.html` | ✅ |

---

## B. レンダラ契約（プラグイン化の肝）

新しい描画方式を「コア無改修」で足せるようにするための取り決め。

### B-1. インターフェース

`src/datapattern/render/base.py` に置く抽象基底:

```python
class Renderer(ABC):
    name: str                        # "html" / "graphviz" / "mermaid" ...
    deterministic: bool

    @abstractmethod
    def supports(self, pattern_type: str) -> bool: ...

    @abstractmethod
    def render(self, pattern: Pattern, ctx: RenderContext) -> Asset: ...
```

- 入力: `datapatterns.json`（読み込み済み `DataPatternModel`）+ レンダオプション
- 出力: `renders/<method>/<pattern-id>.svg` と `renders/<method>/index.json`
  （`pattern-id → {asset_path, title, caption, width, height, method, warnings[]}`）

### B-2. 登録

`renderers/registry.yaml` に宣言し、`render/registry.py` が読み込む:

```yaml
renderers:
  - name: html
    module: datapattern.render.html_renderer:HtmlRenderer
    supports: [option_config, property_set, circuit]
    requires: []                 # Python のみ
    deterministic: true
  - name: wireviz
    module: datapattern.render.wireviz_renderer:WirevizRenderer
    supports: [circuit, property_set]
    requires: [wireviz-cli, graphviz]   # GPLv3。import せず CLI 起動
    external_process: true
    deterministic: true
  - name: graphviz
    module: datapattern.render.graphviz_renderer:GraphvizRenderer
    supports: [circuit, option_config]
    requires: [graphviz]
    external_process: true
    deterministic: true
  - name: mermaid
    module: datapattern.render.mermaid_renderer:MermaidRenderer
    supports: [option_config, circuit]
    requires: []
    deterministic: true
```

> `external_process: true` の方式は、依存ツールをサブプロセスで起動する
> （GPLv3 コードを自社コードに `import` しないため／バージョン固定のため）。
> `requires` が満たせない環境では、レジストリがそのレンダラを自動スキップし
> `html` にフォールバックする。

### B-3. CLI

```bash
python -m datapattern.render --method graphviz --in datapatterns.json --out renders/
```

### B-4. 新方式を足す手順（例: schemdraw）

1. `src/datapattern/render/schemdraw_renderer.py` を追加（`Renderer` を実装）
2. `renderers/registry.yaml` に 1 エントリ追加
3. `skills/datapattern-render-schemdraw/SKILL.md` を追加
4. `tests/test_schemdraw_renderer.py` にゴールデンテスト

→ `model.py` / `schema` / `report.py` / 既存レンダラは**一切触らない**。

### B-5. `connectivity` サブスキーマの設計参考

`DataPatternModel.patterns[].connectivity`（分類 B 用）は、
**WireViz の YAML データモデル** と **`splice-py` の型 enum** を参考に設計する:

- ノード種別: `device` / `connector` / `splice` / `terminal` / `component`
- コネクタ: `pincount` / `pinlabels` / `pincolors`
- ケーブル/電線: `wirecount` / `gauge`（mm² or AWG）/ `colors`（IEC 60757 略号）/ `shield`
- 接続: `from` / `to`（`designator.pin` 形式）/ `via`（splice 経由）

こうしておくと `wireviz_renderer` は connectivity → WireViz YAML をほぼ機械的に写像できる。
出典: [WireViz syntax.md](https://github.com/wireviz/WireViz/blob/master/docs/syntax.md) /
[splice-py](https://github.com/splice-cad/splice-py)

---

## C. skill 構成（プロジェクト内 `skills/`）

| skill | 種別 | 役割 |
|-------|------|------|
| `capital-datapattern-report` | オーケストレータ | パイプライン全体を実行し、パターン種別に応じてレンダラを選択、最終 `report.html` を提示 |
| `capital-addon-analysis` | 解析 | Java アドオンの静的 + 意味解析手順、`DataPatternModel` の埋め方、Capital オブジェクト / プロパティ辞書（実物から漸進的に育てる） |
| `datapattern-render-html` | レンダラ | Jinja2 の表 / カード（既定・ゼロ依存） |
| `datapattern-render-wireviz` | レンダラ | ハーネス / 接続トポロジ図（`wireviz` CLI をサブプロセス起動。GPLv3） |
| `datapattern-render-graphviz` | レンダラ | 抽象接続グラフ・決定木 |
| `datapattern-render-mermaid` *(早期フォロー)* | レンダラ | 軽量・HTML 埋込 |
| `datapattern-render-schemdraw` *(早期フォロー)* | レンダラ | 回路図シンボル（IEC 60617） |
| `datapattern-render-drawio` *(任意)* | レンダラ | 編集可能な .drawio 出力 |

各レンダラ skill は「契約（B 節）＋ その方式固有の実装ノウハウ ＋ 決定論化チェックリスト
（[02 §B-5](02-datapattern-and-rendering.md#b-5-決定論化の共通ルール)）」を持つ。

---

## D. 決定論 vs LLM の切り分け

| 決定論（Python スクリプト） | LLM（skill） |
|------------------------------|--------------|
| `ingest`：ファイル収集・正規化・ハッシュ | Java ソースの**意味理解**（何を検査/操作しているか） |
| `static_scan`：AST から事実抽出 | パターンカタログの**導出**（同値クラス・境界値の設計） |
| JSON Schema 検証 | `rationale` / `testHints` / caption の**文章生成** |
| すべての**レンダリング**（model → 図は純変換） | どのレンダラを使うかの**方針判断**（最終選択はコードが検証） |
| `assemble-report`：Jinja2 組立 | — |
| レジストリ読み込み・レンダラ選択の**実行** | — |
| `combos.py`：option 組合せ生成（境界 + ペアワイズ） | どの観点・制約を組合せ生成に渡すかの**指定** |

原則: **判断は LLM、変換と検証はコード**。LLM 出力は必ず schema 検証を通してから下流へ渡す。

---

## E. `DataPatternModel` スケッチ

`src/datapattern/schema/datapattern.schema.json` で正式定義する。骨子:

```jsonc
{
  "schemaVersion": "1.0",
  "addon": {
    "name": "...",
    "pluginType": "check | action | report",
    "capitalVersion": "2207",           // 分かれば
    "sourceRefs": ["src/.../Foo.java#L10-L42"]
  },
  "generatedFrom": { "evidenceHash": "sha256:..." },
  "patterns": [
    {
      "id": "opt-cfg-001",
      "type": "option_config | circuit | property_set",
      "title": "...",
      "summary": "...",
      "rationale": "なぜこのパターンがこのアドオンのテストに必要か",
      "capitalObjects": [
        { "kind": "connector", "ref": "X1", "properties": { "partNumber": "..." } }
      ],
      "optionExpression": "OPT_A AND NOT OPT_B",         // type=option_config
      "variantMatrix": [                                  // type=option_config
        { "expr": "OPT_A=1,OPT_B=0", "resolvesTo": ["wire W1", "connector X1"] }
      ],
      "connectivity": {                                   // type=circuit
        "nodes": [{ "id": "D1", "kind": "device" }],
        "edges": [{ "from": "D1.p1", "to": "D2.p3", "via": "splice S1" }]
      },
      "propertyExpectations": [                           // type=property_set
        { "object": "wire W1", "property": "csa", "value": "0.5", "why": "下限境界" }
      ],
      "testHints": ["option 式が全 false のとき対象オブジェクトが 0 件になる"],
      "renderHints": { "preferredMethods": ["graphviz", "html"] }
    }
  ]
}
```

---

## F. `report.html` の要件

想定読者は **アドオン開発者本人** と **設計レビュー担当 / レビュアー**。

### F-1. 開発者向け

- 各パターンの `rationale` と `testHints`
- 対象 Capital オブジェクトと設定プロパティを**コピペしやすい表**で
- ソース該当箇所への参照（`addon.sourceRefs` / `pattern` 単位の参照）

### F-2. レビュアー向け

- 冒頭に**パターン一覧サマリ**（種別 × 件数、網羅マトリクス）
- 各パターンの図
- 「**なぜこの範囲で十分か / 何が対象外か**」の明示（カバレッジの根拠）

### F-3. 共通

- **単一ファイルで完結**（画像は inline SVG または data URI、外部依存なし）
- ライト / ダーク両対応
- 印刷可（A4 レイアウト崩れなし）

---

## G. 将来のリポジトリ構成

```text
pyproject.toml                       # uv, ruff, pytest, jsonschema, jinja2, graphviz(py), tree-sitter-java, allpairspy
                                     #   wireviz は実行時に CLI として要求（GPLv3 のため依存に import しない）
src/datapattern/
  __init__.py
  model.py                           # DataPatternModel の dataclass + load/validate
  schema/datapattern.schema.json     # 契約（バージョン付き JSON Schema）
  ingest.py                          # 決定論: 作業マニフェスト生成
  static_scan.py                     # 決定論: tree-sitter-java で事実抽出
  render/
    base.py                          # Renderer ABC + 契約型
    registry.py                      # registry.yaml からレンダラを discover
    html_renderer.py
    wireviz_renderer.py              # connectivity → WireViz YAML → `wireviz` CLI
    graphviz_renderer.py
  report.py                          # 決定論: Jinja2 で report.html を組立
  templates/report.html.j2
  combos.py                          # 決定論: option 組合せ（境界+ペアワイズ）生成
  cli.py                             # datapattern ingest|scan|render|report|run
renderers/registry.yaml
skills/
  capital-datapattern-report/SKILL.md
  capital-addon-analysis/SKILL.md
  datapattern-render-html/SKILL.md
  datapattern-render-wireviz/SKILL.md
  datapattern-render-graphviz/SKILL.md
tests/
  test_model.py  test_static_scan.py  test_combos.py
  test_html_renderer.py  test_wireviz_renderer.py  test_graphviz_renderer.py
  test_report.py  test_registry.py
  fixtures/                          # 手書き datapatterns.json とゴールデン出力
docs/                                # 本ドキュメント群
```

---

## H. 実装ロードマップ（第2弾以降）

| # | 内容 | 完了条件 |
|---|------|----------|
| 1 | スキャフォールド | `pyproject.toml` + `model.py` + JSON Schema + `cli.py` 骨組み、`pytest` が緑 |
| 2 | 縦串（最小 e2e） | 手書き `datapatterns.json` → `datapattern-render-html` → `report.py` → `report.html`、ゴールデンテスト |
| 3 | 解析 | `static_scan.py`（tree-sitter-java）+ `ingest.py` + `combos.py` + `capital-addon-analysis` skill |
| 4 | オーケストレータ | `capital-datapattern-report` skill で全パイプライン結線 |
| 5 | レンダラ拡充 | `wireviz`（CLI 起動）+ `graphviz` + `registry.yaml`。`wireviz` 未導入環境で `html` にフォールバックすること |
| 6 | 早期フォロー | `mermaid` / `schemdraw` / `drawio` を **skill 追加のみ**で導入（疎結合の実証） |

---

## I. 未確定事項

| 事項 | 確定方法 |
|------|----------|
| Capital Java API のパッケージ名・エントリポイント・`IX*` 一覧 | 顧客 SDK ドキュメント / 実物ソース（→ [01 §D](01-capital-logic-research.md#d-要検証事項実物ソース顧客-sdk-ドキュメントで確定)） |
| custom check / action / report の実装契約 | 同上 |
| option expression / configuration の API 読み出し方法 | 同上 |
| ダミー `examples/sample-addon` を作るか | 第2弾で判断（現時点は不要） |
| 実装言語の細部（uv か Poetry か、Python 最低バージョン） | 第2弾スキャフォールド時 |

---

## J. 開発環境（導入済みの Claude Code plugin）

「公式マーケットプレイス plugin ＋ プロジェクト内 `skills/` の自作」方針。
以下は `claude-plugins-official`（anthropics/claude-plugins-official）から **user スコープ**で導入済み。

| plugin | 用途 | このプロジェクトでの使いどころ |
|--------|------|--------------------------------|
| `superpowers` | harness-engineering 手法（brainstorming / writing-plans / executing-plans / subagent-driven-development / TDD / systematic-debugging / requesting・receiving-code-review / writing-skills / using-git-worktrees） | 第2弾以降の実装を plan→work→review サイクルで進める土台。`test-driven-development` で縦串→レンダラを回す |
| `skill-creator` | skill の新規作成・改善・eval | `skills/` 配下の自作 skill（`capital-datapattern-report` 等）の雛形生成と評価 |
| `pyright-lsp` | Python 型チェック / コードインテリジェンス（LSP、モデルコンテキスト消費なし） | `src/datapattern/` の型安全性 |
| `pr-review-toolkit` | PR レビュー用エージェント群（code-reviewer / silent-failure-hunter / code-simplifier / comment-analyzer / pr-test-analyzer / type-design-analyzer） | レンダラ契約・`DataPatternModel` の型設計レビュー、決定論化の検証 |

> 自作予定の skill は [§C skill 構成](#c-skill-構成プロジェクト内-skills) を参照。
> `superpowers` の `writing-skills` / `writing-plans` と `skill-creator` を併用して作る。

出典: [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) /
[superpowers](https://github.com/anthropics/claude-plugins-official) /
[Diagrams Plugins for Claude Code（Claude Skills Hub）](https://claudeskills.info/plugins/category/diagrams/) /
[jgraph/drawio-mcp（将来 drawio レンダラを検討する場合の参考）](https://github.com/jgraph/drawio-mcp/blob/main/plugins/claude-code/README.md)

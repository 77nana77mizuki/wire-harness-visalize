# 02. データパターンの分類と 図の描画方式

> 前提知識は [01-capital-logic-research.md](01-capital-logic-research.md)。
> アーキテクチャは [03-architecture.md](03-architecture.md)。

---

## A. データパターン3分類

アドオンのソースと前提情報から洗い出す「テスト用データパターン」を、次の 3 種に分類する。
（3 種すべてを対象とする。`DataPatternModel.patterns[].type` の値になる）

| # | `type` | 内容 | 主な図の形 |
|---|--------|------|-----------|
| A | `option_config` | オプション / バリアント構成パターン | マトリクス表・決定木 |
| B | `circuit` | 回路 / サブ回路の設計パターン | 接続グラフ・ハーネス図・回路図 |
| C | `property_set` | 部品・回路のプロパティ設定パターン | プロパティカード・表 |

### A-1. 分類 A: `option_config`（オプション / バリアント構成）

**狙い**: 150% 設計における option expression が、どの 100% 構成を生むかを網羅する
（→ [01 §A-5](01-capital-logic-research.md#a-5-構成メカニズム150-設計--データパターンの源泉)）。

同値クラス / 境界値の例:

| 観点 | パターン |
|------|----------|
| 式の真理値 | 全 option が true / 全 false / 一部 true |
| 論理構造 | 単一コード / AND / OR / NOT / ネスト式 |
| 排他制約 | 相互排他な option を同時 true にした異常系 |
| 未知コード | 定義されていない option code を含む式 |
| 既定 | option 未指定（デフォルト構成） |
| 多重度 | 同一オブジェクトに複数の option 割り当て |

アドオンソースからの導出シグナル: option / variant / module code を扱う API 呼び出し、
式評価ロジック、構成切替に依存する分岐。

> **組合せ列挙は決定論的スクリプトで**: option コードの妥当な組合せ（全網羅は爆発するので
> **境界値 + ペアワイズ**）は Python で機械生成できる（`allpairspy`、Microsoft PICT 等）。
> LLM は「どの観点を試すか」を設計し、実際の組合せ表はコードが吐く。

### A-2. 分類 B: `circuit`（回路 / サブ回路の設計パターン）

**狙い**: アドオンが処理対象とする回路トポロジのバリエーションを網羅する。

同値クラス / 境界値の例:

| 観点 | パターン |
|------|----------|
| 最小構成 | device 2 個 + 電線 1 本 |
| 分岐 | splice を含む / 含まない |
| ケーブル | multicore / shield / overbraid を含む |
| 接続形態 | daisy chain、highway 経由、point-to-point |
| 論理 vs 物理 | signal のみ / conductor 割当済み |
| 異常系 | 未接続ピン、ループ、宙ぶらりんの splice |

アドオンソースからの導出シグナル: connector / pin / wire / splice のコレクション走査、
接続関係をたどるコード、トポロジ判定ロジック。

### A-3. 分類 C: `property_set`（プロパティ設定パターン）

**狙い**: オブジェクト種別ごとに「設定すべきプロパティのテンプレート」と必須項目を示し、
設定漏れ・不正値のテストデータを列挙する。

同値クラス / 境界値の例:

| 観点 | パターン |
|------|----------|
| 必須欠落 | part number 未設定、signal 名 空 |
| 型 / 書式不一致 | 数値項目に文字列、命名規則違反 |
| 範囲外 | CSA が下限未満 / 上限超過、長さ 0 or 負 |
| 参照整合性 | library part 参照切れ、存在しない cavity 参照 |
| 正常テンプレート | 全必須項目を妥当値で埋めた基準ケース |
| 拡張属性 | カスタム属性あり / なし、多言語値 |

アドオンソースからの導出シグナル: getter/setter 名、属性キーの文字列リテラル、
バリデーション条件、必須チェック。

### A-4. アドオン種別との対応（仮説）

| アドオン種別 | 重点分類 |
|--------------|----------|
| custom check（DRC） | C（違反データ）＞ B ＞ A |
| custom action | B（選択対象の多様性）＞ A（option 展開状態）＞ C |
| custom report | A（全構成）＞ C（全属性網羅）＞ B |

---

## B. 図の描画方式の評価

### B-1. 前提: 何を描くのか

本ツールが描くのは Capital の設計そのものではなく、**「テストで用意すべきデータパターンの説明図」**。
つまり:

- 実データより**小さく単純**（1 パターン = 数個〜十数個のオブジェクト）
- **静的**（バリアントは描画前に 100% へ解決済み）
- **説明が主目的**（レビュアーが網羅性を判断できること）

この前提だと「フル機能のハーネス CAD」は不要で、
**プログラムから決定論的に生成でき、単一 HTML に埋め込める**方式が向く。

### B-2. 汎用「Diagram as Code」方式

| 方式 | 対応パターン | 依存 | 決定論性 | 手直し | 判定 |
|------|-------------|------|----------|--------|------|
| **HTML/CSS + Jinja2** | A, C（B は簡易） | なし（Python のみ） | ◎ | HTML 編集 | **第1弾・既定** |
| **Graphviz（DOT）** | B（抽象グラフ）, A（決定木） | `graphviz` バイナリ | ○（engine 固定・全 sort・ID 固定で安定） | 低 | **第1弾** |
| **Mermaid** | A（tree）, B（graph）, ER | レンダラ側のみ（HTML に生テキスト埋込） | ○ | 低 | 早期フォロー（低コスト） |
| **schemdraw** | B（電気回路図シンボル） | `schemdraw` + `matplotlib` | ◎（命令的配置） | 中 | 早期フォロー（回路図が要るとき） |
| **draw.io（`drawpyo`）** | A, B, C | `drawpyo`（Python, GPLv3） | ◎（XML 直生成） | ◎（drawio で編集、Confluence 貼付） | 任意（編集必須なら） |
| **D2** | B, C（`sql_table`） | Go バイナリ | △（自動レイアウトが実行間で揺れる） | 中 | 見送り |
| **PlantUML** | 構造図全般 | JVM | ○ | 低 | 見送り（JVM 依存） |

### B-3. ドメイン特化ツール（WireViz / Splice CAD 他）

ユーザー提案の WireViz・SpliceCAD を含め、配線・ハーネス専用ツールを評価した。

#### B-3-1. WireViz — ★ 分類 B の第一候補

| 項目 | 評価 |
|------|------|
| 何をするか | connectors / cables / connections を YAML（または Python dict）で記述 → **Graphviz 経由で配線図を生成**。コネクタのピンアウト、電線色（IEC 60757 / DIN 47100 等）、ゲージ（mm²↔AWG 自動換算）、シールド、BOM を扱う |
| 出力 | **SVG / PNG / .gv / HTML / BOM（TSV）** |
| 実装 | 純 Python + Graphviz。Python 3.7+。CLI（`wireviz foo.yml`）と Python API の両方 |
| 決定論性 | ◎（入力が同じなら Graphviz 出力も安定。乱数なし） |
| 本ツールとの相性 | 分類 B（回路 / サブ回路のトポロジ）に**ほぼ専用**。connector・cavity・wire・splice・multicore・shield という Capital の語彙とほぼ 1:1。ピンアウト表はそのまま分類 C の可視化にも使える |
| ライセンス | **GPLv3**。→ 自社の（プロプライエタリな）コードに `import` せず、**CLI をサブプロセス起動**して疎結合に保つ（アームズレングス。最終判断は法務） |
| 制約（できないこと） | 条件分岐 / バリアント（← 本ツールは描画前に 100% へ解決するので問題なし）、システム全体の配線、階層グループ、3-way スプライスは名前付きテンプレートインスタンスが必要、任意の SVG パス |
| バージョン | 活発にメンテ（2025 年に 0.41 系）。Hackaday / Adafruit / FOSDEM 2025 で取り上げ |

**採用方針**: `datapattern-render-wireviz` を第1弾レンダラに含める。
`DataPatternModel.patterns[].connectivity` を WireViz YAML へ決定論変換 → `wireviz` CLI → SVG。

#### B-3-2. Splice CAD / `splice-py` — 参照のみ（コア採用は不可）

| 項目 | 評価 |
|------|------|
| 何をするか | 型安全な Python ライブラリ（`splice-py`, **MIT**）で harness を記述し、**Splice 互換 JSON** を生成。コネクタ / ケーブル / コア / フライングリード / ヒューズ・リレー等の型を持つ |
| 描画 | **レンダリング（SVG / PDF / CSV）は Splice のクラウドサービス側**。`splice-py` 単体は JSON 生成のみ。MCP の "live bridge" はローカルだがブラウザアプリ必須 |
| ブロッカー | 図を得るにはハーネス JSON を **外部（splice-cad.com）へアップロード**する必要がある。Fujitsu の非公開アドオンのテストデータを外部送信するのは不可 |
| 使いどころ | `splice-py` の**データモデルは `DataPatternModel.connectivity` 設計の参考**になる（型 enum、自動デジグネータ採番 X1/F1/CB1、事前バリデーション） |

#### B-3-3. その他（いずれも本用途には過剰 or 不適）

| ツール | 概要 | 判定 |
|--------|------|------|
| Harness Studio / Wiring Studio | KBL/VEC/X2ML の import・比較・修復・検証・変換ができる商用 Web ハーネスエディタ。AI 修復機能あり | 自動レポート生成には不向き。フォーマット変換の参照として記憶 |
| QElectroTech | GPL の GUI 回路図エディタ（IEC 60617 シンボル） | スクリプト生成に不向き |
| KiCad / 各種 EDA | 基板・回路設計 | 目的が違う |
| Wirely | WireViz を Flask でラップした Web ツール | WireViz を直接使うので不要 |

### B-4. 分類 × 推奨方式（更新版）

| 分類 | 第1候補 | 補助 |
|------|---------|------|
| A `option_config` | **HTML 表**（構成マトリクス）。組合せは `allpairspy`/PICT で決定論生成 | Graphviz / Mermaid の決定木 |
| B `circuit` | **WireViz**（CLI サブプロセス。ハーネス / 接続トポロジ） | Graphviz（抽象グラフ）、schemdraw（回路図シンボル） |
| C `property_set` | **HTML プロパティカード / 表**（Jinja2） | WireViz のピンアウト表、draw.io（編集可能） |

### B-5. 実装順とスキル化方針

- **第1弾で skill 化**: `datapattern-render-html` / `datapattern-render-wireviz` /
  `datapattern-render-graphviz`
- **早期フォロー**: `datapattern-render-mermaid`（低コスト）/
  `datapattern-render-schemdraw`（回路図シンボル）/ `datapattern-render-drawio`（編集可能成果物）
- いずれも **コア（`DataPatternModel` 契約・パイプライン）を一切変更せず、skill と
  レンダラモジュールの追加のみ** で導入できる
  （→ [03 §B レンダラ契約](03-architecture.md#b-レンダラ契約プラグイン化の肝)）。

### B-6. 決定論化の共通ルール

- すべてのコレクションを安定ソート（キーは pattern id / object id）
- ノード / エッジ ID はパターンキーから決定的に導出（乱数・実行時刻を使わない）
- 外部ツール（Graphviz、`wireviz` CLI）は**バージョンを固定**し、サブプロセスで起動
- 出力にタイムスタンプを入れない（入れるならフッター1箇所のみ、テストでは除外）
- 生成した SVG / HTML をゴールデンファイルとしてスナップショットテスト
- **外部 SaaS へデータを送る方式は採用しない**（Splice クラウド等）

### B-7. ライセンス整理

| 依存 | ライセンス | 扱い |
|------|-----------|------|
| Graphviz | EPL 1.0 | サブプロセス起動。問題なし |
| WireViz | GPLv3 | **`import` しない。`wireviz` CLI をサブプロセス起動**。生成物（SVG）は成果物に埋め込み可 |
| `drawpyo` | GPLv3 | 採用するなら CLI/別プロセス分離を検討 |
| schemdraw | MIT | `import` 可 |
| `splice-py` | MIT | データモデル参照のみ。実行時依存にしない |
| Jinja2 / allpairspy | BSD 系 | `import` 可 |

> GPLv3 ツールを**サブプロセスとして呼ぶ**構成は一般に「アームズレングス」とみなされるが、
> 配布形態（社内利用か外販か）で結論が変わるため、最終判断は法務レビューを通すこと。

### B-8. 出典

- [WireViz（GitHub, GPLv3）](https://github.com/wireviz/WireViz)
- [WireViz README](https://github.com/wireviz/WireViz/blob/master/docs/README.md) /
  [WireViz syntax.md（YAML データモデル全仕様）](https://github.com/wireviz/WireViz/blob/master/docs/syntax.md)
- [WireViz（PyPI）](https://pypi.org/project/wireviz/)
- [FOSDEM 2025: WireViz – Beautiful wiring documentation](https://archive.fosdem.org/2025/schedule/event/fosdem-2025-4612-wireviz-beautiful-wiring-documentation/)
- [Create wiring harnesses using WireViz 0.41（Adafruit, 2025-10）](https://blog.adafruit.com/2025/10/07/create-wiring-harnesses-using-wireviz-0-41/)
- [wireviz-web（AGPL）](https://github.com/wireviz/wireviz-web)
- [Splice CAD](https://splice-cad.com/) /
  [splice-py（GitHub, MIT）](https://github.com/splice-cad/splice-py) /
  [splice-cad-mcp（データフロー・オフライン可否）](https://github.com/splice-cad/splice-cad-mcp)
- [Splice CAD: Cable Harness Design Tool（Hackaday, 2025-07）](https://hackaday.com/2025/07/07/splice-cad-cable-harness-design-tool/)
- [Harness Studio](https://harness-studio.app/) / [Wiring Studio](https://wiring.studio/)
- [10 Options for Drawing Wiring Schematics/Harnesses（HP Academy）](https://www.hpacademy.com/technical-articles/8-options-for-drawing-wiring-schematicsharnesses-in-motorsport-applications/)
- [A Simple Web-Based Wiring Harness Tool（Hackaday, Wirely）](https://hackaday.com/2022/07/15/a-simple-web-based-wiring-harness-tool/)
- [QElectroTech](https://qelectrotech.org/)
- [drawpyo（GitHub）](https://github.com/MerrimanInd/drawpyo)
- [Schemdraw ドキュメント](https://schemdraw.readthedocs.io/)
- [Mermaid vs D2 vs Graphviz（Diagrams.so）](https://diagrams.so/learn/diagram-as-code-comparison)
- [allpairspy（PyPI, ペアワイズ生成）](https://pypi.org/project/allpairspy/)

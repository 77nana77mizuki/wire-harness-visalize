# 01. Capital Logic 調査 — ドメインモデルと Java 拡張 API

> 本書は「Capital Logic のアドオン開発で、テストに必要なデータパターンを洗い出す」ための
> 前提知識をまとめたもの。関連文書:
> [02-datapattern-and-rendering.md](02-datapattern-and-rendering.md) /
> [03-architecture.md](03-architecture.md)

---

## A. Capital Logic ドメインモデル

### A-1. Capital Logic とは

Siemens Capital（旧 Mentor Graphics Capital）の一機能で、**論理コネクティビティ設計（signal）**と
**物理配線設計（wire / conductor）**の両方をオーサリングするグラフィカル環境。
論理コンセプト設計から下流のハーネス設計（Capital Harness Designer）へ連続する
「correct-by-construction（作った時点で正しい）」フローの起点となる。

### A-2. 図面（ダイアグラム）種別

| 図面種別 | 概要 |
|----------|------|
| 論理コネクティビティ図 | signal（論理信号）ベースの接続を表現。物理的な電線は未確定 |
| 配線図（wiring / wire diagram） | conductor（電線）を配置した物理接続図 |
| ブロックビュー / アセンブリビュー | サブシステムやアセンブリを箱で抽象化した俯瞰図 |
| ハイウェイ接続図 | 多数の信号を束ねた highway 接続の表現 |
| （下流）ハーネス図 | Capital Harness Designer 側。Logic の出力を受けて製造用ハーネスへ展開 |

### A-3. オブジェクト種別

設計コンテナ:

- project / design / diagram / revision / **build list**（互換性・構成の集合）

接続要素:

- **device**（機器）、**pin**、**connector**、**cavity**（コネクタ内の端子穴）
- **signal / net**（論理信号）
- **wire / conductor**（物理電線）
- **splice**（分岐点）、**multicore**（多芯ケーブル）、**shield**（シールド）、
  **overbraid**（オーバーブレード）、**daisy chain**（数珠つなぎ）、**highway**

ライブラリ / 共有:

- **library part**（部品ライブラリの実体）
- **shared object**（複数ダイアグラムで共有されるオブジェクト。design-wide object とは
  スコープ・振る舞いが異なる）
- **assembly** / **block**

### A-4. プロパティ / 属性（データパターンの主対象）

| カテゴリ | 例 |
|----------|-----|
| 識別・命名 | 命名規則（naming preference）で自動採番される名称、参照名 |
| 部品 | library part 参照、part number |
| 電線 | CSA（断面積）、ゲージ、色、長さ |
| 論理 | signal 名 / net 名 |
| **構成制御** | **option code / variant expression / module code / configuration** |
| 航空 | aerospace effectivity（適用号機範囲） |
| 検証 | DRC（design rule check）関連属性 |
| 拡張 | ユーザー定義のカスタム属性 |

### A-5. 構成メカニズム（150% 設計）— データパターンの源泉

1. 1 つの設計に「あり得る全構成」を盛り込む（**150% 設計**）。
2. 各オブジェクトに **option code / module code** を割り当て、**option expression**
   （例: `OPT_A AND NOT OPT_B`）で「どの構成のときに存在するか」を表現する。
3. 特定の option 値の組（**configuration / variant**）を与えると、式が解決されて
   **100% 設計（allowable configuration）**が得られる。

> **テスト設計上の意味**: 「どの option expression が、どの 100% 構成（＝どの物理オブジェクト集合）
> を生むか」の組合せが、アドオンをテストするうえでの中心的なデータパターン。
> → [02 章 分類 A（option_config）](02-datapattern-and-rendering.md#a-データパターン3分類)

### A-6. カスタマイズ / 拡張ポイント

- Capital Integration Server（SOA 連携・業務システム統合）
- custom action（ユーザー操作の追加）
- custom DRC / rule check（独自の設計ルールチェック）
- custom report（独自帳票）
- Capital Logic Report Builder（レポート定義）
- Capital E/E Reporter（Web ブラウザから設計データ・図面へアクセス）

**アドオンはこれらの拡張点に Java で実装される**（→ B 節）。

### A-7. 出典

- [Capital Logic Designer 製品ページ](https://plm.sw.siemens.com/en-US/capital/products/capital-logic-designer/)
- [論理・物理配線システム設計 blog（Siemens EE Systems）](https://blogs.sw.siemens.com/ee-systems/2023/04/04/master-logical-and-physical-wiring-systems-design-with-capital-logic-designer/)
- [Capital Logic ブローシャ（SIEMENS EDA / directindustry）](https://pdf.directindustry.com/pdf/siemens-eda/capital-logic/60189-327489.html)
- [KBL / VEC 標準（Siemens）](https://plm.automation.siemens.com/global/en/products/electrical-electronics/kblstandard.html)
- [KBL Implementation Guidelines（PROSTEP ECAD WIKI）](https://ecad-wiki.prostep.org/specifications/kbl/guidelines/)

---

## B. Capital の Java 拡張 API

### B-1. 確認できた事実

| 項目 | 内容 | 確度 |
|------|------|------|
| 言語 | **Java**（および JavaScript）プラグイン | 高 |
| 拡張点 | custom check / rule check（DRC）、custom action、custom report、UI カスタマイズ | 高 |
| オブジェクトモデル | インターフェースは **`IX` プレフィックス**（VeSys / Capital 共通。例: `IXConnector`） | 中〜高 |
| デプロイ | コンパイルした **JAR を Capital の plugins フォルダに配置**して読み込み | 中 |
| 設計思想 | forward-compatible extensions（API バージョン間の前方互換を重視） | 高 |

`IX` プレフィックスは「ユーザー記憶の "IX○○クラス"」と一致する。
`IXDevice` / `IXWire` / `IXSignal` / `IXConnector` / `IXSplice` などが存在すると推測される
（正式一覧は D 節のとおり要検証）。

### B-2. 静的解析で拾うべきシグナル（将来の `static_scan.py` 設計メモ）

| シグナル | そこから分かること |
|----------|--------------------|
| `import` 文 + `IX*` 型の使用箇所 | アドオンが触る Capital オブジェクト種別 |
| 実装インターフェース / 継承クラス / アノテーション | プラグイン種別（check / action / report） |
| プロパティアクセス（getter/setter 名、属性キー文字列リテラル） | 対象プロパティ集合 |
| option expression / variant / module code を扱う API 呼び出し | 構成パターン（分類 A）の要否 |
| DRC の合否分岐（`if`/`return`）、例外パス | 境界値・異常系パターンの候補 |
| コレクション走査（全 connector を回す等） | 対象オブジェクトの多重度・種類の広がり |

### B-3. アドオン種別ごとのテスト観点（仮説 — 実物で確定）

| プラグイン種別 | 主な入力 | テストで変えるべきもの |
|----------------|----------|------------------------|
| custom check（DRC） | 設計オブジェクトグラフ | 合格ケース / 違反ケース / 境界 / 対象外オブジェクト |
| custom action | 選択オブジェクト + パラメータ | 選択の種類・数・組合せ、Undo/Redo、option 展開状態 |
| custom report | 設計全体 or フィルタ結果 | 空設計 / 大規模 / 全オブジェクト種別網羅 / 多言語属性 |

### B-4. 出典

- [What use is an API in Capital?（Paul Johnston, Mentor blog — 現在は Siemens blog へリダイレクト）](https://blogs.mentor.com/paul_johnston/blog/2015/02/09/what-use-is-an-application-programming-interface-api-in-capital/)
- [RGBSI 求人票（Capital / VeSys 経験必須。API オブジェクトの `IX` 命名に言及）](https://www.wayup.com/i-j-RGBSI-027492245234821/)
- [Capital プラグインの配置フォルダに関する Q&A（Siemens Community）](https://community.sw.siemens.com/s/question/0D54O00008CxWwISAV/i-want-to-know-in-which-folder-the-plugins-java-file-need-to-be-added-so-that-it-will-be-loaded-in-the-capital-software)
- [Plugin Development Best Practices for Capital tools（Siemens Community 記事）](https://community.sw.siemens.com/s/article/plugin-development-best-practices-for-capital-tools-7011)
- [Capital plugin での javax.mail 利用（Siemens Community）](https://community.sw.siemens.com/s/question/0D54O00006eoDHmSAM/using-javax-mail-inside-a-capital-plugin)
- [How to Create Custom Action for Functional Design?（Siemens Community）](https://community.sw.siemens.com/s/question/0D54O00007vJFkHSAW/how-to-create-custom-action-for-functional-design)
- [E/E システムデータ管理・統合 / API（Siemens）](https://plm.sw.siemens.com/en-US/capital/ee-systems-data-integrations/data-management/)

> ⚠️ Siemens Community / blog は要ログインまたは JavaScript レンダリングのため、
> 本調査では全文を取得できていない。B 節の詳細は実物で裏取りすること（→ D 節）。

---

## C. データ交換フォーマット（参考）

アドオンの入力そのものではないが、テストデータの生成・比較で役立つ可能性がある。

| フォーマット | 概要 |
|--------------|------|
| **KBL**（Kabelbaumliste / Harness Description List） | VDA/PSI 推奨。独自動車業界標準。情報モデル + データ辞書 + XML スキーマ |
| **VEC**（Vehicle Electrical Container） | 次世代車向け。トポロジ・部品の詳細記述が可能 |
| HCV / JT | Capital Harness Analyzer が扱う可視化・解析用フォーマット |

出典: [Wiring Harness Design & Engineering（Siemens, KBL 標準）](https://plm.automation.siemens.com/global/en/products/electrical-electronics/kblstandard.html) /
[Capital Harness Analyzer](https://www.siemens.com/en-us/products/capital/offerings/wiring-harness-analyzer/) /
[4Soft kbl-model（KBL の JAXB モデル / OSS）](https://github.com/4Soft-de/kbl-model)

---

## D. 要検証事項（実物ソース・顧客 SDK ドキュメントで確定）

1. Capital Java API の**正確なパッケージ名**（`com.mentor.capital.*` 等）
2. プラグインの**エントリポイント**（基底クラス / インターフェース / アノテーション）と登録方法
3. **`IX*` インターフェースの完全な一覧**と、A-3 のドメインオブジェクトとの対応表
4. custom **check / action / report** それぞれの実装契約（実装すべきメソッド、渡されるコンテキストオブジェクト）
5. **option expression / configuration** を API からどう読み出すか（式の評価は API 側か自前か）
6. プラグインの JAR 依存関係の扱い（Capital 同梱ライブラリ、クラスローダ分離の有無）
7. Capital のバージョン（リリース番号。例: 2207 系）と、それによる API 差異

これらは以下で確定する:

- 顧客環境に同梱される **Capital SDK / API リファレンス**（Xcelerator Academy / Support Center）
- **実物のアドオンソースコード**（`import` とクラス階層から逆引き）

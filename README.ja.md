# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

ハーネス中立な学術研究コアおよびマルチエージェント協調クロスレビューツールスイート。13の学術スキルと検証ツールを提供し、ベンダー中立なAgent Plugins v1仕様およびstdio MCP（Model Context Protocol）サーバーに対応。Hermes Agent、Claude Code、Cursor、スタンドアロンCLIサブエージェントをネイティブにサポートします。

著者:Junfu Shi(SJF,xngg1021)、Hermes Agent。現在の提供範囲:[Source Lineage License 1.0](LICENSE)。

## ライセンス

本通知を含むスナップショットは、[LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) で特定された対象物と権利について **Source Lineage License 1.0** を採用する。最初の SLL コミットとツリー、およびその後の境界記録コミットは、[LICENSE-HISTORY.md](LICENSE-HISTORY.md) と [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) で区別される。記録された移行以降、本通知を保持するスナップショットは同じ提供範囲を引き継ぐ。

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` までの履歴スナップショットは MIT ライセンスで配布されており、それらの複製に適用される条件に従う。受領者は有効な MIT 権限を保持し、SLL への移行を求められない。[旧プロジェクト MIT 本文](LICENSES/MIT-pre-SLL.txt)は保存され、[tests/upstream/LICENSE](tests/upstream/LICENSE) とその第三者由来記録は変更されない。新しいルート提供はこれらの権利を消さない。

SLL は、適用されるライセンス、通知、ソース系譜の条件に従い、使用、研究、改変、商用利用、配布、独自追加を広く許可する。コピーレフトではなく、ソース開示を要求しない。複製を提供しない純粋なネットワークサービスは、それ自体ではコアサービス系譜通知条件を発動しない。明示的な特許許諾はない。第三者の素材はそれぞれの条件に従う。情報的な要約は英語原本の [LICENSE](LICENSE) が優先する。`LicenseRef-Source-Lineage-1.0` はローカル参照であり SPDX 割当てではなく、OSI 承認を主張しない。[貢献の受付](CONTRIBUTING.md)は下流のライセンス権限とは独立している。

## スキル

| スキル | バージョン | 機能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 同一性とソース別引用数の照合、更新・撤回シグナルの検査、OA 本文の特定と PDF 同一性の検証 |
| `skills/literature-analysis` | 1.3.0 | 12 のワークフロー:トピック類似度、局所テキスト重複、反証、著者プロファイル、模擬査読、誤謬検査、レビューマトリクス、投稿先候補、BibTeX、バイリンガル読解、研究ギャップ探索、再現 |
| `skills/academic-writing` | 1.1.1 | 論文推敲、引用基準案内（ISO 690 国際基準および地域・機関別プロファイル）、投稿規程、検出サービス、投稿資料、審査要件 |
| `skills/math-computation` | 1.2.1 | 既存の領域・タスク経路と修正済みの数値・統計例題、領域別リファレンス 4 編 |
| `skills/quantitative-paper-audit` | 1.1.0 | 論文が報告する統計量(効果量、p 値、信頼区間、OR/RR、検出力)の再計算と数値不整合の検出 |
| `skills/research-reproducibility` | 1.0.1 | 構造化チェックリスト、5段階の事実、再現可能な監査記録を備えた14段階の再現監査パイプライン |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 検索ログ、文献選定記録、効果量換算、異質性、固定・変量効果の統合、感度分析、出版バイアス診断 |
| `skills/literature-watch` | 1.1.0 | 週次ブループリント:OpenAlex と Crossref でトピック、著者、DOI の新規作品を監視し、重複排除のうえ新規のみ報告 |
| `skills/retraction-watch` | 1.1.0 | 週次ブループリント:OpenAlex の is_retracted と Crossref 更新レコード(update-to シグナル)に対して DOI 監視リストを再検査し、状態変化のみ報告 |
| `skills/research-object-identity` | 1.1.0 | 決定論的研究資源の識別および来歴・トレーサビリティ：識別子正規化、5状態判定、コンテンツアドレス指定派生グラフ、因果DAG検証、ミリ秒単位のオフライン逆方向追跡 |
| `skills/claim-evidence-graph` | 1.0.0 | 決定論的主張と根拠の対応関係：科学的主張、実証証拠記録、計算来歴の接続 |
| `skills/decision-ledger` | 1.0.0 | 研究上の意思決定と失敗記録：研究上の選択、失敗試行の記録、路線の断念理由、結果の訂正履歴を追記記録 |
| `skills/cross-review-five` | 2.0.0 | 動的マルチモデル／サブエージェント協調クロスレビュー（Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Geminiなど）：v2 4段階Sparse Deliberationパイプライン（ハンガリー法による最適マッチング、P0-P3重要度判定対応） |

13 のスキルには 21 編の Markdown リファレンスが含まれ、必要時にのみ読み込まれる。

## 学術標準とグローバル・プロファイル基準

引用スタイル、報告ガイドライン、メタデータ規約は対象ジャーナル、助成機関、学問分野、司法管轄区に依存します。本リポジトリは **ISO 690:2021**（書誌参照および引用指針）、**ISO 5127:2017**（情報・ドキュメンテーション用語）、**W3C PROV**（来歴データモデル）を国際基準として確立し、各国の地域プロファイル（日本の学協会指針・JIS X 0807参考、中国大陸 GB/T 7714-2025、スペイン UNE-ISO 690 等）および分野別標準（APA、IEEE、PRISMA 2020、ICMJE 等）に対応しています。投稿先機関・学会の要求事項が常に優先されます。詳細は[学術標準アーキテクチャ](docs/standards/README.md)および[自然な学術用語ガイド](docs/terminology/README.md)を参照してください。

## 統合とポータブル利用

### 1. Agent Plugins v1 および MCP サーバー
本リポジトリは標準 Agent Plugins v1（`plugin.json`）および stdio MCP サーバー（`mcp.json` / `scripts/mcp_server.py`）を提供し、Claude Code、Cursor、Gemini CLI などとネイティブに連携可能です:

```bash
python scripts/mcp_server.py
```

### 2. Hermes でのインストール
Hermes 環境で実行:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

残りのスキルは完全識別子のディレクトリ名を置き換えてインストールする。通常の tap はデフォルトブランチを読むため、新しい tap は上記のスキルセットをインストールする。マージ前に作業ブランチを検査する場合は、そのブランチをローカルにチェックアウトし、インストール済み Hermes バージョンのローカルフォルダ手順に従う。tap コマンドが PR ブランチを選択するとは想定しないこと。

関連スキルは上流 `245e48008fa814b3251f50755eb656bd9fb86cb1` で確認済み:arxiv、grounded-citations、docx、pdf、manim-video。huggingface-hub と llama-cpp は任意カタログにあり、別途インストールが必要な場合がある。ocr-and-documents と pc-hardware-benchmark は当該スナップショットに存在せず、依存関係でもない。セッションツールと文書・ブラウザバックエンドはローカル設定に依存する。

## データソースへのアクセス

- OpenAlex の基本クエリは匿名で実行でき、日次予算は小さい。2026-09-06 時点の文書では匿名 1 日 0.10 ドル、無料 API キーで 1 日 1 ドル、上限は毎秒 100 リクエスト。費用はクエリ種別により異なり、無制限アクセスではない。任意キーは `OPENALEX_API_KEY` に保存する。`per_page`(最大 100)とカーソルページネーションを使用する。
- Crossref はスロットリング付きの公開メタデータアクセスを提供する。更新関係と Retraction Watch シグナルには DOI と方向の照合が必要であり、レコードの不在は論文が影響を受けていない証明にならない。
- Unpaywall は `UNPAYWALL_EMAIL` に実在の連絡先メールを必要とする。場所が見つからないことは OA コピーが存在しない証明にならない。
- arXiv、Europe PMC、PubMed E-utilities、DOAJ は補助ソースであり、それぞれの方針がある。既定のテストではすべてが実行されるわけではない。Semantic Scholar は共有の匿名制限と個別割当てのキー制限を持つ。アクセス権は引用文脈の利用可能性を保証しない。
- Scite、Dimensions、Scopus、Web of Science、AI 検出製品は任意の外部サービスである。使用前に現在のアカウント・API 権限と割当てを確認すること。普遍的な無料枠や固定価格は約束されない。

[OpenAlex 認証](https://help.openalex.org/api/authentication/)、[予算とクエリ費用](https://help.openalex.org/api/llm-quick-reference/)、[Crossref 更新フィルタ](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/) を参照。

## 検証

専用の Python 環境を使用する。実行時ライブラリはタスク別であり、Hermes にインストール済みである保証はない。QA 依存はすべてのマーク付き例題が実行できるよう広めに設定されている:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA はメタデータ、リファレンス、個人パス・既知シークレットパターン、Python 構文、マーク付き実行フェンスを検証する。各 smoke 例題は新しいサブプロセスで変更なしに実行される。プロット例題は `PLOT_DIR`(既定 `~/plots`、明示的に展開)を受け付け、テストは一時ディレクトリを使用する。未分類の Python フェンスは拒否される。`fragment:` ブロックは構文検査されるが名前付き入力を必要とし、単独では実行されない。`external-test:` ブロックは手動の外部コマンドでのみ実行される。合格した構成済みチェックでは 0、コード・スキーマ・同一性の失敗では 1、転送・認証・割当ての利用不能では 2 を返す。未構成の任意サービスは SKIP のままである。

固定された Hermes オーサリングテストは、スキルごとの規則を変えずに再利用される。上流の全配布個体数チェックはこの tap には適用されず、本リポジトリのハーネスは 13 のスキルすべてを検査し、固定されたバンドル・任意カタログに対してリファレンスを解決する。これは完全な Hermes インストールテストではない。CI は依存のインストールにのみネットワークを使用し、通常の PR テストは学術 API を呼び出さない。

CI は GitHub Actions により Linux x86_64 (Python 3.10-3.14)、Linux ARM64 (ubuntu-24.04-arm)、Ubuntu 26.04 プレビュー Canary (ubuntu-26.04 および ubuntu-26.04-arm)、Windows x86_64、Windows ARM64 (windows-11-arm)、macOS ARM64 (macos-latest)、macOS Intel (macos-15-intel) の全プラットフォーム・全アーキテクチャを網羅し、632 件の単体テストがすべて合格、上流 main 最新ブランチに対するリアルタイム Canary 検証も含めて実行される。別の tap 統合ワークフローが main へのプッシュ時に実行され、tests/upstream/provenance.json に記録された固定 Hermes チェックアウトをインストールし、このリポジトリに対して tap add、search、install、list を実行する。正確なバージョン、チェック項目、制約は[監査文書](docs/audit-20260906.md)にある。

tools/longtail/ は確定的な極端長尾シナリオ生成器を保持します: 解結合された因子軸上に 4096 個の SHA256 シード候補を生成し、貪欲法で網羅を選択し、generated-scenarios.json に網羅性レポートを出力します。これはスキルのストレステスト入力層であり、セマンティック展開は別段階です。

scripts/scfabric/ は科学計算・統計分析実行層です: ハードウェアプローブ、dtype ゲート付きバックエンドカタログ、5 つの負荷プロファイル、等価性検証付きベンチマークおよび ComputeReceipt。実測は [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md) にあります。

## 研究・計画文書

- [ペインポイント図鑑 v0(英語)](docs/pain-atlas-v0.en.md)、[中文版](docs/pain-atlas-v0.zh.md):学術知識作業のライフサイクル上の摩擦点。定量主張には出典検証状態を付す。
- [研究計画 v0(英語)](docs/research-plan-v0.en.md)、[中文版](docs/research-plan-v0.zh.md):Research Object モデル、中核機能領域、候補方向、第 1 段階の因子分解行列。

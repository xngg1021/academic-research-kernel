# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

特定の実行環境に依存しない、自律型エージェント研究ワークフロー向けの決定論的学術研究状態管理・検証ツールセットです。研究成果・資料の取り込み基盤と汎用 Model Context Protocol（MCP）サーバーを通じて、研究対象の識別と来歴・トレーサビリティ、実証的な証拠記録・検証記録、主張と根拠の対応関係、および追記専用の研究上の意思決定と失敗記録を一元的に結び付けます。14 の専門学術スキルが検証済み研究状態の生成と利用を担い、Claude Code、Cursor、Codex、Gemini CLI、Hermes Agent をネイティブにサポートします。検証範囲と外部サービスの制約は[監査文書](docs/project-lineage-audit-20260920.md)に記録されています。

著者：Junfu Shi（SJF、xngg1021）、Hermes Agent。現在の提供範囲：[Source Lineage License 1.0](LICENSE)。

## クイックスタート

[uv](https://docs.astral.sh/uv/getting-started/installation/) を用いてバージョン 2.2.0 を実行します：

```bash
uvx academic-research-kernel@2.2.0 mcp
```

[2.2.0 リリース](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.2.0)には配布パッケージのハッシュ値と公開状態が記録されています。配布用 wheel をダウンロードしたうえで、ローカル環境から `uvx --from ./academic_research_kernel-2.2.0-py3-none-any.whl academic-research-kernel mcp` として実行することも可能です。Python 3.10–3.14 に対応しており、`uvx --python 3.12` で対応インタプリタを明示的に指定できます。統計計算を含む全 12 個の決定論的ツールが基本インストールに含まれています。

## インストールの確認

```bash
uvx academic-research-kernel@2.2.0 doctor
uvx academic-research-kernel@2.2.0 --version
```

オフライン診断により依存関係、スキーマ、全 12 個のツール定義を検査します。任意の外部サービスが未設定のままでもエラーにはなりません。機械可読な出力には `doctor --json` を使用します。

## パッケージのインストール

```bash
uv tool install academic-research-kernel==2.2.0
academic-research-kernel doctor
academic-research-kernel mcp
```

または、`pipx install academic-research-kernel==2.2.0`、あるいは対応する仮想環境内で `python -m pip install academic-research-kernel==2.2.0` を実行してインストールできます。`[full]` は拡張的な科学計算スキル例題向けのライブラリを追加し、`[qa]` は PDF パーサーを含むリポジトリ検証ツールを追加します。`[research]` はクリーンインストール環境間で一貫した PDF フォントデコードを行うため `pypdf==6.19.0` と `fonttools==4.65.0` を追加します（いずれも Python 3.10 に対応）。構造化 HTML/XML およびサイズ制限付き DOCX/XLSX の読み取りには標準ライブラリを使用します。GPU バックエンドと有償サービスは任意です。

## Hermes

Hermes プロセスの PATH から uv を参照できる状態にしたうえで、ポータブルプラグインをインストールして明示的に有効化します：

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

既存の互換識別子 `academic-skills` はそのまま維持され、`paper-research` を含む 14 のスキルが利用可能になります。プラグインの `mcp.json` は Python 3.12 とリポジトリの `uv.lock` を用いて `uv run --frozen --no-dev --no-editable` を呼び出し、独立した実行環境を `${PLUGIN_DATA}/runtime` 配下に構築します。初回実行時に Hermes 本体やシステムの Python パッケージを流用せず依存関係をセットアップするため、不足しているパッケージやインタプリタの取得にネットワーク接続が必要です。従来のスキル単体 tap による導入も引き続きサポートされています。

## ソースからの実行

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

依存関係の分類、再現手順、リリース識別情報、公開チェックポイント、検証範囲については[配布とリリース案内](docs/distribution-release.md)を参照してください。

## ライセンス

本通知を含むスナップショットは、[LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) で特定された対象物と権利について **Source Lineage License 1.0** を採用する。最初の SLL コミットとツリー、およびその後の境界記録コミットは、[LICENSE-HISTORY.md](LICENSE-HISTORY.md) と [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) で区別される。記録された移行以降、本通知を保持するスナップショットは同じ提供範囲を引き継ぐ。

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` までの履歴スナップショットは MIT ライセンスで配布されており、それらの複製に適用される条件に従う。受領者は有効な MIT 権限を保持し、SLL への移行を求められない。[旧プロジェクト MIT 本文](LICENSES/MIT-pre-SLL.txt)は保存され、[tests/upstream/LICENSE](tests/upstream/LICENSE) とその第三者由来記録は変更されない。新しいルート提供はこれらの権利を消さない。

SLL は、適用されるライセンス、通知、ソース系譜の条件に従い、使用、研究、改変、商用利用、配布、独自追加を広く許可する。コピーレフトではなく、ソース開示を要求しない。複製を提供しない純粋なネットワークサービスは、それ自体ではコアサービス系譜通知条件を発動しない。明示的な特許許諾はない。第三者の素材はそれぞれの条件に従う。情報的な要約は英語原本の [LICENSE](LICENSE) が優先する。`LicenseRef-Source-Lineage-1.0` はローカル参照であり SPDX 割当てではなく、OSI 承認を主張しない。[貢献の受付](CONTRIBUTING.md)は下流のライセンス権限とは独立している。

## スキル

| スキル | バージョン | 機能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 同一性とソース別引用数の照合、更新・撤回シグナルの検査、OA 本文の特定と PDF 同一性の検証 |
| `skills/literature-analysis` | 1.3.0 | 12 のワークフロー：トピック類似度、局所テキスト重複、反証、著者プロファイル、模擬査読、誤謬検査、レビューマトリクス、投稿先候補、BibTeX、バイリンガル読解、研究ギャップ探索、再現 |
| `skills/academic-writing` | 1.1.1 | 論文推敲、引用基準案内（ISO 690、APA、MLA、Chicago、IEEE、AMA および地域・機関別プロファイル）、投稿規程、任意の検出サービス、投稿資料、機関審査要件 |
| `skills/math-computation` | 1.2.1 | 既存の領域・タスク経路と修正済みの数値・統計例題、領域別リファレンス 4 編 |
| `skills/quantitative-paper-audit` | 1.1.0 | 論文が報告する統計量（効果量、p 値、信頼区間、OR/RR、達成検出力）の再計算と数値不整合の検出 |
| `skills/research-reproducibility` | 1.0.1 | 構造化チェックリスト、5 段階の事実階層、再現可能な監査記録を備えた 14 段階の再現監査パイプライン |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 検索ログ、文献選定記録、効果量換算、異質性、固定・変量効果の統合、感度分析、出版バイアス診断 |
| `skills/literature-watch` | 1.1.0 | 週次ブループリント：OpenAlex と Crossref でトピック、著者、DOI の新規引用作品を監視し、重複排除のうえ新規項目のみ報告 |
| `skills/retraction-watch` | 1.1.0 | 週次ブループリント：OpenAlex の `is_retracted` と Crossref 更新レコード（`update-to` シグナル）に対して DOI 監視リストを再検査し、状態変化のみ報告 |
| `skills/research-object-identity` | 1.1.0 | 決定論的研究資源の識別および来歴・トレーサビリティ：識別子正規化、5 状態判定、コンテンツアドレス指定派生グラフ、因果 DAG 検証、100 ミリ秒未満のオフライン逆方向追跡 |
| `skills/claim-evidence-graph` | 1.0.0 | 決定論的な主張と根拠の対応関係：科学的主張、証拠記録、計算来歴の接続 |
| `skills/decision-ledger` | 1.0.0 | 研究上の意思決定と失敗記録：研究上の選択、失敗試行（ネガティブ結果）、研究ルートの状態・なぜその路線を断念したか、結果の訂正履歴を時系列で追記記録 |
| `skills/paper-research` | 1.0.0 | DOI・URL・ローカル論文および付録資料の読解、候補フィールドの検証、統計値の再計算、永続的な研究状態管理、出典箇所付き中国語レポート生成、2 論文比較 |
| `skills/cross-review-five` | 2.0.0 | 任意のモデルやサブエージェント（Kimi K3、DeepSeek V4 Pro、GLM 5.3、Claude、Gemini など）に対応する動的マルチレビュアーパネル編成：ハンガリー法（Kuhn-Munkres）最適割当て、主張クラスタリング、匿名相互検証、P0–P3 重要度判定を備えた v2 Sparse Deliberation パイプライン |

14 のスキルには計 22 編の Markdown リファレンスが含まれ、必要時にのみ読み込まれます。

## 学術標準とグローバル・プロファイル基準

引用スタイル、報告ガイドライン、メタデータ規約は対象ジャーナル、助成機関、学問分野、法域に依存します。本リポジトリは **ISO 690:2021**（書誌参照および引用指針）、**ISO 5127:2017**（情報・ドキュメンテーション用語）、**W3C PROV**（来歴データモデル）を国際基準として確立し、各国の地域プロファイル（日本の学協会指針・JIS X 0807 参考、中国大陸 GB/T 7714-2025、スペイン UNE-ISO 690:2024、ドイツ DIN ISO 690:2021 など）および分野別標準（APA 第 7 版、IEEE、ACM、Vancouver、Chicago、PRISMA 2020、ICMJE）に対応しています。投稿先機関・学会の要求事項が既定プロファイルより常に優先されます。詳細は[学術標準アーキテクチャ](docs/standards/README.md)および[自然な学術用語ガイド](docs/terminology/README.md)を参照してください。

バージョン 2.2.0 では、DOI 等の外部識別子の整合性、定量判定フラグの相互排他性、およびカーネルと検証記録で共有される要確認事項の契約を検証します。キャッシュの完全性は保持された元の成果物エンベロープと正規化バインディングから独立して再構築されるため、状態レコードとそのキャッシュ宣言の双方を削除しても不正なキャッシュ再生が成立することはありません。詳細は[4 項目のブロッカー解消記録](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21)を参照してください。

## 統合とポータブル利用

### 1. Agent Plugins v1 および MCP サーバー
本リポジトリはベンダー中立な **Agent Plugins v1** 仕様（`plugin.json`）に準拠し、stdio **MCP サーバー**（`mcp.json` / `scripts/mcp_server.py`）を通じて中核の学術検証・統計再計算ツールを公開します。Claude Code、Cursor、Gemini CLI などのエージェントフレームワークと互換性があります（リポジトリ識別子は `academic-research-kernel` ですが、後方互換性のためプラグインマニフェスト名 `academic-skills` と MCP 設定エイリアスは維持されています）。

```bash
# エージェント環境に stdio MCP サーバーとして追加
uvx academic-research-kernel mcp
```

### 2. Hermes でのネイティブインストール
Hermes 環境で以下を実行します：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

残りのスキルは完全識別子のディレクトリ名を置き換えてインストールします。通常の tap はデフォルトブランチを読むため、新しい tap は上記のスキルセットをインストールします。マージ前に作業ブランチを検査する場合は、そのブランチをローカルにチェックアウトし、インストール済み Hermes バージョンのローカルフォルダ手順に従ってください。tap コマンドが自動的にプルリクエストのブランチを選択するとは想定しないでください。

関連スキルは上流 `245e48008fa814b3251f50755eb656bd9fb86cb1` で確認済みです：arxiv、grounded-citations、docx、pdf、manim-video。huggingface-hub と llama-cpp は任意カタログにあり、別途インストールが必要な場合があります。ocr-and-documents と pc-hardware-benchmark は当該スナップショットに存在せず、依存関係でもありません。セッションツールと文書・ブラウザバックエンドはローカル設定に依存します。

## データソースへのアクセス

- OpenAlex の基本クエリは匿名で実行できますが、日次予算は小さくなります。2026-09-06 時点の文書では匿名 1 日 0.10 ドル、無料 API キーで 1 日 1 ドル、上限は毎秒 100 リクエストと定められています。費用はクエリ種別により異なり、無制限アクセスではありません。任意キーは `OPENALEX_API_KEY` に保存し、`per_page`（最大 100）とカーソルページネーションを使用してください。
- Crossref はスロットリング付きの公開メタデータアクセスを提供します。更新関係と Retraction Watch シグナルには DOI と方向の照合が必要であり、レコードの不在は論文が影響を受けていない証明にはなりません。
- Unpaywall は `UNPAYWALL_EMAIL` に実在の連絡先メールアドレスを必要とします。場所が見つからないことは OA コピーが存在しない証明にはなりません。
- arXiv、Europe PMC、PubMed E-utilities、DOAJ は補助ソースであり、それぞれ独自の方針があります。既定のテストではすべてが実行されるわけではありません。Semantic Scholar は共有の匿名制限と個別割当てのキー制限を持ちますが、API アクセス権は引用文脈の利用可能性を保証しません。
- Scite、Dimensions、Scopus、Web of Science、AI 検出製品は任意の外部サービスです。使用前に現在のアカウント・API 権限と割当てを確認してください。普遍的な無料枠や固定価格は約束されません。

[OpenAlex 認証](https://help.openalex.org/api/authentication/)、[予算とクエリ費用](https://help.openalex.org/api/llm-quick-reference/)、[Crossref 更新フィルタ](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)を参照してください。

## 決定論的取り込みと公開カーネルインターフェース

バージョン 2.2.0 は `ResearchArtifactEnvelope v1`、`ArtifactIngestionReceipt v1`、15 個のアダプター（14 のスキルおよび opaque fallback）、ならびに 12 個のステートレス stdio MCP ツールを提供します。受理された取り込み検証記録は、保持される各セマンティック変更（研究対象、主張と根拠の対応関係レコード、研究上の意思決定と失敗記録レコード、要確認事項、物理検証記録、成果物登録）を種別、識別子、正規化 SHA-256 によって拘束します。キャッシュ再生時はトランスポートスナップショットのハッシュとは独立してこれらのコミットメントを検証します。空の記録も有効であり、失敗したアトミックバッチは部分的な状態を残しません。

来歴コンテンツの読み取り権限は帯域外で明示的に付与されます。信頼された Python 呼び出し元はシリアライズ済み検証記録やスナップショットを再生する際に `LineageVerificationContext` を渡します。一方、MCP 呼び出し元は上限付きのコンテンツバイト列のみを渡すことができ、ホストのファイルシステムルートを指定することはできません。既定のコンテンツ予算は 10 MiB であり、信頼されたホストは生成側と検証側が同一ポリシーに従う条件下でより大きな成果物を明示的に許可できます。コンテンツ権限がない場合、`fully_verified` の主張は独立して再現できず、構造化された無効検証結果を返します。非構造化テキストは不透明なまま保持され、異論は可視状態に保たれ、コミット、路線の断念、再開、ルーティング、真偽判断の主導権は研究者に留保されます。

契約と互換性については[カーネルアーキテクチャ文書](docs/kernel-architecture.md)を参照してください。配布および公開チェックポイントは[リリースガイド](docs/distribution-release.md)に記録されています。英語および簡体字中国語 README は最新状態に同期されており、各言語の翻訳状態は[多言語マニフェスト](docs/i18n/manifest.json)で明示的に管理されています。最終候補の識別情報、厳密な HEAD CI、累積レビューおよびマージ証跡は[完了記録](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)に記録されています。

## 検証とテスト

専用の Python 環境を使用してください。実行時ライブラリはタスク別であり、Hermes にプリインストールされている保証はありません。QA 依存関係はすべてのマーク付き例題が実行できるよう広めに設定されています：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA はメタデータ、リファレンス、個人パス・既知シークレットパターン、Python 構文、マーク付き実行コードブロックを検証します。各 smoke 例題は新しいサブプロセスで変更なしに実行されます。プロット例題は `PLOT_DIR`（既定は `~/plots`、明示的に展開）を受け付け、テスト時は一時ディレクトリを使用します。未分類の Python コードブロックは拒否されます。`fragment:` ブロックは構文検査されますが名前付き入力を必要とし、単独では実行されません。`external-test:` ブロックは手動の外部検証コマンドでのみ実行され、設定済みチェックの合格時は 0、コード・スキーマ・同一性の失敗時は 1、通信・認証・クォータの利用不能時は 2 を返します。未設定の任意サービスは SKIP のままとなります。

固定バージョンの Hermes オーサリングテストは、スキルごとの規則を変えずに再利用されます。上流の全体配布チェックはこの tap には適用されず、本リポジトリのテストハーネスは 14 のスキルすべてを検査し、固定されたバンドル・任意カタログに対してリファレンスを解決します。これは完全な Hermes インストールテストではありません。CI は依存関係のインストールにのみネットワークを使用し、通常のテストは外部の学術 API を呼び出しません。

CI は GitHub Actions により Linux x86_64（Python 3.10–3.14）、Linux ARM64（ubuntu-24.04-arm）、Ubuntu 26.04 プレビュー Canary（ubuntu-26.04 および ubuntu-26.04-arm）、Windows x86_64、Windows ARM64（windows-11-arm）、macOS ARM64（macos-latest）、macOS Intel（macos-15-intel）の全プラットフォーム・全アーキテクチャを網羅し、上流の最新ブランチに対するリアルタイム Canary 検証も実行します。ベースライン候補のローカル検証では 1165 件のテストが通過しており、現在の修正結果とカバレッジ境界は[正確性修復記録](docs/maintenance/correctness-repair-20261008.md)に記録されています（リモート証跡は検証対象の HEAD を個別に識別します）。別の tap 統合ワークフローが main へのプッシュ時に実行され、tests/upstream/provenance.json に記録された固定 Hermes チェックアウトをインストールし、本リポジトリに対して tap add、search、install、list を検証します。正確なバージョン、チェック項目、制約は[監査文書](docs/project-lineage-audit-20260920.md)に記載されています。

[tools/longtail/](tools/longtail/README.md) には決定論的な長尾因子生成器が格納されています：4096 個の SHA256 シード候補から 30 シナリオを選出し、機械計算による検証カバレッジ報告を出力します。v3 モデルでは能力ファミリー（E01）、リポジトリの実際の 14 スキル（E02）、タスク目標（E03）を個別に集計します。各シナリオは 1 つの主要スキル、サポートされるタスク目標、互換性のある能力を持ち、すべてのスキルは宣言された中核目標を含む少なくとも 2 つの異なる目標の下で 2 回以上出現する必要があります。スキルディレクトリの不一致は検証失敗となります。セマンティック展開（タスクチェーン、オラクル、実行イベント注入）は別段階であり、因子カバレッジはワークフロー実行カバレッジを証明するものではありません。

scripts/scfabric/ は科学計算・統計分析ツール群の実行層です：ハードウェアプローブ、dtype ゲート付きバックエンドカタログ、5 つのワークロードプロファイル、数値等価性検査付きの対ベンチマーク、および ComputeReceipt を備えています。本機での初回測定結果は [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md) に記録されており、既定では CPU を使用し、検証記録がある場合のみアクセラレータを有効化します。

## ローカル Agent による論文研究

`academic-research-kernel[research]==2.2.0` をインストールし、パッケージ同梱のワークフローをエクスポートします：

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Work または互換性のあるローカル Agent にエクスポートされた `SKILL.md` を読み込ませたうえで、DOI、公開リンク、またはローカル資料バンドルのみを渡して次のように指示します：
「研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。」
2 本の論文を比較する場合は、データ、手法、評価条件、主要結果を比較し、どの結果が直接比較可能かを説明するよう依頼します。Agent は同一タスク内で原文読解、候補フィールド検証、統計計算、データ取り込み、レポート生成、独立した出典照合までを一貫して実行します。既存の MCP インターフェースは 12 個のツールを維持し、新しいオーケストレーション機能は CLI とポータブルスキルで提供されます。

プログラムの実際の実行ステージは以下の通りです：

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` は本文および付録資料を取得・解析し、マニフェスト、ソースハッシュ、原文セグメント位置を保存します。`finish` は Agent が生成した構造化抽出結果を検証し、既存の統計ツールを用いて対象となる t/p 値、2 群効果量、件数・割合の主張を再計算したうえで、カーネル状態と中国語 Markdown/HTML レポートを保存します。`compare` は比較可能条件に関する Agent の明示的な評価を検証します。これらのコマンドは常駐の Work モデルを内蔵しておらず、セマンティックな読解は現在の Agent が [paper-research](skills/paper-research/SKILL.md) に従って実行します。保存された元ファイルと抽出スナップショットにより決定論的なオフライン再生が可能であり、ネットワーク取得と新規のセマンティック読解は個別の操作として明確に区別されます。

## 2.0.1 正確性検証と配布パッケージの検証

バージョン 2.0.1 以降の正確性修復により、公開ツール `academic_recompute_statistics` は t 検定の p 値および 2 群の Cohen's d / Hedges' g を公開し、信頼区間（CI）とオッズ比・リスク比（OR/RR）は下位の Python 関数として維持されます。報告値の精度が重要な場合は `p_value_literal`（例：`"1.0e-5"`）または `p_value_decimals` を渡してください。リテラル文字列は末尾のゼロを保持し、数値入力は数値表現のみを保持します。複数の精度指定が競合する場合は明示的にエラーとなります。四捨五入（round-half-up）の比較は下限境界を含み上限境界を除きます。通常の統計的不一致は正常な科学的検証結果として扱われ、無効な入力や部分的な計算失敗のみが `isError` を設定します。

撤回チェックは今回の観測結果（True / False / unknown）を既知の最新値（last-known）とは別に記録します。クエリ前の短い予約ロックにより同一 DOI の観測順序が保証され、他の DOI の更新も保持されます。現在の観測と過去の確認履歴は別個のバージョンを持ち、遅れて到着した有効な確認が保持履歴を更新した場合でも、より新しい unknown 観測は今回のチェックにおいて未検証として明示的に残されます。回帰テスト内の HTTP フィクスチャにはテストデータである旨が明記されています。

MCP サーバーは `ping` に応答し、`notifications/cancelled` を含む有効な通知には応答を返さず、不正な入力の後も stdio セッションを維持します。同期実装であるためプリエンプティブなキャンセルは宣言しません。メッセージ処理は [MCP メッセージ仕様](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)および [ping 仕様](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)に準拠しています。

分離された環境で現在のチェックアウトから配布パッケージをビルド・検証するには以下を実行します：

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` は候補 sdist をリポジトリ外にそのまま展開し、`ARK_REPO` と `ARK_SDIST` をその候補に設定してテスト、静的 QA、実行可能コードブロック、i18n チェックを実行します。wheel と sdist のインストールはそれぞれ新しい環境を使用し、uvx はローカル wheel と独立したキャッシュを使用します。レポートには成果物ハッシュと実際のインポートパスが記録されます。定期実行される軽量な Hermes チェックは固定版と最新版、およびテスト対象の SHA を個別に報告します。外部契約 JSON とジョブサマリーは `healthy`、`degraded`、`failed` を使用し、スキップされたプローブも明示的に記録します。

## 研究・計画文書

以下の 2 文書は探索的な計画リファレンスであり、拘束力のあるロードマップではありません。文書内の方向番号は docs/direction-primitive-mapping.json に保存されたグループ分けから再計算されます。

- [ペインポイント図鑑 v0（英語）](docs/pain-atlas-v0.en.md)、[中文版](docs/pain-atlas-v0.zh.md)：学術知識作業のライフサイクル上の摩擦点。定量主張には出典検証状態を付しています。
- [研究計画 v0（英語）](docs/research-plan-v0.en.md)、[中文版](docs/research-plan-v0.zh.md)：Research Object モデル、中核機能領域、候補方向、第 1 段階の因子分解行列。

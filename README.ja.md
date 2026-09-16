# hermes-academic-skills

English · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · 日本語 · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md)

Hermes Agent 向けの 11 の中国語学術スキル。出典検証、文献分析、学術執筆、数値計算、定量論文監査、再現性監査、系統的レビューとメタ分析、研究オブジェクトの同一性と系譜、クロスモデルレビュー編成、さらに週次監視自動化 2 件をカバーする。リポジトリには実行可能な例題チェックが含まれ、検証範囲と外部サービス上の制約は[監査文書](docs/audit-20260906.md)に記録されている。

著者:Junfu Shi(SJF,xngg1021)、Hermes Agent。現在の提供範囲:[Source Lineage License 1.0](LICENSE)。

## ライセンス

本通知を含むスナップショットは、[LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) で特定された対象物と権利について **Source Lineage License 1.0** を採用する。最初の SLL コミットとツリー、およびその後の境界記録コミットは、[LICENSE-HISTORY.md](LICENSE-HISTORY.md) と [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) で区別される。記録された移行以降、本通知を保持するスナップショットは同じ提供範囲を引き継ぐ。

`439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` までの履歴スナップショットは MIT ライセンスで配布されており、それらの複製に適用される条件に従う。受領者は有効な MIT 権限を保持し、SLL への移行を求められない。[旧プロジェクト MIT 本文](LICENSES/MIT-pre-SLL.txt)は保存され、[tests/upstream/LICENSE](tests/upstream/LICENSE) とその第三者由来記録は変更されない。新しいルート提供はこれらの権利を消さない。

SLL は、適用されるライセンス、通知、ソース系譜の条件に従い、使用、研究、改変、商用利用、配布、独自追加を広く許可する。コピーレフトではなく、ソース開示を要求しない。複製を提供しない純粋なネットワークサービスは、それ自体ではコアサービス系譜通知条件を発動しない。明示的な特許許諾はない。第三者の素材はそれぞれの条件に従う。情報的な要約は英語原本の [LICENSE](LICENSE) が優先する。`LicenseRef-Source-Lineage-1.0` はローカル参照であり SPDX 割当てではなく、OSI 承認を主張しない。[貢献の受付](CONTRIBUTING.md)は下流のライセンス権限とは独立している。

## スキル

| スキル | バージョン | 機能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.1.1 | 同一性とソース別引用数の照合、更新・撤回シグナルの検査、OA 本文の特定と PDF 同一性の検証 |
| `skills/literature-analysis` | 1.2.0 | 12 のワークフロー:トピック類似度、局所テキスト重複、反証、著者プロファイル、模擬査読、誤謬検査、レビューマトリクス、投稿先候補、BibTeX、バイリンガル読解、研究ギャップ探索、再現 |
| `skills/academic-writing` | 1.1.1 | 編集、引用ガイダンス(APA、MLA、Chicago、IEEE、AMA、GB/T)、ジャーナル指示、任意の検出サービス、投稿資料、中国語学術要件 |
| `skills/math-computation` | 1.2.1 | 既存の領域・タスク経路と修正済みの数値・統計例題、領域別リファレンス 4 編 |
| `skills/quantitative-paper-audit` | 1.0.0 | 論文が報告する統計量(効果量、p 値、信頼区間、OR/RR、検出力)の再計算と数値不整合の検出 |
| `skills/research-reproducibility` | 1.0.0 | 構造化チェックリストエンジン、5 段階の事実、4 状態のレシートを備えた 14 段階の再現監査パイプライン |
| `skills/systematic-review-meta-analysis` | 1.0.0 | PRISMA 検索ログ、スクリーニング台帳、効果量換算、異質性、固定・変量効果の統合、感度分析、出版バイアス診断 |
| `skills/literature-watch` | 1.0.0 | 週次ブループリント:OpenAlex と Crossref でトピック、著者、DOI の新規作品を監視し、重複排除のうえ新規のみ報告 |
| `skills/retraction-watch` | 1.0.0 | 週次ブループリント:OpenAlex の is_retracted と Crossref 更新レコード(update-to シグナル)に対して DOI 監視リストを再検査し、状態変化のみ報告 |
| `skills/research-object-identity` | 1.0.0 | 決定的な研究オブジェクト同一性層:識別子の正規化、5 状態判定(信頼度スコアなし)、関係・系譜エッジ。Evidence Receipt を消費 |
| `skills/cross-review-five` | 1.0.0 | 5 モデル異種レビューパネル(Kimi K3、DeepSeek V4 Pro、GLM 5.3、Gemini 3.8 Flash、Gemini 3.1 Pro):plan 独立出力とローテーション相互レビューの 2 段階 |

11 のスキルには 21 編の Markdown リファレンスが含まれ、必要時にのみ読み込まれる。GB/T 7714-2025 が施行されており、執筆リファレンスは検証済みの発効日と明示的に 2015 年例とラベル付けされたものを区別する。2025 年版への完全準拠には対象機関のテンプレートまたは標準本文が必要である。

## Hermes へのインストール

現在の上流 tap 検出は `skills/` 直下の子ディレクトリを検査するため、各スキルはそのルート直下に置かれる。Hermes インストール環境で:

```bash
hermes skills tap add xngg1021/hermes-academic-skills
hermes skills search academic-source-verification
hermes skills install xngg1021/hermes-academic-skills/skills/academic-source-verification
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

固定された Hermes オーサリングテストは、スキルごとの規則を変えずに再利用される。上流の全配布個体数チェックはこの tap には適用されず、本リポジトリのハーネスは 11 のスキルすべてを検査し、固定されたバンドル・任意カタログに対してリファレンスを解決する。これは完全な Hermes インストールテストではない。CI は依存のインストールにのみネットワークを使用し、通常の PR テストは学術 API を呼び出さない。

CI は GitHub Actions により Ubuntu(Python 3.12 と 3.13)、Windows、macOS で完全な QA スイートを実行する。別の tap 統合ワークフローが main へのプッシュ時に実行され、tests/upstream/provenance.json に記録された固定 Hermes チェックアウトをインストールし、このリポジトリに対して tap add、search、install、list を実行する。新規の Hermes セッションやすべての依存バージョン組合せの検証は主張しない。正確なバージョン、チェック項目、制約は[監査文書](docs/audit-20260906.md)にある。

## 研究・計画文書

- [ペインポイント図鑑 v0(英語)](docs/pain-atlas-v0.en.md)、[中文版](docs/pain-atlas-v0.zh.md):学術知識作業のライフサイクル上の摩擦点。定量主張には出典検証状態を付す。
- [研究計画 v0(英語)](docs/research-plan-v0.en.md)、[中文版](docs/research-plan-v0.zh.md):14 のアーキテクチャプリミティブ、Research Object モデル、4 平面、候補方向、第 1 段階の因子分解行列。

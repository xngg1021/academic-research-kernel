# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

本倉庫為自主智能體科研工作流提供確定性的研究狀態管理與學術工具集。系統透過統一的研究資料接入與解析服務和通用 MCP 協定介面，將研究對象身份歸一與證據查核紀錄串聯起來，同時整合學術論斷與證據關聯以及研究決策與失敗紀錄。全倉包含 14 項學術技能，直接相容 Claude Code 與 Cursor，並原生支援 Codex、Gemini CLI 與 Hermes Agent。驗證範圍與外部服務限制記錄於[審計文件](docs/project-lineage-audit-20260920.md)。

作者為 Junfu Shi，筆名 SJF，GitHub 帳號 xngg1021，聯合 Hermes Agent 共同完成。當前授權範圍適用 [Source Lineage License 1.0](LICENSE)。

## 快速開始

請先安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)，隨後啟動 2.1.0 版本服務：

```bash
uvx academic-research-kernel@2.1.0 mcp
```

[2.1.0 Release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0)
頁面記錄了分發套件雜湊值與發布狀態。使用者下載發布的 wheel 套件後，也可直接於本機執行
`uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`。
本工具支援 Python 3.10–3.14，`uvx --python 3.12` 命令可顯式指定受支援的直譯器。
基礎安裝套件已內建全部 12 個確定性工具與統計計算依賴。

## 驗證安裝

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

診斷命令預設離線執行，負責檢查執行環境依賴、資料結構定義與全部 12 個工具宣告；未設定可選外部服務不會導致安裝驗證失敗。
`doctor --json` 命令可輸出機器可讀的診斷結果。

## 安裝軟體套件

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

使用者也可執行 `pipx install academic-research-kernel==2.1.0`，或啟用受支援的虛擬環境執行
`python -m pip install academic-research-kernel==2.1.0`。
`[full]` 擴充項會安裝科學計算範例所需的擴充套件；`[research]` 擴充項會安裝 `pypdf==6.19.0` 與 `fonttools==4.65.0`，為全新環境提供一致的 PDF 字型解碼依賴，這兩個套件均支援 Python 3.10；`[qa]` 擴充項會安裝倉庫驗證工具與上述解析依賴。結構化 HTML/XML 解析與受限 DOCX/XLSX 讀取直接呼叫標準函式庫，GPU 加速後端與付費外部服務均為可選項。

## Hermes

請先確認 Hermes 行程的環境變數 PATH 包含 uv，隨後安裝並顯式啟用外掛：

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

外掛相容名稱 `academic-skills` 保持不變，目前包含全部 14 項技能，涵蓋新增的 `paper-research`。`mcp.json` 設定檔呼叫
`uv run --frozen --no-dev --no-editable` 與 Python 3.12，配合倉庫 `uv.lock` 鎖定檔，
將獨立執行環境部署至 `${PLUGIN_DATA}/runtime`。系統首次啟動時會自動安裝執行依賴，若本機缺少目標直譯器或套件則需要連網取得。
既有的純技能 tap 安裝方式依然可用，具體步驟見下方[安裝與整合](#安裝與整合)章節。

## 從原始碼執行

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

依賴分類與復現步驟，以及發布身份和外部發布條件，均詳見[分發與發布說明](docs/distribution-release.md)。

## 授權條款

包含本通知的程式碼快照依據 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 所述範圍，對文內列明的受著作權保護材料適用 **Source Lineage License 1.0**。首個 SLL 提交與目錄樹，以及隨後的分界記錄提交，分別記錄於 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 與 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md)。自該記錄節點起，所有保留本通知的快照均沿用相同的授權範圍。

截至 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的早期快照按 MIT 授權條款分發，繼續適用對應副本的原有條款。既有接收者保留完整的 MIT 授權權限，無需遷移至 SLL。倉庫已完整保留[前專案 MIT 文本](LICENSES/MIT-pre-SLL.txt)，且 [tests/upstream/LICENSE](tests/upstream/LICENSE) 與配套的第三方來源紀錄均保持原狀，新的根目錄授權不會抹除既有權利。

SLL 授權條款允許使用與研究，支援修改與商用，並涵蓋分發及專有擴充，同時要求遵守對應的授權條款與通知要求及來源追溯條件。該授權條款不屬於 copyleft 協定，不強制要求公開原始碼。僅提供網路服務而不分發軟體副本的行為，不會單獨觸發核心服務的來源通知條件。本授權條款不包含明示專利授權，第三方材料繼續遵循各自原有的授權條款。法律解釋以英文原版 [LICENSE](LICENSE) 為準；`LicenseRef-Source-Lineage-1.0` 僅為本地標識引用，並非 SPDX 官方指配編號，也不代表已獲 OSI 批准。[貢獻接收](CONTRIBUTING.md)規則與下游授權權限相互獨立。

## 技能

| 技能 | 版本 | 功能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 交叉核對文獻身份與各資料源的被引次數，檢查論文更新與撤稿訊號，定位開放取用全文並校驗 PDF 檔案身份 |
| `skills/literature-analysis` | 1.3.0 | 提供十二項文獻分析流程，涵蓋主題相似度比對與局部文本查重，支援反證檢索與作者檔案梳理。該技能同時包含模擬審稿與謬誤查核，提供文獻對比表與選刊評估，並支援 BibTeX 匯出與雙語精讀以及研究空白篩查與復現評估 |
| `skills/academic-writing` | 1.1.1 | 提供論文潤飾編輯與引用規範指南，相容 ISO 690 國際標準及各地區機構規範，涵蓋期刊投稿指引與可選檢測服務，並支援投稿資料準備與大專院校盲審格式查核 |
| `skills/math-computation` | 1.2.1 | 提供多學科計算任務路由與修訂版數值統計計算範例，附帶四篇領域參考文件 |
| `skills/quantitative-paper-audit` | 1.1.0 | 獨立重算論文報告的效應量與 p 值，查核信賴區間、勝算比與風險比及統計檢定力，自動檢測數值不一致 |
| `skills/research-reproducibility` | 1.0.1 | 執行十四階段復現查核流程，提供結構化查核清單與五級事實分類，產製可復現的查核紀錄 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | 管理 PRISMA 檢索日誌與文獻篩選紀錄，執行效應量換算與異質性檢定，支援固定效應與隨機效應合併，並提供敏感性分析與發表偏倚診斷 |
| `skills/literature-watch` | 1.1.0 | 提供按週執行的文獻監控方案，追蹤 OpenAlex 與 Crossref 上的主題、作者及施引文獻更新，自動去重並僅報告新增條目 |
| `skills/retraction-watch` | 1.1.0 | 提供按週執行的撤稿監控方案，比對 OpenAlex 的 `is_retracted` 欄位與 Crossref 的 `update-to` 更新紀錄，複查 DOI 監控清單並僅報告狀態變更 |
| `skills/research-object-identity` | 1.1.0 | 提供確定性科研資源識別與來源追溯，涵蓋識別符歸一與五態查核，支援內容定址衍生圖與因果有向無環圖校驗，並具備毫秒級離線逆向溯源能力 |
| `skills/claim-evidence-graph` | 1.0.0 | 建構確定性的學術論斷與證據關聯，直接連接科學論斷與實證證據紀錄，支援事實查核與計算過程追溯 |
| `skills/decision-ledger` | 1.0.0 | 維護研究決策與失敗紀錄，按時間順序保存科研選擇與失敗嘗試存證，記錄放棄特定路線的原因及後續結果修正 |
| `skills/paper-research` | 1.0.0 | 讀取 DOI、公開連結或本機論文及補充資料，驗證候選欄位並重算核對統計數字，持續保存研究狀態，生成帶原文定位的中文報告與雙論文對比分析 |
| `skills/cross-review-five` | 2.0.0 | 編排多席位異質模型與子智能體交叉審議，相容 Kimi K3 與 DeepSeek V4 Pro，支援 GLM 5.3、Claude 及 Gemini 等模型；內建四階段稀疏審議流程，涵蓋獨立盲審與論斷聚類合併，採用匈牙利演算法分配全域最優互補匿名質詢，並提供審議結果核對、待確認事項紀錄與 P0 至 P3 嚴重度分級 |

上述 14 項技能共包含 22 篇 Markdown 參考文件，由系統按需載入。

## 學術規範與多區域基線

學術引文、元資料與報告規範遵循目標期刊與資助機構的要求，同時適配所屬學科與司法管轄區的規則。本倉庫以國際標準 **ISO 690:2021** 參考文獻與引文指南、**ISO 5127:2017** 文獻與資訊概念詞彙，以及 **W3C PROV** 溯源資料模型作為全球基線，同時支援台灣 CNS 13611 與中國大陸 GB/T 7714-2025，以及西班牙 UNE-ISO 690:2024 和德國 DIN ISO 690:2021 等地區規範，並相容 APA 與 IEEE、PRISMA 2020 與 ICMJE 等學科標準。目標投稿機構的具體規定優先於系統預設規則，詳細說明見[學術規範架構](docs/standards/README.md)與[自然學術術語指南](docs/terminology/README.md)。

系統嚴格校驗 DOI 等外部識別符的一致性、定量查核結論的互斥狀態標誌，以及狀態管理模組與查核紀錄共用的待確認事項規則。系統透過已保存的原始資料包與歸一化雜湊綁定獨立重建快取完整性，即便同時刪除狀態紀錄與查核宣告也無法觸發錯誤的快取命中。相關驗證細節見[四項阻塞收尾](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21)。

## 安裝與整合

### 1. 便攜式 Agent Plugins v1 與 MCP 工具服務
本倉庫遵循廠商中立的 **Agent Plugins v1** 規範並提供 `plugin.json` 清單，同時透過標準輸入輸出協定執行 `mcp.json` 與 `scripts/mcp_server.py` 所定義的通用 **MCP 伺服器**，原生相容 Claude Code 與 Cursor、Gemini CLI 以及各類現代智能體宿主。倉庫名稱現已統一為 `academic-research-kernel`，便攜外掛識別符 `name: "academic-skills"` 與 MCP 工具設定別名繼續保持長期向後相容：

```bash
# 在您的智能體宿主中直接作為 stdio MCP 服務加載
uvx academic-research-kernel mcp
```

### 2. 在 Hermes 中安裝
請於已安裝 Hermes 的環境中執行這組命令：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

使用者安裝其他技能時，只需替換完整識別符裡的技能目錄名。常規 tap 命令預設讀取主分支，全新安裝即可取得上述全部技能。若需於程式碼合併前測試工作分支，請先將目標分支檢出至本機，再參照當前 Hermes 版本的本機目錄安裝說明完成設定，切勿假定 tap 命令會自動切換至拉取請求分支。

捆綁的關聯技能已對照上游提交 `245e48008fa814b3251f50755eb656bd9fb86cb1` 完成核對，涵蓋 `arxiv` 與 `grounded-citations`，以及 `docx`、`pdf` 和 `manim-video`。可選目錄包含 `huggingface-hub` 與 `llama-cpp`，使用時可能需另行安裝。該上游快照未包含 `ocr-and-documents` 與 `pc-hardware-benchmark`，這兩項也不是本倉庫的依賴項。工作階段檢索工具、文件處理元件與瀏覽器後端均取決於本機環境設定。

## 資料源存取

- OpenAlex 基礎查詢支援匿名呼叫，每日匿名額度較小。2026-09-06 核對的官方文件規定匿名存取每日額度為 $0.10，免費 API 金鑰每日額度為 $1，且每秒請求上限為 100 次；不同查詢類型的計費權重各異，並非無限量存取。使用者可將可選金鑰存入 `OPENALEX_API_KEY`，並透過上限為 100 的 `per_page` 參數配合游標分頁拉取資料。
- Crossref 提供帶限流的公開元資料介面。程式解析更新關係與撤稿監控訊號時必須同時核對 DOI 與關聯方向，未檢索到更新紀錄並不證明目標論文未受影響。
- Unpaywall 要求透過環境變數 `UNPAYWALL_EMAIL` 設定真實聯絡信箱。介面未回傳全文連結並不代表該論文不存在開放取用副本。
- arXiv 與 Europe PMC，以及 PubMed E-utilities 和 DOAJ 均屬於補充資料源，各自適用獨立的存取策略，預設測試套件不會全部呼叫。Semantic Scholar 的匿名共享限額與專屬金鑰配額實行分離管理，能夠連通 API 並不保證一定能取得引文上下文。
- Scite 與 Dimensions，以及 Scopus、Web of Science 和各類 AI 檢測服務均屬於可選外部商業服務。使用者呼叫前須自行核對當前帳號權限、API 授權範圍與剩餘配額，本倉庫不承諾通用免費額度或固定價格。

詳細規則參見 [OpenAlex 認證](https://help.openalex.org/api/authentication/)、[預算與查詢成本](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新過濾器](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

## 確定性入庫與內核公開介面

系統公開介面提供 `ResearchArtifactEnvelope v1` 與 `ArtifactIngestionReceipt v1` 資料結構，內建覆蓋全部 14 項技能與 1 項未分類文本兜底的 15 個研究資料接入與解析轉接器，並暴露 12 個無狀態標準輸入輸出 MCP 工具。入庫產生的查核紀錄會用類型、唯一識別與規範 SHA-256 雜湊綁定每一次狀態變更，涵蓋研究對象與學術論斷關聯，以及研究決策紀錄、待確認事項與原始證據檔案註冊。快取重放會獨立於傳輸快照雜湊之外校驗這些雜湊紀錄；空的決策紀錄同樣合法，原子批次一旦執行失敗不會殘留半成品狀態。

來源與產製歷程的原文讀取權限須透過外部呼叫參數顯式授予。可信 Python 呼叫方重放序列化的查核紀錄或狀態快照時可傳入 `LineageVerificationContext`；MCP 協定呼叫方只能傳入受限的檔案內容位元組流，不得指定宿主檔案系統根目錄。單次內容讀取預算預設為 10 MiB；只要生產端與驗證端採用一致的預算策略，可信宿主即可顯式授權處理更大體積的研究資料。若呼叫時缺少原文讀取權限，標記為 `fully_verified` 的查核宣告將無法獨立重現，系統會回傳結構化的驗證失敗結果。未結構化的自由文本保持原樣儲存，評審分歧始終公開可見；狀態提交與路線終止，以及路線重開、工具路由選擇與最終學術判斷均由研究者自主掌控。

資料結構規範與版本相容規則詳見[架構文件](docs/kernel-architecture.md)。軟體套件、`uvx` 執行入口與官方 MCP Registry 的發布狀態記錄於[發布說明](docs/distribution-release.md)。全部 21 個語種的 README 均已同步至 2.1.0 版本，全倉文件的多語言同步雜湊值記錄於[多語言清單](docs/i18n/manifest.json)。候選版本身份與對應提交的 CI 紀錄，以及歷次審議與合併存證，均彙總於[收尾紀錄](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)。

## QA 與測試

測試與查核請使用獨立的 Python 虛擬環境。具體執行依賴隨任務類型變化，Hermes 宿主環境不保證預設預裝；QA 環境會安裝完整的測試依賴，以便執行全部帶標記的程式碼範例：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

QA 腳本負責校驗技能元資料與參考檔案路徑，排查個人本機路徑與已知金鑰洩露模式，並檢查 Python 語法及標記為可執行的程式碼區塊。每個 `smoke-test` 範例均會啟動全新的獨立子行程原樣執行；繪圖範例接收 `PLOT_DIR` 環境變數並顯式展開預設路徑 `~/plots`，自動化測試期間則會改用暫存目錄。QA 門禁會直接拒絕未標註分類的 Python 程式碼區塊；帶 `fragment:` 標記的程式碼區塊僅接受語法檢查，因依賴外部具名輸入而不單獨執行；帶 `external-test:` 標記的程式碼區塊僅透過手動執行外部查核命令運作。已設定的檢查項全部通過時，該外部查核命令回傳狀態碼 0；遇到程式碼錯誤、資料結構不符或文獻身份查核失敗時回傳 1；遇到網路傳輸故障、認證失敗或配額耗盡時回傳 2；未設定的可選外部服務則保持 `SKIP` 狀態。

測試套件複用了固定版本的技能編寫規範測試，並完整保留各技能原有的單項校驗規則。上游 Hermes 完整發行套件的全域目錄檢查不適用於本倉庫；本倉庫測試覆蓋全部 14 項技能，並對照固定版本的捆綁目錄與可選技能清單解析跨技能引用。這套檢查不等同於完整的 Hermes 用戶端安裝測試。持續整合流水線僅在安裝依賴套件時存取網路，常規拉取請求測試不會呼叫外部學術 API。

持續整合流水線透過 GitHub Actions 覆蓋三大作業系統的 x86_64 與 ARM64 架構。測試範圍包含執行 Python 3.10 至 3.14 的 Linux x86_64 與 `ubuntu-24.04-arm` 映像，涵蓋 `ubuntu-26.04` 與 `ubuntu-26.04-arm` 預遷移環境，同時覆蓋 Windows x86_64 與 `windows-11-arm`，以及 `macos-latest` 與 `macos-15-intel` 環境，並附帶針對上游 `main` 分支最新程式碼的即時載入檢驗。本機完整迴歸測試套件通過 1165 項測試，詳細驗證結果與測試覆蓋範圍見[正確性修復紀錄](docs/maintenance/correctness-repair-20261008.md)，遠端執行紀錄會單獨標明被測提交雜湊值。同時，每當程式碼推送至 `main` 分支時，獨立的 tap 整合工作流會自動安裝 `tests/upstream/provenance.json` 所記錄的固定版本 Hermes，並對本倉庫依次執行 `tap add` 與 `search`，以及 `install` 和 `list` 驗證。各項測試的確切版本、檢查範圍與已知限制詳見[審計文件](docs/project-lineage-audit-20260920.md)。

[tools/longtail/](tools/longtail/README.md) 目錄提供確定性長尾因子產生器，從 4096 個 SHA256 種子候選中篩選出 30 個測試場景，並輸出機器計算的核驗覆蓋度報告。v3 模型分別統計 E01 能力族、對應倉庫實際 14 項技能的 E02 技能項以及 E03 任務目標。每個測試場景僅綁定一項主測技能、一個受支援的任務目標與相容的能力族；每項技能至少出現 2 次且覆蓋 2 個不同任務目標，並必須包含該技能宣告的核心目標。一旦實際技能目錄與因子目錄出現偏差，校驗即會報錯退出。包含任務鏈建構、驗證判據設計及實際事件注入在內的語義展開仍屬於獨立階段，因子層面的覆蓋度並不代表完整工作流已完成執行驗證。

`scripts/scfabric/` 目錄提供科學計算與統計分析工具，內建硬體探針與帶資料類型門禁的後端目錄，包含五類工作負載畫像與帶數值等價校驗的配對基準測試，並產製 `ComputeReceipt` 查核紀錄。本機首輪實測資料見 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)；系統預設採用 CPU 執行計算，僅在具備有效查核紀錄時才啟用硬體加速器。

## 讓本地 Agent 研究論文

請先安裝 `academic-research-kernel[research]==2.1.0`，隨後匯出軟體套件隨附的正式工作流：

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

請讓 Work 或其他相容的本地智能體讀取匯出的 `SKILL.md`，隨後只需提供論文 DOI、公開連結或本機資料包，並發送指令：
“請研究這篇論文與補充資料，梳理實驗方法並核對可重算的關鍵統計數字，生成一份帶原文出處的中文報告。”
針對雙論文對比任務可直接發送指令：“請比較這兩篇論文的資料集與實驗方法，核對評估條件與主要結果，並說明哪些結論可以直接橫向對比。”
智能體會在同一任務內依次完成原文閱讀與候選欄位驗證，執行統計重算與狀態入庫，並最終生成研究報告及獨立原文複核結果。
既有的 MCP 伺服器保持 12 個基礎工具不變，新增的研究編排入口統一由命令列工具與便攜技能包提供。

命令列工具的分步呼叫入口為：

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` 子命令負責取得並解析論文正文與補充資料，自動保存資料清單、檔案雜湊值及原文段落定位資訊。
`finish` 子命令負責校驗智能體讀取原文後生成的結構化候選資料，呼叫內建統計函式重算符合條件的 t 檢定與 p 值、兩組效應量以及計數與百分比，
隨後保存研究狀態並匯出中文 Markdown 與 HTML 報告。`compare` 子命令負責校驗智能體針對兩篇論文的資料集、實驗條件與結果可比性生成的結構化結論。
命令列工具本身不內建常駐大模型，語義閱讀完全由當前智能體參照 [paper-research](skills/paper-research/SKILL.md) 規範完成，無需額外設定模型帳戶。
已保存的原始文獻與抽取快照支援確定性離線重放，最終報告會明確區分離線重放、連網取得與重新語義閱讀。

## 2.0.1 正確性修復與分發驗證

2.0.1 版本全面加固了統計重算與並行狀態更新的正確性。公開的 `academic_recompute_statistics` 工具直接提供 t 檢定 p 值以及兩組樣本的 Cohen's d 與 Hedges' g 效應量重算；信賴區間與勝算比及風險比計算繼續作為內部 Python 函式提供。當分析任務需要嚴格保留原論文的報告精度時，呼叫方可傳入字串字面量 `p_value_literal` 如 `"1.0e-5"`，或顯式指定小數位數 `p_value_decimals`。字串字面量會完整保留末尾有效零，純數值輸入僅按本身的浮點數值解析；若同時傳入相互衝突的精度參數，工具會明確報錯回傳。四捨五入一致性比對採用下界包含、上界排除的半開區間規則。常規的統計數值偏差屬於正常的科學查核結果，僅在輸入參數非法或計算過程異常中斷時才會將 `isError` 設為真值。

撤稿狀態查核會分別記錄本輪觀測到的 `True`、`False` 或 `unknown` 狀態以及上一次確認的有效值。系統在發起外部查詢前透過短鎖分配版本號，確保同一 DOI 的觀測結果按序登記，同時保留其他 DOI 的並行更新增量。本輪觀測值與既往確認紀錄採用獨立的版本序列：較晚回傳的權威確認結果可以更新既往確認紀錄，同時不會掩蓋較新一次查詢因網路或介面受限而產生的本輪未知狀態。迴歸測試任務鏈所使用的外部回應樣例均已顯式標明為測試資料。

MCP 伺服器原生支援 `ping` 探活請求，收到 `notifications/cancelled` 等合法通知訊息時保持靜默不回包，並在遇到格式錯誤的輸入後繼續維持標準輸入輸出工作階段不中斷。當前的同步伺服器實作不宣告支援搶佔式任務取消。訊息處理嚴格遵循 [MCP 訊息規範](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)
與 [ping 規範](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)。

使用獨立隔離環境建置並驗證當前檢出版本的分發套件：

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` 選項會將候選原始碼分發套件原樣解包至倉庫目錄之外，顯式設定 `ARK_REPO` 與
`ARK_SDIST` 環境變數，隨後依次執行套件內單元測試與靜態 QA，並執行程式碼範例檢查及多語言同步校驗。
wheel 與 sdist 分發套件各自使用全新的獨立虛擬環境完成安裝測試，`uvx` 驗收則直接呼叫本機建置的 wheel 套件並搭配獨立快取目錄。
驗收報告會完整記錄分發套件雜湊值與實際匯入路徑。定時執行的輕量級 Hermes 相容性檢查會分別回報固定基線版本與最新上游主分支的被測提交雜湊值；外部介面契約 JSON 報告與任務摘要明確區分 `healthy`、`degraded` 與 `failed` 三種狀態，並將跳過的探測項單獨列明。

## 研究與規劃文件

下列兩份文件屬於探索性研究規劃參考，並非強制性的開發路線圖；文內的研究方向編號均依據 `docs/direction-primitive-mapping.json` 保存的分組關係重算得出。

- [問題圖集 v0 英文版](docs/pain-atlas-v0.en.md)與[問題圖集 v0 中文版](docs/pain-atlas-v0.zh.md)：按科研全生命週期梳理學術知識工作的常見阻礙，並為各項定量論斷標註核實狀態。
- [研究計劃 v0 英文版](docs/research-plan-v0.en.md)與[研究計劃 v0 中文版](docs/research-plan-v0.zh.md)：闡述研究對象模型與核心能力領域，並列出候選研究方向及階段一因子分解表。

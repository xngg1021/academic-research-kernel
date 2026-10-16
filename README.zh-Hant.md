# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

這是一套給科研人員和 AI 助手使用的學術查核與文獻研究工具包。平時用大模型讀論文或寫綜述，最怕模型編造參考文獻與算錯統計數字，或者讀完幾十篇文獻後找不到某句結論出自哪一頁。為了解決這些問題，本倉庫把 14 項常用科研工作流與 12 個確定性查核工具封裝成標準 MCP 服務和命令列工具，用來核對文獻真偽與撤稿狀態，重算論文裡的統計結果，精讀論文並生成帶原文頁碼的中文報告，管理文獻綜述篩選紀錄，以及把每一條研究結論和背後的證據及失敗嘗試對應保存下來。所有工具均可在 Claude Code 與 Cursor 中直接呼叫，也原生支援 Codex、Gemini CLI 與 Hermes Agent。詳細的驗證範圍與外部介面限制見[審計文件](docs/project-lineage-audit-20260920.md)。

作者為 Junfu Shi，筆名 SJF，GitHub 帳號 xngg1021，聯合 Hermes Agent 共同完成。當前授權範圍適用 [Source Lineage License 1.0](LICENSE)。

## 快速開始

請先安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)，隨後直接啟動 2.1.0 版本的 MCP 服務：

```bash
uvx academic-research-kernel@2.1.0 mcp
```

[2.1.0 Release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) 頁面記錄了安裝套件雜湊值與發布狀態。如果您已將發布的 wheel 安裝套件下載到本機，也可以直接執行 `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`。本工具支援 Python 3.10–3.14，`uvx --python 3.12` 命令可顯式指定受支援的 Python 直譯器。基礎安裝套件已內建全部 12 個查核工具與統計計算依賴。

## 驗證安裝

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

`doctor` 自檢命令預設離線執行，負責檢查執行環境依賴、資料格式定義與全部 12 個工具介面；即使沒有設定可選的外部資料庫金鑰，自檢也不會報錯。執行 `doctor --json` 可輸出供程式讀取的 JSON 結果。

## 安裝軟體套件

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

您也可以使用 `pipx install academic-research-kernel==2.1.0` 安裝，或者在虛擬環境內執行 `python -m pip install academic-research-kernel==2.1.0`。安裝時加上 `[full]` 會一併安裝擴充科學計算範例所需的套件；加上 `[research]` 會安裝 `pypdf==6.19.0` 與 `fonttools==4.65.0`，保證不同機器解析 PDF 字型時結果一致，這兩個套件均支援 Python 3.10；加上 `[qa]` 則會安裝倉庫自檢與測試所需的解析依賴。結構化 HTML/XML 解析和常規 DOCX/XLSX 讀取直接使用 Python 標準函式庫，GPU 加速與付費資料庫均為可選項。

## Hermes

請先確認 Hermes 行程的環境變數 `PATH` 中包含 `uv`，再安裝並啟用外掛：

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

為了保持舊設定相容，外掛名稱仍為 `academic-skills`，內部已包含新增 `paper-research` 在內的全部 14 項技能。`mcp.json` 會呼叫 `uv run --frozen --no-dev --no-editable` 與 Python 3.12，並按照倉庫的 `uv.lock` 鎖定檔把獨立執行環境安裝到 `${PLUGIN_DATA}/runtime` 目錄。首次啟動時系統會自動下載缺失的依賴套件，不會改動 Hermes 本身或系統的 Python 環境。如果您只想安裝純技能文件而不啟用外掛服務，請參考下方[安裝與整合](#安裝與整合)章節。

## 從原始碼執行

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

各類依賴的用途劃分、本機復現步驟與發布校驗清單，詳見[分發與發布說明](docs/distribution-release.md)。

## 授權條款

包含本聲明的程式碼版本按照 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 界定的範圍，對受著作權保護的專案材料適用 **Source Lineage License 1.0**。首次切換到 SLL 的提交與後續記錄分界的提交，分別登記在 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 與 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中。自該節點起保留本聲明的後續版本，均沿用相同的授權範圍。

截至提交 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的早期版本按 MIT 授權條款發布，繼續適用當時的授權條款。早期版本的取得者保留完整的 MIT 授權，不需要遷移到 SLL。倉庫完整保留了[原專案 MIT 授權文本](LICENSES/MIT-pre-SLL.txt)，且 [tests/upstream/LICENSE](tests/upstream/LICENSE) 與第三方程式碼來源說明均未改動，新的授權條款不會取消早期版本的既有授權。

SLL 授權條款允許自由使用與研究，支援修改程式碼與商業應用，也允許重新分發和閉源擴充，前提是保留規定的授權聲明與來源追溯資訊。該授權條款不是傳染性的 copyleft 協定，不要求使用者公開自己的原始碼。單純透過網路提供服務而不分發軟體副本，不會觸發核心服務的來源署名要求。本授權條款不包含明示專利授權，第三方材料繼續適用各自原有的授權條款。具體條款以英文原版 [LICENSE](LICENSE) 為準；`LicenseRef-Source-Lineage-1.0` 只是本地標識名，並非 SPDX 官方編號，也不代表已通過 OSI 認證。[外部貢獻規則](CONTRIBUTING.md)與下游使用者的授權權限相互獨立。

## 技能一覽

| 技能 | 版本 | 能幫您做什麼 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 交叉核對論文真偽與各資料庫的被引次數，排查更正或撤稿紀錄，查找開放取用全文，並核對本機 PDF 是否真是目標論文 |
| `skills/literature-analysis` | 1.3.0 | 提供十二項日常文獻分析流程，可以查找相似論文與比對段落重複，檢索反面證據與梳理作者學術背景。該技能同時支援模擬審稿與檢查論證漏洞，生成文獻對比表與推薦投稿期刊，並支援匯出 BibTeX、雙語對照閱讀以及篩查研究空白與評估復現條件 |
| `skills/academic-writing` | 1.1.1 | 輔助潤飾學術文稿並核對引用格式，支援 ISO 690 國際標準與各國大專院校期刊規範，提供投稿指南查詢與可選檢測服務，並協助準備投稿資料與盲審匿名檢查 |
| `skills/math-computation` | 1.2.1 | 把符號推導、數值計算與統計檢定任務分發給可靠的 Python 計算工具，附帶四篇分學科參考指南 |
| `skills/quantitative-paper-audit` | 1.1.0 | 根據論文正文給出的平均值、標準差和樣本數，獨立重算效應量、p 值、信賴區間與勝算比及統計檢定力，幫您揪出論文裡的算術錯誤或統計矛盾 |
| `skills/research-reproducibility` | 1.0.1 | 按照十四步查核清單，逐項檢查一篇論文的程式碼與資料、依賴版本與關鍵指標能不能真正跑通復現 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | 記錄 PRISMA 文獻檢索與篩選過程，換算不同研究的效應量，執行異質性檢定與固定或隨機效應合併，並做敏感性分析與發表偏倚診斷 |
| `skills/literature-watch` | 1.1.0 | 按週自動查詢 OpenAlex 與 Crossref，監控指定主題、作者或某篇 DOI 的最新施引文獻，自動去重後只回報新發表的論文 |
| `skills/retraction-watch` | 1.1.0 | 按週複查關注清單裡的論文 DOI，比對 OpenAlex 的 `is_retracted` 標記與 Crossref 的 `update-to` 更正紀錄，只在論文發生撤稿或更正時發出提醒 |
| `skills/research-object-identity` | 1.1.0 | 把雜亂的 DOI、arXiv 編號與本機檔案雜湊值整理成統一的身份紀錄，核實資源有效狀態，並看清每份分析結果是由哪些原始資料一步步產生的 |
| `skills/claim-evidence-graph` | 1.0.0 | 把文章裡的每一條學術論斷和背後的原文段落、資料表或計算紀錄直接關聯起來，方便隨時核對某句結論有沒有證據支撐 |
| `skills/decision-ledger` | 1.0.0 | 按時間順序維護研究決策與失敗紀錄，把做過的方法選擇與走不通的失敗嘗試記下來，同時保存放棄某條路線的原因及後來的結果修正，避免重複踩坑 |
| `skills/paper-research` | 1.0.0 | 輸入 DOI、網頁連結或本機論文及補充資料，驗證提取出的關鍵欄位並重算核對統計數字，持續保存研究紀錄，生成帶原文頁碼出處的中文報告或兩篇論文的橫向對比 |
| `skills/cross-review-five` | 2.0.0 | 組織多個不同大模型或子智能體對同一份文稿或程式碼獨立盲審，自動合併重複意見並安排交叉質詢，按 P0 至 P3 標註問題嚴重程度，同時把未達成共識的分歧單獨保留下來 |

上述 14 項技能共配有 22 篇 Markdown 參考指南，只在執行對應任務時按需讀取。

## 學術規範與各國引用標準

參考文獻格式、統計報告要求與元資料規範因目標期刊與資助機構而異，同時取決於所屬學科與所在地區。本倉庫以國際標準 **ISO 690:2021** 參考文獻與引文指南、**ISO 5127:2017** 文獻與資訊詞彙，以及 **W3C PROV** 來源追溯模型作為通用基線，同時內建台灣 CNS 13611 與中國大陸 GB/T 7714-2025，以及西班牙 UNE-ISO 690:2024 和德國 DIN ISO 690:2021 等地區規範，並支援 APA 與 IEEE，以及 PRISMA 2020 和 ICMJE 等學科標準。實際寫作時，目標投稿期刊或學校的具體規定始終優先於預設規則，詳見[學術規範架構](docs/standards/README.md)與[自然學術術語指南](docs/terminology/README.md)。

系統保存研究狀態時會自動檢查 DOI 等文獻編號前後是否一致，防止同一項統計查核同時出現互相矛盾的判定結果，並把尚待人工確認的疑點統一收進待確認清單。快取校驗會直接根據保存下來的原始資料與雜湊紀錄重新核對完整性，哪怕同時刪掉狀態紀錄和查核宣告，重放時也會報錯攔下而不會誤判通過。具體修復細節見[四項阻塞收尾說明](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21)。

## 安裝與整合

### 1. 通用 Agent Plugins v1 與 MCP 服務
本倉庫遵循通用的 **Agent Plugins v1** 規範並提供 `plugin.json`，同時透過標準輸入輸出協定執行 `mcp.json` 與 `scripts/mcp_server.py` 定義的 **MCP 伺服器**，可直接在 Claude Code 與 Cursor、Gemini CLI 以及各類支援 MCP 的智能體用戶端中使用。雖然倉庫現已改名為 `academic-research-kernel`，但外掛名 `name: "academic-skills"` 與原有的 MCP 設定別名均保持不變，舊設定無需修改即可繼續使用：

```bash
# 在您的智能體用戶端中直接作為 stdio MCP 服務啟動
uvx academic-research-kernel mcp
```

### 2. 在 Hermes 中按需安裝單項技能
如果您在 Hermes 環境中只想安裝某幾項技能文件，可以直接新增技能源：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

安裝其他技能時，只需替換命令末尾的技能目錄名。常規 `tap` 命令預設讀取主分支，新安裝即可取得上述全部 14 項技能。如果您想在程式碼合併前測試某個開發分支，請先把該分支檢出到本機資料夾，再按本機目錄方式安裝，不要指望 `tap` 命令會自動拉取未合併的分支。

配套關聯技能已對照上游提交 `245e48008fa814b3251f50755eb656bd9fb86cb1` 核對完畢，包含 `arxiv` 與 `grounded-citations`，以及 `docx`、`pdf` 和 `manim-video`。可選技能目錄包含 `huggingface-hub` 與 `llama-cpp`，需要時可單獨安裝。該上游版本不包含 `ocr-and-documents` 與 `pc-hardware-benchmark`，本倉庫也不依賴這兩項。

## 學術資料源與介面限額

- OpenAlex 基礎查詢支援匿名使用，但匿名每日額度較小。根據 2026-09-06 核對的官方文件，匿名存取每日額度為 $0.10，申請免費 API 金鑰後每日額度為 $1，每秒最多發送 100 次請求；不同查詢方式的扣費標準不同，並非不限量使用。建議將免費金鑰存入環境變數 `OPENALEX_API_KEY`，查詢時配合上限為 100 的 `per_page` 參數與游標分頁。
- Crossref 提供帶限流的公開元資料介面。查核論文更正與撤稿訊號時必須同時核對 DOI 與更新方向；介面沒查到紀錄不代表論文一定沒有問題。
- Unpaywall 要求在環境變數 `UNPAYWALL_EMAIL` 中填入真實聯絡信箱。如果介面沒有回傳全文位址，不代表網路上不存在其他開放取用版本。
- arXiv 與 Europe PMC，以及 PubMed E-utilities 和 DOAJ 屬於補充資料源，各自有獨立的限流規則，預設自動化測試不會逐一請求。Semantic Scholar 的匿名公共額度與專屬金鑰額度分開計算，能連上介面也不保證每篇論文都開放了引文上下文。
- Scite 與 Dimensions，以及 Scopus、Web of Science 和商業 AI 檢測工具屬於可選的外部付費服務。呼叫前請先確認您自己的帳號權限與剩餘配額，本倉庫不提供通用免費額度。

詳細介面說明見 [OpenAlex 認證指南](https://help.openalex.org/api/authentication/)、[額度與查詢計費說明](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新過濾器文件](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

## 研究紀錄保存與權限範圍

系統的資料接入層採用 `ResearchArtifactEnvelope v1` 與 `ArtifactIngestionReceipt v1` 格式，內建 15 個解析器，涵蓋全部 14 項學術技能外加 1 個普通文本兜底解析器，並對外提供 12 個無狀態的 stdio MCP 工具。每當系統保存研究對象與學術論斷關聯，或者寫入研究決策紀錄、待確認事項與證據檔案時，查核紀錄都會記下對應的類型、唯一編號與 SHA-256 雜湊值。離線重放時會直接核對這些雜湊值；新建的空決策紀錄同樣有效，而一旦某次批次寫入中途出錯，系統會自動回滾，不會留下半截損壞的資料。

如果某條查核紀錄要標記為 `fully_verified` 已完全核實，呼叫方必須提供對應的原始檔案內容，以便系統獨立複核。Python 本機呼叫可透過 `LineageVerificationContext` 傳入原文，MCP 協定呼叫則只允許直接傳入檔案內容位元組流，不允許讀取宿主機任意檔案路徑。單次讀取的檔案大小預設上限為 10 MiB，受信任的本機宿主環境可以按需調高上限。如果沒有提供原文內容，系統不會把結果標為已完全核實。未經提取的自由文本保持原樣儲存，不同審稿模型的分歧意見全部公開保留；何時保存紀錄與放棄哪條路線，以及重開哪項嘗試與最終採納哪條學術結論，始終由研究者自己決定。

資料格式與版本相容規則見[架構文件](docs/kernel-architecture.md)，Python 軟體套件、`uvx` 與官方 MCP Registry 的發布細節見[分發與發布說明](docs/distribution-release.md)。全部 21 個語種的 README 均已更新至 2.1.0 版本，全倉文件的多語言雜湊同步狀態記錄於[多語言清單](docs/i18n/manifest.json)，早期的完整評審與合併存證彙總於[收尾紀錄](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)。

## 本機自檢與測試

執行測試請使用獨立的 Python 虛擬環境。不同科研任務用到的計算套件各不相同，Hermes 預設環境不一定全部預裝；安裝 `requirements-qa.txt` 可以配齊全部測試依賴，用來跑通所有帶標記的程式碼範例：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

`scripts/qa.py` 會自動檢查技能標頭資訊與參考檔案路徑，掃描是否誤留了個人電腦路徑或金鑰字串，並驗證 Python 語法與可執行程式碼範例。每個標有 `smoke-test: true` 的程式碼區塊都會在全新的子行程裡原樣跑一遍；繪圖範例透過 `PLOT_DIR` 讀取保存目錄，預設展開為 `~/plots`，跑自動化測試時則會寫入暫存資料夾。未註明類別的 Python 程式碼區塊會被直接攔下；標有 `fragment:` 的程式碼片段只檢查語法而不單獨執行；標有 `external-test:` 的程式碼區塊只有手動執行 `scripts/verify_external_apis.py` 時才會連網執行。所有設定項檢查通過時該命令回傳 0，程式碼、格式或文獻核對出錯回傳 1，網路不通、金鑰失效或配額用盡回傳 2，未設定的可選外部服務則顯示 `SKIP`。

測試套件沿用了固定版本的 Hermes 技能編寫規範檢查，完整測試本倉庫的全部 14 項技能，並對照固定版本的內建與可選技能目錄核對引用關係。持續整合環境只在安裝依賴套件時連網，平時的程式碼提交測試不會請求外部學術資料庫。

GitHub Actions 持續整合覆蓋三大作業系統的 x86_64 與 ARM64 架構。測試範圍包含執行 Python 3.10 至 3.14 的 Linux x86_64 與 `ubuntu-24.04-arm` 映像，涵蓋 `ubuntu-26.04` 與 `ubuntu-26.04-arm` 預遷移環境，同時覆蓋 Windows x86_64 與 `windows-11-arm`，以及 `macos-latest` 與 `macos-15-intel` 環境，並附帶針對上游 `main` 分支最新程式碼的即時載入檢驗。本機完整迴歸測試套件共通過 1165 項測試，詳細結果與覆蓋範圍見[正確性修復紀錄](docs/maintenance/correctness-repair-20261008.md)，遠端測試日誌會單獨標明所測的程式碼提交雜湊值。每當程式碼推送到 `main` 分支時，獨立的整合測試工作流還會自動安裝 `tests/upstream/provenance.json` 記錄的固定版本 Hermes，實測對本倉庫執行 `tap add` 與 `search`，以及 `install` 和 `list` 全流程。各項檢查的確切版本與限制見[審計文件](docs/project-lineage-audit-20260920.md)。

[tools/longtail/](tools/longtail/README.md) 目錄存放確定性長尾測試場景產生器，從 4096 個 SHA256 種子候選中選出 30 個代表性測試場景，並自動生成核驗覆蓋度報告，分別統計 16 類能力族、倉庫實際的 14 項技能以及 36 項具體任務目標。每項技能至少出現 2 次並覆蓋 2 個不同任務目標，且必須包含該技能的核心目標。

`scripts/scfabric/` 目錄提供科學計算與統計分析基準測試工具，包含硬體檢測與數值精度門禁，並提供五類計算負載測試及 `ComputeReceipt` 查核紀錄。首輪實測資料見 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)；計算任務預設使用 CPU，只有在基準測試查核通過並生成紀錄後才會啟用硬體加速。

## 讓本地 Agent 幫您讀論文寫報告

安裝帶 `[research]` 擴充的 2.1.0 軟體套件後，可以把論文精讀技能直接匯出到您的本機智能體目錄：

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

讓 Work 或其他本機智能體讀取匯出的 `SKILL.md`，然後只需把論文 DOI、公開網頁連結或本機資料夾發給智能體，直接說：
“請研究這篇論文與補充資料，整理實驗方法並核對能重算的關鍵數字，給我一份帶出處的中文報告。”
如果要對比兩篇論文，可以直接說：“請比較這兩篇論文的資料與實驗方法，核對評估條件與主要結果，並說明哪些結論可以直接比較。”智能體會在同一個任務裡讀完原文與附件並提取關鍵數字，隨後呼叫統計工具重算核對、保存研究狀態，並生成帶原文頁碼與段落定位的中文報告。原有的 12 個 MCP 工具保持不變，這套新流程透過命令列與匯出的技能檔案配合完成。

命令列工具分三步執行：

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` 負責下載或讀取論文正文與補充資料，記錄檔案雜湊值並按頁碼和章節建立原文段落索引。`finish` 負責檢查智能體讀完原文後提取出的結構化資料，呼叫統計函式重算符合條件的 t 檢定與 p 值、兩組效應量以及計數和百分比，保存查核後的研究狀態並匯出中文 Markdown 與 HTML 報告。`compare` 負責查核智能體對兩篇論文的資料、實驗條件和結果可比性作出的對比結論。由於正文閱讀直接由您當前使用的智能體按照 [paper-research](skills/paper-research/SKILL.md) 完成，命令列工具本身不需要額外設定大模型帳號。保存下來的原始文獻與提取快照隨時可以離線重放，生成的報告也會明確標出哪些結論來自離線重放、連網取得或重新閱讀。

## 統計重算精度與軟體套件驗證

公開的 `academic_recompute_statistics` 工具支援重算 t 檢定的 p 值以及兩組樣本的 Cohen's d 與 Hedges' g 效應量，信賴區間、勝算比與風險比計算則可呼叫內部 Python 函式。如果核對論文時需要保留小數點末尾的零，可以傳入字串參數 `p_value_literal` 如 `"1.0e-5"`，或者用 `p_value_decimals` 指定小數位數。字串參數會保留末尾有效零，普通數字只按浮點數值本身處理；如果同時傳入了互相衝突的精度設定，工具會直接報錯提醒。四捨五入核對採用下界包含、上界排除的規則。重算後發現原論文數字與重算值不一致屬於正常的科學查核結果，只有輸入參數不合法或計算過程出錯時才會將 `isError` 設為真值。

撤稿狀態查核會把本次連網查到的 `True`、`False` 或 `unknown` 結果與上一次確認過的有效狀態分開保存。系統在發起查詢前透過簡短鎖機制按順序記錄同一篇 DOI 的觀測結果，同時保留其他文獻的並行更新。如果最新一次查詢因為網路波動或介面限流暫時回傳 `unknown`，系統會如實標出本次檢查尚未核實，但不會沖掉之前已經確認過的既有紀錄。迴歸測試裡用到的外部回應均已標明為本機測試樣本。

MCP 伺服器支援 `ping` 連通性檢查，收到 `notifications/cancelled` 等合法通知時按協定保持靜默，遇到格式錯誤的輸入也不會中斷當前標準輸入輸出連線。訊息處理遵循 [MCP 訊息規範](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)與 [ping 規範](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)。

如需使用隔離環境建置並驗證當前版本的安裝套件，可執行：

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` 參數會把建置出的原始碼套件解包到倉庫目錄之外的暫存資料夾，設定 `ARK_REPO` 與 `ARK_SDIST` 環境變數，並對解包後的檔案依次執行單元測試與靜態自檢，同時執行程式碼範例檢查與多語言同步校驗。wheel 套件與原始碼套件各自在全新的虛擬環境中測試安裝，`uvx` 則使用本機 wheel 套件配合獨立快取目錄完成驗證。定時執行的輕量級 Hermes 相容性檢查會分別回報固定基線版本與最新上游主分支的被測提交雜湊值；外部介面檢查報告與任務摘要明確區分 `healthy`、`degraded` 與 `failed` 三種狀態，並單獨列出跳過的檢查項。

## 早期研究與規劃文件

下面兩份文件是專案立項階段的探索性設計筆記，不是強制開發路線圖；文內的研究方向編號均根據 `docs/direction-primitive-mapping.json` 保存的分組關係自動重算得出。

- [問題圖集 v0 英文版](docs/pain-atlas-v0.en.md)與[問題圖集 v0 中文版](docs/pain-atlas-v0.zh.md)：梳理日常科研工作各環節的常見阻礙，並為文中的定量說法標註核實狀態。
- [研究計劃 v0 英文版](docs/research-plan-v0.en.md)與[研究計劃 v0 中文版](docs/research-plan-v0.zh.md)：說明研究對象模型與核心能力劃分，並列出候選研究方向及第一階段的長尾場景分解表。

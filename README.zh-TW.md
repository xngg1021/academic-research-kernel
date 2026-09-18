# academic-research-kernel

English · [简体中文](README.zh-CN.md) · 繁體中文 · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md)

跨宿主中立的學術能力內核與多智能體交叉審議工具套件。倉庫提供 13 個學術技能與核驗工具，支援便攜式 Agent Plugins v1 規範與 MCP (Model Context Protocol) 服務入口，原生相容 Hermes Agent、Claude Code、Cursor 與終端獨立子代理。涵蓋來源核驗、文獻分析、學術寫作、數值計算、定量論文審計、復現審計、系統綜述與統合分析、研究物件身份與譜系、動態多模型交叉審議，以及兩套週更監控自動化。倉庫附帶可執行的示例檢查；驗證範圍與外部服務限制記錄於[審計文檔](docs/audit-20260906.md)。

作者：Junfu Shi（SJF，xngg1021），Hermes Agent。當前授權範圍：[Source Lineage License 1.0](LICENSE)。

## 授權條款

含本通知的快照，對 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 所識別的受保護材料與權利，採用 **Source Lineage License 1.0**。首個 SLL 提交與樹，以及其後的邊界記錄提交，於 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 與 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中區分。自該記錄邊界起保留本通知的快照，攜帶相同的授權範圍。

截至 `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` 的歷史快照按 MIT 許可分發，受適用於那些副本的條款約束。接收者保留有效的 MIT 權限，無需遷移至 SLL。[前項目 MIT 文本](LICENSES/MIT-pre-SLL.txt)已保存；[tests/upstream/LICENSE](tests/upstream/LICENSE) 及其第三方來源記錄保持原狀。新的根授權不抹除既有權利。

SLL 廣泛允許使用、研究、修改、商用、分發與專有增補，受相應許可、通知與來源譜系條件約束。它不屬 copyleft，不要求原始碼披露。純網路服務且不提供副本者，不單獨觸發核心服務譜系通知條件。無明示專利授予。第三方材料仍受其自身條款約束。以英文原版 [LICENSE](LICENSE) 為準；`LicenseRef-Source-Lineage-1.0` 為本地引用，非 SPDX 指配，亦不聲稱 OSI 批准。[貢獻接收](CONTRIBUTING.md)與下游許可權限相互獨立。

## 技能

| 技能 | 版本 | 功能 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | 交叉核對身份與來源特定的被引數；檢查更新與撤稿訊號；定位開放獲取文本並核驗 PDF 身份 |
| `skills/literature-analysis` | 1.3.0 | 十二個工作流：主題相似、局部文本重疊、反證、作者檔案、模擬評審、謬誤檢查、評審矩陣、期刊候選、BibTeX、雙語閱讀、研究空白篩查、復現 |
| `skills/academic-writing` | 1.1.1 | 編輯、引文規範（APA、MLA、Chicago、IEEE、AMA、GB/T）、期刊須知、可選檢測服務、投稿材料、中文學術要求 |
| `skills/math-computation` | 1.2.1 | 既有領域與任務路由及修正後的數值與統計示例；四篇領域參考文件 |
| `skills/quantitative-paper-audit` | 1.1.0 | 反算論文報告的統計量（效應量、p 值、信賴區間、OR/RR、實現功效）並檢測數值錯配 |
| `skills/research-reproducibility` | 1.0.1 | 十四階段復現審計流水線，含結構化清單引擎、五層事實與四態回執 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA 檢索日誌、篩選台帳、效應量換算、異質性、固定與隨機效應合併、敏感性與發表偏倚診斷 |
| `skills/literature-watch` | 1.1.0 | 週更藍圖：監控主題、作者與 DOI 在 OpenAlex 與 Crossref 的新作品；去重並只報告新增 |
| `skills/retraction-watch` | 1.1.0 | 週更藍圖：對照 OpenAlex is_retracted 與 Crossref 更新記錄（update-to 訊號）複查 DOI 監控清單；只報告狀態變化 |
| `skills/research-object-identity` | 1.1.0 | 確定性研究物件身份層與生產譜系核心（Provenance Kernel v1）：識別符歸一、五態判定、內容定址衍生圖、因果 DAG 校驗與毫秒級離線逆向溯源 |
| `skills/claim-evidence-graph` | 1.0.0 | 確定性科學論斷-證據圖核心：連接學術論斷、實證證據錨點、事實核驗與計算譜系 |
| `skills/decision-ledger` | 1.0.0 | 確定性追加式決策與負結果台帳內核：決策圖譜、失敗路徑存證、剪枝因果追溯與內容定址結果修正 |
| `skills/cross-review-five` | 2.0.0 | 動態多席位異構模型/子代理交叉審議（Kimi K3、DeepSeek V4 Pro、GLM 5.3、Claude、Gemini 等）：v2 四階段 Sparse Deliberation 流（盲審產出、斷言級聚類合併、基於匈牙利算法的全局最優互補錯排匿名質詢、對賬與未決保護賬本，支持 P0-P3 嚴重級別） |

十三個技能共含 21 篇 Markdown 參考文件，按需加載。GB/T 7714-2025 已生效；寫作參考區分其已核實生效日期與顯式標註的 2015 示例。完全符合 2025 版需以目標機構的模板或標準文本為準。

## 安裝與集成

### 1. 便攜式 Agent Plugins v1 與 MCP 工具服務
本倉庫遵循廠商中立的 **Agent Plugins v1** 規範（`plugin.json`），並通過 stdio 協議暴露通用的 **MCP 伺服器**（`mcp.json` / `scripts/mcp_server.py`），原生相容 Claude Code、Cursor、Gemini CLI 與任意現代智能體宿主：

```bash
# 在您的智能體宿主中直接作為 stdio MCP 服務加載
python scripts/mcp_server.py
```

### 2. 在 Hermes 中安裝
在 Hermes 安裝環境中執行：

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

安裝其餘技能時替換完整標識符中的目錄名。常規 tap 讀取預設分支，新裝即得上述技能集。如需在合併前檢查工作分支，在本地檢出該分支並遵循所裝 Hermes 版本的本地目錄安裝說明。不要假定 tap 命令會選中 PR 分支。

捆綁相關技能以上游 `245e48008fa814b3251f50755eb656bd9fb86cb1` 為準核對：arxiv、grounded-citations、docx、pdf、manim-video。huggingface-hub 與 llama-cpp 在可選目錄中，可能需另行安裝。ocr-and-documents 與 pc-hardware-benchmark 在該快照中未找到，亦非依賴項。會話工具與文檔及瀏覽器後端取決於本地配置。

## 數據源訪問

- OpenAlex 基本查詢可匿名運行，每日預算較小。2026-09-06 的現行文檔規定匿名每日 0.10 美元、免費 API 密鑰每日 1 美元，每秒請求上限 100。費用因查詢類型而異，這並非無限制訪問。可選密鑰存於 `OPENALEX_API_KEY`。使用 `per_page`（最大 100）與遊標分頁。
- Crossref 提供公開元數據訪問並有限流。更新關係與 Retraction Watch 訊號需要 DOI 與方向核對；記錄缺失不證明論文未受影響。
- Unpaywall 需要真實聯絡郵箱存於 `UNPAYWALL_EMAIL`。未找到位置不證明不存在開放獲取副本。
- arXiv、Europe PMC、PubMed E-utilities 與 DOAJ 為補充來源，各有其政策。預設測試不會全部調用。Semantic Scholar 有共享匿名限額與單獨分配的密鑰限額；訪問權不保證引文上下文可用。
- Scite、Dimensions、Scopus、Web of Science 與 AI 檢測產品為可選外部服務。使用前核對當前帳戶與 API 權限及配額；不承諾通用免費層或固定價格。

見 [OpenAlex 認證](https://help.openalex.org/api/authentication/)、[預算與查詢成本](https://help.openalex.org/api/llm-quick-reference/) 與 [Crossref 更新過濾器](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

## 驗證

使用專用 Python 環境。運行時函式庫按任務而定，不保證 Hermes 已裝。QA 依賴更廣，使全部標記示例可運行：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA 校驗元數據、參考文件、個人路徑與已知密鑰模式、Python 語法與標記為可執行的代碼塊。每個 smoke 示例在全新子進程中原樣運行；繪圖示例接受 `PLOT_DIR`（預設 `~/plots`，顯式展開），測試使用臨時目錄。未分類的 Python 代碼塊被拒絕；`fragment:` 塊做語法檢查但需顯式輸入，不單獨執行。`external-test:` 塊僅經手動外部命令運行。QA 在通過的檢查上返回 0，代碼、schema 或身份失敗返回 1，傳輸、認證或配額不可用返回 2；未配置的可選服務保持 SKIP。

固定版本的技能編寫規範測試（authoring tests）被複用，其逐技能規則不改動。完整 Hermes 上游發行包的全局測試不適用於本 tap；本倉庫測試覆蓋全部十三個技能，並按固定的捆綁與可選目錄解析參考文件。這不是完整的 Hermes 安裝測試。CI 僅在安裝依賴時使用網絡；常規 PR 測試不調用學術 API。

CI 經 GitHub Actions 在 Ubuntu（Python 3.10、3.11、3.12 與 3.13）、Windows（Python 3.12）與 macOS（Python 3.12）六組矩陣上運行完整 QA 套件。另有一個 tap 集成工作流在 main 推送時運行：安裝 tests/upstream/provenance.json 所記錄的固定 Hermes 檢出，並針對本倉庫執行 tap add、search、install 與 list。不聲稱全新 Hermes 會話與每種依賴版本組合已驗證。確切版本、檢查項與限制見[審計文檔](docs/audit-20260906.md)。

## 研究與規劃文檔

- [痛點圖集 v0（英文）](docs/pain-atlas-v0.en.md)、[中文版](docs/pain-atlas-v0.zh.md)：按生命週期枚舉學術知識工作摩擦，定量論斷標註核實狀態。
- [研究計劃 v0（英文）](docs/research-plan-v0.en.md)、[中文版](docs/research-plan-v0.zh.md)：十四架構原語、Research Object 模型、四平面、候選方向與階段一因子分解矩陣。

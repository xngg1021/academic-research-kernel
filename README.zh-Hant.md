# academic-research-kernel

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

這是一套面向科研人員與 AI 智慧體的確定性學術查核與論文工程核心。

平時用大型語言模型讀論文或寫論文，最容易撞上兩類硬傷。讀別人的論文時，模型按機率續寫文字，經常順著作者的敘述把算錯的統計量與湊出來的消融表格，或者已經撤稿的文獻與空殼程式碼倉庫當成事實複述出來。寫自己的論文時，單靠提示詞叮囑模型檢查格式，很難攔住雙盲匿名殘留與手抄表格塗改，也難以自動發現圖表懸空引用或漏掉目標會議的必寫章節。

本倉庫從第一性原理出發，把這兩件事拆開處理：讓大型語言模型專心負責自然語言閱讀與語義提煉，把所有能用數學公式與公開資料庫介面，以及語法解析樹和雜湊校驗定死的環節，全部交給確定性程式碼執行。全倉將 14 項科研工作流與 18 個標準 MCP 服務工具，以及 16 組命令列子命令收攏在同一套狀態核心之上，原生支援 Claude Code 與 Cursor，也直接相容 Codex、Gemini CLI 與 Hermes Agent。詳細的驗證範圍與外部介面範圍見[審計文件](docs/kernel-architecture.md)。

作者為 Junfu Shi，筆名 SJF，GitHub 帳號 xngg1021。當前授權範圍適用 [Source Lineage License 1.0](LICENSE)。

---

## 一、兩分鐘快速上手

先安裝 [uv](https://docs.astral.sh/uv/getting-started/installation/)，再按您的使用方式任選一條命令安裝 `2.4.2` 版本：

```bash
# 方式一：安裝帶 PDF 解析支援的完整命令列工具，並匯出論文精讀技能給本機智慧體
uv tool install "academic-research-kernel[research]==2.4.2"
academic-research-kernel research skill --output ./paper-research

# 方式二：作為標準 stdio MCP 服務啟動，供 Claude Code / Cursor / Codex 等用戶端呼叫
uvx academic-research-kernel@2.4.2 mcp
```

安裝完成後，可以先跑一次離線環境自檢，並直接試試文獻查核與會刊規則查詢：

```bash
academic-research-kernel doctor
academic-research-kernel verify-source https://doi.org/10.1038/nature14539 --normalize-only
academic-research-kernel venue-template --action list-venues
```

`doctor` 命令預設離線執行，負責檢查執行環境依賴、26 套 JSON 資料格式與全部 18 個 MCP 工具介面；即使沒有設定可選的外部資料庫金鑰，自檢也不會報錯。直接在終端機執行 `mcp` 子命令會讓程式進入標準輸入輸出監聽狀態，等待 MCP 用戶端發來請求。[2.4.2 Release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.4.2) 頁面記錄了建置產物的 SHA-256 雜湊值。本工具支援 Python 3.10 至 3.14，基礎安裝套件已內建全部工具，科學計算套件只在呼叫分佈檢定或檢定力重算時按需載入。

---

## 二、上半場：讀別人的論文與查核外部證據

審讀外部論文或撰寫文獻綜述時，系統按「先核實文獻與程式碼真偽，再重算表格與統計數字，最後生成帶原文頁碼的報告」逐層推進。

### 1. 讓本機智慧體精讀單篇論文或橫向對比兩篇論文

將匯出的 `./paper-research/SKILL.md` 交給您的本機智慧體，發給它一個 DOI、公開網頁連結或本機資料夾，直接下達指令：
「請研究這篇論文與補充材料，整理實驗方法並核對能重算的關鍵數字，給我一份帶出處的中文報告。」

命令列分三步配合智慧體完成核驗：

```bash
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` 負責讀取 PDF（`.pdf`）與 HTML（`.html`、`.htm`）、XML/JATS（`.xml`）與 DOCX/XLSX（`.docx`、`.xlsx`），以及 LaTeX/BibTeX（`.tex`、`.bib`、`.bbl`）、Markdown（`.md`）、純文字（`.txt`）或 Python（`.py`）原始碼包，計算檔案雜湊並按頁碼與章節建立原文段落索引。智慧體讀完原文填好候選提取結果後，`finish` 會逐條核對每個數字是否真實出現在聲明的原文位置，自動呼叫統計重算引擎驗證數值是否自洽，保存研究狀態並生成帶頁碼出處的中文 Markdown 與 HTML 報告。`compare` 負責核驗兩篇論文在資料集、實驗條件與評估指標上是否具備直接可比性。保存下來的原始材料與提取快照隨時可用 `academic-research-kernel research replay --project PROJECT` 離線重放。

### 2. 查證文獻真偽、開放取用全文與審稿紀錄及程式碼倉庫

針對外部取證、復現查核與增量文獻巡檢，可以直接在終端機呼叫七組子命令：

```bash
# 核對 DOI/arXiv 編號、校驗本機 PDF 首頁真偽，或在 OpenAlex 與 Crossref 交叉查核更新與撤稿訊號
academic-research-kernel verify-source 10.1038/nature14539
academic-research-kernel verify-source ./paper.pdf --verify-pdf --title "Expected Paper Title"
academic-research-kernel verify-source 10.1038/nature14539 --check-updates

# 按 Unpaywall 與 arXiv、OpenAlex 與 Semantic Scholar 及 Europe PMC 順序定位開放取用全文並校驗 DOI
academic-research-kernel locate-oa 10.1038/nature14539

# 查核 OpenReview 審稿紀錄、評分均值與變異數，或計算會刊全量投稿的真實分位數與賽道錄用率
academic-research-kernel openreview-audit --forum-id Forum_Synth_01 --mirror-json ./venue-mirror.json
academic-research-kernel openreview-audit --venue-stats ./venue-mirror.json --topic-regex "memory|agent"

# 掃描程式碼倉庫的真實非第三方原始碼體量、Git 提交紀錄與 README 宣稱命令是否對得上
academic-research-kernel repo-forensics --local-repo ./target-repo

# 執行 14 階段復現查核清單裁定，或執行文獻增量監控與撤稿巡檢離線自測
academic-research-kernel repro-checklist --input ./repro-checklist.json
academic-research-kernel literature-watch --self-test
academic-research-kernel retraction-watch --self-test
```

`locate-oa` 會拒絕把 `is_oa=false` 的付費牆落地頁或 DOI 不匹配的紀錄當成全文連結。`openreview-audit` 會自動過濾缺失評分並按 `forum_id` 去重，只用普通審稿人的評分計算均分與變異數，把領域主席的元審稿與最終決定單獨分列。`repo-forensics` 優先透過 `git ls-files` 區分專案自有原始碼與打包進來的第三方目錄，防止把塞滿第三方函式庫的倉庫誤判為高工作量專案。

### 3. 15 類統計與取證重算、物理下界校驗與統合分析

公開的 `academic_recompute_statistics` MCP 工具與 `recompute.py` 引擎支援 15 類確定性查核。基礎檢定涵蓋 $t$ 檢定與 $F$ 檢定，以及 $\chi^2$ 檢定與迴歸係數 $\beta/\text{SE}$ 的 Wald 檢定；區間與效應量檢定涵蓋信賴區間對稱性與 $2\times 2$ 列聯表勝算比及風險比，以及雙樣本 Cohen's $d$ 與 Hedges' $g$ 效應量；自洽檢定涵蓋百分比分母反推與有界量表標準差可能性，以及自由度核對和 $t$ 檢定統計檢定力反算。

針對機器學習與系統論文常見的表格異常，`2.3.0` 版本新增了三項表格取證體檢能力（可透過 `academic-research-kernel table-forensics --input spec.json` 或 MCP 呼叫）：
- **樣本分區守恆 `partition_conservation`**：核對總樣本量是否嚴格等於各互斥子集計數之和；
- **消融實驗恆定偏移 `ablation_delta_regularity`**：檢測消融表的多列指標之間是否存在人為加減常數的固定平移現象；
- **未壓縮儲存與全量掃描頻寬下界 `storage_bandwidth_bounds`**：在假定未壓縮定寬浮點表示與單次全量線性掃描的前提下，根據向量條數、向量長度與位元組寬度計算裸向量體積下界與全表掃描延遲下界，排查聲稱完整未壓縮儲存卻低於裸向量體積的矛盾。

如果核對論文時需要保留小數點末尾的有效零，可以傳入字串參數 `p_value_literal` 如 `"1.0e-5"`，或用 `p_value_decimals` 指定小數位數。多篇研究的固定效應與 DerSimonian-Laird 隨機效應合併、異質性 $Q/I^2/\tau^2$ 與 Egger 偏倚檢定可直接執行：

```bash
academic-research-kernel meta-analyze --input studies.json
```

---

## 三、下半場：寫自己的論文與投稿前確定性門禁

自己動手寫論文與準備投稿時，系統提供從工作區初始化與實驗資料轉三線表，到雙盲匿名清洗與投稿前硬性門禁的四步工具鏈。

```bash
# 1. 查看內建的 8 大會刊規格、初始化論文目錄，或從 ClaimEvidenceGraph 匯出已就緒的 % ark:claim=<id> 證據錨點清單
academic-research-kernel venue-template --action list-venues
academic-research-kernel venue-template --action scaffold --workspace-dir ./workspace --slug my-paper --venue iclr
academic-research-kernel venue-template --action export-ceg-anchors --ceg ./ceg.json

# 2. 將實驗結果收據或 paper-research 提取與對比產物直接渲染為 LaTeX booktabs 三線表
academic-research-kernel receipt-to-latex --input ./results-receipt.json --caption "Main Results" --label "tab:main"
academic-research-kernel receipt-to-latex --input ./extraction.json --from-research extraction --caption "Extracted Metrics" --label "tab:ext"

# 3. 執行雙盲匿名掃描，攔截 .tex/.bib 與編譯後 PDF 詮釋資料中的實名與致謝及自引暗號和本機路徑
academic-research-kernel sanitize-blind --target ./workspace/my-paper

# 4. 執行投稿前全量門禁，並可選開啟 --check-academic-style 掃描中英文 AI 套話、含糊方法句與無錨點強聲明
academic-research-kernel pre-submission-lint --tex ./workspace/my-paper/main.tex --venue iclr --contribution-type systems_architecture --check-academic-style
```

`receipt-to-latex` 全程採用 `Decimal` 精確十進位捨入，避免手抄實驗表格改錯數字或浮點精度漂移。`double-blind-sanitize` 既掃描文本中的 `\author` 與自訂實名巨集，以及 `\icmlauthor` 與 `pdfauthor` 設定，也會直接讀取編譯後 PDF 的 `/Author` 與 `/Creator` 文件屬性字典。`pre-submission-lint` 對照 `skills/academic-writing/references/venue-specs.json` 中的當屆規則，檢查是否誤開 `final`、`preprint` 或 `camera-ready` 巨集套件選項，跨頁追蹤文末豁免聲明使 `Reproducibility Statement`、`Ethics Statement` 與 `Acknowledgments` 不再虛增正文頁數，利用平衡大括號屏蔽 `\newcommand` 與 `\def` 巨集定義體以消除未呼叫草稿巨集的 `TODO` 誤報，跨檔案核對 `\ref`、`\Cref` 與 `\label{...}` 及 `lstlisting[label={...}]` 是否閉合，攔截 `Author et al. ~\cite{...}` 作者名重複偽影與著者年份制下全篇混用裸 `\cite` 的排印缺陷，攔截雙盲初審稿中的非匿名致謝與基金號揭露，並在耗時隨文本長度線性增長的前提下校驗摘要與結論中的定量論斷在 `ClaimEvidenceGraph` 中是否真正連向 `support_status == "supported"` 的正向證據邊。

參考文獻格式轉換、縮寫大括號保護匯出、跨源去重、引文關係圖與綜述對比表可直接呼叫：

```bash
academic-research-kernel bibliography --from bibtex --to csl --input refs.bib
academic-research-kernel bibliography --action export-bibtex --input works.json --output refs.bib
academic-research-kernel bibliography --action deduplicate --input works.json --output deduped.json
```

### 同行評議中五類確定性缺陷的宏觀分佈：ICLR 2026 共 `19,473` 篇有分稿件

為說明缺失誤差棒與版式超限、表格消融異常與漏引基線及缺失復現程式碼這五類確定性檢查的現實依據，我們在不擬合任何經驗權重與主觀分數閾值的前提下，按論文粒度統計了 ICLR 2026 共 `19,473` 篇有分投稿與 `75,769` 條官方審稿意見中至少一條審稿意見指出對應缺陷的稿件佔比 `k / N`；全集包含四類常規決定共 `18,791` 篇與帶評語程序性拒稿 `682` 篇，`SHA-256` 奇偶分半子集分別為 `9,765` 篇與 `9,708` 篇，所有單篇稿件均保持完全匿名，彙總數據見[去識別化統計彙總表](docs/benchmarks/iclr2026-openreview-incidence-receipt.json)：

| 錄用檔位與可靠度分層 | 有效投稿數 $N$ | 評分均值 / Soundness 均值 | 審稿意見提及五類確定性缺陷的稿件佔比 `k / N` |
| --- | --- | --- | --- |
| **Oral 口頭報告** | 224 | 6.40 / 3.07 | **48.2%** (`108/224`)，含缺失誤差棒 12.1% 與表格消融異常 7.1%，以及漏引基線 2.7% |
| **Poster 海報錄用** | 5,134 | 5.36 / 2.83 | **54.0%** (`2,772/5,134`)，含缺失誤差棒 19.5% 與表格消融異常 7.9%，以及漏引基線 4.9% |
| **Rejected 拒稿** | 8,453 | 3.96 / 2.49 | **59.8%** (`5,057/8,453`)，含缺失誤差棒 23.4% 與表格消融異常 10.5%，以及漏引基線 6.1% |
| **Withdrawn 撤稿** | 4,980 | 3.35 / 2.33 | **62.6%** (`3,117/4,980`)，含缺失誤差棒 23.8% 與表格消融異常 12.4%，以及漏引基線 6.8% |
| **Desk Reject 程序性拒稿** | 682 | 4.01 / 2.46 | **63.6%** (`434/682`)，含缺失誤差棒 21.8% 與表格消融異常 11.6%，以及漏引基線 6.6% |
| **Soundness $\ge 3.25 \to \le 2.0$** | 1,077 $\to$ 2,861 | $\ge 3.25 \to \le 2.0$ | **49.1% $\to$ 67.4%** (`529/1,077` $\to$ `1,928/2,861`)，含缺失誤差棒 14.9% $\to$ 27.5% 與缺程式碼 15.6% $\to$ 27.7% |


## 四、14 項學術技能一覽與智慧體整合

| 技能 | 版本 | 能幫您做什麼 |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.3.0 | 交叉核對論文真偽與各資料庫被引數，排查更正或撤稿紀錄，定位開放取用全文，審計 OpenReview 審稿紀錄並取證程式碼倉庫 |
| `skills/literature-analysis` | 1.3.0 | 按雪球法拓展相關文獻，對比多篇論文的方法與分歧，梳理作者學術履歷，按評審清單審讀稿件並支援 BibTeX、RIS 與 CSL-JSON 互轉 |
| `skills/quantitative-paper-audit` | 1.2.0 | 根據論文報告的統計量獨立重算 $p$ 值與效應量及信賴區間、勝算比與統計檢定力，並查核樣本分區守恆與消融恆定偏移及物理頻寬下界 |
| `skills/math-computation` | 1.2.1 | 呼叫 SymPy 與 NumPy 及 SciPy、statsmodels 與 PyTorch 完成符號推導與微積分求解，涵蓋線性代數與微分方程及作業研究最佳化和蒙地卡羅模擬 |
| `skills/academic-writing` | 1.3.2 | 輔助潤色論文結構與語言，按各國規範排版參考文獻，並提供投稿前版式門禁與雙盲匿名清洗，以及實驗收據轉 LaTeX 三線表和會刊範本生成 |
| `skills/research-reproducibility` | 1.0.1 | 查核論文配套程式碼的提交雜湊與依賴鎖定檔，以及亂數種子與容差設定，把重跑實驗的結果整理成可複查的核驗紀錄 |
| `skills/systematic-review-meta-analysis` | 1.0.1 | 記錄 PRISMA 文獻檢索與篩選流程，轉換效應量，檢定異質性，執行固定或隨機效應模型合併以及留一法敏感度與發表偏倚分析 |
| `skills/literature-watch` | 1.1.0 | 按主題、作者或引文 DOI 每週巡檢 OpenAlex 與 Crossref，自動跨源去重並只回報上次檢查之後新發表的論文 |
| `skills/retraction-watch` | 1.1.0 | 按週複查關注清單裡的論文 DOI，比對 OpenAlex 的 `is_retracted` 標記與 Crossref 的 `update-to` 更正紀錄，只在狀態變化時提醒 |
| `skills/research-object-identity` | 1.1.0 | 把雜亂的 DOI、arXiv 編號與本機檔案雜湊整理成統一的身份紀錄，核實資源有效狀態，並看清每份分析結果是由哪些原始材料生成的 |
| `skills/claim-evidence-graph` | 1.0.0 | 把文章裡的每一條學術論斷和背後的原文段落、資料表或計算紀錄直接關聯起來，方便隨時核對某句結論有沒有正向證據支撐 |
| `skills/decision-ledger` | 1.0.0 | 按時間順序維護研究決策與陰性結果紀錄，把做過的方法選擇與走不通的失敗嘗試，以及放棄原因和後續修正記下來，避免重複踩坑 |
| `skills/paper-research` | 1.1.0 | 輸入 DOI、網頁連結或本機論文及補充材料，驗證提取出的關鍵欄位並重算核對統計數字，生成帶原文頁碼出處的中文報告或雙篇對比 |
| `skills/cross-review-five` | 2.0.1 | 組織多個不同大型模型或子智慧體對同一份文稿或程式碼獨立盲審，自動合併重複意見並安排交叉質詢，按 P0 至 P3 標註嚴重度並保留分歧 |

上述 14 項技能共配有 22 篇 Markdown 參考指南與 1 套機器可讀會刊規格庫，只在執行對應任務時按需讀取。

### 安裝與用戶端整合方式

1. **Python 軟體套件與可選依賴安裝**
   ```bash
   uv tool install academic-research-kernel==2.4.2
   ```
   您也可以使用 `pipx install academic-research-kernel==2.4.2` 或在虛擬環境內執行 `python -m pip install academic-research-kernel==2.4.2`。加上 `[research]` 會固定安裝 `pypdf==7.0.0` 與 `fonttools==4.65.0`，保證不同機器解析數位 PDF 字型時結果一致；加上 `[full]` 會一併安裝擴展科學計算範例所需的函式庫；加上 `[qa]` 會安裝倉庫自檢與測試所需的解析依賴。

2. **通用 Agent Plugins v1 與 MCP 用戶端掛載**
   本倉庫遵循 **Agent Plugins v1** 規範並提供 `plugin.json`，透過標準輸入輸出協定執行 `mcp.json` 與 `scripts/mcp_server.py` 定義的 **MCP 伺服器**，對外暴露全部 18 個查核與統計工具。雖然倉庫名為 `academic-research-kernel`，但外掛名稱 `name: "academic-skills"` 與原有的 MCP 設定別名保持不變，舊設定無需修改即可繼續使用。

3. **在 Hermes 中安裝外掛或按需安裝單項技能**
   請先確認 Hermes 行程的環境變數 `PATH` 中包含 `uv`，再安裝並啟用外掛，或直接透過 `tap` 按需安裝單項技能：
   ```bash
   # 方式 A：安裝完整外掛
   hermes plugins install xngg1021/academic-research-kernel --no-enable
   hermes plugins enable academic-skills

   # 方式 B：透過 tap 按需安裝單項技能文件
   hermes skills tap add xngg1021/academic-research-kernel
   hermes skills search academic-source-verification
   hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
   ```
   `mcp.json` 會呼叫 `uv run --frozen --no-dev --no-editable` 與 Python 3.12，按照倉庫的 `uv.lock` 鎖定檔把獨立執行環境安裝到 `${PLUGIN_DATA}/runtime` 目錄，不會改動宿主環境。配套關聯技能已對照上游提交 `245e48008fa814b3251f50755eb656bd9fb86cb1` 核對完畢，包含 `arxiv` 與 `grounded-citations`，以及 `docx`、`pdf` 和 `manim-video`。

4. **從原始碼執行**
   ```bash
   git clone https://github.com/xngg1021/academic-research-kernel.git
   cd academic-research-kernel
   uv sync --frozen --no-dev --no-editable
   uv run --frozen --no-dev --no-editable academic-research-kernel doctor
   uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
   ```
   各類依賴的用途劃分與發布校驗流程詳見[分發與發布說明](docs/distribution-release.md)。

---

## 五、工作原理：三層確定性狀態核心與學術規範及外部資料源

### 1. 研究紀錄保存與位元組級複核規則

系統的資料接入層採用 `ResearchArtifactEnvelope v1` 與 `ArtifactIngestionReceipt v1` 格式，內建 15 個解析器，涵蓋全部 14 項學術技能外加 1 個普通文本兜底解析器，對外提供 18 個無狀態的 stdio MCP 工具。每當系統保存研究對象與學術論斷關聯，或者寫入研究決策紀錄與待核實事項及證據檔案時，核驗紀錄都會記下對應的類型、唯一編號與 SHA-256 雜湊值。離線重放時會直接根據保存下來的原始材料與雜湊紀錄重新核對完整性；一旦某次批次寫入中途出錯，系統會自動原子回滾，不會留下半截損壞的資料。

如果某條核驗紀錄要標記為 `fully_verified` 已完全核實，呼叫方必須提供對應的原始檔案內容，以便系統獨立複核。Python 本機呼叫可透過 `LineageVerificationContext` 傳入原文，MCP 協定呼叫則只允許直接傳入檔案內容位元組流，不允許讀取主機任意檔案路徑，單次讀取的檔案大小預設上限為 10 MiB。如果沒有提供原文內容，系統不會把結果標為已完全核實。未經提取的自由文本保持原樣儲存，不同審稿模型的分歧意見全部公開保留；何時保存紀錄、放棄哪條路線以及最終採納哪條學術結論，始終由研究者自己決定。

撤稿狀態查核會把本次聯網查到的 `True`、`False` 或 `unknown` 結果與上一次確認過的有效狀態分開保存。如果最新一次查詢因為網路波動或介面限流暫時返回 `unknown`，系統會如實標出本次檢查尚未核實，不會沖掉之前已經確認過的既有紀錄。MCP 伺服端支援 `ping` 連通性檢查，收到 `notifications/cancelled` 等合法通知時按協定保持靜默，遵循 [MCP 訊息規範](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)與 [ping 規範](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping)。

### 2. 學術規範與各國引用標準基線

本倉庫以國際標準 **ISO 690:2021** 參考文獻與引文指南、**ISO 5127:2017** 文獻與資訊詞彙，以及 **W3C PROV** 來源追溯模型作為通用基線，同時內建中國大陸 GB/T 7714-2025 與西班牙 UNE-ISO 690:2024 及德國 DIN ISO 690:2021 等地區規範，並支援 APA 與 IEEE，以及 PRISMA 2020 和 ICMJE 等學科標準。實際寫作時，目標投稿期刊或學校的具體規定始終優先於預設規則，詳見[學術規範架構](docs/standards/README.md)與[自然學術術語指南](docs/terminology/README.md)。

### 3. 學術資料源與介面限額

- **OpenAlex**：基礎首屏查詢支援匿名使用。無金鑰每秒最多發送 10 次請求，設定免費或預付費金鑰後每秒最多 30 次請求，年度訂閱方案每秒最多 50 次請求；匿名存取每日額度為 $0.10，申請免費 API 金鑰後每日額度為 $1。翻頁讀取 `next_cursor` 需設定環境變數 `OPENALEX_API_KEY`，未配金鑰時翻頁會在保留首屏結果後自動截斷。
- **Crossref**：提供帶限流的公開詮釋資料介面。查核論文更正與撤稿信號時必須同時核對 DOI 與更新方向；介面沒查到紀錄不代表論文一定沒有問題。
- **Unpaywall**：要求在環境變數 `UNPAYWALL_EMAIL` 中填入真實聯絡信箱。如果介面沒有返回全文位址，不代表網路上不存在其他開放取用版本。
- **arXiv 與 Europe PMC、PubMed E-utilities 與 DOAJ 以及 Semantic Scholar**：各自有獨立的限流規則，Semantic Scholar 的匿名公共額度與專屬金鑰額度分開計算。
- **Scite 與 Dimensions、Scopus 與 Web of Science 以及商業 AI 檢測工具**：屬於可選的外部付費服務，呼叫前請先確認您自己的帳號權限與剩餘配額。

詳細介面說明見 [OpenAlex 認證指南](https://help.openalex.org/api/authentication/)、[額度與查詢計費說明](https://help.openalex.org/api/llm-quick-reference/)及 [Crossref 更新過濾文件](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/)。

---

## 六、本機驗證與測試套件及授權條款

### 1. 本機自檢、長尾基準與打包驗證

執行測試請使用獨立的 Python 虛擬環境，安裝 `requirements-qa.txt` 可以配齊全部測試依賴：

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

如需在倉庫目錄之外的純淨虛擬環境中建置並驗證 Wheel 與原始碼分發包，涵蓋全部 16 組 CLI 子命令、`[research]` PDF 提取與 `uvx` 獨立快取執行，可執行：

```bash
uv build --no-create-gitignore
python scripts/release_manifest.py --dist dist --output dist/release-manifest.json
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

GitHub Actions 持續整合覆蓋 Linux x86_64 的 Python 3.10、3.12 與 3.14 環境，同時覆蓋 Linux ARM64 的 `ubuntu-24.04-arm` 映像檔與 Windows x86_64、Windows ARM64 的 `windows-11-arm` 映像檔以及 macOS ARM64 的 `macos-latest` 映像檔，並附帶針對上游 Hermes 的即時相容性檢驗。本機完整迴歸測試套件共通過 1364 項測試，在[正確性修復紀錄](docs/maintenance/correctness-repair-20261008.md)與早期的[收尾紀錄](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)基線上持續擴充。[tools/longtail/](tools/longtail/README.md) 目錄存放確定性長尾測試場景產生器，`scripts/scfabric/` 目錄提供科學計算基準測試工具，首輪實測說明見 [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md)。全部 21 個語種共 23 份 README 檔案均已同步至 2.4.2 版本，狀態記錄於[多語言清單](docs/i18n/manifest.json)。

### 2. 授權條款

包含本聲明的程式碼版本按照 [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md) 界定的範圍，對受版權保護的專案材料適用 **Source Lineage License 1.0**。首次切換到 SLL 的提交與後續記錄分界的提交，分別登記在 [LICENSE-HISTORY.md](LICENSE-HISTORY.md) 與 [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) 中。自該節點起保留本聲明的後續版本，均沿用相同的授權範圍。

SLL 授權條款允許自由使用與研究，支援修改程式碼與商業應用，也允許重新分發和閉源擴展，前提是保留規定的許可聲明與來源追溯資訊。該授權條款不是傳染性的 copyleft 協定，不要求使用者公開自己的原始碼。單純透過網路提供服務而不分發軟體副本，不會觸發核心服務的來源署名要求。本授權條款不包含明示專利授權，第三方材料繼續適用各自原有的授權條款。具體條款以英文原版 [LICENSE](LICENSE) 為準；`LicenseRef-Source-Lineage-1.0` 只是本機識別名，並非 SPDX 官方編號，也不代表已通過 OSI 認證。[外部貢獻規則](CONTRIBUTING.md)與下游使用者的許可權限相互獨立。

# academic-research-kernel

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

A deterministic scholarly verification and manuscript engineering kernel for researchers and AI agents.

When researchers use large language models to read or write papers, two failure modes recur. While reading external papers, a model generates text probabilistically and readily repeats miscalculated $p$-values, shifted ablation tables, retracted references, or hollow code repositories as if they were verified facts. While writing your own manuscript, asking a model in prose to check formatting cannot reliably catch residual author metadata in double-blind PDFs, transcription errors in LaTeX tables, dangling figure references, or missing required venue sections.

Built from first principles, this repository separates semantic reading from deterministic verification: your language model handles reading and synthesis, while deterministic code handles mathematical recomputation, public database queries, syntax-tree checks, and SHA-256 provenance verification. The repository unifies 14 scholarly workflows, 12 standard Model Context Protocol (MCP) tools, and 13 CLI command groups on a single state kernel, working out of the box with Claude Code, Cursor, Codex, Gemini CLI, and Hermes Agent. Validation scope and external service limits are documented in [the project audit](docs/kernel-architecture.md).

Author: Junfu Shi (SJF, xngg1021). License: [Source Lineage License 1.0](LICENSE).

---

## 1. Two-Minute Quick Start

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then choose either the local CLI + agent skill path or the stdio MCP server path for version `2.3.1`:

```bash
# Option 1: Install the full CLI with digital PDF support and export the paper-research skill
uv tool install "academic-research-kernel[research]==2.3.1"
academic-research-kernel research skill --output ./paper-research

# Option 2: Start the stdio MCP server for Claude Code, Cursor, Codex, or Gemini CLI
uvx academic-research-kernel mcp
```

Run an offline environment check and try source normalization or the built-in venue specification catalog right away:

```bash
academic-research-kernel doctor
academic-research-kernel verify-source https://doi.org/10.1038/nature14539 --normalize-only
academic-research-kernel venue-template --action list-venues
```

The `doctor` command runs offline and checks runtime dependencies, all 26 JSON schemas, and all 12 MCP tool definitions; leaving optional external API keys unconfigured will not fail the check. Running `mcp` in a terminal waits silently on standard input/output for JSON-RPC requests from an MCP client. The [2.3.1 release page](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.3.1) lists package SHA-256 hashes. Python 3.10–3.14 is supported, and statistical libraries load on demand only when distribution or power calculations are invoked.

---

## 2. First Half: Reading External Papers & Auditing Evidence

When reading external papers or conducting a literature review, the workflow moves from verifying bibliographic and repository authenticity, to recomputing reported statistics, to generating page-anchored reports.

### 1. Read a Paper or Compare Two Papers with Your Local Agent

Point your local agent at the exported `./paper-research/SKILL.md`, pass a DOI, public URL, or local bundle, and ask:
“Read this paper and its supplements, summarize the method, recompute every verifiable number, and write a source-linked report.”

Under the hood, three CLI steps back the agent workflow:

```bash
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` ingests PDF, HTML, XML/JATS, DOCX, XLSX, or LaTeX/BibTeX (`.tex`, `.bib`, `.bbl`) source bundles, hashes every file, and indexes passages by page and structural section. Once your agent reads the text and writes the extraction candidate JSON, `finish` verifies that every extracted number appears verbatim at its declared source locator, runs deterministic statistical checks, commits the verified state, and renders source-linked Markdown and HTML reports. `compare` validates structured comparability across two papers' datasets, experimental conditions, and metrics. Any saved project can be replayed offline with `academic-research-kernel research replay --project PROJECT`.

### 2. Audit Bibliographic Authenticity, Open-Access Full Texts, OpenReview & Code Repositories

Four standalone CLI commands handle external forensic verification:

```bash
# Normalize DOI/arXiv identifiers and cross-check OpenAlex and Crossref metadata and retractions
academic-research-kernel verify-source 10.1038/nature14539

# Locate open-access full text across Unpaywall, arXiv, OpenAlex, Semantic Scholar, and Europe PMC
academic-research-kernel locate-oa 10.1038/nature14539

# Audit OpenReview review scores, variance, and venue-wide quantiles or topic acceptance rates
academic-research-kernel openreview-audit --forum-id Forum_Synth_01 --mirror-json ./venue-mirror.json
academic-research-kernel openreview-audit --venue-stats ./venue-mirror.json --topic-regex "memory|agent"

# Inspect a repository's non-vendor source lines, Git commit history, and README command claims
academic-research-kernel repo-forensics --local-repo ./target-repo
```

`locate-oa` rejects paywalled landing pages (`is_oa=false`) and mismatched DOIs rather than mislabeling abstracts as full text. `openreview-audit` filters non-finite ratings, deduplicates records by `forum_id`, and computes score means and variance strictly over reviewer ratings while separating meta-reviews and final decisions. `repo-forensics` uses `git ls-files` when available to separate first-party code from bundled third-party directories.

### 3. 15 Deterministic Statistical & Forensic Checks, Physical Bounds & Meta-Analysis

Both the `academic_recompute_statistics` MCP tool and `recompute.py` expose 15 deterministic checks covering $t$-test, $F$-test, and $\chi^2$ $p$-values, regression $\beta/\text{SE}$ Wald checks, confidence-interval symmetry, $2\times 2$ odds and risk ratios, two-group Cohen's $d$ and Hedges' $g$, percentage denominator reconstruction, bounded-scale standard-deviation bounds (Popoviciu and Bhatia-Davis), degrees-of-freedom sample-size checks, and two-sample $t$-test statistical power.

Version `2.3.0` adds three table-forensic checks for machine learning and systems papers (available via `academic-research-kernel table-forensics --input spec.json` and MCP):
- **Sample Partition Conservation (`partition_conservation`)**: Verifies that a declared total sample size equals the exact sum of mutually exclusive subset counts;
- **Ablation Constant Offset (`ablation_delta_regularity`)**: Detects suspicious constant-delta shifts across multi-metric ablation rows;
- **Uncompressed Storage & Full-Scan Bandwidth Bounds (`storage_bandwidth_bounds`)**: Under explicit assumptions of uncompressed fixed-width vectors (`N * D * bytes_per_element`) and a single-pass full linear scan, computes raw vector byte lower bounds and full-scan latency lower bounds to flag inconsistent uncompressed footprint or full-scan latency claims.

When trailing zeros in a reported $p$-value matter, pass `p_value_literal` (such as `"1.0e-5"`) or `p_value_decimals`. Multi-study fixed-effect and DerSimonian-Laird random-effects pooling, $Q/I^2/\tau^2$ heterogeneity, and Egger regression run directly via:

```bash
academic-research-kernel meta-analyze --input studies.json
```

---

## 3. Second Half: Writing Your Own Paper & Pre-Submission Gates

When drafting and preparing your own manuscript for submission, four deterministic CLI tools cover workspace scaffolding, LaTeX table generation, double-blind sanitization, and venue rule linting:

```bash
# Step 1: Inspect built-in specs for 8 major venues (ICLR 2027, NeurIPS, ICML, ACL, KDD, Nature, IEEE, ACM) and initialize a workspace
academic-research-kernel venue-template --action list-venues
academic-research-kernel venue-template --action scaffold --workspace-dir ./workspace --slug my-paper --venue iclr

# Step 2: Render verified JSON experiment receipts into booktabs LaTeX tables with bold best and underlined second-best values
academic-research-kernel receipt-to-latex --input ./results-receipt.json --caption "Main Results" --label "tab:main"

# Step 3: Scan .tex, .bib, and compiled PDF metadata (/Author, /Creator) for identity leaks, self-citations, or local paths
academic-research-kernel sanitize-blind --target ./workspace/my-paper

# Step 4: Run pre-submission linting against venue-specs.json (anonymous package flags, page limits, required sections, and CEG links)
academic-research-kernel pre-submission-lint --tex ./workspace/my-paper/main.tex --venue iclr --contribution-type systems_architecture
```

`receipt-to-latex` uses exact `Decimal` half-up rounding so numbers are never altered by hand transcription or binary floating-point drift. `double-blind-sanitize` inspects `\author`, custom identity macros, `\icmlauthor`, `pdfauthor`, acknowledgments, and compiled PDF Info dictionaries. `pre-submission-lint` checks `skills/academic-writing/references/venue-specs.json` for non-anonymous package options (`final`, `preprint`, `camera-ready`), tracks post-conclusion exempt sections (`Reproducibility Statement`, `Ethics Statement`, `Use of Large Language Models`, `Acknowledgments`) across pages so exempt statements never inflate `main_body_pages`, masks balanced-brace `\newcommand`/`\def` definitions to eliminate false-positive `TODO` warnings, resolves cross-file `\ref`/`\Cref` targets against `\label{...}` and `lstlisting[label={...}]` (`UNDEFINED_LATEX_LABEL_REF`), flags redundant `Author et al. ~\cite{...}` prefixes (`AUTHOR_YEAR_CITE_DUPLICATION`) and bare `\cite` dominance under author–year styles (`NATBIB_BARE_CITE_DOMINANT`), blocks unredacted `Acknowledgments` funding disclosures in double-blind submissions (`FORBIDDEN_ACKS_IN_DOUBLE_BLIND_SUBMISSION`), and verifies in linear time that quantitative claims in the Abstract and Conclusion resolve to `support_status == "supported"` edges in `ClaimEvidenceGraph`.

Convert and normalize bibliographic files at any time with:

```bash
academic-research-kernel bibliography --from bibtex --to csl --input refs.bib
```

### Macro-Distribution of the 5 Deterministic Defect Families in Peer Review (ICLR 2026, $N = 19,473$)

To motivate the kernel's five deterministic verification families (missing dispersion/error bars, format/section/page violations, table/ablation inconsistencies, citation/baseline omissions, and reproducibility/code gaps) without fitting empirical weights or predicting subjective scores, we measured paper-level incidence (`k / N` manuscripts where at least one official review flagged the category in `Weaknesses` or `Questions`) across `19,473` scored submissions (`75,769` official reviews) in ICLR 2026 (`18,791` standard decision records plus `682` desk-rejected records with reviews; `SHA-256` split-half verified `Split 0: N = 9,765` vs. `Split 1: N = 9,708`; individual manuscripts de-identified; [aggregate receipt](docs/benchmarks/iclr2026-openreview-incidence-receipt.json)):

| Decision / Soundness Tier | Submissions ($N$) | Mean Rating / Soundness | Paper-Level Reviewer Hit Rate (`k / N`) Across the 5 Families |
| --- | --- | --- | --- |
| **Oral** | 224 | 6.40 / 3.07 | **48.2%** (`108 / 224`; dispersion 12.1%, table/ablation 7.1%, baseline 2.7%) |
| **Poster** | 5,134 | 5.36 / 2.83 | **54.0%** (`2,772 / 5,134`; dispersion 19.5%, table/ablation 7.9%, baseline 4.9%) |
| **Rejected** | 8,453 | 3.96 / 2.49 | **59.8%** (`5,057 / 8,453`; dispersion 23.4%, table/ablation 10.5%, baseline 6.1%) |
| **Withdrawn** | 4,980 | 3.35 / 2.33 | **62.6%** (`3,117 / 4,980`; dispersion 23.8%, table/ablation 12.4%, baseline 6.8%) |
| **Soundness $\ge 3.25 \to \le 2.0$** | 1,077 $\to$ 2,861 | $\ge 3.25 \to \le 2.0$ | **49.1% $\to$ 67.4%** (`529 / 1,077` $\to$ `1,928 / 2,861`; dispersion 14.9% $\to$ 27.5%, missing code 15.6% $\to$ 27.7%) |


## 4. All 14 Scholarly Skills & Agent Integration

| Skill | Version | What it helps you do |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.3.0 | Cross-check paper identities and citation counts across databases, check retractions, locate open-access full texts, audit OpenReview records, and run repository forensics |
| `skills/literature-analysis` | 1.3.0 | Expand related works via snowballing, compare methods and contradictions across papers, build author profiles, review manuscripts, and convert BibTeX, RIS, and CSL-JSON |
| `skills/quantitative-paper-audit` | 1.2.0 | Recompute $p$-values, effect sizes, confidence intervals, odds ratios, and statistical power from reported statistics, plus partition conservation, ablation offset, and physical bound checks |
| `skills/math-computation` | 1.2.1 | Run symbolic algebra, calculus, linear algebra, differential equations, optimization, and Monte Carlo simulations with SymPy, NumPy, SciPy, statsmodels, and PyTorch |
| `skills/academic-writing` | 1.3.0 | Edit academic prose and structure, format citations across international profiles, and run pre-submission linting, double-blind sanitization, receipt-to-LaTeX table generation, and venue templating |
| `skills/research-reproducibility` | 1.0.1 | Audit companion code commits, lockfiles, random seeds, and numerical tolerances, recording reproduction runs in verifiable receipts |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Record PRISMA search and screening logs, convert effect sizes, test heterogeneity, pool fixed or random effects, and run leave-one-out sensitivity and publication-bias checks |
| `skills/literature-watch` | 1.1.0 | Monitor OpenAlex and Crossref weekly for new papers by topic, author, or cited DOI, deduplicating results so only newly published works are reported |
| `skills/retraction-watch` | 1.1.0 | Recheck a DOI watchlist weekly against OpenAlex retraction flags and Crossref update records, reporting only papers whose status changed |
| `skills/research-object-identity` | 1.1.0 | Normalize DOIs, arXiv IDs, and file hashes into canonical records, verify resource status, and trace how derived files were produced from raw sources |
| `skills/claim-evidence-graph` | 1.0.0 | Link each scientific claim to the exact source passage, table, or calculation record that supports or contradicts it |
| `skills/decision-ledger` | 1.0.0 | Keep an append-only Research Decision Log of methodological choices, failed attempts, reasons for dropping a direction, and later outcome revisions |
| `skills/paper-research` | 1.1.0 | Read a paper and its supplements from a DOI, URL, or local folder, verify extracted numbers, save structured research state, and generate source-linked reports or two-paper comparisons |
| `skills/cross-review-five` | 2.0.1 | Coordinate independent blind reviews across multiple language models or subagents, merge overlapping points, assign cross-challenges, and grade issues from P0 to P3 while preserving unresolved dissent |

Across the 14 skills, 22 Markdown reference guides and 1 machine-readable venue specification catalog are loaded on demand when a task requires them.

### Installation & Harness Integration

1. **Python Package & Optional Extras**
   ```bash
   uv tool install academic-research-kernel==2.3.1
   ```
   You can also run `pipx install academic-research-kernel==2.3.1` or `python -m pip install academic-research-kernel==2.3.1` inside a virtual environment. Adding `[research]` pins `pypdf==7.0.0` and `fonttools==4.65.0` for deterministic digital PDF font decoding across Python 3.10–3.14; `[full]` installs extended scientific computing libraries; `[qa]` installs repository test and lint dependencies.

2. **Universal Agent Plugins v1 & Multi-Agent MCP Registration (Claude Code, Codex, Cursor, Gemini CLI)**
   This repository follows the vendor-neutral **Agent Plugins v1** format (`plugin.json`) and exposes its 12 verification and statistical tools through a standard stdio **MCP server** (`mcp.json` / `scripts/mcp_server.py`, supporting MCP protocol versions `2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`, and `2026-07-28`):
   ```bash
   # Claude Code CLI
   claude mcp add academic-research-kernel -- uvx academic-research-kernel mcp

   # OpenAI Codex CLI
   codex mcp add academic-research-kernel -- uvx academic-research-kernel mcp

   # Direct stdio launch (Cursor .cursor/mcp.json or Gemini CLI ~/.gemini/settings.json)
   uvx academic-research-kernel mcp
   ```

3. **Native Hermes Installation**
   Ensure `uv` is on the Hermes process `PATH`, then install the full plugin or register the skill tap for individual skills:
   ```bash
   # Option A: Install and enable the full plugin
   hermes plugins install xngg1021/academic-research-kernel --no-enable
   hermes plugins enable academic-skills

   # Option B: Install individual skills via tap
   hermes skills tap add xngg1021/academic-research-kernel
   hermes skills search academic-source-verification
   hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
   ```
   `mcp.json` invokes `uv run --frozen --no-dev --no-editable` with Python 3.12 to materialize an isolated environment under `${PLUGIN_DATA}/runtime` from `uv.lock` without modifying your host Python installation. Related skills checked against upstream Hermes commit `245e48008fa814b3251f50755eb656bd9fb86cb1` include `arxiv`, `grounded-citations`, `docx`, `pdf`, and `manim-video`.

4. **Run from Source**
   ```bash
   git clone https://github.com/xngg1021/academic-research-kernel.git
   cd academic-research-kernel
   uv sync --frozen --no-dev --no-editable
   uv run --frozen --no-dev --no-editable academic-research-kernel doctor
   uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
   ```
   See [the release guide](docs/distribution-release.md) for packaging and publication verification recipes.

---

## 5. Under the Hood: Three-Layer State Kernel, Standards & Data Sources

### 1. Research State Storage & Verification Boundaries

The ingestion module uses `ResearchArtifactEnvelope v1` and `ArtifactIngestionReceipt v1`, pairing 15 adapters (one for each of the 14 skills plus a plain-text fallback) with 12 stateless stdio MCP tools. Whenever the system saves research objects, claim–evidence links, Research Decision Log entries, items needing review, or verification records, it records their canonical SHA-256 hashes in an ingestion receipt. Replaying a cache checks those hashes directly against the saved source packages. Empty decision logs are valid, and any batch write that fails mid-way rolls back atomically without leaving partial files behind.

Marking a record as `fully_verified` requires access to the underlying source bytes so the check can be reproduced independently. Trusted Python callers provide this through `LineageVerificationContext`, while MCP callers pass bounded file bytes directly rather than exposing host filesystem paths (capped at 10 MiB by default). Without the source bytes, a `fully_verified` claim fails validation. Unstructured notes stay untouched, reviewer disagreements remain visible, and human researchers remain in charge of committing state, dropping or reopening research routes, and making final scholarly judgments.

Retraction checks store the current run's observation (`True`, `False`, or `unknown`) separately from the last confirmed status. If a network error or rate limit produces an `unknown` result on the latest run, the system reports that the current check is unverified while preserving previously confirmed history. The stdio MCP server replies to `ping`, stays silent on valid notifications such as `notifications/cancelled`, and keeps the session open if a client sends malformed input, following the [MCP message contract](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) and [ping specification](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

### 2. Scholarly Standards & Multi-Profile Baseline

This repository uses **ISO 690:2021** (bibliographic references), **ISO 5127:2017** (documentation vocabulary), and **W3C PROV** (provenance records) as its international baseline, alongside regional standards such as GB/T 7714-2025 in Mainland China, UNE-ISO 690:2024 in Spain, and DIN ISO 690:2021 in Germany, plus disciplinary guides including APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, and ICMJE. A target journal's own instructions always override default settings. See the [Scholarly Standards Architecture](docs/standards/README.md) and [Natural Terminology Guide](docs/terminology/README.md).

### 3. Data-Source Access & Rate Limits

- **OpenAlex**: Allows anonymous first-page queries with a small daily budget ($0.10/day anonymous at 10 req/s; $1/day with a free API key at 30 req/s; 50 req/s on annual plans). Following `next_cursor` beyond the first page requires `OPENALEX_API_KEY`.
- **Crossref**: Provides public metadata with rate limits. Checking corrections and retractions requires verifying both the DOI and the update direction; an empty result does not prove a paper has no issues.
- **Unpaywall**: Requires a real contact email in `UNPAYWALL_EMAIL`. If Unpaywall returns no link, an open-access copy may still exist elsewhere.
- **arXiv, Europe PMC, PubMed E-utilities, DOAJ & Semantic Scholar**: Serve as additional sources with their own rate limits.
- **Scite, Dimensions, Scopus, Web of Science & commercial AI detectors**: Optional third-party services; check your own account permissions and quotas before calling them.

See [OpenAlex authentication](https://help.openalex.org/api/authentication/), [budgets/query costs](https://help.openalex.org/api/llm-quick-reference/), and [Crossref update filters](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

---

## 6. Local Validation, Test Suite & License

### 1. Validation, Long-Tail Benchmarks & Package Acceptance

Run the test suite in a dedicated Python virtual environment:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

To build and verify the wheel and source archive in fresh virtual environments outside the repository (covering all 13 CLI command groups, `[research]` PDF extraction, and isolated `uvx` execution), run:

```bash
uv build --no-create-gitignore
python scripts/release_manifest.py --dist dist --output dist/release-manifest.json
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

GitHub Actions runs the orthogonal test matrix across Linux x86_64 (Python 3.10, 3.12, and 3.14), Linux ARM64 (`ubuntu-24.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), and macOS ARM64 (`macos-latest`), alongside live compatibility checks against upstream Hermes. The local regression suite passes 1340 tests (extending the baseline in [the correctness repair report](docs/maintenance/correctness-repair-20261008.md) and the [closeout ledger](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342)). [tools/longtail/](tools/longtail/README.md) contains the deterministic scenario generator, and `scripts/scfabric/` contains the scientific computing benchmark tools documented in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md). All 21 locales (23 README files including Chinese regional aliases) are synchronized with the 2.3.1 baseline in [the i18n manifest](docs/i18n/manifest.json).

### 2. License

Covered material in this repository is licensed under the **Source Lineage License 1.0** (`LicenseRef-Source-Lineage-1.0`), within the scope stated in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md); provenance and historical boundary records are maintained in [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md) and [LICENSE-HISTORY.md](LICENSE-HISTORY.md).

Under SLL 1.0, you may use, study, modify, commercialize, redistribute, and build proprietary extensions on the covered material as long as you preserve the required license and lineage notices. SLL 1.0 is not a copyleft license and does not require you to open-source your own code. Using the software over a network without distributing copies does not trigger core-service attribution, no express patent grant is included, and third-party components (such as [tests/upstream/LICENSE](tests/upstream/LICENSE)) remain under their own licenses. The English text in [LICENSE](LICENSE) is authoritative; `LicenseRef-Source-Lineage-1.0` is a local identifier rather than an SPDX-assigned identifier or a claim of OSI approval. [Inbound contributions](CONTRIBUTING.md) are governed separately from downstream license rights.

# academic-research-kernel (`v3.0.0`)

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-CN.md)

**Standalone scholarly verification, LaTeX submission gates, and transactional evidence state (`CLI` + `MCP` + `7` Agent Skills).**

Large language models summarize papers fluently yet fail predictably on exact arithmetic and external ground truth: they repeat miscalculated $p$-values, miss rounding-impossible percentages, cite retracted or fabricated DOIs, leave author metadata inside double-blind PDFs, and lose track of which source table backs which claim.

`academic-research-kernel` (`3.0.0`) separates semantic reading from deterministic checks. Run it directly from your terminal or wire it into any MCP / `SKILL.md` agent workflow:

```bash
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel verify-work "10.1038/nature14539" --normalize-only
# -> {"input": "10.1038/nature14539", "type": "doi", "normalized": "10.1038/nature14539", "canonical_id": "doi:10.1038/nature14539"}
```

> **Empirical case study included**: Reproducible SHA-256 receipts across **four AI conference series and five frozen public snapshots** (`74,637` primary-cohort submissions across `75,574` raw mirror submissions, `248,174` official reviews; see [Section 4](#4-case-study-openreview-snapshots-across-four-ai-conference-series-20252027) and [peer-review-forensics-2025-2027-v1.json](docs/benchmarks/peer-review-forensics-2025-2027-v1.json)).

Author: Junfu Shi (SJF, `xngg1021`). License: [Source Lineage License 1.0](LICENSE). Architecture: [docs/kernel-architecture.md](docs/kernel-architecture.md).

---

## 1. Two-Minute Quick Start: Three Entry Modes & Dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then choose how you want to invoke the kernel (Python `3.10`–`3.14`, `~25 ms` CLI cold start):

### Mode A: Direct Command-Line Tool (Human Researchers, CI & Shell Scripts)

```bash
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel doctor
academic-research-kernel lint-submission ./manuscript/main.tex --venue iclr --phase submission
```

### Mode B: Universal stdio MCP Server (Claude Code, Codex, Cursor, Gemini CLI)

Exposes **24 deterministic MCP tools** over bounded-frame stdio JSON-RPC 2.0 (`2024-11-05` through `2026-07-28`):

```bash
# Claude Code CLI
claude mcp add academic-research-kernel -- uvx --from "academic-research-kernel[research]==3.0.0" academic-research-kernel mcp

# OpenAI Codex CLI
codex mcp add academic-research-kernel -- uvx --from "academic-research-kernel[research]==3.0.0" academic-research-kernel mcp
```

### Mode C: Agent Skills (Hermes Agent or Any `SKILL.md`-Compatible Harness)

```bash
# Install the 7-skill plugin in Hermes Agent
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills

# Or export the standalone audit-paper skill + JSON schemas to any local folder
academic-research-kernel research skill --output ./audit-paper
```

**Dependency layout**: State management (`SQLite STRICT + WAL`), CLI dispatch, and MCP protocol control use Python's standard library, importing declared scientific and schema packages (`jsonschema`, `numpy`, `scipy`, `statsmodels`) lazily on demand. The `[research]` extra installs `pypdf==7.0.0` and `fonttools==4.65.0` for isolated subprocess PDF text/metadata scanning; details in [docs/distribution-release.md](docs/distribution-release.md).

---

## 2. Seven Workflow Skills & Task Routing

`v3.0.0` consolidates all `14` legacy `v2.4.2` skill directories into **seven task-oriented skills**:

| Skill Directory | Concrete Task & Scope Boundary | Key CLI Commands & MCP Tools |
| --- | --- | --- |
| [`skills/audit-paper`](skills/audit-paper/SKILL.md) | Check statistics, tables, source locators, and reproducibility checklists in an external/paired paper (emits item-level checks, not blanket truth verdicts) | `research`, `table-forensics`, `repro-checklist`, `ledger`, `academic_recompute_statistics` |
| [`skills/verify-citations`](skills/verify-citations/SKILL.md) | Verify DOIs/metadata, monitor Crossref/OpenAlex retractions in SQLite, merge corpora, and locate legal OA PDFs (existence $\neq$ claim support) | `verify-work`, `retraction-watch`, `literature-watch`, `collect-corpus`, `locate-oa` |
| [`skills/audit-peer-review`](skills/audit-peer-review/SKILL.md) | Analyze offline OpenReview score/length/unanimity distributions and companion repos (descriptive forensics, not AI-authorship proof) | `openreview-audit`, `repo-forensics --github-repo`, `academic_openreview_audit` |
| [`skills/meta-analysis`](skills/meta-analysis/SKILL.md) | Pool fixed/random effects (`DL`), run subgroup $Q_{\text{between}}$ & WLS meta-regression, Egger/trim-and-fill, and build citation matrices | `meta-analyze`, `bibliography`, `academic_meta_analyze` |
| [`skills/check-submission`](skills/check-submission/SKILL.md) | Gate **your own draft** before submission: multi-file LaTeX, venue limits, double-blind PDF/source anonymity, `CEG` anchors, and `booktabs` tables | `lint-submission`, `sanitize-submission`, `generate-table`, `check-venue` |
| [`skills/cross-review`](skills/cross-review/SKILL.md) | Coordinate **live multi-model** blind review, anonymous `Proposal-N` challenge, and minority-protected synthesis under a strict single-line verdict grammar | `cross-review`, `academic_cross_review` |
| [`skills/compute-math`](skills/compute-math/SKILL.md) | Probe CPU/GPU/BLAS/thread environments, emit schema-validated `ComputeReceipt`, and route tasks to installed scientific Python packages | `compute-probe`, `academic_scfabric_hardware_probe` |

### Quick Disambiguation: Which Review/Check Skill Do I Need?

| Object in Hand | Entry Skill | Primary Output |
| --- | --- | --- |
| An external paper you want to audit | `audit-paper` | Locator-bound statistical, table, and reproducibility check results |
| Your own manuscript draft before submission | `check-submission` | Format, page-limit, anonymity, and `CEG` grounding gate report |
| Published OpenReview conference records | `audit-peer-review` | Cohort score/word-count distributions and screening statistics |
| A claim/spec needing live multi-model review | `cross-review` | Clustered findings and SHA-bound challenge synthesis receipt |

**How `academic-research-kernel` fits alongside peer open-source tools**: Broad domain skill collections (such as `Scientific Agent Skills`) and discovery/RAG systems (`AI-Scientist`, `PaperQA`) focus on literature synthesis and draft generation, while specialized verifiers focus on single axes such as multi-provider bibliography GUI/CLI validation (`RefChecker`, evaluated on benchmarks like `HALLMARK`), APA test-statistic rounding (`statcheck`), or Claude-Code/Codex reviewer workflows (`Anti-Autoresearch`). `academic-research-kernel` focuses on a **host-neutral CLI/MCP verification & SQLite state kernel** that links **author-side multi-file LaTeX/anonymity submission gates** and **auditor-side statistical, retraction, meta-analysis, and OpenReview snapshot receipts** under a single transactional schema contract.

---

## 3. End-to-End Workflows, Verified Scope & Known Limits

### Workflow A: Audit an External Paper, Citation List, or Meta-Analysis

```bash
# 1. Prepare a PDF/LaTeX bundle, validate extracted stats, and check table partition conservation
academic-research-kernel research prepare ./paper.pdf --project ./paper-state
academic-research-kernel research finish --project ./paper-state --candidate ./candidate.json
academic-research-kernel table-forensics --input ./table-spec.json

# 2. Verify citations, locate legal Open Access full text, and monitor retractions in SQLite
academic-research-kernel verify-work "10.1038/nature14539" --check-updates
academic-research-kernel locate-oa "10.1038/nature14539" --email "you@example.edu" --fallback-openalex
academic-research-kernel retraction-watch --dois "10.1038/nature14539" --state-db ./watch.sqlite3 --live

# 3. Pool multi-study effect sizes (fixed & DerSimonian-Laird random effects + Q / I^2 / tau^2 + Egger + trim-and-fill)
academic-research-kernel meta-analyze --input ./studies.json
```

### Workflow B: Pre-Submission Gate for Your Own LaTeX & PDF Manuscript

```bash
# 1. Inspect venue rules (ICLR, NeurIPS, ICML, ACL, etc.) or export verified CEG claim anchors
academic-research-kernel check-venue --list-venues
academic-research-kernel check-venue --export-ceg-anchors ./ceg.json

# 2. Render verified JSON experiment receipts into Decimal-rounded booktabs LaTeX tables
academic-research-kernel generate-table ./results-receipt.json --caption "Main Results" --label "tab:main"

# 3. Scan multi-file TeX, BibTeX, and compiled PDF (/Info + XMP streams in isolated worker) for anonymity leaks
academic-research-kernel sanitize-submission ./submission-dir --forbidden-token "Alice Smith"

# 4. Run full pre-submission gate (nested \input/\subfile/\import, declared .bib scope, shared-page limit, CEG binding)
academic-research-kernel lint-submission ./submission-dir/main.tex \
  --venue iclr --phase submission --pdf ./submission-dir/main.pdf \
  --ceg ./ceg.json --require-ceg-binding --check-academic-style
```

**Development regression summary & known limitations**:
- On the 30-case offline development regression suite ([real-world-audit-benchmark-v1.json](docs/benchmarks/real-world-audit-benchmark-v1.json): `16` frozen-snapshot DOI/retraction cases + `12` published Nuijten/Bakker statistical cases + `2` repository gate cases), `v3.0.0` replays `TP = 10, TN = 6, FP = 0, FN = 0` on bibliographic/retraction checks and `TP = 8, TN = 5, FP = 1, FN = 0` (`TP = 18, TN = 11, FP = 1, FN = 0` overall).
- **Disclosed rounding limitation (`S14`)**: `recompute.py` currently evaluates exact reported test statistics against reported $p$-value rounding intervals rather than intervalizing coarse 1-decimal test statistics (`t(15) = 2.3, p = .033` yields the single disclosed `FP`), so numerical flags require human verification of input rounding before claiming a manuscript error. In double-blind checks, generic third-party repository URLs emit review `warning` items rather than hard blocks unless paired with `--forbidden-token` or explicit self-repository phrasing.

---

## 4. Case Study: OpenReview Snapshots Across Four AI Conference Series (2025–2027)

Running [run_peer_review_and_incidence_benchmarks.py](tools/benchmarks/run_peer_review_and_incidence_benchmarks.py) over frozen `papercopilot/paperlists@181a85021c63ab26745c42ed70a9d9ea7b57ad7e` metadata mirrors (`74,637` unique submissions in explicit primary cohorts across `75,574` total mirror submissions, `72,289` scored papers, and `248,174` positive official reviews; full SHA-256 receipt and excluded-track breakdowns in [peer-review-forensics-2025-2027-v1.json](docs/benchmarks/peer-review-forensics-2025-2027-v1.json)) surfaces three descriptive snapshot patterns:

| Snapshot & Explicit Primary Cohort (`181a8502`) | Scored Papers ($N$) | Positive Reviews (Mean / Paper) | Paper Mean Score (Valid Scale) | Review Words Median (`conf=2` vs `conf=4`) | Unanimous Rate (`i.i.d.` Marginal Baseline) |
| --- | ---: | ---: | --- | --- | ---: |
| **ICLR 2026** (all public; `19,813` unique; `1,319` `rating=0` isolated) | 19,454 | 74,540 (`3.83`) | `4.26` (`2,4,6,8,10`) | `391` (`328` vs `409`) | **8.13%** (`1,578/19,412`; base `5.07%`) |
| **ICLR 2027** (`2026-11-12` rebuttal snapshot; `42,790` total) | 40,801 | 126,369 (`3.10`) | `2.06` (`1–4` int; `57.4%` at `2`) | `429` (`405` vs `451`) | **23.90%** (`9,752/40,801`; base `19.80%`) |
| **ICML 2026** (`main` accepted public; `334` ratings of `6`) | 6,341 | 24,378 (`3.84`) | `4.15` (`1–6` int rec.) | `345` (`298` vs `364`) | **16.53%** (`1,048/6,341`; base `12.35%`) |
| **NeurIPS 2025** (`main` Oral/Spotlight/Poster; raw mirror `6,212`*) | 5,275 | 21,301 (`4.04`) | `4.34` (`1–6` int rating) | `389` (`330.5` vs `409.5`) | **14.01%** (`739/5,275`; base `8.97%`) |
| **COLM 2025** (`main` Poster accepted; word counts absent in mirror) | 418 | 1,586 (`3.79`) | `6.50` (`1–10` int rating) | `—` (not in mirror) | **7.89%** (`33/418`; base `5.46%`) |

*\*Cohort transparency*: The raw `nips/nips2025.json` mirror (`6,212` records) mixes `main` (`5,526`, including `251` opted-in public `Reject`), `Datasets & Benchmarks` (`591`, including `94` `Reject`), and `Position` (`95`, including `55` `Reject` and all `125` ratings `> 6` across `74` Position papers); all `937` non-primary records are preserved in `mirror_cohort_breakdown` inside the receipt rather than dropped silently.

1. **Scale compression, reviewer-count shift & unanimity**: In `ICLR 2027` (`42,790` submissions), compressing the scale to `1–4` (`57.36%` at score `2`) alongside a lower mean review count per scored paper (`3.10`, modal `3`, vs. `3.83`, modal `4` in `ICLR 2026`) raises the empirical-marginal independent-sampling unanimity baseline $\sum_k p_k^m$ from **`5.07%`** to **`19.80%`**, accounting mechanically for most of the observed jump from **`8.13%`** to **`23.90%`**. Unanimous-score rates are structural snapshot indicators and must not be equated with AI-reviewing or collusion rates.
2. **Self-reported confidence & review length**: Across all four snapshots with word counts, self-reported `confidence = 2` reviews have lower median word counts than `confidence = 4` reviews (`328` vs `409` in `ICLR 2026`, `298` vs `364` in `ICML 2026`, `330.5` vs `409.5` in `NeurIPS 2025` `main` accepted, and `405` vs `451` in `ICLR 2027`). Separately, `ICML 2026` program chairs officially sanctioned `398` reciprocal-review LLM-policy violators (`497` desk rejections).
3. **Polarity-blind topic-mention screening (`ICLR 2026`)**: Across `19,473` joined scored `ICLR 2026` submissions and `75,769` official reviews ([iclr2026-openreview-incidence-receipt.json](docs/benchmarks/iclr2026-openreview-incidence-receipt.json), verified against `insomnia7/iclr2026_stats@50507ab3`), regex topic screening over `Weaknesses` and `Questions` matches at least one of five check families in **`48.2%`** of Oral, **`54.0%`** of Poster, **`59.8%`** of Rejected, and **`63.6%`** of Desk-Rejected papers (`59.0%` overall; measures topic-term mention prevalence rather than confirmed defect rate).

---

## 5. Architecture, Security Guardrails, Local QA & License

1. **Transactional `SQLite STRICT + WAL` state (`state_db.py`, `_stdlib.py`, `mcp_server.py`)**: Replaces legacy multi-file JSON lockfiles with foreign-keyed `STRICT` tables, `SAVEPOINT` atomic batches, `application_id = 0x41524B33` / `user_version = 4` migration guards, mandatory schema validation across all `26` artifact kinds, single-claim outer binding target verification on `quantitative_audit` / `evidence_receipt` ingestion, cycle-checked provenance graphs, and dual-sequence (`applied_seq` + `confirmed_seq`) retraction state.
2. **Untrusted PDF & network isolation (`research/sources.py`, `double_blind_sanitizer.py`)**: Every PDF read executes inside a bounded `python -I -c` worker subprocess (`pypdf==7.0.0`, `fonttools==4.65.0`). Outbound HTTP (`controlled_urlopen`) disables ambient proxies, pins resolved public DNS addresses to block DNS-rebinding TOCTOU attacks, and enforces byte caps. MCP `academic_double_blind_sanitize` redacts matched strings (`matched="[REDACTED]"`).
3. **External API etiquette & local QA gates**: `doctor` never makes network calls (`OPENALEX_API_KEY` optional for higher quotas; `Unpaywall` uses `--email` / `UNPAYWALL_EMAIL` or `--fallback-openalex`). Legacy `2.4.x` CLI aliases remain supported (`retraction-watch --import-legacy-json old-watch.json --state-db watch.sqlite3` migrates watch files; see [CHANGELOG.md](CHANGELOG.md)).

```bash
uv lock --check
uv run --frozen --extra qa --extra research pytest -q tests
uv build --no-create-gitignore
uv run --frozen --extra qa --no-editable python -m twine check --strict dist/*
PYTHONPATH=src python -m academic_research_kernel.release_gate --package-acceptance --dist dist
```

### License

Covered material in this repository is licensed under the **Source Lineage License 1.0** (`LicenseRef-Source-Lineage-1.0`) within the scope stated in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md); provenance and preserved-MIT upstream boundaries (`SLL-APPLICATION.json`) are documented in [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md), [LICENSE-HISTORY.md](LICENSE-HISTORY.md), and [REPOSITORY-IDENTITY.md](REPOSITORY-IDENTITY.md). SLL 1.0 permits free academic and commercial use, modification, redistribution, and proprietary extensions provided required license and lineage notices are preserved; network service use without distributing copies does not trigger attribution obligations, and third-party files such as [tests/upstream/LICENSE](tests/upstream/LICENSE) remain under their original licenses.

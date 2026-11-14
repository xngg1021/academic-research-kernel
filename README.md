# academic-research-kernel (`v3.0.0`)

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-CN.md)

**Deterministic scholarly verification, peer-review forensics, and LaTeX submission gates for researchers and AI agents.**

Large language models read and summarize papers fluently, yet fail predictably on tasks that require exact arithmetic or external ground truth: they repeat miscalculated $p$-values, overlook rounding-impossible percentages, cite retracted or hallucinated DOIs, miss residual author metadata in double-blind PDFs, and lose track of which table row backs which manuscript claim.

`academic-research-kernel` (`3.0.0`) separates semantic reading from deterministic verification. Your model or researcher handles reading and synthesis; a single stdlib-first Python package (`src/academic_research_kernel/`) backed by `SQLite STRICT + WAL` handles statistical recomputation, Crossref/OpenAlex/Unpaywall verification, offline OpenReview forensics, meta-analysis pooling, and multi-file LaTeX/PDF pre-submission gates.

Author: Junfu Shi (SJF, `xngg1021`). License: [Source Lineage License 1.0](LICENSE). Architecture details: [docs/kernel-architecture.md](docs/kernel-architecture.md).

---

## 1. Empirical Evidence: Peer-Review Forensics Across Five Major AI Venues (2025–2027)

Why pair every paper audit and submission workflow with deterministic verification? Running `academic-research-kernel openreview-audit --venue-summary` across frozen public OpenReview metadata mirrors (`75,574` unique public submissions, `73,226` positively scored papers, and `251,800` positive official reviews across five major AI conference snapshots from `papercopilot/paperlists@181a85021c63ab26745c42ed70a9d9ea7b57ad7e`; SHA-256 receipts and reproduction script in [docs/benchmarks/peer-review-forensics-2025-2027-v1.json](docs/benchmarks/peer-review-forensics-2025-2027-v1.json)) highlights three descriptive empirical patterns:

| Venue & Frozen Public Mirror (`181a8502`) | Scored Papers ($N$) | Positive Reviews | Paper Mean Score (Scale) | Review Words Median (`conf=2` vs `conf=4`) | Unanimous Identical-Score Rate |
| --- | ---: | ---: | --- | --- | ---: |
| **ICLR 2026** (`19,813` unique submissions; `1,319` `rating=0` isolated) | 19,454 | 74,540 | `4.26` (2–10 even) | `391` (`328` vs `409`) | **8.13%** (`1,578 / 19,412`) |
| **ICLR 2027** (`2026-11-12` rebuttal window, `42,790` total) | 40,801 | 126,369 | `2.06` (1–4 int; `57.4%` at `2`) | `429` (`405` vs `451`) | **23.90%** (`9,752 / 40,801`) |
| **ICML 2026** (accepted public; `398` LLM-policy violators sanctioned) | 6,341 | 24,378 | `4.15` (1–5 rec.) | `345` (`298` vs `364`) | **16.53%** (`1,048 / 6,341`) |
| **NeurIPS 2025** (accepted public; 2026 reached `30,709` submissions) | 6,212 | 24,927 | `4.36` (1–6 rating) | `382` (`324` vs `402`) | **13.60%** (`845 / 6,212`) |
| **COLM 2025** (accepted public; word-count fields absent in mirror) | 418 | 1,586 | `6.50` (1–10 rating) | `—` (not in mirror) | **7.89%** (`33 / 418`) |

1. **Score compression & unanimous convergence**: When ICLR compressed its rating scale from five even integers (`2, 4, 6, 8, 10`) to four integers (`1–4`) under a `42,790`-paper submission surge (`ICLR 2027`), `57.36%` of all `126,369` reviews landed on score `2`, and the share of multi-reviewer papers receiving **identical scores from every reviewer** nearly tripled from **`8.13%`** (`1,578 / 19,412` in `ICLR 2026`) to **`23.90%`** (`9,752 / 40,801` in `ICLR 2027`). Note that rating-scale cardinality, review stage, and accepted-only public filtering directly affect identical-score base rates.
2. **Self-reported confidence & review length**: Across all four mirrors that record review word counts, self-reported `confidence = 2` reviews are shorter than `confidence = 4` reviews (`328` vs `409` words in `ICLR 2026`, `298` vs `364` in `ICML 2026`, `324` vs `402` in `NeurIPS 2025`), while narrowing in `ICLR 2027` (`405` vs `451` words). Self-reported confidence and word counts are descriptive metadata rather than standalone proof of LLM-generated reviewing; separately, ICML 2026's program chairs officially sanctioned `398` reciprocal-review LLM-policy violators (`497` desk rejections).
3. **High topic-screening mention rate in peer reviews & verified benchmark accuracy**: Across `19,473` joined scored `ICLR 2026` submissions and `75,769` official reviews ([iclr2026-openreview-incidence-receipt.json](docs/benchmarks/iclr2026-openreview-incidence-receipt.json), verified against `insomnia7/iclr2026_stats@50507ab3`), lexical topic-screening regexes over `Weaknesses` and `Questions` fields match at least one of the five deterministic check families (dispersion/error bars, format/section/page rules, table/ablation consistency, baseline/citation coverage, or reproducibility/code) in **`48.2%`** of Oral papers, **`54.0%`** of Poster papers, **`59.8%`** of Rejected papers, and **`63.6%`** of Desk-Rejected papers (`59.0%` overall; polarity-blind keyword screening counts topic mentions and requires deterministic/human adjudication). On the 30-item real-world audit benchmark ([real-world-audit-benchmark-v1.json](docs/benchmarks/real-world-audit-benchmark-v1.json), `v3.0.0`: `16` frozen-snapshot bibliographic/retraction items + `12` published Nuijten/Bakker statistical examples/observations + `2` repository gate cases), the kernel achieves `TP = 10, TN = 6, FP = 0, FN = 0` on offline bibliographic/retraction classification and `TP = 8, TN = 5, FP = 1, FN = 0` on statistical & gate checks.

---

## 2. Two-Minute Quick Start: Three Ways to Use

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then pick the entry mode that matches your workflow (Python `3.10`–`3.14`, `~25 ms` CLI cold start):

### Mode A: Direct Command-Line Tool (Human Researchers & Shell Scripts)

```bash
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel doctor
academic-research-kernel verify-work "10.1038/nature14539" --normalize-only
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

---

## 3. Seven First-Principles Skills (Consolidating All 14 Legacy `v2.x` Skills)

In `v3.0.0`, all `14` legacy `v2.4.2` skill directories were consolidated from first principles into **seven self-explanatory workflow skills** so both human researchers and agents know immediately which workflow to load:

| Skill Directory | Plain-English Purpose | Key CLI Commands & MCP Tools |
| --- | --- | --- |
| [`skills/audit-paper`](skills/audit-paper/SKILL.md) | Audit single/paired papers, recompute stats/tables, adjudicate reproducibility, and manage CEG & decision ledgers | `research`, `table-forensics`, `repro-checklist`, `ledger`, `academic_recompute_statistics` |
| [`skills/verify-citations`](skills/verify-citations/SKILL.md) | Verify DOIs/updates, monitor retractions & new papers, merge corpora, and locate OA PDFs (`arXiv` + 4-service DOI chain) | `verify-work`, `retraction-watch`, `literature-watch`, `collect-corpus`, `locate-oa` |
| [`skills/audit-peer-review`](skills/audit-peer-review/SKILL.md) | Audit OpenReview venue mirrors, forum scores, and local/remote companion code repos | `openreview-audit`, `repo-forensics --github-repo`, `academic_openreview_audit` |
| [`skills/meta-analysis`](skills/meta-analysis/SKILL.md) | Pool fixed/random effects, run subgroup $Q_{\text{between}}$ & WLS meta-regression, build citation graphs & matrices | `meta-analyze`, `bibliography`, `academic_meta_analyze` |
| [`skills/check-submission`](skills/check-submission/SKILL.md) | Scaffold venue workspaces, render receipt/comparison tables, and gate TeX/PDF double-blind submissions | `lint-submission`, `sanitize-submission`, `generate-table`, `check-venue` |
| [`skills/cross-review`](skills/cross-review/SKILL.md) | Run multi-model blind review, deterministic graph clustering, anonymous challenge, and minority-evidence protection | `cross-review`, `academic_cross_review` |
| [`skills/compute-math`](skills/compute-math/SKILL.md) | Probe CPU/GPU & BLAS/thread environments, emit `ComputeReceipt`, and route multi-domain math tasks | `compute-probe`, `academic_scfabric_hardware_probe` |

---

## 4. End-to-End Workflows: Auditing External Papers vs. Checking Your Own Manuscript

### Workflow 1: Audit an External Paper, Peer-Review Mirror, or Meta-Analysis

```bash
# 1. Prepare a PDF/LaTeX bundle, validate extracted stats, and audit table conservation
academic-research-kernel research prepare ./paper.pdf --project ./paper-state
academic-research-kernel research finish --project ./paper-state --candidate ./candidate.json
academic-research-kernel table-forensics --input ./table-spec.json

# 2. Audit an OpenReview mirror (ICLR / ICML / NeurIPS / COLM) without hitting live Cloudflare 403s
academic-research-kernel openreview-audit --venue-summary ./iclr2027.json
academic-research-kernel repo-forensics ./companion-repo

# 3. Verify citations, locate legal Open Access full text, and monitor retractions in SQLite
academic-research-kernel verify-work "10.1038/nature14539"
academic-research-kernel locate-oa "10.1038/nature14539" --email "you@example.edu" --fallback-openalex
academic-research-kernel retraction-watch --dois "10.1038/nature14539" --state-db ./watch.sqlite3 --live

# 4. Pool multi-study effect sizes (fixed & DerSimonian-Laird random effects + Q / I^2 / tau^2 + Egger + trim-and-fill)
academic-research-kernel meta-analyze --input ./studies.json
```

### Workflow 2: Pre-Submission Gate for Your Own LaTeX & PDF Manuscript

```bash
# 1. Inspect venue rules (ICLR, NeurIPS, ICML, ACL, etc.) or export verified CEG claim anchors
academic-research-kernel check-venue --list-venues
academic-research-kernel check-venue --export-ceg-anchors ./ceg.json

# 2. Render verified JSON experiment receipts into Decimal-rounded booktabs LaTeX tables
academic-research-kernel generate-table ./results-receipt.json --caption "Main Results" --label "tab:main"

# 3. Scan multi-file TeX, BibTeX, and compiled PDF (/Info + XMP streams in isolated worker) for anonymity leaks
academic-research-kernel sanitize-submission ./submission-dir --forbidden-token "Alice Smith"

# 4. Run full pre-submission gate (root/nested \input, declared .bib scope, shared-page body limit, CEG claim binding)
academic-research-kernel lint-submission ./submission-dir/main.tex \
  --venue iclr --phase submission --pdf ./submission-dir/main.pdf \
  --ceg ./ceg.json --require-ceg-binding --check-academic-style
```

---

## 5. Architecture, Security Guardrails & External Data Limits

1. **Pure-stdlib `SQLite STRICT + WAL` kernel (`state_db.py`, `_stdlib.py`)**: Replaces 40+ legacy JSON-file wrappers and custom lockfiles (`32,167 -> ~16,000` non-test Python LOC) with transactional `STRICT` tables, `SAVEPOINT` batch rollback, `application_id = 0x41524B33` / `user_version = 4` identity and schema-migration guards, mandatory schema binding across all `26` formal artifact kinds, cycle-checked provenance graphs, and dual-sequence (`applied_seq` + `confirmed_seq`) retraction state.
2. **Untrusted PDF & network isolation (`research/sources.py`, `double_blind_sanitizer.py`)**: Every PDF read (`research prepare`, `lint-submission`, `sanitize-submission`) executes inside an isolated `python -I -c` worker subprocess with wall-clock timeouts and bounded pipes (`pypdf==7.0.0`). Outbound HTTP (`controlled_urlopen`) disables ambient proxies, pins resolved public DNS addresses to block DNS-rebinding TOCTOU attacks, and enforces strict byte budgets. MCP `academic_double_blind_sanitize` redacts matched strings (`matched="[REDACTED]"`) so sensitive author identifiers never echo back into third-party logs.
3. **External API etiquette**: `doctor` never makes network calls. `OpenAlex` supports anonymous first-page queries (`OPENALEX_API_KEY` recommended for higher quotas and cursor pagination); `Crossref` provides public metadata and `update-to` retraction notices; `Unpaywall` requires a contact email via `--email` or `UNPAYWALL_EMAIL` (with `--fallback-openalex` available when unset).

---

## 6. Upgrading to `3.0.0`, Local QA & License

### Key `2.4.x -> 3.0.0` Changes

- **Single package entrypoint**: Legacy `scripts/*.py` wrappers were folded into `academic_research_kernel` (`academic-research-kernel mcp` replaces `python scripts/mcp_server.py`; `python -m academic_research_kernel.release_gate` replaces `scripts/verify_release_assets.py` and `scripts/package_acceptance.py`). Both legacy CLI subcommand names (`verify-source`, `pre-submission-lint`, `sanitize-blind`, `receipt-to-latex`, `venue-template`) and the streamlined `3.0.0` aliases (`verify-work`, `lint-submission`, `sanitize-submission`, `generate-table`, `check-venue`) are supported.
- **SQLite watch state migration**: Import legacy `v2.4.x` JSON watch files once via `academic-research-kernel retraction-watch --import-legacy-json old-watch.json --state-db watch.sqlite3`. Full changelog: [CHANGELOG.md](CHANGELOG.md).

### Local Verification & Isolated Package Acceptance

```bash
uv lock --check
uv run --frozen --extra qa --extra research pytest -q tests
uv build --no-create-gitignore
uv run --frozen --extra qa --no-editable python -m twine check --strict dist/*
PYTHONPATH=src python -m academic_research_kernel.release_gate --package-acceptance --dist dist
```

### License

Covered material in this repository is licensed under the **Source Lineage License 1.0** (`LicenseRef-Source-Lineage-1.0`) within the scope stated in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md); provenance and preserved-MIT upstream boundaries (`SLL-APPLICATION.json`) are documented in [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md), [LICENSE-HISTORY.md](LICENSE-HISTORY.md), and [REPOSITORY-IDENTITY.md](REPOSITORY-IDENTITY.md). SLL 1.0 permits free academic and commercial use, modification, redistribution, and proprietary extensions provided required license and lineage notices are preserved; network service use without distributing copies does not trigger attribution obligations, and third-party files such as [tests/upstream/LICENSE](tests/upstream/LICENSE) remain under their original licenses.

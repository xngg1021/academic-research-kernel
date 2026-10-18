# academic-research-kernel

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

This repository is a practical toolkit for verifying scholarly sources, checking statistical numbers, and tracking research evidence with AI agents. When researchers use language models to read papers or draft literature reviews, models often invent citations, misread tables, or lose track of which page supports a specific claim. To prevent this, `academic-research-kernel` packages 14 scholarly workflows and 12 deterministic verification tools behind a standard Model Context Protocol (MCP) server and command-line interface. You can use it to check paper identities and retractions, recompute reported statistics, read papers into source-linked reports, manage systematic review screening logs, and record every claim alongside its supporting evidence and negative results. It works directly with Claude Code, Cursor, Codex, Gemini CLI, and Hermes Agent. Validation scope and external service limits are documented in [the project audit](docs/project-lineage-audit-20260920.md).

Author: Junfu Shi (SJF, xngg1021), Hermes Agent. License: [Source Lineage License 1.0](LICENSE).

## Quick start

If you want your AI agent to read a paper, check its numbers, and generate a report, install the package with PDF support and export the `paper-research` workflow into your agent's skill directory; if you want to connect the 12 verification tools as a background MCP server for an MCP client, install [uv](https://docs.astral.sh/uv/getting-started/installation/) and start the stdio server:

```bash
# 1. Read PDF papers and generate reports with your local AI agent
uv tool install "academic-research-kernel[research]==2.1.0"
academic-research-kernel research skill --output ./paper-research

# 2. Or start the background stdio MCP server for an MCP client
uvx academic-research-kernel@2.1.0 mcp
```

Note that running `mcp` in a terminal waits silently for JSON-RPC requests from an MCP client rather than opening an interactive menu. The [2.1.0 release page](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0) lists package hashes and publication status. If you download the release wheel, you can also run it locally with `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`. The package supports Python 3.10–3.14, and `uvx --python 3.12` selects a specific Python version. The base installation includes all 12 verification tools and loads statistical libraries on demand when statistical recomputation is called.

## Verify installation

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

The `doctor` command runs offline and checks runtime dependencies, JSON schemas, and all 12 tool definitions. Leaving optional external APIs unconfigured will not fail the check. Pass `doctor --json` if you need machine-readable output.

## Package install

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

You can also install the package with `pipx install academic-research-kernel==2.1.0` or `python -m pip install academic-research-kernel==2.1.0` inside a virtual environment. Installing with `[full]` adds libraries used in extended scientific computing examples. Installing with `[research]` adds `pypdf==6.19.0` and `fonttools==4.65.0` so PDF font decoding behaves identically across clean environments on Python 3.10 and newer. Installing with `[qa]` adds repository test tools on top of those parsing libraries. HTML, XML, DOCX, and XLSX reading use the Python standard library, while GPU backends and paid scholarly databases remain optional.

## Hermes

Make sure `uv` is on the Hermes process `PATH`, then install and enable the plugin:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

The plugin keeps the `academic-skills` name for compatibility and includes all 14 skills, including `paper-research`. Its `mcp.json` configuration runs `uv run --frozen --no-dev --no-editable` with Python 3.12 and the repository's `uv.lock` file, storing its isolated environment under `${PLUGIN_DATA}/runtime`. On first run, it installs its own dependencies without modifying Hermes or system Python packages. If you prefer installing individual skills without the plugin runtime, see [Integration & Portable Usage](#integration--portable-usage).

## Run from source

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

See [distribution and release](docs/distribution-release.md) for dependency groups, reproducible build steps, and release verification checkpoints.

## License

Snapshots containing this notice apply **Source Lineage License 1.0** to the covered material and rights described in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). The initial SLL commit and the subsequent boundary-recording commit are recorded in [LICENSE-HISTORY.md](LICENSE-HISTORY.md) and [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Later snapshots that keep this notice carry the same license scope.

Historical snapshots through commit `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` were distributed under the MIT License. Users of those earlier snapshots keep their MIT permissions and do not need to migrate to SLL. The [previous MIT license text](LICENSES/MIT-pre-SLL.txt) and [tests/upstream/LICENSE](tests/upstream/LICENSE) are preserved unchanged.

SLL permits use, study, modification, commercial use, redistribution, and proprietary extensions, provided you keep the required license and source-lineage notices. It is not copyleft and does not require disclosing your source code. Running a network service without distributing software copies does not trigger the source-lineage notice requirement. The license includes no express patent grant, and third-party files remain under their original licenses. The English [LICENSE](LICENSE) text is authoritative; `LicenseRef-Source-Lineage-1.0` is a local identifier rather than an SPDX or OSI-approved code. [Contribution rules](CONTRIBUTING.md) are separate from downstream license rights.

## Skills

| Skill | Version | What it does |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Check paper metadata and citation counts across databases, inspect corrections or retractions, find open-access full text, and verify that a local PDF matches the cited work |
| `skills/literature-analysis` | 1.3.0 | Twelve everyday workflows: find similar papers, check text overlap, search for counter-evidence, summarize author histories, run mock peer review, check reasoning flaws, build comparison tables, suggest target journals, export BibTeX, read bilingually, spot research gaps, and plan reproduction |
| `skills/academic-writing` | 1.1.1 | Revise academic prose, format citations (ISO 690, APA, MLA, Chicago, IEEE, AMA, and regional standards), check journal author guidelines, prepare submission files, and verify anonymization for blind review |
| `skills/math-computation` | 1.2.1 | Route symbolic, numerical, and statistical calculation tasks to verified Python tools, accompanied by four domain reference guides |
| `skills/quantitative-paper-audit` | 1.1.0 | Recompute reported effect sizes, p-values, confidence intervals, odds or risk ratios, and statistical power from summary numbers to catch reporting errors |
| `skills/research-reproducibility` | 1.0.1 | Audit whether a paper's code, data, dependencies, and reported metrics can be reproduced across a 14-step checklist |
| `skills/systematic-review-meta-analysis` | 1.0.1 | Record PRISMA search and screening logs, convert effect sizes, test heterogeneity, pool fixed or random effects, and run sensitivity and publication-bias checks |
| `skills/literature-watch` | 1.1.0 | Monitor OpenAlex and Crossref weekly for new papers by topic, author, or cited DOI, deduplicating results so only new works are reported |
| `skills/retraction-watch` | 1.1.0 | Recheck a DOI watchlist weekly against OpenAlex retraction flags and Crossref update records, reporting only papers whose status changed |
| `skills/research-object-identity` | 1.1.0 | Normalize DOIs, arXiv IDs, and file hashes into canonical records, verify resource status, and trace how derived files were produced from raw sources |
| `skills/claim-evidence-graph` | 1.0.0 | Link each scientific claim to the exact source passage, table, or calculation record that supports or contradicts it |
| `skills/decision-ledger` | 1.0.0 | Keep an append-only Research Decision Log of methodological choices, failed attempts, reasons for dropping a direction, and later outcome revisions |
| `skills/paper-research` | 1.0.0 | Read a paper and its supplements from a DOI, URL, or local folder, verify extracted numbers, save structured research state, and generate source-linked Chinese reports or two-paper comparisons |
| `skills/cross-review-five` | 2.0.0 | Coordinate independent blind reviews across multiple language models or subagents, merge overlapping points, assign cross-challenges, and grade issues from P0 to P3 while preserving unresolved dissent |

Across the 14 skills, 22 Markdown reference guides are loaded on demand when a task requires them.

## Scholarly Standards & Multi-Profile Baseline

Citation formats, reporting checklists, and metadata rules depend on your target journal, funder, discipline, and region. This repository uses **ISO 690:2021** (bibliographic references), **ISO 5127:2017** (documentation vocabulary), and **W3C PROV** (provenance records) as its international baseline, alongside regional standards such as GB/T 7714-2025 in Mainland China, UNE-ISO 690:2024 in Spain, and DIN ISO 690:2021 in Germany, plus disciplinary guides including APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, and ICMJE. A target journal's own instructions always override default settings. See the [Scholarly Standards Architecture](docs/standards/README.md) and [Natural Terminology Guide](docs/terminology/README.md).

When saving research state, the kernel checks that DOIs and external identifiers match, prevents contradictory statistical verdicts on the same check, and tracks unresolved questions in a shared review list. Cache verification rebuilds state directly from saved source packages and hash bindings rather than trusting summary lists, so deleting both a record and its cache entry will still be caught during replay. Details are recorded in the [four-blocker closeout](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integration & Portable Usage

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
This repository follows the vendor-neutral **Agent Plugins v1** format (`plugin.json`) and exposes its verification and statistical tools through a standard stdio **MCP server** (`mcp.json` / `scripts/mcp_server.py`). You can load it directly in Claude Code, Cursor, Codex, Gemini CLI, or any other MCP-compatible client. Although the repository is named `academic-research-kernel`, the plugin name `academic-skills` and existing MCP aliases remain unchanged so existing configurations keep working:

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Native Hermes Installation
From an existing Hermes installation, you can also register the skill tap directly:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

To install another skill, replace the directory name at the end of the command. Because `tap add` reads the default branch, a fresh install gets the 14 skills listed above. If you want to test an unmerged work branch, check out that branch locally and install from the local folder rather than expecting `tap` to pull a pull-request branch.

Related skills checked against upstream Hermes commit `245e48008fa814b3251f50755eb656bd9fb86cb1` include `arxiv`, `grounded-citations`, `docx`, `pdf`, and `manim-video`. Optional skills such as `huggingface-hub` and `llama-cpp` can be installed separately. Neither `ocr-and-documents` nor `pc-hardware-benchmark` is required.

## Data-source access

- OpenAlex allows anonymous first-page queries with a small daily budget. Current OpenAlex rate limits are 10 requests per second without a key, 30 requests per second with a free or prepaid API key, and 50 requests per second on annual plans; anonymous use covers $0.10/day and a free API key covers $1/day. Following `next_cursor` beyond the first page requires an API key in `OPENALEX_API_KEY` (anonymous second-page cursor requests return HTTP 401 and are truncated to the first page).
- Crossref provides public metadata with rate limits. Checking corrections and retractions requires verifying both the DOI and the update direction; an empty result does not prove a paper has no issues.
- Unpaywall requires a real contact email in `UNPAYWALL_EMAIL`. If Unpaywall returns no link, an open-access copy may still exist elsewhere.
- arXiv, Europe PMC, PubMed E-utilities, and DOAJ serve as additional sources with their own rate limits. Semantic Scholar separates shared anonymous limits from dedicated API key quotas, and API access does not guarantee that citation context snippets are available for every paper.
- Scite, Dimensions, Scopus, Web of Science, and commercial AI detectors are optional third-party services. Check your own account permissions and quotas before calling them.

See [OpenAlex authentication](https://help.openalex.org/api/authentication/), [budgets/query costs](https://help.openalex.org/api/llm-quick-reference/), and [Crossref update filters](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Research state storage and verification boundaries

The ingestion module uses `ResearchArtifactEnvelope v1` and `ArtifactIngestionReceipt v1`, pairing 15 adapters (one for each of the 14 skills plus a plain-text fallback) with 12 stateless stdio MCP tools. Whenever the system saves research objects, claim–evidence links, Research Decision Log entries, items needing review, or verification records, it records their canonical SHA-256 hashes in an ingestion receipt. Replaying a cache checks those hashes directly. Empty decision logs are valid, and any batch write that fails mid-way rolls back cleanly without leaving partial files behind.

Marking a record as `fully_verified` requires access to the underlying source bytes so the check can be reproduced independently. Trusted Python callers provide this through `LineageVerificationContext`, while MCP callers pass bounded file bytes directly rather than exposing host filesystem paths. The default file size limit is 10 MiB, which a trusted host can raise when needed. Without the source bytes, a `fully_verified` claim fails validation. Unstructured notes stay untouched, reviewer disagreements remain visible, and human researchers stay in charge of committing state, dropping or reopening research routes, and making final scholarly judgments.

See [the architecture guide](docs/kernel-architecture.md) for data contracts and [the release guide](docs/distribution-release.md) for packaging details. All 21 root and regional READMEs are synchronized with the 2.1.0 baseline, and [the manifest](docs/i18n/manifest.json) tracks cryptographic synchronization hashes across all locales. Release verification and review records are archived in the [closeout ledger](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validation and testing

Run the test suite in a dedicated Python virtual environment so optional scientific libraries do not conflict with your host setup:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

`scripts/qa.py` checks skill frontmatter, file links, accidental local paths or secret strings, Python syntax, and executable code examples. Every `smoke-test: true` code block runs in a clean subprocess, saving plots to `PLOT_DIR` (`~/plots` by default, or a temporary folder during tests). Unlabeled Python blocks are rejected, `fragment:` blocks are syntax-checked only, and `external-test:` blocks run only when you invoke `scripts/verify_external_apis.py`. That external check exits with `0` when all configured checks pass, `1` on code or data errors, and `2` when network or quota limits prevent access; unconfigured optional services are marked `SKIP`.

Our test suite reuses the upstream Hermes skill-authoring rules for each individual skill while validating all 14 skills in this repository against the pinned catalog. CI accesses the network only to install packages; standard pull-request checks never call external scholarly APIs.

GitHub Actions runs the full test matrix across Linux x86_64 (Python 3.10–3.14), Linux ARM64 (`ubuntu-24.04-arm`), Ubuntu 26.04 preview runners (`ubuntu-26.04` and `ubuntu-26.04-arm`), Windows x86_64, Windows ARM64 (`windows-11-arm`), macOS ARM64 (`macos-latest`), and macOS Intel (`macos-15-intel`), alongside live compatibility checks against upstream Hermes. The local regression suite passes 1316 tests (extending the 1165-test baseline in [the correctness repair report](docs/maintenance/correctness-repair-20261008.md)). On pushes to `main`, a separate workflow installs the pinned Hermes commit from `tests/upstream/provenance.json` and tests `tap add`, `search`, `install`, and `list` against this repository. See [the project audit](docs/project-lineage-audit-20260920.md) for exact versions and test boundaries.

[tools/longtail/](tools/longtail/README.md) contains the deterministic scenario generator, which draws 4096 SHA256-seeded candidates, selects 30 test scenarios, and outputs a coverage report across 16 capability families (E01), the 14 repository skills (E02), and 36 task goals (E03). Every skill appears at least twice across at least two distinct goals, including its core workflow goal.

`scripts/scfabric/` contains the scientific computing benchmark tools, including hardware detection, numeric precision checks, five workload profiles, and `ComputeReceipt` logs. Benchmark results are recorded in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); calculations use the CPU by default and enable hardware accelerators only when verified by a benchmark receipt.

## Read and compare papers with a local Agent

Install the `[research]` extra and export the `paper-research` skill to your local agent workspace:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Point Work or another local agent at that exported `SKILL.md`, provide a DOI, public URL, or local folder, and ask:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
If you have two papers, ask the agent to compare their datasets, methods, experimental conditions, and results, and to explain which numbers can be compared directly. The agent will read the source files, extract candidate numbers, run statistical checks, save the verified state, and write a source-linked report in one workflow.

Under the hood, the CLI runs three steps:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` downloads or reads the paper and its supplements, records file hashes, and indexes text passages by page and section. `finish` checks the structured numbers extracted by your agent, recomputes t-tests, p-values, two-group effect sizes, and percentages, saves the verified state, and writes Chinese Markdown and HTML reports. `compare` checks a structured comparison between two papers. Because the CLI relies on your active agent to read the prose following [paper-research](skills/paper-research/SKILL.md), it does not require a separate model API account. Saved source files and extraction snapshots can be replayed offline at any time.

## Statistical precision, retraction tracking, and package verification

The `academic_recompute_statistics` MCP tool recomputes t-test p-values and two-group Cohen's d or Hedges' g effect sizes, while confidence intervals and odds or risk ratios are available as Python functions. When trailing zeros in a reported p-value matter, pass `p_value_literal` (such as `"1.0e-5"`) or `p_value_decimals`. String literals keep trailing zeros, plain numbers use their floating-point value, and conflicting precision settings return an explicit error. Rounding checks include the lower half-way boundary and exclude the upper boundary. Finding that a paper's reported number disagrees with the recomputed value returns a normal verification result; `isError` is set only when the input is invalid or the calculation itself fails.

Retraction checks store the current run's observation (`True`, `False`, or `unknown`) separately from the last confirmed status. A short lock orders updates for the same DOI without overwriting other DOIs in the watchlist. If a network error or rate limit produces an `unknown` result on the latest run, the system reports that the current check is unverified while preserving the previously confirmed history. Regression tests use labeled local HTTP fixtures instead of live network calls.

The stdio MCP server replies to `ping`, stays silent on valid notifications such as `notifications/cancelled`, and keeps the session open if a client sends malformed input, following the [MCP message contract](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages) and [ping specification](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

To build and verify release packages in an isolated environment, run:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` unpacks the source archive into a temporary directory outside the repository, sets `ARK_REPO` and `ARK_SDIST`, and runs the unit tests, static QA, executable examples, and i18n checks against the unpacked files. Both the wheel and source archive are tested in fresh virtual environments, and `uvx` is tested against the local wheel with an isolated cache.

## Research and planning documents

These two background documents record early design notes rather than a fixed roadmap; their direction numbers are generated from `docs/direction-primitive-mapping.json`.

- [Pain Atlas v0 (English)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): common failure points across everyday academic research and verification status for quantitative claims.
- [Research Plan v0 (English)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): design notes on research object tracking, core capabilities, and the long-tail scenario matrix.

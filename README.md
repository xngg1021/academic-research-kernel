# academic-research-kernel

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

This repository provides a deterministic research-state kernel and 14 scholarly skills for agentic research workflows. It connects research object identity, evidence and verification records, claim–evidence relationships, and an append-only Research Decision Log through deterministic research artifact ingestion and a standard Model Context Protocol (MCP) server. All 14 skills read and write verified research state across Claude Code, Cursor, Codex, Gemini CLI, and Hermes Agent. [The audit](docs/project-lineage-audit-20260920.md) documents the validation scope and external-service limitations.

Author: Junfu Shi (SJF, xngg1021), Hermes Agent. Current scoped offer: [Source Lineage License 1.0](LICENSE).

## Quick start

Run version 2.1.0 with [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel@2.1.0 mcp
```

The [2.1.0 release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.1.0)
records distribution hashes and publication status. The release wheel also runs locally
with `uvx --from ./academic_research_kernel-2.1.0-py3-none-any.whl academic-research-kernel mcp`.
The package supports Python 3.10–3.14, and `uvx --python 3.12` explicitly selects a compatible interpreter.
The base installation includes all 12 deterministic tools and their statistical dependencies.

## Verify

```bash
uvx academic-research-kernel@2.1.0 doctor
uvx academic-research-kernel@2.1.0 --version
```

The offline diagnostic checks dependencies, schemas and all 12 tool definitions.
Optional services can remain unconfigured. Use `doctor --json` for machine-readable output.

## Package install

```bash
uv tool install academic-research-kernel==2.1.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Alternatively, install with `pipx install academic-research-kernel==2.1.0` or
`python -m pip install academic-research-kernel==2.1.0` inside a supported virtual environment.
`[full]` adds libraries for extended scientific skill examples; `[qa]` adds repository
validation tools, including the PDF parser. `[research]` adds `pypdf==6.19.0` and
`fonttools==4.65.0` for consistent PDF font decoding across clean installations;
both support Python 3.10. Structured HTML/XML and bounded DOCX/XLSX reading use
the standard library. GPU backends and paid services remain optional.

## Hermes

Install uv so it is on Hermes' process PATH, then install and explicitly enable the portable plugin:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

The plugin keeps the `academic-skills` identifier for compatibility and bundles all 14 skills, including `paper-research`. Its
`mcp.json` invokes `uv run --frozen --no-dev --no-editable` with Python 3.12 and the
checkout's `uv.lock`; its environment lives under `${PLUGIN_DATA}/runtime`.
It bootstraps dependencies on first use, without borrowing Hermes' or the system's Python
packages. First use needs network access to obtain missing packages/interpreter.
The older skill-only tap remains supported under [Integration & Portable Usage](#integration--portable-usage).

## From source

```bash
git clone https://github.com/xngg1021/academic-research-kernel.git
cd academic-research-kernel
uv sync --frozen --no-dev --no-editable
uv run --frozen --no-dev --no-editable academic-research-kernel doctor
uv run --frozen --no-dev --no-editable python scripts/mcp_server.py
```

See [distribution and release](docs/distribution-release.md) for dependency classification,
reproduction, release identity, publication checkpoints and validation scope.

## License

The snapshot containing this notice adopts **Source Lineage License 1.0** for the Covered Material and rights identified in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). The first SLL commit and tree, and the later boundary-recording commit, are distinguished in [LICENSE-HISTORY.md](LICENSE-HISTORY.md) and [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Snapshots from that recorded transition forward retaining this notice carry the same scoped offer.

Historical snapshots through `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` were MIT-licensed, subject to the terms applicable to those copies. Recipients retain valid MIT permissions and need not migrate to SLL. The [former project MIT text](LICENSES/MIT-pre-SLL.txt) is preserved; [tests/upstream/LICENSE](tests/upstream/LICENSE) and its third-party provenance remain unchanged. The new root offer does not erase those rights.

SLL broadly permits use, study, modification, commercial use, distribution and proprietary additions, subject to applicable license, notice and source-lineage conditions. It is not copyleft and requires no source disclosure. Pure network service without supplying copies does not by itself trigger the Core service-lineage notice condition. There is no express patent grant. Third-party material remains under its own terms. The exact English [LICENSE](LICENSE) controls this informational summary; `LicenseRef-Source-Lineage-1.0` is a local reference, not SPDX assignment, and no OSI approval is claimed. [Contribution intake](CONTRIBUTING.md) is separate from downstream license permissions.

## Skills

| Skill | Version | What it does |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Cross-check identity and source-specific citation counts; inspect update/retraction signals; locate OA text and verify PDF identity |
| `skills/literature-analysis` | 1.3.0 | Twelve workflows: topic similarity, local text overlap, counter-evidence, author profiles, mock review, fallacy checks, review matrix, journal candidates, BibTeX, bilingual reading, research-gap screening, reproduction |
| `skills/academic-writing` | 1.1.1 | Editing, citation guidance (ISO 690, APA, MLA, Chicago, IEEE, AMA, and regional profiles), journal instructions, optional detection services, submission materials, and institutional requirements |
| `skills/math-computation` | 1.2.1 | Existing domain/task routing with corrected numerical/statistical examples; four domain/advanced reference files |
| `skills/quantitative-paper-audit` | 1.1.0 | Recompute reported statistics (effect size, p values, CIs, OR/RR, achieved power) and detect numerical mismatches |
| `skills/research-reproducibility` | 1.0.1 | Fourteen-stage reproduction audit pipeline with structured verification checklists, five fact tiers, and reproducible audit records |
| `skills/systematic-review-meta-analysis` | 1.0.1 | PRISMA search logs, literature screening logs, effect-size conversion, heterogeneity, fixed/random pooling, sensitivity and publication-bias diagnostics |
| `skills/literature-watch` | 1.1.0 | Weekly blueprint: watch topics, authors and DOI citing works on OpenAlex and Crossref; deduplicate and report only new items |
| `skills/retraction-watch` | 1.1.0 | Weekly blueprint: recheck a DOI watchlist against OpenAlex is_retracted and Crossref update records (update-to signals); report only status changes |
| `skills/research-object-identity` | 1.1.0 | Deterministic research-resource identification and provenance tracking: identifier normalization, 5-state verification, content-addressed derivation graphs, causal DAG validation, and sub-100ms lineage tracing |
| `skills/claim-evidence-graph` | 1.0.0 | Deterministic scientific claim–evidence linking connecting assertions, evidence records, and computational provenance |
| `skills/decision-ledger` | 1.0.0 | Research Decision Log: deterministic, append-only log of research decisions, failed attempts (negative results), reasons for stopping routes, and outcome revisions |
| `skills/paper-research` | 1.0.0 | DOI/URL/local paper and supplement reading with validated field candidates, statistical checks, persistent research state, source-linked Chinese reports and two-paper comparison |
| `skills/cross-review-five` | 2.0.0 | Dynamic multi-reviewer panel orchestration supporting arbitrary models/subagents (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, etc.): v2 Sparse Deliberation pipeline with Kuhn-Munkres Hungarian assignment, assertion-level clustering, targeted anonymous challenge, and P0-P3 severity grading |

There are 22 Markdown reference files across the fourteen skills. References load only when needed.

## Scholarly Standards & Multi-Profile Baseline

Citation styles, reporting criteria, and metadata contracts depend on the target journal, institution, funder, discipline, and jurisdiction. The repository establishes **ISO 690:2021** (Bibliographic references), **ISO 5127:2017** (Information and documentation vocabulary), and **W3C PROV** (Provenance data model) as international baselines, alongside regional profiles (e.g., GB/T 7714-2025 in Mainland China, UNE-ISO 690:2024 in Spain, DIN ISO 690:2021 in Germany) and disciplinary standards (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Target venue requirements take precedence over default profiles. See the [Scholarly Standards Architecture](docs/standards/README.md) and [Natural Terminology Guide](docs/terminology/README.md).

The kernel validates DOI and identifier coherence, mutually exclusive quantitative verdict flags, and the shared uncertainty contract across kernel state and verification records. Cache replay reconstructs completeness from retained source envelopes and normalized bindings rather than trusting a receipt's mutation lists, so removing both a state record and its cache declaration cannot produce an accepted replay. See the [four-blocker closeout](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integration & Portable Usage

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
This repository conforms to the vendor-neutral **Agent Plugins v1** specification (`plugin.json`) and exposes its academic verification and statistical recomputation tools through a stdio **MCP server** (`mcp.json` / `scripts/mcp_server.py`). It runs directly in Claude Code, Cursor, Codex, Gemini CLI, and other MCP-compatible agent hosts. While the repository identity is `academic-research-kernel`, the plugin manifest name `academic-skills` and MCP configuration aliases remain stable for backward compatibility.

```bash
# Add as stdio MCP server in your agent harness
uvx academic-research-kernel mcp
```

### 2. Native Hermes Installation
From a Hermes installation:

```bash
hermes skills tap add xngg1021/academic-research-kernel
hermes skills search academic-source-verification
hermes skills install xngg1021/academic-research-kernel/skills/academic-source-verification
```

Install the others by substituting their directory name in the full identifier. A normal tap reads the default branch, so the skill set above is what a fresh tap installs. To inspect a work branch before merge, check out that branch locally and follow the installed Hermes version's local-folder installation instructions. Do not assume the tap command selects a PR branch.

Bundled related skills checked at upstream `245e48008fa814b3251f50755eb656bd9fb86cb1`: arxiv, grounded-citations, docx, pdf, manim-video. huggingface-hub and llama-cpp are in the optional catalog and may need installation. ocr-and-documents and pc-hardware-benchmark were not found in that snapshot and are not dependencies. Session tools and document/browser backends depend on local configuration.

## Data-source access

- OpenAlex basic queries can run anonymously with a smaller daily budget. On 2026-09-06 current docs specify $0.10/day anonymous and $1/day with a free API key, plus a 100 requests/second ceiling. Costs differ by query type; this is not unlimited access. Store an optional key in `OPENALEX_API_KEY`. Use `per_page` (maximum 100) and cursor pagination.
- Crossref has public metadata access with throttling. Update relationships and Retraction Watch signals require DOI/direction checks; missing records do not prove a paper is unaffected.
- Unpaywall requires a real contact email in `UNPAYWALL_EMAIL`. An absent location does not prove that no OA copy exists.
- arXiv, Europe PMC, PubMed E-utilities and DOAJ are supplementary sources with their own policies. They are not all exercised by default tests. Semantic Scholar has shared anonymous limits and separately assigned key limits; access does not guarantee citation-context availability.
- Scite, Dimensions, Scopus, Web of Science and AI-detection products are optional external services. Check current account/API entitlements and quotas before use; no universal free tier or fixed price is promised.

See [OpenAlex authentication](https://help.openalex.org/api/authentication/), [budgets/query costs](https://help.openalex.org/api/llm-quick-reference/), and [Crossref update filters](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-filters/).

## Deterministic ingestion and public kernel

The ingestion layer provides `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 15 adapters (the 14 skills plus opaque fallback), and 12 stateless stdio MCP tools. Accepted ingestion receipts bind each retained semantic mutation by kind, identity, and canonical SHA-256 across research objects, claim–evidence records, Research Decision Log entries, items needing review, physical verification records, and artifact registrations. Cache replay checks those commitments independently of transport snapshot hashes. Empty logs are valid, and failed atomic batches leave no partial state.

Lineage content authority is explicit and out of band. Trusted Python callers pass `LineageVerificationContext` when replaying serialized receipts or snapshots; MCP callers may supply bounded content bytes, never a host filesystem root. The default content budget is 10 MiB; a trusted host may explicitly authorize larger artifacts under the same producer/verifier policy. Without content authority, a `fully_verified` claim cannot be independently reproduced and returns a structured invalid verification result. Opaque prose stays opaque, dissent stays visible, and researchers retain control of commits, pruning, reopening, routing and truth judgments.

See [the architecture](docs/kernel-architecture.md) for contracts and compatibility rules, and [the release guide](docs/distribution-release.md) for distribution and publication checkpoints. All 21 root and regional READMEs are synchronized with the 2.1.0 baseline, and [the manifest](docs/i18n/manifest.json) tracks cryptographic synchronization hashes across all locales. Release candidate verification, exact-head CI, and review records are archived in the [closeout ledger](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validation

Use a dedicated Python environment. Runtime libraries are task-specific, not guaranteed installed in Hermes. QA dependencies are broader so all marked examples can run:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q -rs tests
python scripts/i18n_sync.py --check
python scripts/verify_external_apis.py --output external-status.json --summary external-summary.md
git diff --check
```

`scripts/qa.py` validates skill metadata, file references, personal-path and secret patterns, Python syntax, and marked executable code fences. Each `smoke-test: true` fence runs unchanged in a fresh subprocess; plot examples read `PLOT_DIR` (defaulting to an explicitly expanded `~/plots`, or a temporary directory under test). QA rejects unclassified Python fences, syntax-checks `fragment:` blocks without running them standalone, and reserves `external-test:` blocks for `scripts/verify_external_apis.py`. That external verifier returns `0` when configured checks pass, `1` on code, schema, or identity failures, and `2` when transport, authentication, or quota limits block access; unconfigured optional services report `SKIP`.

The test suite runs the pinned Hermes authoring checks without altering their per-skill rules. Because upstream whole-distribution population checks do not apply to a standalone tap, our test harness validates all 14 skills and resolves references against the pinned bundled and optional catalog rather than simulating a full Hermes installation. CI uses network access only to install dependencies, and standard pull-request tests do not call live scholarly APIs.

CI runs the full QA suite across Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 preview canary (ubuntu-26.04 & ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest), and macOS Intel (macos-15-intel), alongside live upstream canary validation. The local full regression suite passes 1165 tests; detailed verification results and coverage boundaries are recorded in [the correctness repair](docs/maintenance/correctness-repair-20261008.md), and remote CI logs record each tested HEAD separately. On pushes to `main`, a separate tap integration workflow installs the pinned Hermes checkout from `tests/upstream/provenance.json` and exercises `tap add`, `search`, `install`, and `list` against this repository. Exact versions, checks, and limitations are documented in [the audit](docs/project-lineage-audit-20260920.md).

[tools/longtail/](tools/longtail/README.md) holds the deterministic long-tail factor generator: 4096 SHA256-seeded candidates, 30 selected scenarios and a machine-computed coverage report. The v3 model separately counts capability families (E01), the 14 actual repository skills (E02), and task goals (E03). Each scenario has one primary skill, a supported task goal and compatible capabilities; every skill must appear at least twice under two distinct goals, including its declared core goal. Skill-directory drift fails validation. Semantic expansion (task chains, oracles and executed event injection) remains a separate stage; factor coverage does not prove workflow execution coverage.

`scripts/scfabric/` provides the scientific calculation and statistical benchmark suite: hardware probing, a backend catalog with dtype gates, five workload profiles, paired parity benchmarks, and `ComputeReceipt` records. First-round measurements are documented in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); the runtime defaults to CPU and enables hardware accelerators only when backed by a verified receipt.

## Research a paper with a local Agent

Install `academic-research-kernel[research]==2.1.0` and export the packaged workflow:

```sh
academic-research-kernel research skill --output ./agent-skills/paper-research
```

Let Work or a compatible local Agent read that exported `SKILL.md`, then ask:
“研究这篇论文及其补充材料，整理方法，核对能重算的关键数字，给我一份带出处的中文报告。”
Supply only the DOI, public link or local bundle. For two papers, ask it to compare data,
methods, evaluation conditions and results, explaining what is directly comparable.
The Agent continues through original-text reading, candidate validation, calculation,
ingestion, report generation and independent source review in the same task. The existing
MCP surface retains its 12 tools; the new orchestration lives in the CLI and portable skill.

The actual program stages are:

```sh
academic-research-kernel research prepare INPUT --project PROJECT
academic-research-kernel research finish --project PROJECT --candidate CANDIDATE.json
academic-research-kernel research compare LEFT_PROJECT RIGHT_PROJECT --analysis COMPARISON.json --output OUTPUT
```

`prepare` acquires and parses material into a manifest, source hashes and located segments.
`finish` validates an Agent-produced extraction and recomputes eligible t/p, two-group
effect-size and count/percentage claims using existing statistical tools, then saves kernel
state and Chinese Markdown/HTML reports. `compare` validates an Agent's explicit assessment
of comparable conditions. These commands do not embed a resident Work model: semantic
reading is performed by the current Agent following [paper-research](skills/paper-research/SKILL.md).
Saved original files and extraction snapshots support deterministic offline replay. Network
acquisition and a new semantic reading remain separately identified operations.

## 2.0.1 correctness and distribution verification

Release 2.0.1 hardens statistical recomputation, retraction state tracking, and stdio MCP session handling. The public `academic_recompute_statistics` tool
exposes t-test p-values and two-group Cohen's d/Hedges' g, while confidence intervals and OR/RR remain
lower-level Python functions. Callers can pass `p_value_literal` (for example `"1.0e-5"`)
or `p_value_decimals` when reported decimal precision matters: string literals preserve
trailing zeros, numeric inputs retain only their floating-point value, and conflicting
precision arguments fail explicitly. Round-half-up comparisons include the lower
rounding boundary and exclude the upper boundary. A statistical mismatch returns a normal
verification result, whereas invalid inputs or partial calculation failures set `isError`.

Retraction checks record each run's `True`/`False`/`unknown` observation separately
from the last-known confirmed state. A brief pre-query lock orders same-DOI
observations and preserves concurrent updates to other DOIs. Because current observations and historical
confirmations carry separate sequence numbers, a late confirmation can update retained
history while a newer `unknown` response remains explicitly unverified for the current check.
The regression chains use explicitly labeled HTTP test fixtures in place of live network responses.

MCP responds to `ping`, remains silent for valid notifications (including
`notifications/cancelled`), and keeps the stdio session alive after invalid input.
The synchronous implementation does not advertise preemptive cancellation.
Message handling follows the [MCP message contract](https://modelcontextprotocol.io/specification/2024-11-05/basic/messages)
and [ping specification](https://modelcontextprotocol.io/specification/2024-11-05/basic/utilities/ping).

Build and verify this checkout's distributions with an isolated environment:

```bash
python -m build
python -m twine check --strict dist/*
python scripts/package_acceptance.py --dist dist --uvx --source-checks --report package-acceptance.json
```

`--source-checks` extracts the candidate sdist unchanged outside the checkout,
sets `ARK_REPO` and `ARK_SDIST` to that candidate, and runs its tests, static QA,
executable fences and i18n check. Wheel and sdist installations each use a fresh
environment; uvx uses the local wheel with an independent cache. The report records
artifact hashes and installed import paths. Scheduled lightweight pinned/latest
Hermes checks report the tested SHA independently. External contract JSON and
job summaries use `healthy`, `degraded` and `failed`; skipped probes remain explicit.

## Research and planning documents

These two documents are exploratory planning references, not a binding roadmap. Their direction numbers are recomputed from the stored grouping in docs/direction-primitive-mapping.json.

- [Pain Atlas v0 (English)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): friction points across the academic knowledge-work life cycle, with verification states attached to quantitative claims.
- [Research Plan v0 (English)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): the Research Object model, core capability areas, candidate directions and the phase-one factor decomposition matrix.

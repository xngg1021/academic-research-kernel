# academic-research-kernel

<!-- mcp-name: io.github.xngg1021/academic-research-kernel -->

[English](README.md) · [简体中文](README.zh-Hans.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md) · [Português](i18n/pt/README.md) · [Русский](i18n/ru/README.md) · [Bahasa Indonesia](i18n/id/README.md) · [Italiano](i18n/it/README.md) · [हिन्दी](i18n/hi/README.md) · [العربية](i18n/ar/README.md) · [বাংলা](i18n/bn/README.md) · [اردو](i18n/ur/README.md) · [Tiếng Việt](i18n/vi/README.md) · [Türkçe](i18n/tr/README.md) · [فارسی](i18n/fa/README.md) · [Kiswahili](i18n/sw/README.md) · [Polski](i18n/pl/README.md)

Harness-neutral deterministic research-state kernel for agentic research workflows. It unifies research object identity, empirical evidence receipts, tripartite claim-evidence graphs (CEG), and append-only research decision logs through a deterministic ingestion bridge and universal Model Context Protocol (MCP) server. 13 specialized scholarly skills act as producers and consumers of verified research state, with native support for Claude Code, Cursor, Codex, Gemini CLI, and Hermes Agent. Validation scope and external-service limitations are recorded in [the audit](docs/project-lineage-audit-20260920.md).

Author: Junfu Shi (SJF, xngg1021), Hermes Agent. Current scoped offer: [Source Lineage License 1.0](LICENSE).

## Quick start

After 2.0.0 is published to PyPI, run with [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx academic-research-kernel mcp
```

Publication is a separate release step: check the [2.0.0 release](https://github.com/xngg1021/academic-research-kernel/releases/tag/v2.0.0)
manifest for the actual PyPI status. Before publication, download the release wheel
and use `uvx --from ./academic_research_kernel-2.0.0-py3-none-any.whl academic-research-kernel mcp`.
For a fixed product identity, use `uvx academic-research-kernel@2.0.0 mcp`.
Python 3.10–3.14 is supported; `uvx --python 3.12` explicitly selects a supported interpreter.
All 12 deterministic tools, including statistics, are included in the base install.

## Verify

```bash
uvx academic-research-kernel doctor
uvx academic-research-kernel --version
```

The offline diagnostic checks dependencies, schemas and all 12 tool definitions.
Optional services can remain unconfigured. Use `doctor --json` for machine-readable output.

## Package install

```bash
uv tool install academic-research-kernel==2.0.0
academic-research-kernel doctor
academic-research-kernel mcp
```

Alternatively, install with `pipx install academic-research-kernel==2.0.0` or
`python -m pip install academic-research-kernel==2.0.0` inside a supported virtual environment.
`[full]` adds libraries for extended scientific skill examples; `[qa]` adds repository
validation tools. GPU backends and paid services remain optional.

## Hermes

Install uv so it is on Hermes' process PATH, then install and explicitly enable the portable plugin:

```bash
hermes plugins install xngg1021/academic-research-kernel --no-enable
hermes plugins enable academic-skills
```

The existing `academic-skills` identity and all 13 skills are preserved. The plugin's
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
| `skills/cross-review-five` | 2.0.0 | Dynamic multi-reviewer panel orchestration supporting arbitrary models/subagents (Kimi K3, DeepSeek V4 Pro, GLM 5.3, Claude, Gemini, etc.): v2 Sparse Deliberation pipeline with Kuhn-Munkres Hungarian assignment, assertion-level clustering, targeted anonymous challenge, and P0-P3 severity grading |

There are 21 Markdown reference files across the thirteen skills. References load only when needed.

## Scholarly Standards & Multi-Profile Baseline

Citation styles, reporting criteria, and metadata contracts depend on the target journal, institution, funder, discipline, and jurisdiction. The repository establishes **ISO 690:2021** (Bibliographic references), **ISO 5127:2017** (Information and documentation vocabulary), and **W3C PROV** (Provenance data model) as international baselines, alongside regional profiles (e.g., GB/T 7714-2025 in Mainland China, UNE-ISO 690:2024 in Spain, DIN ISO 690:2021 in Germany) and disciplinary standards (APA 7th, IEEE, ACM, Vancouver, Chicago, PRISMA 2020, ICMJE). Target venue requirements take precedence over default profiles. See the [Scholarly Standards Architecture](docs/standards/README.md) and [Natural Terminology Guide](docs/terminology/README.md).

The final PR #12 repair validates DOI/identifier coherence, inverse quantitative verdict flags, and the shared kernel/receipt uncertainty contract. Cache completeness is reconstructed from retained source envelopes and normalized bindings, independently of the receipt's mutation lists; removing both a record and its cache declaration cannot produce an accepted replay. See the [four-blocker closeout](docs/project-lineage-audit-20260920.md#four-blocker-successor--2026-09-21).

## Integration & Portable Usage

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
This repository conforms to the vendor-neutral **Agent Plugins v1** specification (`plugin.json`) and exposes core academic verification and statistical recompute tools via a stdio **MCP server** (`mcp.json` / `scripts/mcp_server.py`). Compatible with Claude Code, Cursor, Gemini CLI, and any modern agent framework. (Note: While the repository identity is `academic-research-kernel`, the plugin manifest name `academic-skills` and MCP configuration aliases remain stable for backward compatibility.)

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

PR #12 provides `ResearchArtifactEnvelope v1`, `ArtifactIngestionReceipt v1`, 14 adapters (the 13 skills plus opaque fallback), and 12 stateless stdio MCP tools. Accepted ingestion receipts bind each retained semantic mutation by kind, identity and canonical SHA-256: objects, CEG records, ledger records, uncertainties, physical receipts and artifact registrations. Cache replay checks those commitments independently of transport snapshot hashes. Empty ledgers are valid; failed atomic batches leave no partial state.

Lineage content authority is explicit and out of band. Trusted Python callers pass `LineageVerificationContext` when replaying serialized receipts or snapshots; MCP callers may supply bounded content bytes, never a host filesystem root. The default content budget is 10 MiB; a trusted host may explicitly authorize larger artifacts under the same producer/verifier policy. Without content authority, a `fully_verified` claim cannot be independently reproduced and returns a structured invalid verification result. Opaque prose stays opaque, dissent stays visible, and researchers retain control of commits, pruning, reopening, routing and truth judgments.

See [the architecture](docs/kernel-architecture.md) for contracts and compatibility. Distribution and publication checkpoints are recorded in [the release guide](docs/distribution-release.md). English and Simplified Chinese README are current; other translation states remain explicit in [the manifest](docs/i18n/manifest.json). Final candidate identity, exact-head CI, cumulative review and merge evidence are recorded in the [closeout ledger](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5754741342).

## Validation

Use a dedicated Python environment. Runtime libraries are task-specific, not guaranteed installed in Hermes. QA dependencies are broader so all marked examples can run:

```bash
python -m pip install -r requirements-qa.txt
python -m pip install 'torch>=2.5,<3' --index-url https://download.pytorch.org/whl/cpu
python scripts/qa.py
python -m pytest -q tests
python scripts/verify_external_apis.py
git diff --check
```

QA validates metadata, references, personal-path/known-secret patterns, Python syntax and marked executable fences. Each smoke example runs unchanged in a fresh subprocess. Plot examples accept `PLOT_DIR` (default `~/plots`, explicitly expanded); tests use a temporary directory. Unclassified Python fences are rejected; `fragment:` blocks are syntax-checked but require named inputs and are not executed standalone. `external-test:` blocks run only via the manual external command. It returns 0 on passed configured checks, 1 on code/schema/identity failure, and 2 on transport/authentication/quota unavailability; optional unconfigured services remain SKIP.

Pinned Hermes authoring tests are reused without changing their per-skill rules. Upstream whole-distribution population checks do not apply to this tap; our harness checks thirteen skills and resolves references against the pinned bundled/optional catalog. This is not a complete Hermes installation test. CI uses network only to install dependencies; ordinary PR tests do not call scholarly APIs.

CI runs the full QA suite across Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 preview canary (ubuntu-26.04 & ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest), and macOS Intel (macos-15-intel), with live upstream canary validation. The final candidate passed 974 local tests with zero skips; exact-head remote results are recorded separately in the closeout ledger. A separate tap integration workflow runs on pushes to main: it installs the pinned Hermes checkout recorded in tests/upstream/provenance.json and exercises tap add, search, install and list against this repository. Exact versions, checks and limitations are in [the audit](docs/project-lineage-audit-20260920.md).

[tools/longtail/](tools/longtail/README.md) holds the deterministic long-tail factor generator: 4096 SHA256-seeded candidates, 30 selected scenarios and a machine-computed coverage report. The v3 model separately counts capability families (E01), the 13 actual repository skills (E02), and task goals (E03). Each scenario has one primary skill, a supported task goal and compatible capabilities; every skill must appear at least twice under two distinct goals, including its declared core goal. Skill-directory drift fails validation. Semantic expansion (task chains, oracles and executed event injection) remains a separate stage; factor coverage does not prove workflow execution coverage.

scripts/scfabric/ is the scientific compute fabric: hardware probe, backend catalog with dtype gates, five workload profiles, paired benchmark with parity admission, and ComputeReceipt. First-round measurements on this machine are in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); the rule of thumb is CPU by default, accelerator only with a receipt.

## Research and planning documents

These two documents are exploratory planning references, not a binding roadmap. Their direction numbers are recomputed from the stored grouping in docs/direction-primitive-mapping.json.

- [Pain Atlas v0 (English)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): friction points across the academic knowledge-work life cycle, with verification states attached to quantitative claims.
- [Research Plan v0 (English)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): the Research Object model, core capability areas, candidate directions and the phase-one factor decomposition matrix.

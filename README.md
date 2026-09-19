# academic-research-kernel

English · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Deutsch](README.de.md) · [Français](README.fr.md) · [Español](README.es.md)

Harness-neutral academic research core and multi-agent deliberation suite. It provides 13 academic skills and verification tools with portable Agent Plugins v1 and MCP (Model Context Protocol) entrypoints, as well as native integration for Hermes Agent, Claude Code, Cursor, and custom CLI subagents. They cover source verification, literature analysis, academic writing, numerical computation, quantitative paper audit, reproduction audits, systematic review and meta-analysis, research-object identity and lineage, dynamic cross-model review orchestration, plus two weekly monitoring automations. The repository includes executable example checks; validation scope and external-service limitations are recorded in [the audit](docs/audit-20260906.md).

Author: Junfu Shi (SJF, xngg1021), Hermes Agent. Current scoped offer: [Source Lineage License 1.0](LICENSE).

## License

The snapshot containing this notice adopts **Source Lineage License 1.0** for the Covered Material and rights identified in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). The first SLL commit and tree, and the later boundary-recording commit, are distinguished in [LICENSE-HISTORY.md](LICENSE-HISTORY.md) and [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Snapshots from that recorded transition forward retaining this notice carry the same scoped offer.

Historical snapshots through `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` were MIT-licensed, subject to the terms applicable to those copies. Recipients retain valid MIT permissions and need not migrate to SLL. The [former project MIT text](LICENSES/MIT-pre-SLL.txt) is preserved; [tests/upstream/LICENSE](tests/upstream/LICENSE) and its third-party provenance remain unchanged. The new root offer does not erase those rights.

SLL broadly permits use, study, modification, commercial use, distribution and proprietary additions, subject to applicable license, notice and source-lineage conditions. It is not copyleft and requires no source disclosure. Pure network service without supplying copies does not by itself trigger the Core service-lineage notice condition. There is no express patent grant. Third-party material remains under its own terms. The exact English [LICENSE](LICENSE) controls this informational summary; `LicenseRef-Source-Lineage-1.0` is a local reference, not SPDX assignment, and no OSI approval is claimed. [Contribution intake](CONTRIBUTING.md) is separate from downstream license permissions.

## Skills

| Skill | Version | What it does |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.2.0 | Cross-check identity and source-specific citation counts; inspect update/retraction signals; locate OA text and verify PDF identity |
| `skills/literature-analysis` | 1.3.0 | Twelve workflows: topic similarity, local text overlap, counter-evidence, author profiles, mock review, fallacy checks, review matrix, journal candidates, BibTeX, bilingual reading, research-gap screening, reproduction |
| `skills/academic-writing` | 1.1.1 | Editing, citation guidance (APA, MLA, Chicago, IEEE, AMA, GB/T), journal instructions, optional detection services, submission materials, Chinese academic requirements |
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

## Integration & Portable Usage

### 1. Universal Agent Plugins v1 & Model Context Protocol (MCP)
This repository conforms to the vendor-neutral **Agent Plugins v1** specification (`plugin.json`) and exposes core academic verification and statistical recompute tools via a stdio **MCP server** (`mcp.json` / `scripts/mcp_server.py`). Compatible with Claude Code, Cursor, Gemini CLI, and any modern agent framework. (Note: While the repository identity is `academic-research-kernel`, the plugin manifest name `academic-skills` and MCP configuration aliases remain stable for backward compatibility.)

```bash
# Add as stdio MCP server in your agent harness
python scripts/mcp_server.py
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

CI runs the full QA suite across Linux x86_64 (Python 3.10-3.14), Linux ARM64 (ubuntu-24.04-arm), Ubuntu 26.04 preview canary (ubuntu-26.04 & ubuntu-26.04-arm), Windows x86_64, Windows ARM64 (windows-11-arm), macOS ARM64 (macos-latest), and macOS Intel (macos-15-intel), with 625 passed unit tests and live upstream canary validation. A separate tap integration workflow runs on pushes to main: it installs the pinned Hermes checkout recorded in tests/upstream/provenance.json and exercises tap add, search, install and list against this repository. Exact versions, checks and limitations are in [the audit](docs/audit-20260906.md).

tools/longtail/ holds the deterministic extreme long-tail scenario generator: 4096 SHA256-seeded candidate combinations over the decoupled factor axes, greedy coverage selection, and the machine-computed coverage report in generated-scenarios.json. It is the input layer for stress-testing the skills; semantic expansion (task chains, oracles, injected events) is a separate stage.

scripts/scfabric/ is the scientific compute fabric: hardware probe, backend catalog with dtype gates, five workload profiles, paired benchmark with parity admission, and ComputeReceipt. First-round measurements on this machine are in [docs/scientific-compute-fabric.md](docs/scientific-compute-fabric.md); the rule of thumb is CPU by default, accelerator only with a receipt.

## Research and planning documents

These two documents are exploratory planning references, not a binding roadmap. Their direction numbers are recomputed from the stored grouping in docs/direction-primitive-mapping.json.

- [Pain Atlas v0 (English)](docs/pain-atlas-v0.en.md), [中文版](docs/pain-atlas-v0.zh.md): friction points across the academic knowledge-work life cycle, with verification states attached to quantitative claims.
- [Research Plan v0 (English)](docs/research-plan-v0.en.md), [中文版](docs/research-plan-v0.zh.md): the Research Object model, core capability areas, candidate directions and the phase-one factor decomposition matrix.

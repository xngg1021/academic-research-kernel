# hermes-academic-skills

Nine Chinese-language academic skills for Hermes Agent. They cover source verification, literature analysis, academic writing, numerical computation, quantitative paper audit, reproduction audits, systematic review and meta-analysis, plus two weekly monitoring automations. The repository includes executable example checks; validation scope and external-service limitations are recorded in [the audit](docs/audit-20260906.md).

Author: Junfu Shi (SJF, xngg1021), Hermes Agent. Current scoped offer: [Source Lineage License 1.0](LICENSE).

## License

The snapshot containing this notice adopts **Source Lineage License 1.0** for the Covered Material and rights identified in [LICENSE-APPLICATION.md](LICENSE-APPLICATION.md). The first SLL commit and tree, and the later boundary-recording commit, are distinguished in [LICENSE-HISTORY.md](LICENSE-HISTORY.md) and [SOURCE-LINEAGE.md](SOURCE-LINEAGE.md). Snapshots from that recorded transition forward retaining this notice carry the same scoped offer.

Historical snapshots through `439ce4a29d6d2d9137308d7f9f045863e9f0c5b3` were MIT-licensed, subject to the terms applicable to those copies. Recipients retain valid MIT permissions and need not migrate to SLL. The [former project MIT text](LICENSES/MIT-pre-SLL.txt) is preserved; [tests/upstream/LICENSE](tests/upstream/LICENSE) and its third-party provenance remain unchanged. The new root offer does not erase those rights.

SLL broadly permits use, study, modification, commercial use, distribution and proprietary additions, subject to applicable license, notice and source-lineage conditions. It is not copyleft and requires no source disclosure. Pure network service without supplying copies does not by itself trigger the Core service-lineage notice condition. There is no express patent grant. Third-party material remains under its own terms. The exact English [LICENSE](LICENSE) controls this informational summary; `LicenseRef-Source-Lineage-1.0` is a local reference, not SPDX assignment, and no OSI approval is claimed. [Contribution intake](CONTRIBUTING.md) is separate from downstream license permissions.

## Skills

| Skill | Version | What it does |
| --- | --- | --- |
| `skills/academic-source-verification` | 1.1.1 | Cross-check identity and source-specific citation counts; inspect update/retraction signals; locate OA text and verify PDF identity |
| `skills/literature-analysis` | 1.2.0 | Twelve workflows: topic similarity, local text overlap, counter-evidence, author profiles, mock review, fallacy checks, review matrix, journal candidates, BibTeX, bilingual reading, research-gap screening, reproduction |
| `skills/academic-writing` | 1.1.1 | Editing, citation guidance (APA, MLA, Chicago, IEEE, AMA, GB/T), journal instructions, optional detection services, submission materials, Chinese academic requirements |
| `skills/math-computation` | 1.2.1 | Existing domain/task routing with corrected numerical/statistical examples; four domain/advanced reference files |
| `skills/quantitative-paper-audit` | 1.0.0 | Recompute reported statistics (effect size, p values, CIs, OR/RR, achieved power) and detect numerical mismatches |
| `skills/research-reproducibility` | 1.0.0 | Fourteen-stage reproduction audit pipeline with a structured checklist engine, five fact tiers and a four-state receipt |
| `skills/systematic-review-meta-analysis` | 1.0.0 | PRISMA search logs, screening ledgers, effect-size conversion, heterogeneity, fixed/random pooling, sensitivity and publication-bias diagnostics |
| `skills/literature-watch` | 1.0.0 | Weekly blueprint: watch topics, authors and DOI citing works on OpenAlex and Crossref; deduplicate and report only new items |
| `skills/retraction-watch` | 1.0.0 | Weekly blueprint: recheck a DOI watchlist against OpenAlex is_retracted and Crossref relations; report only status changes |

There are 21 Markdown reference files across the nine skills. References load only when needed. GB/T 7714-2025 is now in force; the writing reference distinguishes its verified effective date from explicitly labelled 2015 examples. Full 2025 compliance requires the target institution's template or standard text.

## Install in Hermes

Current upstream tap discovery inspects immediate child directories under `skills/`. Each skill therefore lives directly under that root. From a Hermes installation:

```bash
hermes skills tap add xngg1021/hermes-academic-skills
hermes skills search academic-source-verification
hermes skills install xngg1021/hermes-academic-skills/skills/academic-source-verification
```

Install the other three by substituting their directory name in the full identifier. A normal tap reads the default branch; these changes become its default only after this PR is merged. To inspect a work branch before merge, check out that branch locally and follow the installed Hermes version's local-folder installation instructions. Do not assume the tap command selects a PR branch.

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

Pinned Hermes authoring tests are reused without changing their per-skill rules. Upstream whole-distribution population checks do not apply to this tap; our harness checks nine skills and resolves references against the pinned bundled/optional catalog. This is not a complete Hermes installation test. CI uses network only to install dependencies; ordinary PR tests do not call scholarly APIs.

Linux/Python 3.12 is tested in this pass. Linux, macOS and Windows remain intended platforms; native Windows/macOS execution, every dependency-version combination, and a fresh Hermes session are not claimed. Exact versions, checks and limitations are in [the audit](docs/audit-20260906.md).

# Project Lineage, PR/CI, and Residual-Risk Audit — 2026-09-20

## Scope and evidence boundary

This audit covers the canonical repository `xngg1021/academic-research-kernel` from PR #1 through the open PR #12. It cross-checks GitHub PR metadata, each PR head SHA, the `Skill correctness QA` workflow run attached to that exact head, job conclusions, open standalone issues, PR #12 review threads, the project-planning records, and the repository's executable tests and QA gates.

The GitHub snapshot was taken on 2026-09-20 UTC. “Successful CI” below means the workflow run attached to the listed head concluded `success`; an intentionally condition-false job is reported separately as `skipped` and is never counted as a pass. Local verification after the remediation work is recorded in the final section.

## Executive result

- PR history: **12 total; 11 merged; PR #12 open**.
- Exact-head CI history at audit start: **12/12 workflow runs successful; 0 failed or cancelled runs**.
- Standalone GitHub issues: **0 open, 0 closed**. Review findings are therefore accounted for from PR threads and repository audit records rather than an issue tracker.
- PR #12 review debt at audit start: **31 unresolved threads** — **30 P1 and 1 P2**; 12 threads were already outdated by intervening edits and 19 were on current lines. The first remediation implemented and closed all 31. Reviews of heads `24469778b15b`, `5e9a802c1bbd`, `9bb8726b5b0e`, `73f57fdc64c7`, and `d388fa11fefe` then opened **7 P1**, **6 P1 + 1 P2**, **5 P1 + 3 P2**, **5 P1**, and **8 P1 + 1 P2** findings respectively. All five follow-up sets are implemented with regression coverage; the newest set remains gated on the next exact-head matrix and review.
- Verified remediation checkpoints: heads `24469778b15b`, `5e9a802c1bbd`, `9bb8726b5b0e`, `73f57fdc64c7`, and `d388fa11fefe` passed runs [35494388854](https://github.com/xngg1021/academic-research-kernel/actions/runs/35494388854), [35495732974](https://github.com/xngg1021/academic-research-kernel/actions/runs/35495732974), [35496991058](https://github.com/xngg1021/academic-research-kernel/actions/runs/35496991058), [35497895958](https://github.com/xngg1021/academic-research-kernel/actions/runs/35497895958), and [35498961191](https://github.com/xngg1021/academic-research-kernel/actions/runs/35498961191). Each had upstream canary plus all 12 platform jobs successful; `tap-lifecycle` was condition-false and skipped as designed.
- Historical 2026-09-06 correctness audit: **34/34 grouped findings resolved** (`P0=0`, `P1=22`, `P2=12`), with resolution evidence retained in `docs/findings.json` and executable regression suites.
- Current implementation gate after remediation: **720 passed, 3 intentionally skipped**. Before this pass the actual baseline was 663 passed and 3 skipped; the earlier “666 passed” wording conflated collected tests with passed tests and has been corrected.
- Open code defects found at P0/P1: **0 locally reproduced after the latest follow-up remediation**, subject to the new PR-head remote matrix and review gate. Remaining items are explicit operational, governance, distribution, localization, or experimental-scope limitations listed below.

## Complete PR and exact-head CI ledger

| PR | Scope | Status | Audited head | Commits | Exact-head QA run | Jobs |
| ---: | --- | --- | --- | ---: | --- | --- |
| [#1](https://github.com/xngg1021/academic-research-kernel/pull/1) | Correctness, portability, current APIs | merged | `447f88c22630` | 5 | [34011128209](https://github.com/xngg1021/academic-research-kernel/actions/runs/34011128209): success | 1/1 `offline` success |
| [#2](https://github.com/xngg1021/academic-research-kernel/pull/2) | SLL 1.0 licensing transition | merged | `0f63f115a468` | 2 | [34901160163](https://github.com/xngg1021/academic-research-kernel/actions/runs/34901160163): success | 1/1 `offline` success |
| [#3](https://github.com/xngg1021/academic-research-kernel/pull/3) | Execution/evidence hardening and five skills | merged | `69e58ad09d3d` | 5 | [35117139533](https://github.com/xngg1021/academic-research-kernel/actions/runs/35117139533): success | 1/1 `offline` success |
| [#4](https://github.com/xngg1021/academic-research-kernel/pull/4) | Sparse Deliberation v2 and compute hardening | merged | `ee223b9b02dc` | 17 | [35248822907](https://github.com/xngg1021/academic-research-kernel/actions/runs/35248822907): success | 6 platform checks success; tap skipped |
| [#5](https://github.com/xngg1021/academic-research-kernel/pull/5) | Statistical/reference/i18n hardening | merged | `ca2e9d2d75f4` | 12 | [35274317969](https://github.com/xngg1021/academic-research-kernel/actions/runs/35274317969): success | upstream canary + 10 platform checks success; tap skipped |
| [#6](https://github.com/xngg1021/academic-research-kernel/pull/6) | Research-object provenance kernel | merged | `6470af3d2666` | 4 | [35346581800](https://github.com/xngg1021/academic-research-kernel/actions/runs/35346581800): success | upstream canary + 10 platform checks success; tap skipped |
| [#7](https://github.com/xngg1021/academic-research-kernel/pull/7) | Repository identity migration | merged | `c3a960f38868` | 1 | [35347905575](https://github.com/xngg1021/academic-research-kernel/actions/runs/35347905575): success | upstream canary + 10 platform checks success; tap skipped |
| [#8](https://github.com/xngg1021/academic-research-kernel/pull/8) | Identity closeout and roadmap re-evaluation | merged | `daa6d4c55d78` | 1 | [35351378790](https://github.com/xngg1021/academic-research-kernel/actions/runs/35351378790): success | upstream canary + 10 platform checks success; tap skipped |
| [#9](https://github.com/xngg1021/academic-research-kernel/pull/9) | Claim-Evidence Graph v1 | merged | `3cde7e018e63` | 4 | [35359362517](https://github.com/xngg1021/academic-research-kernel/actions/runs/35359362517): success | upstream canary + 10 platform checks success; tap skipped |
| [#10](https://github.com/xngg1021/academic-research-kernel/pull/10) | Node 24, Ubuntu 26, locator determinism | merged | `689b076c036c` | 2 | [35366683037](https://github.com/xngg1021/academic-research-kernel/actions/runs/35366683037): success | upstream canary + 12 platform checks success; tap skipped |
| [#11](https://github.com/xngg1021/academic-research-kernel/pull/11) | Research Decision Log v1 | merged | `4a7e8738d23c` | 16 | [35448287394](https://github.com/xngg1021/academic-research-kernel/actions/runs/35448287394): success | upstream canary + 12 platform checks success; tap skipped |
| [#12](https://github.com/xngg1021/academic-research-kernel/pull/12) | Artifact Ingestion Bridge v1 | open | `51c288144298` (pre-remediation snapshot) | 2 | [35488732107](https://github.com/xngg1021/academic-research-kernel/actions/runs/35488732107): success | upstream canary + 12 platform checks success; tap skipped |

Remediation checkpoints `24469778b15b`, `5e9a802c1bbd`, `9bb8726b5b0e`, `73f57fdc64c7`, and `d388fa11fefe` are exact-head verified by runs `35494388854`, `35495732974`, `35496991058`, `35497895958`, and `35498961191` (13 successful jobs each, `tap-lifecycle` skipped). The next commit containing the nine sixth-review fixes must pass its own matrix before merge.

### CI interpretation

PRs #1–#3 predate the platform matrix and only ran the then-current `offline` job. PR #4 introduced a six-platform matrix. PRs #5–#9 added the upstream canary and a ten-platform/architecture matrix. PRs #10–#12 expanded it to twelve platform checks, including Ubuntu 26.04 x86_64/ARM64 canaries.

The `tap-lifecycle` job is gated to `workflow_dispatch` or a push to `main`, so it is expected to show `skipped` on pull requests. This preserves a real integration check against the repository after merge, but it leaves PR heads without that one remote installation path. The PR suite still exercises local discovery, upstream canary loading, and a real stdio MCP initialize/list/call exchange.

## PR #12 remediation ledger

The 31 review findings were not treated as independent one-line patches. They were closed through seven invariant groups so the same failure class cannot reappear through another adapter or surface.

| Invariant group | Covered findings | Construction result |
| --- | ---: | --- |
| Trust-boundary integrity | 1, 2, 22, 25 | Envelope IDs/hashes, evidence enums, declared CEG digests, lineage receipt digests, and Draft 2020-12 payload schemas are verified at runtime. Unknown fields, producer-major drift, oversize/deep payloads, and tampered snapshots fail closed. |
| Transactionality and idempotency | 5, 6, 8, 9, 24 | Cache identity includes every mutation-affecting envelope field and caller binding; it is state-scoped, staged until commit, preserves original binding indexes, rejects conflicting object IDs, and rolls back the entire atomic batch. |
| Lossless state replay | 4, 7, 11, 13, 20, 21, 23 | CEG, ledger, receipt registries, evidence checksum/excerpt, claim relations, and canonical lineage edge types round-trip through strict loaders. Complete kernel snapshots carry a tamper-evident digest. |
| Public MCP correctness | 3, 12, 17, 20, 21, 25 | MCP initializes usable CEG/Ledger primitives, validates tool arguments, uses implemented trace APIs, returns structured `isError`, preserves full state, and is covered through a real stdio subprocess exchange. |
| Producer/adapter contract fidelity | 10, 14, 15, 18, 26, 27 | Actual reproduction `status`, canonical research-object fields, cross-review registries, lineage bindings, screening-only matrices, and citation-only deltas are accepted and preserved. |
| Evidence epistemics | 19, 28, 29, 30 | Dangling support edges are rejected; missing math/quantitative verdicts become `unverifiable` uncertainties rather than contradiction/support; uncertainty state contributes to the receipt-attested kernel digest. |
| Audit context | 31 | Caller metadata is preserved on receipts while intentionally excluded from content-addressed receipt identity. |

Additional P1 defects outside the 31 review threads were found during implementation and fixed: `LineageReceipt` nested dictionaries were reachable despite a frozen dataclass; receipt validation did not recompute declared lineage/receipt digests; a global “producer major 1” rule rejected the real `cross-review-five` 2.x producer; the quantitative schema rejected several real recomputation result shapes and treated `consistent: null` as contradiction; direct `CanonicalWork.to_dict()` output and meta-analysis-only artifacts were rejected; and an empty-but-valid cross-review registry could be acknowledged without preservation. CEG and ledger frozen mappings now also resist direct backing-map mutation and non-JSON values.

The seven follow-up P1 findings are also closed in code: academic-evidence CEG IDs bind the target work; MCP artifact validation accepts the physical receipt context needed by receipt-backed snapshots; screening decisions cannot overwrite included-study objects; caller metadata is excluded from mutation cache identity while remaining on each returned receipt; ledger bindings expose the real content-addressed correction ID; producer-generated `missing_input` lineage receipts verify consistently; and timestamp-only lineage receipt emissions share one registry identity.

The next review produced six P1 findings and one P2 finding, all now closed in code: retrieval-specific query/identifier metadata no longer mutates stable work objects; claim identity binds the effective locator while evidence identity additionally binds the physical receipt; screening results prefer unique `record_id` over shared `study_id`; retained-prior retraction state becomes an explicit uncertainty rather than a false current negative; artifact preflight recomputes lineage receipt identities; MCP lineage activities require caller-supplied timestamps; and Decision Ledger snapshots replay against exactly their declared verification manifest before unrelated kernel receipts are synchronized.

The subsequent review produced five P1 findings and three P2 findings, all now closed in code: lineage anchors bind their effective locator; publication-status observations bind their resolved work; CEG validation reports integrity failures as validation results; claim traces expose supporting and refuting anchors in addition to lineage receipts; truncated retraction checks become coverage uncertainties; screening decisions use a closed vocabulary; incremental CEG/Ledger mutations persist the same derived uncertainties as snapshot replay; and adapter-generated identities use 128-bit widths. The implementation also reuses richer pre-existing work objects and applies the same context/width invariant to adjacent reproduction, review, literature, meta-analysis, and math adapters.

The fifth review produced five P1 findings, all now closed locally with focused regressions: resolved CEG/Ledger uncertainties are removed from the kernel queue; included-study extraction objects and adjacent screening decisions are scoped to their review artifact; successful receipt verification no longer carries an `error` key or MCP `isError`; adapters reject unknown or ineffective binding fields before deriving mutation cache keys; and support versus contradiction receipts for the same proposition converge on one semantic CEG claim while retaining distinct evidence anchors.

The sixth review produced eight P1 findings and one P2 finding, all now closed locally with focused regressions: accepted cache receipts are bound to and validated against their full ingestion context; envelope lineage references are preserved, verified against physical receipts, and represented as resolvable uncertainty when absent; physical receipts are deeply immutable; CEG snapshots replay against their declared receipt availability before synchronization; only kernel-owned derived uncertainties are removed; screening decisions are scoped to the review instance; blank academic claims fail closed; wrapped canonical works use the complete runtime schema; and a confirmed retraction under truncated coverage retains both the alert and the coverage uncertainty.

## Project-planning audit

The 2026-09-17 agenda audit's principal factual defect is closed: the invalid, unreproducible `146/138/136` direction counts were voided; `direction-primitive-mapping.json` now records the grouping; and `../scripts/recompute_direction_coverage.py` reproduces all 235 rows under single/core/baseline sensitivity runs. The leverage table was downgraded from a gate to a documented judgment, and the README labels the planning documents exploratory rather than binding.

This audit reran the calculation and reproduced:

| Direction | single | core | baseline |
| --- | ---: | ---: | ---: |
| Research Object Identity and Lineage | 34 | 64 | 88 |
| Method / Supplement Miner | 30 | 59 | 85 |
| Decision / Negative Result Ledger | 36 | 36 | 63 |
| Claim-Evidence Graph | 15 | 47 | 58 |
| Constraint Compiler | 18 | 18 | 49 |
| Learning Error + Adaptive Practice | 20 | 20 | 29 |

The remaining planning limitations are recorded below; they are not silently represented as completed work.

## Open P0–P3 and historical-residual register

| ID | Severity | Type | Status | Residual / next gate |
| --- | --- | --- | --- | --- |
| OPEN-P0 | P0 | Code/security/data loss | none open | No P0 was found in the current audit. |
| OPEN-P1 | P1 | Code correctness | none locally reproduced after latest follow-up remediation | Closure still depends on the updated PR-head remote matrix and review gate; a regression reopens this row. |
| OPS-01 | P2 | CI coverage | accepted operational limitation | `tap-lifecycle` cannot test an unmerged PR head through the pinned remote tap. It runs on `main`; local discovery, upstream canary, and stdio MCP tests cover the PR path. |
| EXT-01 | P2 | External verification | open/credential-bound | Live OpenAlex/Crossref/Unpaywall and hardware-specific accelerator claims were not re-executed in this offline correctness pass. No absence or success is inferred from an unavailable credential/service. |
| GOV-01 | P2 | Historical provenance | grandfathered, cannot be reconstructed honestly | The original 235 pain-atlas entries lack per-item source-model and cross-confirmation provenance. New entries must record both; old entries remain explicitly marked as missing rather than backfilled speculatively. |
| DIST-01 | P3 | Distribution | planned | PyPI/`uvx`, console packaging, and official MCP Registry publication remain the explicitly scoped PR #13 deliverable. |
| I18N-01 | P3 | Localization | queued | With this audit added, 55 canonical documents are tracked; 22 localized instances are current and 1,078 are explicitly queued. No queued item is reported as translated. |
| GOV-02 | P3 | Independent agenda validation | open | The requested re-run under an independently defined alternative primitive framework has not been completed. Current rankings are sensitivity-tested only inside the stored fourteen-primitive model. |
| GOV-03 | P3 | Portfolio maintenance | open | `systematic-review-meta-analysis` and `research-reproducibility` have not yet undergone the requested usage-based retain/retire review. |
| SCF-01 | P3 | Experimental compute scope | open | Scientific Compute Fabric remains a standalone measured layer: GPU is absent from CI, five workloads/three scales are covered, and it is not yet wired into `math-computation` routing. |
| ROADMAP-01 | P3 | Product direction | deliberately deferred | Method/Supplement Miner versus Constraint Compiler remains an explicit post-PR #13 decision, not an implied commitment. |

## Verification performed for this remediation

- `python3 -m pytest -q`: **720 passed, 3 skipped**.
- `python3 ../scripts/recompute_direction_coverage.py` (from `docs/`): all 235 pain items reproduced with the documented rankings.
- `python3 scripts/qa.py`: repository static and executable-fence gate.
- `python3 scripts/i18n_sync.py --check`: manifest/hash/status consistency gate.
- `git diff --check`: whitespace and patch-integrity gate.

The final three results are rerun after documentation and manifest updates; the pull request's updated remote matrix remains the authoritative cross-platform merge gate.

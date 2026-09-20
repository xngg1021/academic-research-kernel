# Project Lineage, PR/CI, and Residual-Risk Audit — 2026-09-20

## Scope and evidence boundary

This audit covers the canonical repository `xngg1021/academic-research-kernel` from PR #1 through the PR #12 final candidate. PR #1–#11 evidence below is historical and unchanged. The containing commit is the source candidate; its exact SHA/tree and subsequent remote/merge results are bound by the [closeout evidence annex](https://github.com/xngg1021/academic-research-kernel/pull/12#issuecomment-5750357151). This avoids embedding a commit hash in the very commit it identifies. It cross-checks GitHub PR metadata, each PR head SHA, the `Skill correctness QA` workflow run attached to that exact head, job conclusions, open standalone issues, PR #12 review threads, the project-planning records, and the repository's executable tests and QA gates.

The GitHub snapshot was taken on 2026-09-20 UTC. “Successful CI” below means the workflow run attached to the listed head concluded `success`; an intentionally condition-false job is reported separately as `skipped` and is never counted as a pass. Local verification after the remediation work is recorded in the final section.

## Executive result

- PR history: **12 total; 11 merged; PR #12 open**.
- Exact-head CI history at audit start: **12/12 workflow runs successful; 0 failed or cancelled runs**.
- Standalone GitHub issues: **0 open, 0 closed**. Review findings are therefore accounted for from PR threads and repository audit records rather than an issue tracker.
- PR #12 review debt at audit start: **31 unresolved threads** — **30 P1 and 1 P2**; 12 threads were already outdated by intervening edits and 19 were on current lines. The first remediation implemented and closed all 31. Reviews of heads `24469778b15b`, `5e9a802c1bbd`, `9bb8726b5b0e`, `73f57fdc64c7`, `d388fa11fefe`, `8af81dd29ce1`, `21fa30065f92`, `659fa48466fe`, `6b4265036dd9`, `2f322d96a8e4`, `6228fb5ad48c`, and `1a8ad3ac3094` then opened **7 P1**, **6 P1 + 1 P2**, **5 P1 + 3 P2**, **5 P1**, **8 P1 + 1 P2**, **5 P1 + 3 P2**, **4 P1 + 4 P2**, **2 P1 + 2 P2**, **4 P1 + 1 P2**, **4 P1**, **6 P1**, and **4 P1 + 3 P2** findings respectively. Those twelve historical follow-up sets were implemented with regression coverage. The next exact-head review of `f4709c9d597e` reopened **6 P1 + 2 P2**. At final-wave intake, **117 threads** were observed (**31 resolved, 86 unresolved**); this is an intake snapshot, not the final live-thread count. The eight latest findings and sibling defects are addressed by the candidate below. Final thread dispositions and review census are recorded in the evidence annex after exact-head validation.
- Verified remediation checkpoints: heads `24469778b15b`, `5e9a802c1bbd`, `9bb8726b5b0e`, `73f57fdc64c7`, `d388fa11fefe`, `8af81dd29ce1`, `21fa30065f92`, `659fa48466fe`, `6b4265036dd9`, `2f322d96a8e4`, and `1a8ad3ac3094` passed runs [35494388854](https://github.com/xngg1021/academic-research-kernel/actions/runs/35494388854), [35495732974](https://github.com/xngg1021/academic-research-kernel/actions/runs/35495732974), [35496991058](https://github.com/xngg1021/academic-research-kernel/actions/runs/35496991058), [35497895958](https://github.com/xngg1021/academic-research-kernel/actions/runs/35497895958), [35498961191](https://github.com/xngg1021/academic-research-kernel/actions/runs/35498961191), [35500414450](https://github.com/xngg1021/academic-research-kernel/actions/runs/35500414450), [35501417685](https://github.com/xngg1021/academic-research-kernel/actions/runs/35501417685), [35503474068](https://github.com/xngg1021/academic-research-kernel/actions/runs/35503474068), [35503922950](https://github.com/xngg1021/academic-research-kernel/actions/runs/35503922950), [35504757502](https://github.com/xngg1021/academic-research-kernel/actions/runs/35504757502), and [35507956889](https://github.com/xngg1021/academic-research-kernel/actions/runs/35507956889). Each had upstream canary plus all 12 platform jobs successful; `tap-lifecycle` was condition-false and skipped as designed.
- Historical 2026-09-06 correctness audit: **34/34 grouped findings resolved** (`P0=0`, `P1=22`, `P2=12`), with resolution evidence retained in `docs/findings.json` and executable regression suites.
- Current implementation gate after remediation: **873 passed, zero skipped**. Before this pass the actual baseline was 663 passed and 3 skipped; the earlier “666 passed” wording conflated collected tests with passed tests and has been corrected.
- Candidate code defects at P0/P1/P2: **none reproduced after the consolidated local repair and full suite**. This is local evidence; it does not assert a clean final review before that review occurs. Exact-head CI and the final cumulative review remain mandatory merge gates in the evidence annex. Remaining items are explicit operational, governance, distribution, localization, or experimental-scope limitations listed below.

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

Remediation checkpoints through `1a8ad3ac3094` are exact-head verified by the eleven runs listed above (13 successful jobs each, `tap-lifecycle` skipped). Head `2f322d96a8e4` is a same-tree PR-reference synchronization child of remediation commit `14770943253d`; its exact-head run passed before review surfaced four further P1 findings. Same-tree head `6228fb5ad48c` received an exact-head review with six P1 findings but did not enqueue Actions. Its remediation commit `078bdb27ba20` was synchronized to same-tree head `1a8ad3ac3094`, whose exact-head run passed before the latest review surfaced four P1 and three P2 findings. Those seven historical findings were fixed in `f4709c9d597e4e1a61215530af7bcb85e1dd1d06`. Its run [35510083160](https://github.com/xngg1021/academic-research-kernel/actions/runs/35510083160) completed with 13 successful jobs and the expected tap skip; its actual pytest result was 768 passed. That historical success preceded the latest 6 P1 + 2 P2 review. Run 35510061300 was cancelled and is retained as history, not counted as passing evidence. The new candidate must pass its own matrix and review.

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

The seventh review produced five P1 findings and three P2 findings, all now closed locally with focused regressions: CEG snapshot receipt availability is projected per exact reference rather than per shared subject; MCP preflight enforces the same envelope lineage verification as admission; retained-prior positive retractions preserve both the known alert and the current coverage gap; manuscript objects are scoped to locator/subject context; mathematical evidence anchors retain and bind their effective locator; one explicit outcome-correction binding appends exactly one selected claim correction; conflicting canonical works inside one artifact fail closed; and malformed lineage entities or edges are rejected as MCP argument errors.

The eighth review produced four P1 findings and four P2 findings, all now closed locally with focused regressions: every plan rejects conflicting ResearchObject identities before dictionary overwrite; cross-review evidence is scoped to the full ingestion context and retains its locator; lineage entity and activity types use closed MCP argument enums; untitled review disagreements use canonical JSON reasons; incomplete lineage receipts return normal invalid results; present-but-falsy physical lineage receipts are verified and rejected rather than treated as missing; canonical work metadata deterministically upgrades provisional work placeholders; and opaque fallback objects are scoped to their full envelope context.

The ninth review produced two P1 findings and two P2 findings, all now closed locally with focused regressions: non-string dissenting-opinion reasons use canonical JSON; adapter planning collisions are returned by preflight as ordinary validation errors; manuscript objects always include the full producer context, including producer version; and DOI-only retraction targets use the same normalized canonical-work identity as adjacent ingestion paths.

The tenth review produced four P1 findings and one P2 finding, all now closed locally with focused regressions: cross-artifact object collisions compare canonical JSON bytes rather than Python's bool/int-coercing equality; cached receipts cannot survive after their recorded object, CEG, or Ledger mutations disappear; Ledger verification manifests apply the registry's lineage-timestamp equivalence; academic evidence resolves DOI, arXiv, PMID, and OpenAlex identifiers before query text; and academic receipt verification accepts only the complete canonical evidence-claim digest.

The eleventh review produced four P1 findings, all now closed locally with focused regressions: persisted v1 Decision Ledger snapshots preserve their timestamped lineage-manifest hash mode; ingestion receipts bind every decision, fork, state event, basis, and correction represented by a Ledger snapshot; DOI resolver URLs converge on one canonical work identity across academic evidence, literature analysis, and retraction monitoring; and lineage receipt verification independently replays topology, target closure, roots, trace steps, and coherent verification states instead of trusting re-signed declarations.

The twelfth review produced six P1 findings, all now closed locally with focused regressions: target-scoped closure is verified before any topology status is returned; content-verification claims are replayed against independently observable local bytes and verification mode; cached decision references bind the complete canonical record; legacy timestamped Ledger manifests accept a different but receipt-equivalent lineage emission while preserving the historical wire hash; DOI normalization retains significant trailing suffix punctuation; and per-activity edge memberships plus graph queues are pre-indexed to remove quadratic replay paths.

The thirteenth review produced four P1 findings and three P2 findings, all now closed locally with focused regressions: serialized receipt locators cannot trigger ambient host reads and may consume only caller-authorized, root-contained, size-bounded bytes; in-process relative locators retain their trusted graph-root anchor out of band; producer and verifier use the same canonical structural-failure order; cached CEG support edges and every Ledger mutation record bind their complete canonical digest; duplicate lineage generators return a structured invalid-graph MCP result; and physical lineage entity, activity, and edge records independently enforce the producer's closed type and field contracts.

## Consolidated final-candidate ledger

Closure-candidate parent: `304f016d008f8d526f3eef4f264ddd66885ede12`; base at intake: `ad807295a42ba132a669152dde145f3f530c8fc1`. Same PR #12 and branch `work/research-artifact-ingestion-bridge-v1`; forward-only publication. Final candidate SHA/tree are the containing Git commit and its tree, recorded explicitly in the evidence annex once published.

| Original handoff finding | Severity | Candidate repair and regression |
| --- | --- | --- |
| CEG node/relation content binding | P1 | Full Claim, EvidenceAnchor, SupportEdge and ClaimRelation commitments; same-ID semantic tampering and removals fail replay |
| ResearchObject replacement | P1 | Full object digest; only independently attested minimal-placeholder to canonical-work upgrade is legal |
| Serialized lineage content authority | P1 | Explicit out-of-band context propagates through producer, adapter, CEG, Ledger and kernel replay; wire roots rejected |
| Producer/verifier byte budget mismatch | P1 | Shared bounded algorithm; trusted larger datasets work under an explicit matching policy; untrusted requests stay bounded |
| Uncertainty replacement/removal | P1 | Full adapter record commitments and independently recomputed domain projections; deleted active warning rejected |
| Physical receipt registration omission | P1 | Registry key/payload digest, including zero-claim registration-only ingestion |
| Empty ledger cache rejection | P2 | Container identity binding plus individual records when present; empty/reload/cache/first-append lifecycle passes |
| Malformed MCP registry preflight | P2 | All normalization inside structured validation; scalar/array/null/nested malformed inputs return ordinary invalid results |

`tests/test_ingestion_closeout.py` covers these root-cause families, all ledger record classes, context traversal and wire-budget rejection. Proactive sibling fixes cover producer diagnostics omitted from hashed output, bool/int-coercing uncertainty collision equality, the historical compact academic physical-receipt schema, preflight/apply disagreement, preservation of positional kernel constructor compatibility, and adoption of previously existing records. Existing adversarial, atomic rollback, context-idempotency, lifecycle and schema tests remain enabled.

The complete commitment/authority rules and narrow compatibility exceptions are specified in [kernel architecture](kernel-architecture.md). Snapshot integrity and semantic cache integrity are separate checks. No prose-to-claim inference, automatic truth adjudication, synthetic quality score, or automatic researcher decision was added. All 14 adapters and 12 MCP tools remain. LICENSE/SLL boundary files and PR #1–#11 evidence remain unchanged.

For cost control the final candidate runs the full matrix while Draft via the existing `full-ci` label. Promotion of that already-tested candidate to Ready triggers the single cumulative Codex review without repeating its CI matrix. Normal synchronize events with `full-ci` still run all platform jobs and the upstream canary. The exact successful run, not a skipped promotion workflow, is the required merge evidence. A maximum of one batched repair and closure round is allowed; no third automatic review.

### Final review round 1 and the single closure repair

Candidate `304f016d008f8d526f3eef4f264ddd66885ede12`, tree `22108290a861fbdd41af254e5b8a12df78fcde0b`, passed 819 local tests and exact-head [run 35516780578](https://github.com/xngg1021/academic-research-kernel/actions/runs/35516780578): 13 successful jobs, one expected tap skip, no failed/cancelled jobs. Its [cumulative review 5260863339](https://github.com/xngg1021/academic-research-kernel/pull/12#pullrequestreview-5260863339) returned one P1 and two P2. All three were classified actionable and reproduced; none was dismissed as stylistic or duplicate.

| Round 1 finding | Severity | Closure repair |
| --- | --- | --- |
| Conflicting retraction observations suppress a retained alert | P1 | Schema and runtime require observation agreement; the narrow retained-prior unknown-current exception remains |
| Non-string literature-watch IDs depend on Python representation order | P2 | String-only IDs/registry keys; absent IDs hash canonical JSON, including frozen payloads |
| Duplicate CEG snapshot records silently collapse | P2 | Shared lossless collection validation across CEG, Ledger and kernel uncertainty snapshots |

Sibling audit also repaired duplicate kernel uncertainties and frozen-JSON fallback hashing in monitoring and systematic-review adapters. It verified that canonical metadata distinctions (`1`, `1.0`, `true`) survive legitimate snapshots. `tests/test_ingestion_closure.py` adds 54 focused cases; the closure candidate passes **873 tests, zero skipped**. At closure intake there are **120 threads: 31 already resolved, 89 unresolved** (86 from the first candidate plus these three); final resolved/live counts belong to the evidence annex.

This is the sole permitted repair wave. Its candidate SHA/tree, independent exact-head CI and final closure review are recorded in the annex. A reproducible blocking finding in round 2 stops merge and produces a residual checkpoint; there is no third automatic review. Removing `full-ci` before returning to Draft avoided a duplicate construction matrix; it is added only after the closure candidate passes all local gates.

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

## Code census and accepted historical/operational residuals

Severity labels on external, governance and operational rows describe retained limitations; they are not unresolved reproducible PR #12 code defects. Final code P0/P1/P2 and release-blocking P3 census is recorded after cumulative review in the evidence annex.

| ID | Severity | Type | Status | Residual / next gate |
| --- | --- | --- | --- | --- |
| OPEN-P0 | P0 | Code/security/data loss | none open | No P0 was found in the current audit. |
| OPEN-P1 | P1 | Code correctness | none locally reproduced after latest follow-up remediation | Closure still depends on the updated PR-head remote matrix and review gate; a regression reopens this row. |
| OPEN-P2 | P2 | Code/data contract | none locally reproduced after consolidated repair | Final exact-head review is required; empty ledger and malformed preflight have regression coverage. |
| OPS-01 | P2 | CI coverage | accepted operational limitation | `tap-lifecycle` cannot test an unmerged PR head through the pinned remote tap. It runs on `main`; local discovery, upstream canary, and stdio MCP tests cover the PR path. |
| EXT-01 | P2 | External verification | open/credential-bound | Live OpenAlex/Crossref/Unpaywall and hardware-specific accelerator claims were not re-executed in this offline correctness pass. No absence or success is inferred from an unavailable credential/service. |
| GOV-01 | P2 | Historical provenance | grandfathered, cannot be reconstructed honestly | The original 235 pain-atlas entries lack per-item source-model and cross-confirmation provenance. New entries must record both; old entries remain explicitly marked as missing rather than backfilled speculatively. |
| DIST-01 | P3 | Distribution | planned | PyPI/`uvx`, console packaging, and official MCP Registry publication remain the explicitly scoped PR #13 deliverable. |
| I18N-01 | P3 | Localization | queued | With this audit added, 55 canonical documents are tracked; 3 localized instances are current, 19 README instances are explicitly stale after the current source update, and 1,078 are queued. No stale or queued item is reported as current. |
| GOV-02 | P3 | Independent agenda validation | open | The requested re-run under an independently defined alternative primitive framework has not been completed. Current rankings are sensitivity-tested only inside the stored fourteen-primitive model. |
| GOV-03 | P3 | Portfolio maintenance | open | `systematic-review-meta-analysis` and `research-reproducibility` have not yet undergone the requested usage-based retain/retire review. |
| SCF-01 | P3 | Experimental compute scope | open | Scientific Compute Fabric remains a standalone measured layer: GPU is absent from CI, five workloads/three scales are covered, and it is not yet wired into `math-computation` routing. |
| ROADMAP-01 | P3 | Product direction | deliberately deferred | Method/Supplement Miner versus Constraint Compiler remains an explicit post-PR #13 decision, not an implied commitment. |

## Verification performed for this remediation

- `python -m pytest -q tests`: **873 passed, zero skipped** (CPU PyTorch installed).
- `python3 ../scripts/recompute_direction_coverage.py` (from `docs/`): all 235 pain items reproduced with the documented rankings.
- `python scripts/qa.py`: repository static QA and **40 independent executable fences PASS**.
- `python3 scripts/i18n_sync.py --check`: manifest/hash/status consistency gate.
- `git diff --check`: whitespace and patch-integrity gate.

All local gates are rerun after documentation and manifest updates before publication. The evidence annex records the final candidate SHA, tree, parent, changed-file count and actual gate results, followed by the exact-head remote matrix, review and merge result. No remote success is inferred from this source ledger alone.

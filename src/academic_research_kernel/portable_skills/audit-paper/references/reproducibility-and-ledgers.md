# Reproducibility Adjudication, CEG, and Decision Ledgers

## 1. 14-Stage Reproducibility Adjudication (`repro-checklist`)

Priority order in `academic_research_kernel.repro_checklist`:
1. **`inconsistent`**: Any stage has status `mismatch` (e.g., repository identity does not match paper, or measured metrics contradict claimed direction).
2. **`blocked`**: Any hard stage (`identity`, `code-link`, `repo-identity`, `dependencies`, `build-install`, `smoke-run`) is not `pass` (`missing`, `skipped`, `unknown`, `fail`, or `blocked`). Unchecked hard stages never default to pass.
3. **`reproducible`**: All 14 stages are `pass` (only `dataset`, `model-weights`, or `license` may be `skipped` with `waived: true` and explicit `reason`), and `metric-diff` is `pass`.
4. **`partially-reproducible`**: Hard stages pass, but soft stages or `metric-diff` have remaining gaps.

Independent factual `tier` axis: `no-code-found` -> `environment-broken` -> `runs` -> `direction-reproduced` -> `numbers-reproduced` (or `null` when `identity` is unverified).

## 2. Claim-Evidence Graph (`CEG`) Step-by-Step Workflow

1. **Register claims, supporting/contradicting receipts, and inter-claim relations**:
   ```bash
   academic-research-kernel ledger --db ./state.sqlite3 --action add-claim \
     --claim-id c1 --text "Latency drops by 38.4% at batch size 16." \
     --artifact-id bench_receipt_v1 --locator "Table 2, row 4" --stance supports
   academic-research-kernel ledger --db ./state.sqlite3 --action add-claim \
     --claim-id c2 --text "Latency increases at batch size 16 under tail load." \
     --artifact-id bench_receipt_v2 --locator "Table 3" --stance supports
   # Bidirectional contradicts is allowed; depends_on and refines are strictly acyclic
   academic-research-kernel ledger --db ./state.sqlite3 --action link-claims \
     --claim-id c1 --target-claim-id c2 --relation contradicts
   ```
2. **Validate graph closure and export `ceg.json` (contested/unresolved claims populate `uncertainties`)**:
   ```bash
   academic-research-kernel ledger --db ./state.sqlite3 --action validate-ceg
   academic-research-kernel ledger --db ./state.sqlite3 --action export-ceg --output ./ceg.json
   ```
3. **Bind claims inside LaTeX (`% ark:claim=c1`) and enforce at submission time**:
   ```bash
   academic-research-kernel check-venue --export-ceg-anchors ./ceg.json
   academic-research-kernel lint-submission ./paper/main.tex --ceg ./ceg.json --require-ceg-binding
   ```

## 3. Research Decision & Negative-Result Ledger (`decision-ledger-1.0`)

- **Identifier & lifecycle rules**:
  - `decision_id` matches `^[a-z0-9][a-z0-9._-]{0,63}$`.
  - Lifecycle states are `active`, `pruned` (CLI also accepts `abandoned` / `rejected` as aliases for `pruned`), and `reopened` (`active -> pruned -> reopened -> pruned`).
  - Closed-vocabulary prune `--reason`: `contradicted`, `superseded` (requires `--superseded-by <id>`), `resource_exhausted`, `out_of_scope`, `duplicate`, `external_constraint`, `investigator_error`, `other`.
- **Negative results & independent outcome corrections**:
  - Every `--is-negative-result` requires `--basis-decision-id` pointing to a prior non-negative decision; if recorded without `--artifact-id`, `export-decisions` places an `unsupported_negative_result` entry into `uncertainties` for human review.
  - Use `--action correct-decision --decision-id d0 --verdict negative --rationale "..." --artifact-id ...` to append an outcome correction without mutating lifecycle state.
  - Validate full event-sequence monotonicity, transition legality, supersession acyclicity, and JSON Schema via `ledger --db ./state.sqlite3 --action validate-decisions` or MCP `decision_ledger_validate`.

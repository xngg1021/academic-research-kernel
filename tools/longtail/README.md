# Long-tail factor coverage, v3

This is a deterministic **input model**, not an execution harness or evidence
that a skill's workflows work. Task chains, oracles, acceptance criteria and
actual injected events still need a separate semantic expansion stage.

## Three separate dimensions

- **E01 — capability families:** 16 reusable categories. A task may exercise
  several families, and several skills may share a family.
- **E02 — actual skill under test:** exactly one primary canonical directory
  from `skills/*/SKILL.md`. No secondary skill receives implicit coverage credit.
  Multi-skill interactions are not modeled by padding scenarios with skill names.
- **E03 — concrete task goal:** one of 36 declared goals, chosen only from the
  primary skill's supported goals.

`factor_catalog.json` contains `skill_semantics` for every actual skill: its
source `SKILL.md`, workflow role, capability families, **per-goal capability
allowlist**, relevant event categories and a core `coverage_anchor_goal`.
The generator draws E02 first, E03 from that mapping, and 1–3 distinct E01
families from the chosen goal's allowlist (bounded by the available families).
Each event category also comes from the selected skill's mapping. These are
admission rules for the three task dimensions, not a claim that every remaining
independently sampled persona, object and environment combination is executable.

The source responsibility audit distinguishes literature comparison, counter-
evidence, matrices, bibliography and research gaps (`literature-analysis`) from
stateful new-work monitoring (`literature-watch`). Writing covers editing,
citation styles and submission materials. Computation covers symbolic, numeric
and mathematical verification tasks. Review covers multi-review, challenges and
disagreement reconciliation. CEG covers evidence links and contradiction/lineage
traces; the ledger covers decisions, negative results, explicit prune/reopen
transitions and append-only outcome corrections. These capabilities describe
existing responsibilities; no skill or runtime behavior is added.

## Feasibility and quotas

The seed remains **20260917**, with **4096 candidates** and **30 selected
scenarios**. The candidate supply was measured before setting the new quotas:

- 285–343 candidates per primary skill;
- 3–6 supported goals per skill;
- at least 46 candidates for every supported skill/goal pair;
- with one primary skill per scenario, the maximum uniform quota is
  `floor(30 / 13) = 2`; three appearances each would require 39 slots.

The required representation is therefore **at least two appearances and two
unique task goals for every skill**, including its explicitly declared core
goal. This prevents generic receipt/recovery tasks alone from satisfying skill
coverage. All 16 capability families must appear at least once. Counts are
factor assignments, not successful executions.

The v2 `>=8` pseudo-skill quota actually counted seven E01 families. Its
`>=12 scenarios with 3+ skills` check counted multi-capability combinations.
Neither is a valid quota for the new single-primary-skill model: eight actual
appearances each would require 104 slots. Both are explicitly retired in v3;
`scenarios_with_3plus_capabilities` remains a descriptive counter, not a
multi-skill coverage claim. The v2 tag quotas (language, accessibility, access,
metadata, identifiers, topology, etc.) are unchanged. The 30 object types,
terminal states, critical-tuple uniqueness and five mid-task event markers
remain hard checks. None is relaxed on failure.

The v2 artifact already left four ordinary factor levels uncovered. Its broad
single-select `<=30` level targets remain measured, now separately reported as
`coverage_target_gaps`. They are coverage objectives, distinct from the
catalog's declared hard axes and the quotas above. The report also lists **all**
uncovered levels, including E03's larger-than-30 goal universe. This distinction
is explicit in v3 metadata rather than hiding gaps in a green skill total.
Uncovered levels do not prove infeasibility.

## Selection and reports

Seven deterministic greedy weight sweeps balance level, pair, event and
terminal coverage. Selection reserves remaining slots for primary skill usage,
goal diversity/core goals and hard axes; scarce remaining level opportunities
receive an urgency bonus (`40 / (remaining slots - missing levels + 1)`,
with negative slack clamped to zero). A bounded local comparison of urgency
weights retained the 4096 pool and selected this score with four ordinary factor
gaps; this is observed coverage, not a proof of best attainable coverage. Bit masks implement the same set-coverage arithmetic
without iterating over every factor for each score. Ties use SHA256; equal sweep
scores retain the first sweep. The best sweep minimizes hard problems first,
then ordinary coverage-target gaps. **There is no repair pass or optimality
proof.** If supply or a hard gate fails, generation fails explicitly; quotas are
never reduced automatically.

The v3 report separates `capability_usage_counts`, `skill_usage_counts` and
`task_goal_usage_counts`, each including declared zero-count entries. It also
records all declared levels, uncovered skills/capabilities/goals, per-skill goal
diversity, core goals, candidate supply, each sweep's result and remaining
factor gaps. `event_category_counts` now records actual occurrences rather than
v2's presence-only 0/1 values. `uncovered_required_levels` refers to declared hard
axes; use `coverage_target_gaps` for v2's broader level targets. Consumers must
check `factor_catalog_version` and must not interpret v2 pseudo-skill totals as
actual skill coverage.

## Regeneration and verification

Run from the repository root:

```sh
python tools/longtail/generate.py
python -m pytest -q tests/test_longtail.py tests/test_audit_batch4.py tests/test_audit_batch6.py
```

Use `--output /path/to/scenarios.json` to generate outside the checkout. Tests run
two isolated processes with different Python hash seeds and compare both outputs
byte-for-byte with the committed artifact. Catalog validation compares sorted
live skill-directory names against E02 and the mapping; additions, deletions or
renames fail deterministically. Unsupported skill/capability/goal triples are
checked across the complete candidate pool and selected scenarios.

The artifact is repository validation data. Package versions, public MCP tool
names, kernel contracts, release assets, PyPI and MCP Registry are unchanged.

## Committed seed observation

The committed v3 run covers all 13 skills and all 16 capability families, with
all declared hard quotas satisfied. It leaves 11 of 36 task goals and these
ordinary factor targets uncovered:

- `C10_carrier`: `born_digital_PDF`
- `C21_locator_system`: `legal_neutral_citation`
- `D11_statistical_claim_type`: `hazard_ratio`
- `D11_statistical_claim_type`: `repeated_measures`

The full zero-inclusive counters, per-skill goal lists and remaining task goals
are in `generated-scenarios.json`; no complete-workflow coverage claim follows.

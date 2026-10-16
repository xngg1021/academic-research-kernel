# Long-tail scenario generator, v3

This directory generates deterministic test scenario inputs for the repository's 14 scholarly skills. It is an input generator rather than an execution runner: generating a scenario combination does not by itself run a skill workflow or prove that a full multi-step task succeeded.

## Three separate task dimensions

- `E01_primary_capability` defines 16 reusable capability families. One task can use up to three families, and different skills can share a family.
- `E02_skill_under_test` picks exactly one primary skill from `skills/*/SKILL.md`. Secondary skills receive no implicit coverage credit, and the generator never pads a scenario with extra skill names.
- `E03_task_goal` picks one of 36 concrete task goals supported by the chosen primary skill.

`factor_catalog.json` defines `skill_semantics` for each of the 14 skills: its `SKILL.md` path, role description, supported capability families, allowed capabilities per task goal, event categories, and core `coverage_anchor_goal`. When building a candidate scenario, the generator picks the primary skill (`E02`) first, selects a compatible task goal (`E03`), and then draws one to three capability families (`E01`) allowed for that goal.

Each skill has a distinct scope in the catalog:
- `literature-analysis` covers paper comparison, counter-evidence search, review tables, bibliography export, and research-gap screening, while `literature-watch` handles recurring new-paper alerts.
- `academic-writing` covers manuscript editing, citation formatting, and submission preparation.
- `math-computation` covers symbolic math, numerical calculation, and formula checks.
- `cross-review-five` covers multi-model blind review, cross-challenges, and disagreement tracking.
- `claim-evidence-graph` links claims to evidence passages, while `decision-ledger` records choices, negative results, and abandoned routes.
- `paper-research` covers full-text and supplement reading, statistical recomputation, two-paper comparison, and source-linked reports.

## Quotas and candidate supply

The generator uses seed **20260917** to build **4096 candidate scenarios** and selects **30 scenarios** for the final suite. Before setting quotas, we measured the candidate pool in `generated-scenarios.json`:

- every skill supports between 3 and 6 task goals;
- every valid skill-and-goal pair appears at least 45 times in the 4096-candidate pool;
- with 30 scenarios and 14 skills, the highest uniform floor is `floor(30 / 14) = 2` (requiring 3 appearances per skill would take 42 scenarios).

Every skill must therefore appear **at least twice across at least two distinct task goals**, including its declared core goal, and all 16 capability families must appear at least once.

Earlier v2 counts treated capability families as skills and counted multi-capability scenarios as multi-skill coverage. In v3, `skill_usage_counts` counts actual repository skills (`E02`), while `scenarios_with_3plus_capabilities` is kept only as a descriptive counter. All v2 tag quotas (language, accessibility, offline access, metadata conflicts, non-DOI sources, and non-success terminal states), the 30 object types, critical-tuple uniqueness, and five mid-task event markers remain strict checks.

## Selection algorithm and coverage report

The selector runs seven deterministic greedy passes with different weightings for factor levels, pairs, events, and terminal states. During each pass, it reserves slots for under-used skills, core task goals, and required axes, and adds an urgency bonus (`40 / (remaining slots - missing levels + 1)`, clamped at zero) for scarce remaining levels. Ties break by SHA256, and the pass with the fewest hard-constraint violations and fewest remaining level gaps wins. If any hard quota fails, generation exits with an error rather than lowering the quota.

The output file `generated-scenarios.json` reports `capability_usage_counts`, `skill_usage_counts`, and `task_goal_usage_counts` (including zero counts), along with per-skill goal diversity, candidate supply, sweep scores, `uncovered_required_levels` (hard axes), and `coverage_target_gaps` (broad single-select targets with 30 or fewer levels).

## Regeneration and verification

Run from the repository root:

```sh
python tools/longtail/generate.py
python -m pytest -q tests/test_longtail.py tests/test_audit_batch4.py tests/test_audit_batch6.py
```

Pass `--output /path/to/scenarios.json` to write to a separate path. The test suite runs the generator twice under different `PYTHONHASHSEED` values and verifies that both outputs match `generated-scenarios.json` byte for byte. Adding, removing, or renaming any `skills/*/SKILL.md` directory without updating the catalog fails validation immediately.

## Committed seed coverage

With seed `20260917`, the 30 selected scenarios cover all 14 skills and all 16 capability families, passing every hard quota. Because 30 scenarios cannot cover all 36 task goals or every unconstrained factor level, 12 task goals and 7 observational factor levels remain unselected:

- `A01_role`: `nurse_researcher`
- `A01_role`: `translator`
- `B01_jurisdiction`: `mainland_china`
- `C01_domain`: `law`
- `C06_identifier_topology`: `archival_shelfmark_only`
- `C21_locator_system`: `figure_table`
- `D01_research_design`: `laboratory_experiment`

See `generated-scenarios.json` for the complete counters and per-skill breakdowns.

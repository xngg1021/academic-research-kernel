# -*- coding: utf-8 -*-
"""Deterministic factor-layer scenarios, not executed skill workflows.

E02 selects one primary repository skill; E03 and E01 are derived from its
machine-readable goal/capability mapping. SHA256 counter draws and greedy
weight sweeps remain deterministic. Semantic task chains/oracles are separate.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
SKILLS_ROOT = HERE.parents[1] / "skills"
SEED = 20260917
POOL_SIZE = 4096
SCENARIO_COUNT = 30
CAPABILITY = "E01_primary_capability"
SKILL = "E02_skill_under_test"
GOAL = "E03_task_goal"
TERMINAL = "E04_correct_terminal_state"
SWEEPS = [
    {"level": level, "pair": pair, "event": event, "terminal": terminal}
    for level, pair, event, terminal in [
        (1.0, 3.0, 2.0, 2.0), (4.0, 1.0, 2.0, 2.0),
        (8.0, 1.0, 1.0, 1.0), (12.0, 0.5, 1.0, 1.0),
        (16.0, 0.5, 1.0, 1.0), (24.0, 0.5, 1.0, 1.0),
        (32.0, 0.25, 1.0, 1.0),
    ]
]


def load_catalog():
    return json.loads((HERE / "factor_catalog.json").read_text(encoding="utf-8"))


def discover_skills(skills_root=SKILLS_ROOT):
    return sorted(p.parent.name for p in skills_root.glob("*/SKILL.md"))


def validate_catalog(catalog, skills_root=SKILLS_ROOT):
    """Fail closed on live skill drift or incomplete semantic relationships."""
    axes = catalog["axes"]
    declared = axes[SKILL]["levels"]
    live = discover_skills(skills_root)
    if sorted(declared) != live:
        raise ValueError(f"skill catalog drift: repository={live}, E02={sorted(declared)}")
    semantics = catalog["skill_semantics"]
    if sorted(semantics) != live:
        raise ValueError("skill semantics mapping must exactly match E02")
    if axes[SKILL].get("multi") or axes[GOAL].get("multi"):
        raise ValueError("v3 requires one primary skill and one task goal")
    for axis, spec in axes.items():
        if not spec["levels"] or len(set(spec["levels"])) != len(spec["levels"]):
            raise ValueError(f"empty or duplicate levels: {axis}")
    all_caps, all_goals = set(), set()
    for skill in declared:
        mapping = semantics[skill]
        caps = set(mapping["capability_families"])
        goals = mapping["task_goals"]
        events = mapping["event_categories"]
        if mapping["coverage_anchor_goal"] not in goals:
            raise ValueError(f"unsupported coverage anchor goal: {skill}")
        if mapping["source"] != f"skills/{skill}/SKILL.md" or not mapping["workflow_role"]:
            raise ValueError(f"missing skill source/role: {skill}")
        if not goals or not caps or not caps <= set(axes[CAPABILITY]["levels"]):
            raise ValueError(f"invalid capability mapping: {skill}")
        if not set(goals) <= set(axes[GOAL]["levels"]):
            raise ValueError(f"invalid task goal mapping: {skill}")
        if len(set(events)) < 2 or len(set(events)) != len(events) or not set(events) <= set(catalog["events"]):
            raise ValueError(f"invalid event categories: {skill}")
        used_caps = set()
        for goal, supported in goals.items():
            if not supported or len(set(supported)) != len(supported) or not set(supported) <= caps:
                raise ValueError(f"invalid skill/capability/task mapping: {skill}/{goal}")
            used_caps.update(supported)
        if used_caps != caps:
            raise ValueError(f"unmapped capability: {skill}")
        all_caps.update(caps)
        all_goals.update(goals)
    if all_caps != set(axes[CAPABILITY]["levels"]) or all_goals != set(axes[GOAL]["levels"]):
        raise ValueError("declared capability/task goal has no skill mapping")


def sha_int(seed, candidate_index, axis_id, draw_index):
    raw = f"{seed}|{candidate_index}|{axis_id}|{draw_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest(), "big")


def draw_level(seed, candidate_index, axis_id, n_levels, draw_index=1):
    return sha_int(seed, candidate_index, axis_id, draw_index) % n_levels


def draw_multi(seed, candidate_index, axis_id, n_levels, draw_index=1, min_choice=1, max_choice=3):
    maximum = min(n_levels, max_choice)
    if not 1 <= min_choice <= maximum:
        raise ValueError(f"invalid multi-select bounds: {axis_id}")
    k = sha_int(seed, candidate_index, axis_id, draw_index) % (maximum - min_choice + 1) + min_choice
    picks = []
    for i in range(k):
        v = sha_int(seed, candidate_index, axis_id, draw_index + 10 + i) % n_levels
        while v in picks:
            v = (v + 1) % n_levels
        picks.append(v)
    return picks


def gen_candidates(catalog):
    axes, semantics = catalog["axes"], catalog["skill_semantics"]
    seed = catalog["seed"]
    pool = []
    for ci in range(POOL_SIZE):
        skill = axes[SKILL]["levels"][draw_level(seed, ci, SKILL, len(axes[SKILL]["levels"]))]
        goals = list(semantics[skill]["task_goals"])
        goal = goals[draw_level(seed, ci, GOAL, len(goals))]
        supported = semantics[skill]["task_goals"][goal]
        cap_spec = axes[CAPABILITY]
        idxs = draw_multi(seed, ci, CAPABILITY, len(supported),
                          min_choice=cap_spec["min_choice"], max_choice=cap_spec["max_choice"])
        derived = {SKILL: skill, GOAL: goal, CAPABILITY: [supported[i] for i in idxs]}
        combo = {"_ci": ci}
        for axis, spec in axes.items():
            if axis in derived:
                combo[axis] = derived[axis]
            elif spec.get("multi"):
                combo[axis] = [spec["levels"][i] for i in draw_multi(
                    seed, ci, axis, len(spec["levels"]),
                    min_choice=spec.get("min_choice", 1), max_choice=spec.get("max_choice", 3))]
            else:
                combo[axis] = spec["levels"][draw_level(seed, ci, axis, len(spec["levels"]))]
        pool.append(combo)
    return pool


def admission_problems(catalog, combo):
    skill, goal, caps = combo[SKILL], combo[GOAL], combo[CAPABILITY]
    mapping = catalog["skill_semantics"].get(skill, {})
    allowed = mapping.get("task_goals", {}).get(goal, [])
    spec = catalog["axes"][CAPABILITY]
    if (not isinstance(caps, list) or not caps or len(caps) != len(set(caps))
            or not spec["min_choice"] <= len(caps) <= spec["max_choice"]
            or not set(caps) <= set(allowed)):
        return [f"unsupported skill/capability/task: {skill}/{caps}/{goal}"]
    return []


def values(value):
    return value if isinstance(value, list) else [value]


def combo_tags(catalog, combo):
    tags = Counter()
    for axis, spec in catalog["axes"].items():
        for v in values(combo[axis]):
            tags.update(spec.get("tags", {}).get(v, []))
    return tags


def draw_events_for(catalog, combo):
    """Two distinct categories relevant to the primary skill, not executed events."""
    cats = catalog["skill_semantics"][combo[SKILL]]["event_categories"]
    seed, ci = catalog["seed"], combo["_ci"]
    i1 = sha_int(seed, 0, "event_cat1", ci) % len(cats)
    i2 = sha_int(seed, 0, "event_cat2", ci) % len(cats)
    if i2 == i1:
        i2 = (i2 + 1) % len(cats)
    return [cats[i1], cats[i2]]


def pick_event_id(catalog, cat, ci, slot):
    levels = catalog["events"][cat]
    return levels[sha_int(catalog["seed"], ci, f"event_{cat}", slot) % len(levels)]


def tiebreak(seed, ci):
    return sha_int(seed, ci, "tie", 0)


def has_mid_task(catalog, combo):
    return sha_int(catalog["seed"], combo["_ci"], "mid_task", 1) % 3 == 0


def coverage_state(catalog):
    return {"levels": defaultdict(set), "pairs": defaultdict(set), "events": set(),
            "capabilities": Counter(), "skills": Counter(), "task_goals": Counter(),
            "skill_task_goals": defaultdict(set), "terminals": Counter(), "tags": Counter(),
            "critical_tuples": set()}


def combo_critical_tuple(catalog, combo):
    return tuple("|".join(sorted(combo[ax])) if isinstance(combo[ax], list) else combo[ax]
                 for ax in catalog["critical_tuple"])


def apply_combo(catalog, combo, state):
    for axis in catalog["axes"]:
        state["levels"][axis].update(values(combo[axis]))
    for ax, bx in catalog["pairwise_axes"]:
        state["pairs"][(ax, bx)].update((x, y) for x in values(combo[ax]) for y in values(combo[bx]))
    state["events"].update(draw_events_for(catalog, combo))
    state["capabilities"].update(combo[CAPABILITY])
    state["skills"][combo[SKILL]] += 1
    state["task_goals"][combo[GOAL]] += 1
    state["skill_task_goals"][combo[SKILL]].add(combo[GOAL])
    state["terminals"][combo[TERMINAL]] += 1
    state["tags"].update(combo_tags(catalog, combo))
    state["critical_tuples"].add(combo_critical_tuple(catalog, combo))


def apply_combo_inverse(catalog, combo, state, selected):
    """Recompute remaining contributions: shared levels/pairs must survive."""
    fresh = coverage_state(catalog)
    for other in selected:
        if other is not combo:
            apply_combo(catalog, other, fresh)
    state.clear()
    state.update(fresh)


def quota_requirements():
    return {"non_journal_object": 6, "pre_1990": 6, "non_english": 8, "non_latin": 6,
            "rtl_bidi": 3, "accessibility": 5, "offline_net": 5, "governed_access": 5,
            "metadata_conflict": 8, "study_report_topology": 4, "non_success_terminal": 4,
            "no_doi": 3, "non_crossref_doi": 3, "version_relation": 3,
            "translation_relation": 3, "untrusted_text": 3}


def uncovered_levels(catalog, state):
    return [(axis, lv) for axis, spec in catalog["axes"].items()
            for lv in spec["levels"] if lv not in state["levels"][axis]]


def target_uncovered_levels(catalog, state):
    # Retain v2's <=30-level coverage targets and report every remaining gap.
    return [(axis, lv) for axis, lv in uncovered_levels(catalog, state)
            if axis in catalog["hard_coverage_axes"] or
            (not catalog["axes"][axis].get("multi") and len(catalog["axes"][axis]["levels"]) <= SCENARIO_COUNT)]


def find_critical_duplicates(selected, catalog):
    seen = {}
    for c in selected:
        tup = combo_critical_tuple(catalog, c)
        if tup in seen:
            return [seen[tup], c["_ci"]]
        seen[tup] = c["_ci"]
    return None


def verify_quotas(state, selected, catalog):
    problems = []
    quotas = catalog["coverage_quotas"]
    if len(selected) != SCENARIO_COUNT:
        problems.append(f"scenario count: {len(selected)} != {SCENARIO_COUNT}")
    for tag, need in quota_requirements().items():
        if state["tags"][tag] < need:
            problems.append(f"quota {tag}: {state['tags'][tag]} < {need}")
    for skill in catalog["axes"][SKILL]["levels"]:
        for label, count, need in [
            ("skill", state["skills"][skill], quotas["min_skill_usage"]),
            ("skill task diversity", len(state["skill_task_goals"][skill]), quotas["min_skill_task_goals"]),
        ]:
            if count < need:
                problems.append(f"{label} {skill}: {count} < {need}")
        anchor = catalog["skill_semantics"][skill]["coverage_anchor_goal"]
        if anchor not in state["skill_task_goals"][skill]:
            problems.append(f"skill anchor goal {skill}: missing {anchor}")
    for cap in catalog["axes"][CAPABILITY]["levels"]:
        if state["capabilities"][cap] < quotas["min_capability_usage"]:
            problems.append(f"capability {cap}: {state['capabilities'][cap]} < {quotas['min_capability_usage']}")
    for axis, lv in uncovered_levels(catalog, state):
        if axis in catalog["hard_coverage_axes"]:
            problems.append(f"axis {axis} uncovered level: {lv}")
    for c in selected:
        problems.extend(admission_problems(catalog, c))
    if find_critical_duplicates(selected, catalog):
        problems.append("critical tuple duplicates")
    if sum(has_mid_task(catalog, c) for c in selected) < 5:
        problems.append("mid-task event scenarios < 5")
    return problems


def candidate_supply(catalog, pool):
    """Necessary supply/capacity checks, not proof of joint feasibility."""
    by_skill = {}
    for skill in catalog["axes"][SKILL]["levels"]:
        cs = [c for c in pool if c[SKILL] == skill]
        by_skill[skill] = {
            "candidates": len(cs),
            "task_goal_counts": dict(sorted(Counter(c[GOAL] for c in cs).items())),
            "distinct_critical_tuples": len({combo_critical_tuple(catalog, c) for c in cs}),
            "anchor_goal_candidates": sum(c[GOAL] == catalog["skill_semantics"][skill]["coverage_anchor_goal"] for c in cs),
        }
    return {"primary_skill_slots": SCENARIO_COUNT,
            "maximum_uniform_primary_skill_usage": SCENARIO_COUNT // len(by_skill),
            "per_skill": by_skill}


def verify_supply(catalog, supply):
    q = catalog["coverage_quotas"]
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 1 for v in q.values()):
        raise ValueError("coverage quotas must be positive integers")
    slots = max(q["min_skill_usage"], q["min_skill_task_goals"]) * len(supply["per_skill"])
    if slots > SCENARIO_COUNT:
        raise ValueError(f"infeasible primary skill quota: {slots} slots required, {SCENARIO_COUNT} available")
    for skill, s in supply["per_skill"].items():
        if (s["distinct_critical_tuples"] < q["min_skill_usage"]
                or len(s["task_goal_counts"]) < q["min_skill_task_goals"]
                or s["anchor_goal_candidates"] == 0):
            raise ValueError(f"insufficient candidate supply: {skill}")


def prepare_pool(catalog, pool):
    """Bit masks accelerate ordinary set coverage without changing its score."""
    indices = defaultdict(dict)

    def mask(kind, features):
        result = 0
        for feature in features:
            index = indices[kind].setdefault(feature, len(indices[kind]))
            result |= 1 << index
        return result

    prepared = []
    hard = set(catalog["hard_coverage_axes"])
    for c in pool:
        masks = (
            mask("levels", ((ax, v) for ax in catalog["axes"] if ax not in hard for v in values(c[ax]))),
            mask("hard", ((ax, v) for ax in catalog["axes"] if ax in hard for v in values(c[ax]))),
            mask("pairs", ((ax, bx, x, y) for ax, bx in catalog["pairwise_axes"] for x in values(c[ax]) for y in values(c[bx]))),
            mask("events", draw_events_for(catalog, c)),
            mask("terminals", [c[TERMINAL]]),
        )
        prepared.append((c, masks, combo_tags(catalog, c), tiebreak(catalog["seed"], c["_ci"])))
    axis_masks = {}
    for (axis, value), index in indices["levels"].items():
        axis_masks[axis] = axis_masks.get(axis, 0) | (1 << index)
    return prepared, axis_masks


def skill_deficit(catalog, state, skill, goal=None):
    q = catalog["coverage_quotas"]
    anchor = catalog["skill_semantics"][skill]["coverage_anchor_goal"]
    anchor_missing = anchor not in state["skill_task_goals"][skill] and goal != anchor
    return max(int(anchor_missing), q["min_skill_usage"] - state["skills"][skill] - (goal is not None),
               q["min_skill_task_goals"] - len(state["skill_task_goals"][skill])
               - (goal is not None and goal not in state["skill_task_goals"][skill]))


def greedy_select(catalog, pool, state, quota_weights, w, prepared=None):
    prepared, axis_masks = prepare_pool(catalog, pool) if prepared is None else prepared
    selected, selected_ids = [], set()
    target_axes = [ax for ax, spec in catalog["axes"].items()
                     if ax in catalog["hard_coverage_axes"] or
                     (not spec.get("multi") and len(spec["levels"]) <= SCENARIO_COUNT)]
    covered = [0] * 5
    for step in range(SCENARIO_COUNT):
        deficits = {s: skill_deficit(catalog, state, s) for s in catalog["axes"][SKILL]["levels"]}
        total_deficit = sum(deficits.values())
        slots = SCENARIO_COUNT - step
        due_axes = [ax for ax in catalog["hard_coverage_axes"]
                    if len(catalog["axes"][ax]["levels"]) - len(state["levels"][ax]) >= slots]
        urgency = defaultdict(int)
        for ax in target_axes:
            missing = len(catalog["axes"][ax]["levels"]) - len(state["levels"][ax])
            slack = max(0, slots - missing)
            if missing and ax in axis_masks:
                urgency[slack] |= axis_masks[ax]
        best, best_key = None, None
        for item in prepared:
            c, masks, tags, tie = item
            if c["_ci"] in selected_ids or combo_critical_tuple(catalog, c) in state["critical_tuples"]:
                continue
            s, g = c[SKILL], c[GOAL]
            progress = deficits[s] - skill_deficit(catalog, state, s, g)
            # Reserve slots for actual skills and distinct goals; never silently relax.
            if total_deficit - progress > slots - 1:
                continue
            if any(not (set(values(c[ax])) - state["levels"][ax]) for ax in due_axes):
                continue
            fresh = [(m & ~old).bit_count() for m, old in zip(masks, covered)]
            gain = w["level"] * (fresh[0] + 5 * fresh[1]) + w["pair"] * fresh[2] + w["event"] * fresh[3] + w["terminal"] * fresh[4]
            gain += w["level"] * sum(40.0 / (slack + 1) * (masks[0] & ~covered[0] & urgent).bit_count()
                                     for slack, urgent in urgency.items())
            gain += max(30.0, w["level"] * 20) * progress
            anchor = catalog["skill_semantics"][s]["coverage_anchor_goal"]
            if g == anchor and anchor not in state["skill_task_goals"][s]:
                gain += w["level"] * 20
            gain += max(30.0, w["level"] * 20) * sum(state["capabilities"][cap] < catalog["coverage_quotas"]["min_capability_usage"] for cap in c[CAPABILITY])
            gain += max(30.0, w["level"] * 5) * sum(min(n, max(0, quota_weights.get(tag, 0) - state["tags"][tag])) for tag, n in tags.items())
            key = (gain, tie)
            if best_key is None or key > best_key:
                best, best_key = item, key
        if best is None:
            break
        c, masks, _, _ = best
        selected.append(c)
        selected_ids.add(c["_ci"])
        covered = [a | b for a, b in zip(covered, masks)]
        apply_combo(catalog, c, state)
    return selected


def select_candidates(catalog, pool):
    prepared = prepare_pool(catalog, pool)
    runs = []
    best, best_count = None, None
    for w in SWEEPS:
        state = coverage_state(catalog)
        selected = greedy_select(catalog, pool, state, quota_requirements(), w, prepared)
        problems = verify_quotas(state, selected, catalog)
        gaps = target_uncovered_levels(catalog, state)
        runs.append({"weights": w, "constraint_problem_count": len(problems), "coverage_target_gap_count": len(gaps)})
        # Hard admission precedes coverage breadth; first sweep wins equal scores.
        score = (len(problems), len(gaps))
        if best_count is None or score < best_count:
            best, best_count = (selected, state, w), score
    return (*best, runs)


def build_report(catalog, state, selected, problems, weights):
    declared = {"capabilities": catalog["axes"][CAPABILITY]["levels"],
                "skills": catalog["axes"][SKILL]["levels"],
                "task_goals": catalog["axes"][GOAL]["levels"]}
    report = {
        "chosen_greedy_weights": weights,
        "declared_capabilities": declared["capabilities"],
        "declared_skills": declared["skills"],
        "declared_task_goals": declared["task_goals"],
        "axis_level_counts": {ax: len(state["levels"][ax]) for ax in catalog["axes"]},
        "pairwise_coverage_counts": {"|".join(pair): len(v) for pair, v in sorted(state["pairs"].items())},
        "event_category_counts": dict(sorted(Counter(cat for c in selected for cat in draw_events_for(catalog, c)).items())),
        "capability_usage_counts": {v: state["capabilities"][v] for v in declared["capabilities"]},
        "skill_usage_counts": {v: state["skills"][v] for v in declared["skills"]},
        "task_goal_usage_counts": {v: state["task_goals"][v] for v in declared["task_goals"]},
        "per_skill_task_goal_diversity": {s: {"count": len(state["skill_task_goals"][s]), "task_goals": sorted(state["skill_task_goals"][s])} for s in declared["skills"]},
        "terminal_state_counts": dict(state["terminals"]),
        "quota_tag_counts": dict(state["tags"]),
        "coverage_quotas": catalog["coverage_quotas"],
        "skill_anchor_goals": {s: catalog["skill_semantics"][s]["coverage_anchor_goal"] for s in declared["skills"]},
        "quota_tag_requirements": quota_requirements(),
        "scenarios_with_3plus_capabilities": sum(len(c[CAPABILITY]) >= 3 for c in selected),
        "mid_task_event_scenarios": sum(has_mid_task(catalog, c) for c in selected),
        "uncovered_factor_levels": uncovered_levels(catalog, state),
        "uncovered_required_levels": [(ax, lv) for ax, lv in uncovered_levels(catalog, state) if ax in catalog["hard_coverage_axes"]],
        "coverage_target_gaps": target_uncovered_levels(catalog, state),
        "critical_tuple_duplicates": find_critical_duplicates(selected, catalog),
        "constraint_problems": problems,
        "all_hard_quotas_passed": not problems,
    }
    for name, levels in declared.items():
        report[f"uncovered_{name}"] = [v for v in levels if state[name][v] == 0]
    return report


def run(output_path=HERE / "generated-scenarios.json"):
    catalog = load_catalog()
    validate_catalog(catalog)
    pool = gen_candidates(catalog)
    supply = candidate_supply(catalog, pool)
    verify_supply(catalog, supply)
    selected, state, weights, sweeps = select_candidates(catalog, pool)
    problems = verify_quotas(state, selected, catalog)
    scenarios = []
    for combo in selected:
        ci = combo["_ci"]
        scenarios.append({
            "id": f"S{len(scenarios) + 1:03d}", "candidate_index": ci,
            "factor_combination": {k: v for k, v in combo.items() if k != "_ci"},
            "long_tail_rationale": "", "feasibility_notes": "", "task_chain": [],
            "injected_events": [{"event_category": cat, "event_id": pick_event_id(catalog, cat, ci, slot),
                                 "inject_at_step": None, "mid_task": True if has_mid_task(catalog, combo) else None}
                                for slot, cat in enumerate(draw_events_for(catalog, combo), 1)],
            "attacked_assumptions": [], "acceptance_criteria": [],
            "forbidden_silent_failures": [], "expected_artifacts": [],
            "correct_terminal_state": combo[TERMINAL],
            "replay_spec": {"seed": catalog["seed"], "candidate_index": ci},
        })
    out = {
        "generation_metadata": {
            "seed": catalog["seed"], "scenario_count": len(scenarios), "candidate_pool_size": len(pool),
            "random_algorithm": "SHA256 counter-based deterministic pseudorandom selection",
            "selection_algorithm": "coverage-maximizing deterministic greedy selection with skill/diversity slot reservation, hard-axis slot reservation, remaining-slot coverage urgency, SHA256 tie-break and a deterministic weight sweep (7 sweeps; best picked by hard-constraint-problem count then coverage-target-gap count, first sweep wins ties, no optimality guarantee)",
            "factor_catalog_version": catalog["version"],
            "coverage_note": "Greedy sweep observation only: uncovered_required_levels lists declared hard-axis gaps; coverage_target_gaps retains the v2 single-select <=30-level coverage targets, which v2 itself left partly uncovered. This run did NOT execute a repair pass, so infeasibility and optimality are not proven and no repair or best-attainable claims are made. Uncovered task goals remain explicit; factor coverage is not executed workflow coverage.",
            "repair_executed": False,
            "semantic_model": "one primary actual skill; one supported task goal; 1..3 supported capability families; no secondary skill credit",
            "v2_compatibility": "Breaking coverage semantics: v2 skill_usage_counts and 3plus_skills counted E01 families. v3 skill_usage_counts counts E02 directories; capabilities have separate counters. Declared hard axes and observational coverage targets now have separate gap fields; the old pseudo-skill quotas are replaced by measured primary-skill quotas.",
        },
        "factor_catalog": {k: v["levels"] for k, v in catalog["axes"].items()},
        "candidate_supply": supply,
        "weight_sweep_results": sweeps,
        "coverage_report": build_report(catalog, state, selected, problems, weights),
        "scenarios": scenarios,
    }
    Path(output_path).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    for sweep in sweeps:
        print(f"weights {sweep['weights']}: {sweep['constraint_problem_count']} problems")
    print(f"observed coverage target gaps: {len(target_uncovered_levels(catalog, state))}")
    print(f"selected {len(selected)} scenarios from {len(pool)} candidates; constraint problems: {len(problems)}")
    for p in problems:
        print("  -", p)
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "generated-scenarios.json")
    args = parser.parse_args()
    result = run(args.output)
    sys.exit(1 if result["coverage_report"]["constraint_problems"] else 0)

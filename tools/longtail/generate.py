# -*- coding: utf-8 -*-
"""Deterministic long-tail scenario combinator.

Implements the sampling protocol from the ChatGPT-upgraded stress prompt:

    digest = SHA256(seed | candidate_index | axis_id | draw_index)
    integer = digest as unsigned big-endian integer
    selected_index = integer mod number_of_levels

Phase 1: draw 4096 candidate combinations.
Phase 2: greedily select 30 scenarios maximizing coverage (axis levels,
pairwise combinations, event categories, skills, terminal states, quota
tags), with SHA256(seed|tie|candidate_index) as the deterministic tie-break.

Output: generated-scenarios.json with factor_combination, replay_spec and
machine-computed coverage_report. The semantic expansion (task chains,
oracles, injected events) is a later stage; this generator only produces
the provably-random factor layer.
"""

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
SEED = 20260917
POOL_SIZE = 4096
SCENARIO_COUNT = 30


def load_catalog():
    with open(HERE / "factor_catalog.json", encoding="utf-8") as fh:
        return json.load(fh)


def sha_int(seed, candidate_index, axis_id, draw_index):
    raw = f"{seed}|{candidate_index}|{axis_id}|{draw_index}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest(), "big")


def draw_level(seed, candidate_index, axis_id, n_levels, draw_index=1):
    return sha_int(seed, candidate_index, axis_id, draw_index) % n_levels


def draw_multi(seed, candidate_index, axis_id, levels, draw_index=1):
    """Draw a 1..max_choice sized set for a multi-select axis."""
    n = levels
    k = sha_int(seed, candidate_index, axis_id, draw_index) % 3 + 1  # 1..3
    picks = []
    used = set()
    for i in range(k):
        v = sha_int(seed, candidate_index, axis_id, draw_index + 10 + i) % n
        while v in used:
            v = (v + 1) % n
        used.add(v)
        picks.append(v)
    return picks


def gen_candidates(catalog):
    axes = catalog["axes"]
    pool = []
    for ci in range(POOL_SIZE):
        combo = {}
        for axis_id, spec in axes.items():
            levels = spec["levels"]
            if spec.get("multi"):
                idxs = draw_multi(SEED, ci, axis_id, len(levels))
                combo[axis_id] = [levels[i] for i in idxs]
            else:
                combo[axis_id] = levels[draw_level(SEED, ci, axis_id, len(levels))]
        pool.append(combo)
    return pool


def combo_tags(catalog, combo):
    tags = Counter()
    for axis_id, spec in catalog["axes"].items():
        level_tags = spec.get("tags", {})
        values = combo[axis_id]
        if isinstance(values, list):
            for v in values:
                tags.update(level_tags.get(v, []))
        else:
            tags.update(level_tags.get(values, []))
    return tags


def coverage_state(catalog):
    """Objects tracked by the greedy selector."""
    st = {"levels": defaultdict(set), "pairs": defaultdict(set), "events": set(),
          "skills": Counter(), "terminals": Counter(), "tags": Counter(),
          "critical_tuples": set()}
    return st


def candidate_gain(catalog, combo, state, events_by_cat, quota_weights, w):
    gain = 0.0
    axes = catalog["axes"]
    st = state
    hard_axes = set(catalog.get("hard_coverage_axes", []))
    for axis_id, spec in axes.items():
        values = combo[axis_id]
        if not isinstance(values, list):
            values = [values]
        mult = 5.0 if axis_id in hard_axes else 1.0
        for v in values:
            if v not in st["levels"][axis_id]:
                gain += w["level"] * mult
    for (ax, bx) in catalog["pairwise_axes"]:
        a = combo[ax]
        b = combo[bx]
        av = a if isinstance(a, list) else [a]
        bv = b if isinstance(b, list) else [b]
        for x in av:
            for y in bv:
                if (x, y) not in st["pairs"][(ax, bx)]:
                    gain += w["pair"]
    evs = draw_events_for(catalog, combo)
    for cat in evs:
        if cat not in st["events"]:
            gain += w["event"]
    for skill in combo["E01_primary_capability"]:
        need = 8 - st["skills"][skill]
        if need > 0:
            gain += 30.0
    term = combo["E04_correct_terminal_state"]
    if st["terminals"][term] == 0:
        gain += w["terminal"]
    tags = combo_tags(catalog, combo)
    for tag, count in tags.items():
        need = quota_weights.get(tag, 0) - st["tags"][tag]
        if need > 0:
            gain += 30.0 * min(count, need)
    return gain


def greedy_select(catalog, pool, state, quota_weights, w):
    selected = []
    for _ in range(SCENARIO_COUNT):
        best = None
        best_gain = -1.0
        best_tie = None
        for combo in pool:
            if combo["_ci"] in {c["_ci"] for c in selected}:
                continue
            if combo_critical_tuple(catalog, combo) in state["critical_tuples"]:
                continue
            g = candidate_gain(catalog, combo, state, catalog["events"], quota_weights, w)
            if g > best_gain:
                best_gain, best, best_tie = g, combo, tiebreak(SEED, combo["_ci"])
            elif g == best_gain and best is not None and tiebreak(SEED, combo["_ci"]) > best_tie:
                best, best_tie = combo, tiebreak(SEED, combo["_ci"])
        if best is None:
            print("no candidate satisfies critical-tuple uniqueness; stopping early")
            break
        selected.append(best)
        apply_combo(catalog, best, state)
    return selected


def draw_events_for(catalog, combo):
    """Two events from different categories, deterministic per candidate."""
    cats = list(catalog["events"].keys())
    i1 = sha_int(SEED, 0, "event_cat1", combo["_ci"]) % len(cats)
    i2 = sha_int(SEED, 0, "event_cat2", combo["_ci"]) % len(cats)
    if i2 == i1:
        i2 = (i2 + 1) % len(cats)
    return [cats[i1], cats[i2]]


def pick_event_id(catalog, cat, ci, slot):
    levels = catalog["events"][cat]
    return levels[sha_int(SEED, ci, f"event_{cat}", slot) % len(levels)]


def tiebreak(seed, ci):
    return sha_int(seed, ci, "tie", 0)


def apply_combo(catalog, combo, state):
    axes = catalog["axes"]
    for axis_id, spec in axes.items():
        values = combo[axis_id]
        if not isinstance(values, list):
            values = [values]
        for v in values:
            state["levels"][axis_id].add(v)
    for (ax, bx) in catalog["pairwise_axes"]:
        a = combo[ax]
        b = combo[bx]
        av = a if isinstance(a, list) else [a]
        bv = b if isinstance(b, list) else [b]
        for x in av:
            for y in bv:
                state["pairs"][(ax, bx)].add((x, y))
    evs = draw_events_for(catalog, combo)
    for cat in evs:
        state["events"].add(cat)
    for skill in combo["E01_primary_capability"]:
        state["skills"][skill] += 1
    state["terminals"][combo["E04_correct_terminal_state"]] += 1
    for tag, count in combo_tags(catalog, combo).items():
        state["tags"][tag] += count
    tup = tuple(combo[ax] if not isinstance(combo[ax], list) else "|".join(sorted(combo[ax]))
                for ax in catalog["critical_tuple"])
    state["critical_tuples"].add(tup)


def quota_requirements():
    return {
        "non_journal_object": 6,
        "pre_1990": 6,
        "non_english": 8,
        "non_latin": 6,
        "rtl_bidi": 3,
        "accessibility": 5,
        "offline_net": 5,
        "governed_access": 5,
        "metadata_conflict": 8,
        "study_report_topology": 4,
        "non_success_terminal": 4,
        "no_doi": 3,
        "non_crossref_doi": 3,
        "version_relation": 3,
        "translation_relation": 3,
        "untrusted_text": 3,
    }


def verify_quotas(state, selected, catalog):
    problems = []
    for tag, need in quota_requirements().items():
        if state["tags"][tag] < need:
            problems.append(f"quota {tag}: {state['tags'][tag]} < {need}")
    # FW-02: 遍历 catalog 声明的技能全集, 完全缺席的技能也会被发现
    skill_axis = (catalog.get("axes") or {}).get("E01_primary_capability") or {}
    all_skills = set(skill_axis.get("levels") or [])
    for skill in sorted(all_skills):
        count = state["skills"][skill]
        if count < 8:
            problems.append(f"skill {skill}: {count} < 8")
    multi3 = sum(1 for c in selected if len(c["E01_primary_capability"]) >= 3)
    if multi3 < 12:
        problems.append(f"scenarios with 3+ skills: {multi3} < 12")
    # every level of axes with <=30 levels must appear at least once
    for axis_id, spec in catalog["axes"].items():
        if spec.get("multi"):
            continue
        if len(spec["levels"]) <= 30:
            missing = [lv for lv in spec["levels"] if lv not in state["levels"][axis_id]]
            if missing:
                problems.append(f"axis {axis_id} uncovered levels: {missing[:5]}{'...' if len(missing) > 5 else ''} ({len(missing)} missing)")
    dup = find_critical_duplicates(selected, catalog)
    if dup:
        problems.append(f"critical tuple duplicates: {dup}")
    return problems


def find_critical_duplicates(selected, catalog):
    seen = {}
    for c in selected:
        tup = tuple(
            c[ax] if not isinstance(c[ax], list) else "|".join(sorted(c[ax]))
            for ax in catalog["critical_tuple"]
        )
        if tup in seen:
            return [seen[tup], c["_ci"]]
        seen[tup] = c["_ci"]
    return None


def uncovered_levels(catalog, state):
    out = []
    for axis_id, spec in catalog["axes"].items():
        if spec.get("multi"):
            continue
        if len(spec["levels"]) <= 30:
            for lv in spec["levels"]:
                if lv not in state["levels"][axis_id]:
                    out.append((axis_id, lv))
    return out


def combo_critical_tuple(catalog, combo):
    return tuple(
        combo[ax] if not isinstance(combo[ax], list) else "|".join(sorted(combo[ax]))
        for ax in catalog["critical_tuple"]
    )


def repair_uncovered(catalog, pool, selected, state, max_rounds=80):
    """Swap selected scenarios to cover missing axis levels without
    breaking quotas or critical-tuple uniqueness. Every swap must strictly
    decrease the uncovered-level count; otherwise it is rolled back."""
    selected_set = {c["_ci"] for c in selected}
    rounds = 0
    while rounds < max_rounds:
        missing = uncovered_levels(catalog, state)
        if not missing:
            break
        base_count = len(missing)
        best_new, best_hits, best_tie = None, -1, None
        for combo in pool:
            if combo["_ci"] in selected_set:
                continue
            if combo_critical_tuple(catalog, combo) in state["critical_tuples"]:
                continue
            hits = 0
            for ax, lv in missing:
                v = combo[ax]
                if isinstance(v, list):
                    if lv in v:
                        hits += 1
                elif v == lv:
                    hits += 1
            if hits > best_hits:
                best_new, best_hits, best_tie = combo, hits, tiebreak(SEED, combo["_ci"])
            elif hits == best_hits and best_new is not None and tiebreak(SEED, combo["_ci"]) > best_tie:
                best_new, best_tie = combo, tiebreak(SEED, combo["_ci"])
        if best_new is None or best_hits == 0:
            break
        def loss(c):
            return len(uncovered_levels_candidate(catalog, selected, state, c))
        worst_old = min(selected, key=loss)
        # trial swap with rollback on non-improvement (FW-01: inverse 按剩余集合重算)
        selected.remove(worst_old)
        selected_set.discard(worst_old["_ci"])
        apply_combo_inverse(catalog, worst_old, state, selected)
        selected.append(best_new)
        selected_set.add(best_new["_ci"])
        apply_combo(catalog, best_new, state)
        new_count = len(uncovered_levels(catalog, state))
        if new_count >= base_count:
            selected.remove(best_new)
            selected_set.discard(best_new["_ci"])
            apply_combo_inverse(catalog, best_new, state, selected)
            selected.append(worst_old)
            selected_set.add(worst_old["_ci"])
            apply_combo(catalog, worst_old, state)
            break
        rounds += 1
    return rounds


def uncovered_levels_candidate(catalog, selected, state, candidate):
    """Levels that would become uncovered if candidate were removed."""
    other = [c for c in selected if c is not candidate]
    out = []
    for axis_id, spec in catalog["axes"].items():
        if spec.get("multi"):
            continue
        if len(spec["levels"]) <= 30:
            covered_elsewhere = set()
            for c in other:
                v = c[axis_id]
                if isinstance(v, list):
                    covered_elsewhere.update(v)
                else:
                    covered_elsewhere.add(v)
            v = candidate[axis_id]
            vals = v if isinstance(v, list) else [v]
            for lv in vals:
                if lv not in covered_elsewhere and lv in spec["levels"]:
                    out.append((axis_id, lv))
    return out


def apply_combo_inverse(catalog, combo, state, selected):
    """撤销 combo 的覆盖贡献 (FW-01): 不直接 discard 共享元素,
    而是基于剩余 selected 场景整体重算, 仍被其他场景覆盖的
    level/pair/event/计数不会误删。"""
    fresh = coverage_state(catalog)
    for other in selected:
        if other is not combo:
            apply_combo(catalog, other, fresh)
    state.clear()
    state.update(fresh)


def run():
    catalog = load_catalog()
    pool = gen_candidates(catalog)
    for i, combo in enumerate(pool):
        combo["_ci"] = i

    quota_weights = quota_requirements()

    # weight sweeps: level coverage is the scarcest objective under the
    # 30-scenario budget, so the sweep trades pairwise breadth for it.
    sweeps = [
        {"level": 1.0, "pair": 3.0, "event": 2.0, "skill": 2.0, "terminal": 2.0},
        {"level": 4.0, "pair": 1.0, "event": 2.0, "skill": 2.0, "terminal": 2.0},
        {"level": 8.0, "pair": 1.0, "event": 1.0, "skill": 1.0, "terminal": 1.0},
        {"level": 12.0, "pair": 0.5, "event": 1.0, "skill": 1.0, "terminal": 1.0},
        {"level": 16.0, "pair": 0.5, "event": 1.0, "skill": 1.0, "terminal": 1.0},
        {"level": 24.0, "pair": 0.5, "event": 1.0, "skill": 1.0, "terminal": 1.0},
        {"level": 32.0, "pair": 0.25, "event": 1.0, "skill": 1.0, "terminal": 1.0},
    ]
    best_run = None
    best_problems = None
    for sw in sweeps:
        st = coverage_state(catalog)
        sel = greedy_select(catalog, pool, st, quota_weights, sw)
        problems = verify_quotas(st, sel, catalog)
        score = len(problems)
        if best_problems is None or score < best_problems:
            best_problems = score
            best_run = (sel, st, sw)
        print(f"weights {sw}: {len(problems)} problems")

    selected, state, chosen_weights = best_run
    problems = verify_quotas(state, selected, catalog)
    report = build_report(catalog, state, selected, problems, chosen_weights)

    scenarios = []
    for combo in selected:
        ci = combo["_ci"]
        events = []
        for slot, cat in enumerate(draw_events_for(catalog, combo), start=1):
            events.append({
                "event_category": cat,
                "event_id": pick_event_id(catalog, cat, ci, slot),
                "inject_at_step": None,
                "mid_task": None,
            })
        mid_flip = sha_int(SEED, ci, "mid_task", 1) % 3 == 0
        if mid_flip:
            for ev in events:
                ev["mid_task"] = True
        scenarios.append({
            "id": f"S{len(scenarios) + 1:03d}",
            "candidate_index": ci,
            "factor_combination": {k: v for k, v in combo.items() if k != "_ci"},
            "long_tail_rationale": "",
            "feasibility_notes": "",
            "task_chain": [],
            "injected_events": events,
            "attacked_assumptions": [],
            "acceptance_criteria": [],
            "forbidden_silent_failures": [],
            "expected_artifacts": [],
            "correct_terminal_state": combo["E04_correct_terminal_state"],
            "replay_spec": {"seed": SEED, "candidate_index": ci},
        })

    mid_task_count = sum(
        1 for s in scenarios if any(e.get("mid_task") for e in s["injected_events"])
    )
    if mid_task_count < 5:
        problems.append(f"mid-task events: {mid_task_count} < 5")

    out = {
        "generation_metadata": {
            "seed": SEED,
            "scenario_count": len(scenarios),
            "candidate_pool_size": POOL_SIZE,
            "random_algorithm": "SHA256 counter-based deterministic pseudorandom selection",
            "selection_algorithm": "coverage-maximizing deterministic greedy selection with SHA256 tie-break and a deterministic weight sweep (7 sweeps; best picked by constraint-problem count, no optimality guarantee)",
            "factor_catalog_version": catalog["version"],
            "coverage_note": "Greedy sweep observation only: uncovered_required_levels lists levels the best sweep left uncovered. This run did NOT execute a repair pass, so infeasibility and optimality are not proven and no repair or best-attainable claims are made.",
            "repair_executed": False,
        },
        "factor_catalog": {k: v["levels"] for k, v in catalog["axes"].items()},
        "coverage_report": report,
        "scenarios": scenarios,
    }
    with open(HERE / "generated-scenarios.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"selected {len(scenarios)} scenarios from {POOL_SIZE} candidates")
    print(f"constraint problems: {len(problems)}")
    for p in problems:
        print("  -", p)
    print(f"mid-task event scenarios: {mid_task_count}")
    print(f"3+ skill scenarios: {sum(1 for c in selected if len(c['E01_primary_capability']) >= 3)}")
    print(f"critical tuple duplicates: {find_critical_duplicates(selected, catalog)}")
    return out


def build_report(catalog, state, selected, problems, weights):
    multi3 = sum(1 for c in selected if len(c["E01_primary_capability"]) >= 3)
    missing_levels = [(ax, lv) for ax, lv in uncovered_levels(catalog, state)]
    return {
        "chosen_greedy_weights": weights,
        "axis_level_counts": {
            ax: len(v) for ax, v in sorted(state["levels"].items())
        },
        "pairwise_coverage_counts": {
            "|".join(pair): len(v) for pair, v in sorted(state["pairs"].items())
        },
        "event_category_counts": {c: (1 if c in state["events"] else 0) for c in catalog["events"]},
        "skill_usage_counts": dict(state["skills"]),
        "terminal_state_counts": dict(state["terminals"]),
        "quota_tag_counts": dict(state["tags"]),
        "scenarios_with_3plus_skills": multi3,
        "uncovered_required_levels": missing_levels,
        "critical_tuple_duplicates": find_critical_duplicates(selected, catalog),
        "constraint_problems": problems,
    }


if __name__ == "__main__":
    run()

"""The factor model must not mistake abstract capabilities for actual skills."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from collections import Counter

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools/longtail/generate.py"
spec = importlib.util.spec_from_file_location("longtail_v3", GENERATOR)
lt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lt)


@pytest.fixture(scope="module")
def catalog():
    return lt.load_catalog()


@pytest.fixture(scope="module")
def pool(catalog):
    return lt.gen_candidates(catalog)


@pytest.fixture(scope="module")
def generated():
    return json.loads((GENERATOR.parent / "generated-scenarios.json").read_text(encoding="utf-8"))


def selected(generated):
    return [dict(s["factor_combination"], _ci=s["candidate_index"]) for s in generated["scenarios"]]


def state_for(catalog, combos):
    state = lt.coverage_state(catalog)
    for c in combos:
        lt.apply_combo(catalog, c, state)
    return state


def test_live_skill_catalog_exact_equality(catalog):
    lt.validate_catalog(catalog)
    assert sorted(catalog["axes"][lt.SKILL]["levels"]) == lt.discover_skills()
    assert len(lt.discover_skills()) == 13
    assert not catalog["axes"][lt.SKILL]["multi"]
    assert catalog["version"] == "extreme-academic-longtail-v3"


def test_every_skill_mapping_has_repository_source(catalog):
    assert set(catalog["skill_semantics"]) == set(lt.discover_skills())
    for skill, m in catalog["skill_semantics"].items():
        assert (ROOT / m["source"]).is_file()
        assert m["workflow_role"] and len(m["task_goals"]) >= 2
        assert set(m["capability_families"]) == set().union(*map(set, m["task_goals"].values()))
        assert len(set(m["event_categories"])) >= 2


@pytest.mark.parametrize("change", ["add", "delete", "rename"])
def test_live_skill_drift_fails_deterministically(catalog, tmp_path, change):
    for skill in lt.discover_skills():
        p = tmp_path / skill / "SKILL.md"
        p.parent.mkdir()
        p.write_text("fixture", encoding="utf-8")
    if change == "add":
        (tmp_path / "fourteenth-skill").mkdir()
        (tmp_path / "fourteenth-skill/SKILL.md").write_text("fixture", encoding="utf-8")
    elif change == "delete":
        (tmp_path / "academic-writing/SKILL.md").unlink()
    else:
        (tmp_path / "academic-writing").rename(tmp_path / "renamed-writing")
    failures = []
    for _ in range(2):
        with pytest.raises(ValueError, match="skill catalog drift") as error:
            lt.validate_catalog(catalog, tmp_path)
        failures.append(str(error.value))
    assert failures[0] == failures[1]


@pytest.mark.parametrize("damage", ["missing_skill", "unknown_capability", "unknown_goal", "unknown_event"])
def test_semantic_mapping_drift_is_rejected(catalog, damage):
    c = copy.deepcopy(catalog)
    m = c["skill_semantics"]["academic-writing"]
    if damage == "missing_skill":
        del c["skill_semantics"]["academic-writing"]
    elif damage == "unknown_capability":
        m["task_goals"]["revise_manuscript"] = ["invented_capability"]
    elif damage == "unknown_goal":
        m["task_goals"]["invented_goal"] = ["academic_writing"]
    else:
        m["event_categories"].append("invented_event")
    with pytest.raises(ValueError):
        lt.validate_catalog(c)


def test_coverage_dimensions_are_separate(catalog, generated):
    report = generated["coverage_report"]
    for axis, declared, counts in [
        (lt.CAPABILITY, "declared_capabilities", "capability_usage_counts"),
        (lt.SKILL, "declared_skills", "skill_usage_counts"),
        (lt.GOAL, "declared_task_goals", "task_goal_usage_counts"),
    ]:
        assert set(report[declared]) == set(catalog["axes"][axis]["levels"]) == set(report[counts])
        observed = Counter(v for c in selected(generated) for v in lt.values(c[axis]))
        assert report[counts] == {v: observed[v] for v in report[declared]}
    assert set(report["skill_usage_counts"]).isdisjoint(report["capability_usage_counts"])
    assert "scenarios_with_3plus_skills" not in report
    assert sum(report["skill_usage_counts"].values()) == 30
    assert "Breaking coverage semantics" in generated["generation_metadata"]["v2_compatibility"]


def test_all_skills_meet_usage_and_diversity_quotas(catalog, generated):
    report = generated["coverage_report"]
    assert not report["uncovered_skills"]
    for skill in lt.discover_skills():
        cs = [c for c in selected(generated) if c[lt.SKILL] == skill]
        goals = sorted({c[lt.GOAL] for c in cs})
        assert catalog["skill_semantics"][skill]["coverage_anchor_goal"] in goals
        assert len(cs) >= catalog["coverage_quotas"]["min_skill_usage"] == 2
        assert len(goals) >= catalog["coverage_quotas"]["min_skill_task_goals"] == 2
        assert report["per_skill_task_goal_diversity"][skill] == {"count": len(goals), "task_goals": goals}
    assert {"claim-evidence-graph", "decision-ledger", "academic-writing", "math-computation", "cross-review-five"} <= set(report["skill_usage_counts"])


def test_absent_skill_and_lost_diversity_fail(catalog, generated):
    cs = selected(generated)
    cs = [c for c in cs if c[lt.SKILL] != "claim-evidence-graph"]
    problems = lt.verify_quotas(state_for(catalog, cs), cs, catalog)
    assert "skill claim-evidence-graph: 0 < 2" in problems
    cs = selected(generated)
    writing = [c for c in cs if c[lt.SKILL] == "academic-writing"]
    for c in writing:
        c[lt.GOAL] = writing[0][lt.GOAL]
    problems = lt.verify_quotas(state_for(catalog, cs), cs, catalog)
    assert "skill task diversity academic-writing: 1 < 2" in problems


def test_whole_pool_and_selected_triples_are_compatible(catalog, pool, generated):
    assert len(pool) == 4096
    for c in pool + selected(generated):
        assert not lt.admission_problems(catalog, c)
        events = lt.draw_events_for(catalog, c)
        assert len(set(events)) == 2
        assert set(events) <= set(catalog["skill_semantics"][c[lt.SKILL]]["event_categories"])


@pytest.mark.parametrize("skill,goal,cap", [
    ("academic-writing", "reconstruct_lineage", "provenance_tracking"),
    ("literature-analysis", "monitor_new_work", "literature_monitoring"),
    ("literature-watch", "analyze_research_gaps", "literature_analysis"),
    ("math-computation", "symbolic_computation", "source_verification"),
])
def test_unsupported_triples_rejected(catalog, skill, goal, cap):
    assert lt.admission_problems(catalog, {lt.SKILL: skill, lt.GOAL: goal, lt.CAPABILITY: [cap]})


def test_analysis_is_not_monitoring_and_new_workflows_declared(catalog):
    m = catalog["skill_semantics"]
    assert "literature_monitoring" not in m["literature-analysis"]["capability_families"]
    assert "monitor_new_work" not in m["literature-analysis"]["task_goals"]
    expected = {
        "literature-analysis": {"compare_literature", "identify_counter_evidence", "build_review_matrix", "analyze_research_gaps", "export_bibliography"},
        "academic-writing": {"revise_manuscript", "prepare_citation_style", "prepare_submission_materials"},
        "math-computation": {"symbolic_computation", "numerical_computation", "verify_mathematics"},
        "cross-review-five": {"multi_review", "adversarial_challenge", "reconcile_disagreements"},
        "claim-evidence-graph": {"link_evidence_to_claim", "trace_supporting_refuting_evidence", "validate_contradiction_provenance"},
        "decision-ledger": {"record_decision", "record_negative_result", "prune_route", "reopen_route", "record_outcome_correction"},
    }
    for skill, goals in expected.items():
        assert goals <= set(m[skill]["task_goals"])


def test_supply_and_impossible_quota_fail_without_relaxation(catalog, pool, generated):
    supply = lt.candidate_supply(catalog, pool)
    assert supply == generated["candidate_supply"]
    assert supply["maximum_uniform_primary_skill_usage"] == 2
    lt.verify_supply(catalog, supply)
    c = copy.deepcopy(catalog)
    c["coverage_quotas"]["min_skill_usage"] = 3
    with pytest.raises(ValueError, match="39 slots required, 30 available"):
        lt.verify_supply(c, supply)
    limited = copy.deepcopy(supply)
    limited["per_skill"]["academic-writing"]["task_goal_counts"] = {"revise_manuscript": 300}
    with pytest.raises(ValueError, match="insufficient candidate supply: academic-writing"):
        lt.verify_supply(catalog, limited)


def test_existing_hard_levels_tags_events_and_uniqueness(catalog, generated):
    cs = selected(generated)
    state = state_for(catalog, cs)
    assert len(cs) == 30
    assert lt.verify_quotas(state, cs, catalog) == []
    assert generated["coverage_report"]["all_hard_quotas_passed"]
    assert state["levels"]["C02_primary_object_type"] == set(catalog["axes"]["C02_primary_object_type"]["levels"])
    for tag, need in lt.quota_requirements().items():
        assert state["tags"][tag] >= need
    assert state["events"] == set(catalog["events"])
    assert lt.find_critical_duplicates(cs, catalog) is None
    assert lt.find_critical_duplicates(cs + [cs[0]], catalog) is not None
    state["tags"]["non_crossref_doi"] = 0
    assert "quota non_crossref_doi: 0 < 3" in lt.verify_quotas(state, cs, catalog)


def test_report_lists_all_uncovered_levels_including_large_goal_axis(catalog, generated):
    r = generated["coverage_report"]
    state = state_for(catalog, selected(generated))
    assert r["uncovered_factor_levels"] == [list(x) for x in lt.uncovered_levels(catalog, state)]
    assert r["uncovered_task_goals"] == [g for g, n in r["task_goal_usage_counts"].items() if not n]
    assert len(catalog["axes"][lt.GOAL]["levels"]) > 30
    assert r["coverage_target_gaps"] == [list(x) for x in lt.target_uncovered_levels(catalog, state)]
    assert r["uncovered_task_goals"]  # Honest limitation; not a workflow execution claim.
    assert generated["generation_metadata"]["repair_executed"] is False
    assert "not proven" in generated["generation_metadata"]["coverage_note"]


def test_weight_sweep_first_best_tie_and_all_sweeps(monkeypatch, catalog):
    calls = []

    def fake_select(c, pool, state, quotas, weights, prepared):
        calls.append(weights)
        return [len(calls) - 1]

    scores = [3, 2, 0, 1, 0, 2, 1]
    monkeypatch.setattr(lt, "greedy_select", fake_select)
    monkeypatch.setattr(lt, "verify_quotas", lambda st, sel, c: ["failure"] * scores[sel[0]])
    result, _, weights, runs = lt.select_candidates(catalog, [])
    assert calls == lt.SWEEPS
    assert result == [2] and weights == lt.SWEEPS[2]
    assert [r["constraint_problem_count"] for r in runs] == scores


def test_repeated_isolated_processes_match_committed_bytes(tmp_path, generated):
    reference = (GENERATOR.parent / "generated-scenarios.json").read_bytes()
    for hashseed in ["1", "987654"]:
        output = tmp_path / f"generated-{hashseed}.json"
        env = dict(os.environ, PYTHONHASHSEED=hashseed)
        result = subprocess.run([sys.executable, str(GENERATOR), "--output", str(output)],
                                cwd=tmp_path, env=env, capture_output=True, text=True,
                                encoding="utf-8", timeout=180)
        assert result.returncode == 0, result.stdout + result.stderr
        assert output.read_bytes() == reference
    sweeps = generated["weight_sweep_results"]
    assert len(sweeps) == 7
    best = min(sweeps, key=lambda s: (s["constraint_problem_count"], s["coverage_target_gap_count"]))
    assert best["weights"] == generated["coverage_report"]["chosen_greedy_weights"]
    assert best["constraint_problem_count"] == 0


def test_seed_and_small_multiselect_are_well_defined(catalog, pool):
    c = copy.deepcopy(catalog)
    c["seed"] += 1
    assert lt.gen_candidates(c)[0] != pool[0]
    assert lt.draw_multi(20260917, 0, "test", 1) == [0]
    with pytest.raises(ValueError, match="invalid multi-select bounds"):
        lt.draw_multi(20260917, 0, "test", 1, min_choice=2)


def test_generator_fails_explicitly_on_infeasible_quota(monkeypatch, catalog, tmp_path):
    c = copy.deepcopy(catalog)
    c["coverage_quotas"]["min_skill_task_goals"] = 3
    monkeypatch.setattr(lt, "load_catalog", lambda: c)
    output = tmp_path / "not-generated.json"
    with pytest.raises(ValueError, match="infeasible primary skill quota"):
        lt.run(output)
    assert not output.exists()

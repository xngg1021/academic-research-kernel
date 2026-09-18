# -*- coding: utf-8 -*-
"""Deterministic regression tests for Research Object Provenance Kernel v1.

Covers:
1. Content-addressed streaming file hashing.
2. True three-phase end-to-end scientific pipeline (data_cleaning -> stats -> table_extraction)
   with physical files, real SHA256 hashes, and sub-100ms deterministic traversal.
3. Strict failure on missing on-disk artifacts (no silent pass).
4. Content-tampering detection (hash_mismatch).
5. Idempotent registration with conflict rejection (P1-02).
6. Disjoint Entity and Activity ID namespaces (P1-03).
7. Frozen immutable LineageReceipt deep snapshots (P1-04).
8. Distinct verification coverage states (intact vs unchecked vs missing_artifact) (P1-05).
9. Referential integrity on derivation activities (P1-06).
10. Deterministic content digest and collision-free receipt IDs (P1-08).
11. Strict type and SHA256 format enforcement (P1-09).
12. Single-producer invariant enforcement (P1-10).
13. Script entity referential integrity (P1-11).
14. Target-scoped traversal isolation from unrelated broken components (P2).
15. Deep chain iterative DAG traversal (>1000 nodes without RecursionError) (P3).
16. JSON Schema draft 2020-12 strict validation with additionalProperties: false.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/research-object-identity/scripts"))

import provenance as pr


def test_compute_file_sha256(tmp_path):
    """compute_file_sha256 calculates deterministic streaming SHA256."""
    f = tmp_path / "sample.csv"
    f.write_text("col_a,col_b\n1,2\n3,4\n", encoding="utf-8")
    h1 = pr.compute_file_sha256(f)
    assert len(h1) == 64
    assert h1 == pr.compute_file_sha256(f)

    with pytest.raises(FileNotFoundError):
        pr.compute_file_sha256(tmp_path / "non_existent.csv")


def test_end_to_end_three_phase_scientific_pipeline(tmp_path):
    """Full 3-phase scientific derivation with physical files and exact SHA256 matching:

    raw_survey.csv -> [clean.py@commit: data_cleaning] -> clean_survey.csv
                   -> [calc_stats.py@commit: statistical_analysis] -> stats_report.json
                   -> [extract_table.py@commit: table_extraction] -> table-2-cell-B7
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    # Real physical code files
    clean_py = scripts_dir / "clean.py"
    clean_py.write_text("# clean script\nimport sys\n", encoding="utf-8")
    clean_py_sha = pr.compute_file_sha256(clean_py)

    calc_py = scripts_dir / "calc_stats.py"
    calc_py.write_text("# calc script\nimport scipy.stats\n", encoding="utf-8")
    calc_py_sha = pr.compute_file_sha256(calc_py)

    extract_py = scripts_dir / "extract_table.py"
    extract_py.write_text("# extract script\nprint('formatting table')\n", encoding="utf-8")
    extract_py_sha = pr.compute_file_sha256(extract_py)

    # Real physical data files
    raw_csv = data_dir / "raw_survey.csv"
    raw_csv.write_text("subject_id,score,group\n1,10.5,control\n2,14.2,treatment\n", encoding="utf-8")
    raw_sha = pr.compute_file_sha256(raw_csv)

    clean_csv = data_dir / "clean_survey.csv"
    clean_csv.write_text("subject_id,score,group\n1,10.5,control\n2,14.2,treatment\n", encoding="utf-8")
    clean_sha = pr.compute_file_sha256(clean_csv)

    result_json = data_dir / "stats_report.json"
    result_json.write_text('{"t_stat": 2.451, "p_value": 0.018, "df": 48}', encoding="utf-8")
    result_sha = pr.compute_file_sha256(result_json)

    # Build Provenance Graph
    graph = pr.LineageGraph(root_dir=tmp_path)

    # Register Entities
    e_raw = graph.add_entity("ent-raw-survey", "data_snapshot", sha256=raw_sha, locator=str(raw_csv))
    e_clean_script = graph.add_entity("ent-script-clean", "code_file", sha256=clean_py_sha, locator=str(clean_py))
    e_clean = graph.add_entity("ent-clean-survey", "data_snapshot", sha256=clean_sha, locator=str(clean_csv))
    e_stats_script = graph.add_entity("ent-script-stats", "code_file", sha256=calc_py_sha, locator=str(calc_py))
    e_result = graph.add_entity("ent-stats-report", "statistic_artifact", sha256=result_sha, locator=str(result_json))
    e_extract_script = graph.add_entity("ent-script-extract", "code_file", sha256=extract_py_sha, locator=str(extract_py))
    e_cell = graph.add_entity(
        "ent-table-cell-b7",
        "table_cell",
        locator="paper.pdf#page=4:table=2:cell=B7",
        metadata={"reported_value": "t = 2.45"}
    )

    # Register 3 distinct Activities
    act_clean = graph.add_activity(
        "act-data-cleaning",
        "data_cleaning",
        command="python scripts/clean.py --input raw.csv",
        script_id=e_clean_script.id,
        commit_sha="94330ee505d521d645aa4b99bcea0b17bc00b897",
        parameters={"drop_na": True},
    )
    act_calc = graph.add_activity(
        "act-computation-stats",
        "statistical_analysis",
        command="python scripts/calc_stats.py --data clean.csv",
        script_id=e_stats_script.id,
        commit_sha="80384ba97284b9956b4b878e4eb18533bbe87360",
        parameters={"test": "independent_t_test"},
    )
    act_extract = graph.add_activity(
        "act-table-extraction",
        "table_extraction",
        command="python scripts/extract_table.py --source stats.json",
        script_id=e_extract_script.id,
        commit_sha="ca2e9d29e462542e347f7b9626afe2f880123456",
        parameters={"target_table": "Table 2", "cell": "B7"},
    )

    # Connect Causal Edges
    # Phase 1: Cleaning
    graph.record_used(act_clean.id, e_raw.id)
    graph.record_used(act_clean.id, e_clean_script.id)
    graph.record_generated(act_clean.id, e_clean.id)

    # Phase 2: Statistical computation
    graph.record_used(act_calc.id, e_clean.id)
    graph.record_used(act_calc.id, e_stats_script.id)
    graph.record_generated(act_calc.id, e_result.id)

    # Phase 3: Table extraction
    graph.record_used(act_extract.id, e_result.id)
    graph.record_used(act_extract.id, e_extract_script.id)
    graph.record_generated(act_extract.id, e_cell.id)
    graph.record_derivation(e_cell.id, e_result.id, activity_id=act_extract.id)

    # Validation
    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert v_stat == "intact"
    assert t_stat == "valid_dag"
    assert c_stat == "fully_verified"
    assert err is None

    # Benchmark sub-100ms backtrace
    t0 = time.perf_counter()
    receipt = pr.trace_origin(graph, target_id="ent-table-cell-b7", check_on_disk_hashes=True)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    assert latency_ms < 100.0, f"Latency {latency_ms:.2f}ms exceeded 100ms threshold"

    assert receipt.verification_status == "intact"
    assert receipt.topology_status == "valid_dag"
    assert receipt.content_verification == "fully_verified"
    assert "ent-raw-survey" in receipt.root_ancestors
    assert "ent-script-clean" in receipt.root_ancestors
    assert "ent-script-stats" in receipt.root_ancestors
    assert "ent-script-extract" in receipt.root_ancestors

    # Must contain all 3 sequential activities in topological order
    assert len(receipt.trace_steps) == 3
    assert receipt.trace_steps[0]["activity_id"] == "act-data-cleaning"
    assert receipt.trace_steps[1]["activity_id"] == "act-computation-stats"
    assert receipt.trace_steps[2]["activity_id"] == "act-table-extraction"


def test_missing_file_with_declared_sha_triggers_missing_artifact(tmp_path):
    """P1-01: An entity declaring SHA256 and local locator must fail with missing_artifact if file is missing."""
    graph = pr.LineageGraph()
    fake_path = tmp_path / "ghost_file.csv"
    assert not fake_path.exists()

    graph.add_entity(
        "e_ghost",
        "data_snapshot",
        sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        locator=str(fake_path),
    )

    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert v_stat == "missing_artifact"
    assert c_stat == "missing_artifact"
    assert "does not exist on disk" in err

    receipt = pr.trace_origin(graph, target_id="e_ghost", check_on_disk_hashes=True)
    assert receipt.verification_status == "missing_artifact"


def test_tamper_evident_hash_mismatch(tmp_path):
    """P1-01: If on-disk file content is altered, validation must return hash_mismatch."""
    f = tmp_path / "file.csv"
    f.write_text("orig_content", encoding="utf-8")
    sha = pr.compute_file_sha256(f)

    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot", sha256=sha, locator=str(f))

    # Alter file
    f.write_text("tampered_content", encoding="utf-8")
    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert v_stat == "hash_mismatch"
    assert c_stat == "hash_mismatch"
    assert "Content hash mismatch on entity 'e1'" in err


def test_idempotent_registration_and_conflict_rejection():
    """P1-02: Repeated insert of identical entity/activity is idempotent; conflicting insert raises ValueError."""
    graph = pr.LineageGraph()
    e1 = graph.add_entity("e1", "data_snapshot", sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    e1_dup = graph.add_entity("e1", "data_snapshot", sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    assert e1 is e1_dup

    with pytest.raises(ValueError, match="Conflicting entity registration"):
        graph.add_entity("e1", "code_file")  # Type conflict

    act1 = graph.add_activity("act1", "data_cleaning", command="run clean")
    act1_dup = graph.add_activity("act1", "data_cleaning", command="run clean")
    assert act1 is act1_dup

    with pytest.raises(ValueError, match="Conflicting activity registration"):
        graph.add_activity("act1", "computation_run")  # Type conflict


def test_disjoint_entity_and_activity_id_namespace():
    """P1-03: Entity and Activity must have disjoint ID namespaces."""
    graph = pr.LineageGraph()
    graph.add_entity("shared_id", "data_snapshot")

    with pytest.raises(ValueError, match="already registered as an entity"):
        graph.add_activity("shared_id", "computation_run")

    graph2 = pr.LineageGraph()
    graph2.add_activity("shared_id_2", "computation_run")
    with pytest.raises(ValueError, match="already registered as an activity"):
        graph2.add_entity("shared_id_2", "data_snapshot")


def test_immutable_receipt_and_deep_isolation():
    """P1-04: Receipt is deeply immutable; mutating graph or to_dict() results does not alter receipt."""
    graph = pr.LineageGraph()
    e1 = graph.add_entity("e1", "data_snapshot", metadata={"version": 1})
    act = graph.add_activity("act1", "data_cleaning", parameters={"flag": True})
    graph.record_used(act.id, e1.id)

    receipt = pr.trace_origin(graph, target_id=act.id, check_on_disk_hashes=False)

    # Mutate original graph entity metadata
    e1.metadata["version"] = 999
    assert receipt.entities[0]["metadata"]["version"] == 1

    # Mutate receipt to_dict() output
    d = receipt.to_dict()
    d["entities"][0]["metadata"]["version"] = 888
    assert receipt.entities[0]["metadata"]["version"] == 1


def test_verification_coverage_states_not_collapsed():
    """P1-05: check_on_disk_hashes=False or unhashed entities must report 'unchecked', not 'intact'."""
    graph = pr.LineageGraph()
    e1 = graph.add_entity("e1", "data_snapshot")  # No SHA, no locator

    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert v_stat == "unchecked"
    assert t_stat == "valid_dag"
    assert c_stat == "unchecked"

    receipt = pr.trace_origin(graph, target_id="e1", check_on_disk_hashes=False)
    assert receipt.verification_status == "unchecked"
    assert receipt.content_verification == "unchecked"


def test_derivation_activity_referential_integrity():
    """P1-06: derived_from referencing a missing activity_id must fail validation."""
    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot")
    graph.add_entity("e2", "data_snapshot")
    graph.record_derivation("e2", "e1", activity_id="non_existent_activity")

    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert v_stat == "broken_chain"
    assert "non_existent_activity" in err


def test_deterministic_canonical_receipt_digest_and_collision_free():
    """P1-08: Same graph & target produces identical digest & ID; any state difference alters digest."""
    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot")
    graph.add_entity("e2", "data_snapshot")
    graph.record_derivation("e2", "e1")

    r1 = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=False)
    time.sleep(0.01)
    r2 = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=False)

    assert r1.content_digest == r2.content_digest
    assert r1.receipt_id == r2.receipt_id

    # Alter graph state
    graph.add_entity("e3", "data_snapshot")
    graph.record_derivation("e2", "e3")
    r3 = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=False)

    assert r3.content_digest != r1.content_digest
    assert r3.receipt_id != r1.receipt_id


def test_strict_type_and_sha_format_validation():
    """P1-09: Invalid entity/activity types or malformed SHA256 must fail fast."""
    graph = pr.LineageGraph()
    with pytest.raises(ValueError, match="Invalid entity type"):
        graph.add_entity("e_bad", "nonsense_type")

    with pytest.raises(ValueError, match="Invalid activity type"):
        graph.add_activity("a_bad", "nonsense_type")

    with pytest.raises(ValueError, match="Invalid SHA256 format"):
        graph.add_entity("e_bad_sha", "data_snapshot", sha256="not_a_valid_sha256")


def test_single_producer_invariant():
    """P1-10: An Entity cannot be generated by more than one Activity."""
    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot")
    graph.add_activity("act1", "data_cleaning")
    graph.add_activity("act2", "data_cleaning")

    graph.record_generated("act1", "e1")
    with pytest.raises(ValueError, match="Single-producer violation"):
        graph.record_generated("act2", "e1")


def test_script_id_referential_integrity():
    """P1-11: script_id must reference an existing code_file entity."""
    graph = pr.LineageGraph()
    graph.add_activity("act1", "data_cleaning", script_id="missing_script")

    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert v_stat == "missing_input"
    assert "missing script entity" in err

    # Non code_file entity
    graph2 = pr.LineageGraph()
    graph2.add_entity("not_code", "data_snapshot")
    graph2.add_activity("act2", "data_cleaning", script_id="not_code")
    v_stat2, t_stat2, c_stat2, err2 = pr.validate_lineage(graph2, check_on_disk_hashes=False)
    assert v_stat2 == "broken_chain"
    assert "not a 'code_file' entity" in err2


def test_target_scoped_isolation_from_unrelated_broken_nodes():
    """P2: An unrelated broken component does not invalidate a valid target's trace."""
    graph = pr.LineageGraph()
    # Target subgraph: e1 -> e2
    graph.add_entity("e1", "data_snapshot")
    graph.add_entity("e2", "data_snapshot")
    graph.record_derivation("e2", "e1")

    # Unrelated broken cycle component: c1 -> c2 -> c1
    graph.add_entity("c1", "data_snapshot")
    graph.add_entity("c2", "data_snapshot")
    graph.record_derivation("c2", "c1")
    graph.record_derivation("c1", "c2")

    # Tracing e2 should succeed because e2's ancestor closure does not include c1/c2
    receipt = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=False)
    assert receipt.verification_status == "unchecked"
    assert receipt.topology_status == "valid_dag"
    assert receipt.target_id == "e2"


def test_deep_lineage_chain_no_recursion_error():
    """P3: Linear chain of 1500 derivation steps must not trigger RecursionError."""
    graph = pr.LineageGraph()
    n_nodes = 1500
    for i in range(n_nodes):
        graph.add_entity(f"node_{i}", "data_snapshot")
        if i > 0:
            graph.record_derivation(f"node_{i}", f"node_{i-1}")

    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert v_stat == "unchecked"
    assert t_stat == "valid_dag"

    receipt = pr.trace_origin(graph, target_id=f"node_{n_nodes-1}", check_on_disk_hashes=False)
    assert receipt.topology_status == "valid_dag"
    assert receipt.root_ancestors == ("node_0",)


def test_json_schema_draft_2020_12_validation(tmp_path):
    """LineageReceipt payload must validate against schemas/lineage-receipt.schema.json (2020-12 strict)."""
    schema_file = ROOT / "schemas/lineage-receipt.schema.json"
    schema = json.loads(schema_file.read_text(encoding="utf-8"))

    graph = pr.LineageGraph()
    e_raw = graph.add_entity("raw_1", "data_snapshot", sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    e_out = graph.add_entity("res_1", "statistic_artifact", sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    act = graph.add_activity("clean_1", "data_cleaning", command="python clean.py")

    graph.record_used(act.id, e_raw.id)
    graph.record_generated(act.id, e_out.id)
    graph.record_derivation(e_out.id, e_raw.id, activity_id=act.id)

    receipt = pr.trace_origin(graph, target_id=e_out.id, check_on_disk_hashes=False)
    payload = receipt.to_dict()

    # Draft 2020-12 validation
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(payload)
    assert payload["protocol"] == "lineage-receipt-1.0"
    assert payload["verification_status"] == "unchecked"
    assert payload["topology_status"] == "valid_dag"
    assert payload["root_ancestors"] == ["raw_1"]
    assert len(payload["lineage_digest"]) == 64
    assert len(payload["receipt_digest"]) == 64
    assert len(payload["content_digest"]) == 64


def test_partial_verification_cannot_be_intact(tmp_path):
    """P1: partially_verified content MUST NOT yield verification_status='intact'."""
    f = tmp_path / "local.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    local_sha = pr.compute_file_sha256(f)

    graph = pr.LineageGraph()
    # 1 local file that is verified
    graph.add_entity("e_local", "data_snapshot", sha256=local_sha, locator=str(f))
    # 1 remote HTTP entity whose bytes are not locally verified
    graph.add_entity("e_remote", "data_snapshot", sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", locator="https://example.com/data.csv")
    graph.record_derivation("e_local", "e_remote")

    v_stat, t_stat, c_stat, err = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert v_stat == "partial", f"Expected 'partial', got {v_stat!r}"
    assert c_stat == "partially_verified"
    assert v_stat != "intact"

    # Pure remote case: no local files verified at all
    graph_remote = pr.LineageGraph()
    graph_remote.add_entity("e_rem_only", "data_snapshot", sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", locator="https://example.com/data.csv")
    v_rem, t_rem, c_rem, _ = pr.validate_lineage(graph_remote, check_on_disk_hashes=True)
    assert v_rem == "unchecked"
    assert c_rem == "unverified"
    assert v_rem != "intact"


def test_lineage_digest_separated_from_receipt_digest():
    """P1: lineage_digest identifies graph content; receipt_digest identifies verification verdict."""
    graph = pr.LineageGraph()
    e1 = graph.add_entity("e1", "data_snapshot")
    e2 = graph.add_entity("e2", "data_snapshot")
    graph.record_derivation("e2", "e1")

    # Mode 1: check_on_disk_hashes=False -> unchecked
    r_uncheck = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=False)
    # Mode 2: check_on_disk_hashes=True -> intact (or unchecked for unhashed)
    r_check = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=True)

    # Lineage content digest MUST be identical because the graph structure did not change
    assert r_uncheck.lineage_digest == r_check.lineage_digest
    # But receipt_digest and receipt_id MUST differ because verification mode/assessment differs
    assert r_uncheck.receipt_digest != r_check.receipt_digest
    assert r_uncheck.receipt_id != r_check.receipt_id


def test_edge_exact_idempotence_and_distinct_activity_derivations_retained():
    """P1/P2: record_* is exact-idempotent, and derivations via distinct activities are NOT swallowed."""
    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot")
    graph.add_entity("e2", "data_snapshot")
    graph.add_activity("act_a", "data_cleaning")
    graph.add_activity("act_b", "data_cleaning")

    # Repeat exact same edge -> idempotent, edge count remains 1
    graph.record_derivation("e2", "e1", activity_id="act_a")
    graph.record_derivation("e2", "e1", activity_id="act_a")
    assert len(graph.edges) == 1

    # Derivation via different activity -> distinct edge, count becomes 2
    graph.record_derivation("e2", "e1", activity_id="act_b")
    assert len(graph.edges) == 2

    # In trace_origin, BOTH derivation edges must be retained in receipt.edges
    receipt = pr.trace_origin(graph, target_id="e2", check_on_disk_hashes=False)
    assert len(receipt.edges) == 2
    edge_acts = {ed.get("activity_id") for ed in receipt.edges}
    assert edge_acts == {"act_a", "act_b"}


def test_activity_timestamp_idempotence_conflict():
    """P2: Registering an Activity with same ID but different explicit timestamp must raise ValueError."""
    graph = pr.LineageGraph()
    graph.add_activity("act_ts", "data_cleaning", timestamp="2026-09-18T10:00:00Z")

    # Same timestamp -> idempotent
    act_same = graph.add_activity("act_ts", "data_cleaning", timestamp="2026-09-18T10:00:00Z")
    assert act_same.id == "act_ts"

    # Different timestamp -> conflict rejection
    with pytest.raises(ValueError, match="Conflicting activity registration"):
        graph.add_activity("act_ts", "data_cleaning", timestamp="2026-09-18T12:00:00Z")


def test_failed_receipts_have_distinct_deterministic_ids():
    """P2: Failures must produce distinct deterministic receipt IDs rather than colliding constants."""
    graph = pr.LineageGraph()
    graph.add_entity("e_present", "data_snapshot")

    r_missing1 = pr.trace_origin(graph, target_id="ghost_target_1", check_on_disk_hashes=False)
    r_missing2 = pr.trace_origin(graph, target_id="ghost_target_2", check_on_disk_hashes=False)

    assert r_missing1.receipt_id != r_missing2.receipt_id
    assert not r_missing1.receipt_id.startswith("lin-missing")
    assert r_missing1.receipt_id.startswith("rec-")

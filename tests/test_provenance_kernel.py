# -*- coding: utf-8 -*-
"""Deterministic regression tests for Research Object Provenance Kernel v1.

Covers:
1. Content-addressed entity hashing and W3C PROV-DM tri-structures.
2. End-to-end scientific derivation pipeline:
   raw.csv -> clean.py@commit -> clean.csv -> stats.py@commit+env -> report.json -> table-2-cell-B7
3. Sub-100ms deterministic backtrace from table cell to root raw inputs and execution activities.
4. Tamper-evident hash mismatch detection on modified intermediate files.
5. Cyclic dependency and self-derivation detection.
6. Referential integrity on missing activities and inputs.
7. Full JSON Schema parity against schemas/lineage-receipt.schema.json using modern referencing.Registry.
"""
from __future__ import annotations

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

    # Missing file raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        pr.compute_file_sha256(tmp_path / "non_existent.csv")


def test_end_to_end_scientific_lineage_and_trace(tmp_path):
    """Full scientific pipeline backtrace:

    raw.csv -> cleaning_activity -> clean.csv -> stats_activity -> result.json -> table-2-cell-B7
    Asserts sub-100ms deterministic tracing, parameter identification, and root discovery.
    """
    # 1. Physical mock fixture files
    raw_csv = tmp_path / "raw_survey.csv"
    raw_csv.write_text("subject_id,score,group\n1,10.5,control\n2,14.2,treatment\n", encoding="utf-8")
    raw_sha = pr.compute_file_sha256(raw_csv)

    clean_csv = tmp_path / "clean_survey.csv"
    clean_csv.write_text("subject_id,score,group\n1,10.5,control\n2,14.2,treatment\n", encoding="utf-8")
    clean_sha = pr.compute_file_sha256(clean_csv)

    result_json = tmp_path / "stats_report.json"
    result_json.write_text('{"t_stat": 2.451, "p_value": 0.018, "df": 48}', encoding="utf-8")
    result_sha = pr.compute_file_sha256(result_json)

    # 2. Build In-Memory Provenance Graph
    graph = pr.LineageGraph()

    # Entities
    e_raw = graph.add_entity(
        id="ent-raw-survey",
        type="data_snapshot",
        sha256=raw_sha,
        locator=str(raw_csv),
        metadata={"rows": 2, "source": "field_survey_wave1"}
    )
    e_clean_script = graph.add_entity(
        id="ent-script-clean",
        type="code_file",
        sha256="a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
        locator="scripts/clean.py",
        metadata={"commit": "94330ee505d521d645aa4b99bcea0b17bc00b897"}
    )
    e_clean = graph.add_entity(
        id="ent-clean-survey",
        type="data_snapshot",
        sha256=clean_sha,
        locator=str(clean_csv),
        metadata={"rows": 2, "cleaned_by": "clean.py"}
    )
    e_stats_script = graph.add_entity(
        id="ent-script-stats",
        type="code_file",
        sha256="b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01",
        locator="scripts/calc_stats.py",
        metadata={"commit": "80384ba97284b9956b4b878e4eb18533bbe87360"}
    )
    e_result = graph.add_entity(
        id="ent-stats-report",
        type="statistic_artifact",
        sha256=result_sha,
        locator=str(result_json),
        metadata={"metrics": ["t_stat", "p_value"]}
    )
    e_cell = graph.add_entity(
        id="ent-table-cell-b7",
        type="table_cell",
        locator="paper.pdf#page=4:table=2:cell=B7",
        metadata={"reported_value": "t = 2.45", "confidence_interval": "95% CI [0.42, 4.48]"}
    )

    # Activities
    act_clean = graph.add_activity(
        id="act-data-cleaning",
        type="data_cleaning",
        command="python scripts/clean.py --input raw_survey.csv --output clean_survey.csv",
        script_id=e_clean_script.id,
        commit_sha="94330ee505d521d645aa4b99bcea0b17bc00b897",
        parameters={"drop_na": True, "normalize_scales": False},
        environment={"python": "3.11.15", "platform": "linux"}
    )
    act_calc = graph.add_activity(
        id="act-computation-stats",
        type="statistical_analysis",
        command="python scripts/calc_stats.py --data clean_survey.csv --alpha 0.05",
        script_id=e_stats_script.id,
        commit_sha="80384ba97284b9956b4b878e4eb18533bbe87360",
        parameters={"test_type": "independent_t_test", "two_sided": True},
        environment={"python": "3.11.15", "scipy": "1.14.0"}
    )

    # Edges: Causal links
    graph.record_used(act_clean.id, e_raw.id)
    graph.record_used(act_clean.id, e_clean_script.id)
    graph.record_generated(act_clean.id, e_clean.id)

    graph.record_used(act_calc.id, e_clean.id)
    graph.record_used(act_calc.id, e_stats_script.id)
    graph.record_generated(act_calc.id, e_result.id)

    graph.record_derivation(e_cell.id, e_result.id, activity_id=act_calc.id)

    # 3. Deterministic Validation
    status, err = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert status == "intact"
    assert err is None

    # 4. Backward Traversal Benchmark (Must be under 100ms)
    t0 = time.perf_counter()
    receipt = pr.trace_origin(graph, target_id="ent-table-cell-b7", check_on_disk_hashes=True)
    latency_ms = (time.perf_counter() - t0) * 1000.0
    assert latency_ms < 100.0, f"Lineage trace exceeded 100ms latency budget: {latency_ms:.2f}ms"

    # 5. Assertions on Provenance Findings
    assert receipt.verification_status == "intact"
    assert receipt.target_id == "ent-table-cell-b7"
    # Root source dataset must be strictly identified
    assert "ent-raw-survey" in receipt.root_ancestors
    # All intermediate calculation activities must be accurately reconstructed
    act_ids = [a.id for a in receipt.activities]
    assert "act-data-cleaning" in act_ids
    assert "act-computation-stats" in act_ids

    # Step-by-step causal replay
    assert len(receipt.trace_steps) >= 2
    step1 = receipt.trace_steps[0]
    assert step1["activity_id"] == "act-data-cleaning"
    assert "ent-raw-survey" in step1["inputs"]
    assert "ent-clean-survey" in step1["outputs"]

    step2 = receipt.trace_steps[1]
    assert step2["activity_id"] == "act-computation-stats"
    assert "ent-clean-survey" in step2["inputs"]
    assert "ent-stats-report" in step2["outputs"]


def test_tamper_evident_hash_mismatch(tmp_path):
    """If an intermediate file's content is modified on disk, validate_lineage must flag hash_mismatch."""
    f = tmp_path / "intermediate.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    orig_sha = pr.compute_file_sha256(f)

    graph = pr.LineageGraph()
    e1 = graph.add_entity("e1", "data_snapshot", sha256=orig_sha, locator=str(f))
    act = graph.add_activity("a1", "computation_run")
    graph.record_used(act.id, e1.id)

    # Initial state is intact
    status, _ = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert status == "intact"

    # Modify file on disk (Tampering)
    f.write_text("a,b\n1,99999\n", encoding="utf-8")
    status_tampered, err = pr.validate_lineage(graph, check_on_disk_hashes=True)
    assert status_tampered == "hash_mismatch"
    assert "Content hash mismatch on entity 'e1'" in err

    # Tracing this entity returns hash_mismatch receipt
    rec = pr.trace_origin(graph, target_id="e1", check_on_disk_hashes=True)
    assert rec.verification_status == "hash_mismatch"


def test_cycle_detection_in_causal_graph():
    """Cycles in causal lineage graphs must be rejected with cycle_detected."""
    graph = pr.LineageGraph()
    e1 = graph.add_entity("e1", "data_snapshot")
    e2 = graph.add_entity("e2", "data_snapshot")
    act1 = graph.add_activity("act1", "computation_run")
    act2 = graph.add_activity("act2", "computation_run")

    # Cycle: e1 -> act1 -> e2 -> act2 -> e1
    graph.record_used("act1", "e1")
    graph.record_generated("act1", "e2")
    graph.record_used("act2", "e2")
    graph.record_generated("act2", "e1")  # Cycle back!

    status, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert status == "cycle_detected"
    assert "Causal cycle detected" in err


def test_self_derivation_loop_rejected():
    """Self-derivation (A derived_from A) must be immediately rejected with cycle_detected."""
    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot")
    graph.record_derivation("e1", "e1")

    status, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert status == "cycle_detected"
    assert "Self-derivation loop" in err


def test_missing_activity_or_input_referential_integrity():
    """Edges pointing to non-existent nodes must trigger missing_input or broken_chain."""
    graph = pr.LineageGraph()
    graph.add_entity("e1", "data_snapshot")
    # used edge references phantom activity
    graph.record_used("phantom_act", "e1")

    status, err = pr.validate_lineage(graph, check_on_disk_hashes=False)
    assert status == "missing_input"
    assert "phantom_act" in err


def test_lineage_receipt_json_schema_validation(tmp_path):
    """LineageReceipt serialized payload must strictly validate against schemas/lineage-receipt.schema.json."""
    from referencing import Registry, Resource
    from referencing.jsonschema import DRAFT7

    schema_file = ROOT / "schemas/lineage-receipt.schema.json"
    schema = json.loads(schema_file.read_text(encoding="utf-8"))

    graph = pr.LineageGraph()
    e_in = graph.add_entity("raw_1", "data_snapshot", sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
    e_out = graph.add_entity("res_1", "statistic_artifact", sha256="ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    act = graph.add_activity("clean_1", "data_cleaning", command="python clean.py")

    graph.record_used(act.id, e_in.id)
    graph.record_generated(act.id, e_out.id)
    graph.record_derivation(e_out.id, e_in.id, activity_id=act.id)

    receipt = pr.trace_origin(graph, target_id=e_out.id, check_on_disk_hashes=False)
    payload = receipt.to_dict()

    # Validate against schema
    validator = jsonschema.Draft7Validator(schema)
    validator.validate(payload)
    assert payload["protocol"] == "lineage-receipt-1.0"
    assert payload["verification_status"] == "intact"
    assert payload["root_ancestors"] == ["raw_1"]

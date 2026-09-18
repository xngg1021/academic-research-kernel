# -*- coding: utf-8 -*-
"""Deterministic adversarial regression tests for Claim-Evidence Graph Kernel v1.

Covers:
1. Strict type enforcement and fail-fast validation for claims, evidence anchors, and receipt refs.
2. Idempotent registration with conflict rejection (same ID + different payload raises ValueError).
3. Disjoint Claim and EvidenceAnchor ID namespaces (collision raises ValueError).
4. Semantic cycles (A contradicts B, B contradicts A) are valid and preserved without cycle errors.
5. Dangling edge detection (missing claim, missing evidence anchor, or missing evidence_refs).
6. Strongly typed ReceiptRef binding to LineageReceipt and AcademicEvidenceReceipt.
7. LineageReceipt digest mismatch detection.
8. Insertion-order invariance of canonical graph_digest.
9. Metadata sensitivity of graph_digest.
10. Immutability and deep isolation of exported graph representations.
11. Three-state uncertainty queue discipline (unverifiable -> needs_human=False; contradicted -> needs_human=True).
12. Deterministic contradiction discovery without NLP/clustering.
13. Deterministic claim provenance tracing back to LineageReceipt root inputs and execution steps.
14. Explicit failure report when referenced receipt is missing from registry (no silent empty success).
15. Strict JSON Schema draft 2020-12 parity with additionalProperties: false.
"""
from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/claim-evidence-graph/scripts"))
sys.path.insert(0, str(ROOT / "skills/research-object-identity/scripts"))

import graph as ceg
import provenance as pr


def test_claim_lexical_canonicalization_and_digest():
    """Claim text receives NFC and whitespace normalization without semantic rewriting."""
    c1 = ceg.Claim(id="c1", text="  Scaling  laws   hold. \r\n")
    assert c1.normalized_text == "Scaling laws hold."
    # Different target work produces different claim occurrence digest
    c2 = ceg.Claim(id="c2", text="Scaling laws hold.", target_work_id="work-a")
    c3 = ceg.Claim(id="c3", text="Scaling laws hold.", target_work_id="work-b")
    assert c1.claim_digest != c2.claim_digest
    assert c2.claim_digest != c3.claim_digest


def test_idempotent_registration_and_conflict_rejection():
    """Identical claim or evidence is idempotent; conflicting payload raises ValueError."""
    g = ceg.ClaimEvidenceGraph()
    c1 = g.add_claim("c1", "Text A", target_work_id="work-1")
    c1_dup = g.add_claim("c1", "Text A", target_work_id="work-1")
    assert c1 is c1_dup

    with pytest.raises(ValueError, match="Conflicting claim registration"):
        g.add_claim("c1", "Conflicting Text B")

    ev1 = g.add_evidence("ev1", "table_cell", locator="tab:1:cell:A1")
    ev1_dup = g.add_evidence("ev1", "table_cell", locator="tab:1:cell:A1")
    assert ev1 is ev1_dup

    with pytest.raises(ValueError, match="Conflicting evidence registration"):
        g.add_evidence("ev1", "figure_artifact")  # Type conflict


def test_disjoint_claim_and_evidence_namespace():
    """Claim and EvidenceAnchor must have disjoint ID namespaces."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("shared_id", "A claim")
    with pytest.raises(ValueError, match="already registered as a claim"):
        g.add_evidence("shared_id", "table_cell")

    g2 = ceg.ClaimEvidenceGraph()
    g2.add_evidence("shared_id_2", "table_cell")
    with pytest.raises(ValueError, match="already registered as an evidence anchor"):
        g2.add_claim("shared_id_2", "A claim")


def test_semantic_cycles_are_valid_and_preserved():
    """Unlike provenance DAGs, semantic claim relations may cycle naturally (e.g. mutual contradiction)."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c_a", "Model A outperforms Model B on benchmark X.")
    g.add_claim("c_b", "Model B outperforms Model A on benchmark X.")

    # Mutual contradiction cycle: A <-> B
    g.add_claim_relation("c_a", "c_b", relation_type="contradicts")
    g.add_claim_relation("c_b", "c_a", relation_type="contradicts")

    valid, errors = g.validate_graph()
    assert valid is True
    assert not errors

    # Contradiction discovery retrieves conflicting claim deterministically
    contras_a = g.find_contradictions("c_a")
    assert len(contras_a) == 1
    assert contras_a[0]["conflicting_claim_id"] == "c_b"

    contras_b = g.find_contradictions("c_b")
    assert len(contras_b) == 1
    assert contras_b[0]["conflicting_claim_id"] == "c_a"


def test_dangling_edge_detection():
    """Edges pointing to non-existent claims or evidence anchors must fail validation."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c1", "Claim 1")

    # 1. Dangling EvidenceSupportEdge (missing evidence anchor)
    g.add_support_edge("ghost_ev", "c1", support_status="supported")
    valid, errors = g.validate_graph()
    assert valid is False
    assert any("ghost_ev" in err for err in errors)

    # 2. Dangling ClaimRelationEdge (missing target claim)
    g2 = ceg.ClaimEvidenceGraph()
    g2.add_claim("c1", "Claim 1")
    g2.add_claim_relation("c1", "ghost_target", relation_type="cites")
    valid2, errors2 = g2.validate_graph()
    assert valid2 is False
    assert any("ghost_target" in err for err in errors2)

    # 3. Dangling evidence_ref in ClaimRelationEdge
    g3 = ceg.ClaimEvidenceGraph()
    g3.add_claim("c1", "Claim 1")
    g3.add_claim("c2", "Claim 2")
    g3.add_claim_relation("c1", "c2", relation_type="corroborates", evidence_refs=["missing_ev_anchor"])
    valid3, errors3 = g3.validate_graph()
    assert valid3 is False
    assert any("missing_ev_anchor" in err for err in errors3)


def test_receipt_ref_strongly_typed_validation():
    """ReceiptRef validates supported kinds and 64-hex digest patterns."""
    with pytest.raises(ValueError, match="Invalid receipt kind"):
        ceg.ReceiptRef(kind="invalid_kind", schema_version="1.0")

    with pytest.raises(ValueError, match="Invalid receipt_digest SHA256"):
        ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_digest="bad_digest")


def test_lineage_receipt_digest_mismatch_detection():
    """If registered LineageReceipt has a different digest than declared, validate_graph must flag mismatch."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c1", "Claim 1")

    # Registered mock receipt with digest 'aaa...aaa'
    mock_receipt = {
        "receipt_id": "rec-12345",
        "receipt_digest": "a" * 64,
        "lineage_digest": "b" * 64,
        "verification_status": "intact",
    }
    g.register_receipt("rec-12345", mock_receipt)

    # Evidence anchor declaring different digest 'ccc...ccc'
    ref = ceg.ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id="rec-12345",
        receipt_digest="c" * 64,
    )
    g.add_evidence("ev1", "lineage_receipt", receipt_ref=ref)
    g.add_support_edge("ev1", "c1", support_status="supported")

    valid, errors = g.validate_graph()
    assert valid is False
    assert any("Receipt digest mismatch" in err for err in errors)


def test_insertion_order_invariance_of_graph_digest():
    """Same graph content with different insertion orders must produce identical graph_digest."""
    # Graph A
    ga = ceg.ClaimEvidenceGraph(graph_id="ceg-fixed")
    ga.add_claim("c1", "First claim")
    ga.add_claim("c2", "Second claim")
    ga.add_evidence("ev1", "table_cell")
    ga.add_evidence("ev2", "figure_artifact")
    ga.add_support_edge("ev1", "c1", support_status="supported")
    ga.add_support_edge("ev2", "c2", support_status="supported")
    ga.add_claim_relation("c1", "c2", relation_type="corroborates")

    # Graph B (reversed insertion order)
    gb = ceg.ClaimEvidenceGraph(graph_id="ceg-fixed")
    gb.add_evidence("ev2", "figure_artifact")
    gb.add_evidence("ev1", "table_cell")
    gb.add_claim("c2", "Second claim")
    gb.add_claim("c1", "First claim")
    gb.add_claim_relation("c1", "c2", relation_type="corroborates")
    gb.add_support_edge("ev2", "c2", support_status="supported")
    gb.add_support_edge("ev1", "c1", support_status="supported")

    assert ga.graph_digest() == gb.graph_digest()

    # Altering metadata produces a different digest
    gc = ceg.ClaimEvidenceGraph(graph_id="ceg-fixed")
    gc.add_claim("c1", "First claim", metadata={"note": "different"})
    gc.add_claim("c2", "Second claim")
    gc.add_evidence("ev1", "table_cell")
    gc.add_evidence("ev2", "figure_artifact")
    gc.add_support_edge("ev1", "c1", support_status="supported")
    gc.add_support_edge("ev2", "c2", support_status="supported")
    gc.add_claim_relation("c1", "c2", relation_type="corroborates")

    assert ga.graph_digest() != gc.graph_digest()


def test_deep_isolation_of_exported_representation():
    """Mutating graph entities or exported to_dict() results must not cross-contaminate."""
    g = ceg.ClaimEvidenceGraph()
    c = g.add_claim("c1", "Original text", metadata={"ver": 1})
    d = g.to_dict()

    # Mutate source metadata
    c.metadata["ver"] = 999
    assert d["claims"][0]["metadata"]["ver"] == 1

    # Mutate exported dict
    d["claims"][0]["metadata"]["ver"] = 888
    d2 = g.to_dict()
    assert d2["claims"][0]["metadata"]["ver"] == 999


def test_three_state_uncertainty_discipline():
    """Unverifiable -> needs_human=False; Contradicted -> needs_human=True."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c_unverifiable", "Speculative hypothesis about year 2050.")
    g.add_evidence("ev_unverifiable", "direct_observation")
    # unverifiable support
    g.add_support_edge("ev_unverifiable", "c_unverifiable", support_status="unverifiable")

    g.add_claim("c_contradicted", "Claim refuted by experimental trial.")
    g.add_evidence("ev_refuting", "table_cell")
    # contradicted support
    g.add_support_edge("ev_refuting", "c_contradicted", support_status="contradicted")

    uncertainties = g.extract_uncertainties()
    assert len(uncertainties) == 2

    u_map = {u.subject_id: u for u in uncertainties}
    assert u_map["c_unverifiable"].needs_human is False
    assert u_map["c_contradicted"].needs_human is True


def test_trace_claim_provenance_with_missing_receipt():
    """Tracing provenance of a claim with missing receipt reports explicit unavailable status (no empty success)."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c1", "Claim backed by missing receipt.")
    ref = ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="rec-missing-ghost")
    g.add_evidence("ev1", "lineage_receipt", receipt_ref=ref)
    g.add_support_edge("ev1", "c1", support_status="supported")

    trace = g.trace_claim_provenance("c1")
    assert trace["status"] == "traced"
    assert len(trace["lineage_traces"]) == 1
    t0 = trace["lineage_traces"][0]
    assert t0["status"] == "unavailable"
    assert "not found in registry" in t0["reason"]


def test_end_to_end_claim_to_provenance_penetration(tmp_path):
    """Full penetration: Claim -> EvidenceAnchor -> LineageReceipt -> root data & execution steps."""
    # 1. Build an underlying LineageGraph and emit a LineageReceipt (using PR #6 Provenance Kernel)
    clean_py = tmp_path / "clean.py"
    clean_py.write_text("import sys\n", encoding="utf-8")
    clean_py_sha = pr.compute_file_sha256(clean_py)

    raw_csv = tmp_path / "raw.csv"
    raw_csv.write_text("x,y\n1,2\n", encoding="utf-8")
    raw_sha = pr.compute_file_sha256(raw_csv)

    clean_csv = tmp_path / "clean.csv"
    clean_csv.write_text("x,y\n1,2\n", encoding="utf-8")
    clean_sha = pr.compute_file_sha256(clean_csv)

    lin_graph = pr.LineageGraph(root_dir=tmp_path)
    e_raw = lin_graph.add_entity("raw-data", "data_snapshot", sha256=raw_sha, locator=str(raw_csv))
    e_script = lin_graph.add_entity("clean-script", "code_file", sha256=clean_py_sha, locator=str(clean_py))
    e_clean = lin_graph.add_entity("clean-data", "data_snapshot", sha256=clean_sha, locator=str(clean_csv))
    act = lin_graph.add_activity("clean-act", "data_cleaning", command="python clean.py", script_id=e_script.id)

    lin_graph.record_used(act.id, e_raw.id)
    lin_graph.record_used(act.id, e_script.id)
    lin_graph.record_generated(act.id, e_clean.id)

    lineage_receipt = pr.trace_origin(lin_graph, target_id=e_clean.id, check_on_disk_hashes=True)
    assert lineage_receipt.verification_status == "intact"

    # 2. Build ClaimEvidenceGraph and anchor to the LineageReceipt
    ce_graph = ceg.ClaimEvidenceGraph(graph_id="ceg-scientific-audit")
    ce_graph.register_receipt(lineage_receipt.receipt_id, lineage_receipt)

    c_main = ce_graph.add_claim(
        id="claim-clean-integrity",
        text="The cleaned survey data maintains full participant representation without attrition.",
        target_work_id="work-2026-audit",
        locator="paper.pdf#p=3",
    )

    ev_anchor = ce_graph.add_evidence(
        id="ev-lineage-proof",
        anchor_type="lineage_receipt",
        receipt_ref=ceg.ReceiptRef(
            kind="lineage",
            schema_version="lineage-receipt-1.0",
            receipt_id=lineage_receipt.receipt_id,
            receipt_digest=lineage_receipt.receipt_digest,
        ),
        excerpt="Lineage intact with zero data loss."
    )

    ce_graph.add_support_edge(ev_anchor.id, c_main.id, support_status="supported")

    # 3. Penetrate provenance directly from Claim!
    trace_res = ce_graph.trace_claim_provenance("claim-clean-integrity")
    assert trace_res["status"] == "traced"
    assert trace_res["claim_id"] == "claim-clean-integrity"

    trace_lineage = trace_res["lineage_traces"][0]
    assert trace_lineage["status"] == "available"
    assert trace_lineage["verification_status"] == "intact"
    assert "raw-data" in trace_lineage["root_ancestors"]
    assert len(trace_lineage["trace_steps"]) == 1
    assert trace_lineage["trace_steps"][0]["activity_id"] == "clean-act"


def test_json_schema_draft_2020_12_validation():
    """Exported ClaimEvidenceGraph dictionary strictly matches schemas/claim-evidence-graph.schema.json."""
    schema_path = ROOT / "schemas/claim-evidence-graph.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    g = ceg.ClaimEvidenceGraph(graph_id="ceg-schema-test")
    c1 = g.add_claim("c1", "Claim A", target_work_id="w1", locator="p.1", claim_type="empirical_finding")
    c2 = g.add_claim("c2", "Claim B", target_work_id="w2", locator="p.2", claim_type="benchmark_result")
    ev1 = g.add_evidence("ev1", "table_cell", source_work_id="w1", locator="tab:1", excerpt="12.4%")

    g.add_support_edge("ev1", "c1", support_status="supported")
    g.add_claim_relation("c1", "c2", relation_type="corroborates", evidence_refs=["ev1"])

    payload = g.to_dict()

    # Draft 2020-12 validation
    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(payload)
    assert payload["protocol"] == "claim-evidence-graph-1.0"
    assert payload["graph_id"] == "ceg-schema-test"
    assert len(payload["graph_digest"]) == 64

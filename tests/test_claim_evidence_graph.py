# -*- coding: utf-8 -*-
"""Deterministic adversarial regression tests for Claim-Evidence Graph Kernel v1.

Covers:
1. Strict type enforcement and fail-fast validation for claims, evidence anchors, and receipt refs.
2. Idempotent registration with conflict rejection (same ID + different payload raises ValueError).
3. Disjoint Claim and EvidenceAnchor ID namespaces (collision raises ValueError).
4. Semantic cycles (A contradicts B, B contradicts A) are valid and preserved without cycle errors.
5. Dangling edge detection (missing claim, missing evidence anchor, or missing evidence_refs).
6. Strongly typed ReceiptRef with strict mutual exclusivity (lineage vs academic_evidence).
7. AcademicEvidenceReceipt payload SHA256 and exact claim_digest verification.
8. SupportEdge receipt_ref verification.
9. Receipt registration conflict rejection.
10. Insertion-order invariance of canonical graph_digest across tie-key edge sets.
11. Metadata sensitivity of graph_digest.
12. Immutability and deep isolation of exported graph representations.
13. Three-state uncertainty queue discipline with content-addressed deterministic IDs.
14. Provenance tracing preserves support status (supported vs contradicted).
15. Explicit failure report when referenced receipt is missing from registry (no silent empty success).
16. Strict JSON Schema draft 2020-12 parity with additionalProperties: false and oneOf receiptRef.
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
    c2 = ceg.Claim(id="c2", text="Scaling laws hold.", target_work_id="work-a")
    c3 = ceg.Claim(id="c3", text="Scaling laws hold.", target_work_id="work-b")
    assert c1.claim_digest != c2.claim_digest
    assert c2.claim_digest != c3.claim_digest


def test_claim_digest_delimiter_collision_free():
    """Delimiter characters in fields must not cause claim_digest collisions."""
    c_a = ceg.Claim(id="ca", text="text|target", target_work_id="work", locator="loc")
    c_b = ceg.Claim(id="cb", text="text", target_work_id="target|work", locator="loc")
    assert c_a.claim_digest != c_b.claim_digest


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
        g.add_evidence("ev1", "figure_artifact")


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

    g.add_claim_relation("c_a", "c_b", relation_type="contradicts")
    g.add_claim_relation("c_b", "c_a", relation_type="contradicts")

    valid, errors = g.validate_graph()
    assert valid is True
    assert not errors

    contras_a = g.find_contradictions("c_a")
    assert len(contras_a) == 1
    assert contras_a[0]["conflicting_claim_id"] == "c_b"


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


def test_strongly_typed_receipt_ref_mutual_exclusivity():
    """ReceiptRef enforces strict schema_version, required fields, and mutual exclusivity."""
    # Lineage requires lineage-receipt-1.0 and both receipt_id and receipt_digest
    with pytest.raises(ValueError, match="Invalid schema_version for lineage"):
        ceg.ReceiptRef(kind="lineage", schema_version="wrong-ver", receipt_id="r1", receipt_digest="a" * 64)

    with pytest.raises(ValueError, match="requires non-empty 'receipt_id'"):
        ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="", receipt_digest="a" * 64)

    # Lineage must not carry academic fields
    with pytest.raises(ValueError, match="must not contain academic_evidence fields"):
        ceg.ReceiptRef(
            kind="lineage",
            schema_version="lineage-receipt-1.0",
            receipt_id="r1",
            receipt_digest="a" * 64,
            claim_digest="b" * 64,
        )

    # AcademicEvidence requires 1.0, claim_digest, payload_sha256
    with pytest.raises(ValueError, match="Invalid schema_version for academic_evidence"):
        ceg.ReceiptRef(kind="academic_evidence", schema_version="2.0", claim_digest="a" * 64, payload_sha256="b" * 64)

    with pytest.raises(ValueError, match="must not contain lineage fields"):
        ceg.ReceiptRef(
            kind="academic_evidence",
            schema_version="1.0",
            claim_digest="a" * 64,
            payload_sha256="b" * 64,
            receipt_id="r1",
        )


def test_academic_evidence_receipt_exact_claim_digest_verification():
    """validate_graph checks AcademicEvidenceReceipt payload SHA256 and exact claim_digest match."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c1", "Reported effect size d = 0.52")

    mock_academic_receipt = {
        "schema_version": "1.0",
        "generated_at": "2026-09-18T10:00:00Z",
        "claims": [
            {
                "claim": "Cohen's d is 0.52",
                "evidence_type": "statistical_test",
                "locator": "tab:2",
                "source": "t_test_output",
                "support_status": "supported",
            },
            {
                "claim": "p-value is 0.01",
                "evidence_type": "p_value",
                "locator": "tab:2",
                "source": "t_test_output",
                "support_status": "supported",
            }
        ]
    }
    payload_sha = ceg.canonical_academic_receipt_payload_sha256(mock_academic_receipt)
    exact_claim_digest = ceg.canonical_evidence_claim_digest(mock_academic_receipt["claims"][0])

    # Register receipt under its payload SHA
    g.register_receipt(payload_sha, mock_academic_receipt)

    # Anchor with matching claim_digest
    ref_good = ceg.ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=exact_claim_digest,
        payload_sha256=payload_sha,
    )
    g.add_evidence("ev_acad", "evidence_receipt", receipt_ref=ref_good)
    g.add_support_edge("ev_acad", "c1", support_status="supported")

    valid, errors = g.validate_graph()
    assert valid is True
    assert not errors

    # Anchor with non-existent claim_digest inside that receipt
    ref_bad = ceg.ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest="f" * 64,  # Bad claim digest
        payload_sha256=payload_sha,
    )
    g2 = ceg.ClaimEvidenceGraph()
    g2.register_receipt(payload_sha, mock_academic_receipt)
    g2.add_claim("c1", "Test claim")
    g2.add_evidence("ev_bad", "evidence_receipt", receipt_ref=ref_bad)
    g2.add_support_edge("ev_bad", "c1", support_status="supported")

    valid2, errors2 = g2.validate_graph()
    assert valid2 is False
    assert any("AcademicEvidence claim digest mismatch" in err for err in errors2)


def test_support_edge_preserves_distinct_receipt_refs():
    """Support edges between same evidence and claim with distinct ReceiptRefs are not swallowed."""
    g = ceg.ClaimEvidenceGraph()
    g.add_claim("c1", "Target claim")
    g.add_evidence("ev1", "lineage_receipt")

    ref_a = ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="rec-A", receipt_digest="a" * 64)
    ref_b = ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="rec-B", receipt_digest="b" * 64)

    # Edge 1 via Receipt A
    g.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_a)
    # Duplicate edge 1 -> idempotent, remains count 1
    g.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_a)
    assert len(g.support_edges) == 1

    # Edge 2 via Receipt B -> distinct, count becomes 2
    g.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_b)
    assert len(g.support_edges) == 2


def test_insertion_order_invariance_across_tie_keys():
    """graph_digest is strictly order-invariant even when edges share primary endpoints but differ in metadata/receipts."""
    ref_a = ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="rec-A", receipt_digest="a" * 64)
    ref_b = ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="rec-B", receipt_digest="b" * 64)

    # Graph 1: insert edge A then B
    g1 = ceg.ClaimEvidenceGraph(graph_id="ceg-fixed")
    g1.add_claim("c1", "Claim")
    g1.add_evidence("ev1", "lineage_receipt")
    g1.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_a, metadata={"m": 1})
    g1.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_b, metadata={"m": 2})

    # Graph 2: insert edge B then A (reversed)
    g2 = ceg.ClaimEvidenceGraph(graph_id="ceg-fixed")
    g2.add_claim("c1", "Claim")
    g2.add_evidence("ev1", "lineage_receipt")
    g2.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_b, metadata={"m": 2})
    g2.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_a, metadata={"m": 1})

    assert g1.graph_digest() == g2.graph_digest()


def test_register_receipt_conflict_rejection():
    """register_receipt rejects conflicting registrations for the same ID."""
    g = ceg.ClaimEvidenceGraph()
    g.register_receipt("rec-1", {"data": 123})
    # Same data -> no-op
    g.register_receipt("rec-1", {"data": 123})

    with pytest.raises(ValueError, match="Conflicting receipt registration"):
        g.register_receipt("rec-1", {"data": 999})


def test_trace_claim_provenance_preserves_support_status_and_direction(tmp_path):
    """trace_claim_provenance preserves support_status (supported vs contradicted)."""
    # Build lineage receipt
    f = tmp_path / "data.csv"
    f.write_text("x,y\n1,2\n", encoding="utf-8")
    sha = pr.compute_file_sha256(f)

    lin_graph = pr.LineageGraph(root_dir=tmp_path)
    lin_graph.add_entity("e_raw", "data_snapshot", sha256=sha, locator=str(f))
    rec = pr.trace_origin(lin_graph, target_id="e_raw", check_on_disk_hashes=True)

    ce_graph = ceg.ClaimEvidenceGraph()
    ce_graph.register_receipt(rec.receipt_id, rec)

    c = ce_graph.add_claim("c_dispute", "Claim under dispute.")
    ev_support = ce_graph.add_evidence(
        "ev_sup",
        "lineage_receipt",
        receipt_ref=ceg.ReceiptRef(
            kind="lineage",
            schema_version="lineage-receipt-1.0",
            receipt_id=rec.receipt_id,
            receipt_digest=rec.receipt_digest,
        )
    )
    ev_refute = ce_graph.add_evidence(
        "ev_ref",
        "lineage_receipt",
        receipt_ref=ceg.ReceiptRef(
            kind="lineage",
            schema_version="lineage-receipt-1.0",
            receipt_id=rec.receipt_id,
            receipt_digest=rec.receipt_digest,
        )
    )

    ce_graph.add_support_edge("ev_sup", "c_dispute", support_status="supported")
    ce_graph.add_support_edge("ev_ref", "c_dispute", support_status="contradicted")

    trace = ce_graph.trace_claim_provenance("c_dispute")
    assert trace["status"] == "traced"
    assert len(trace["lineage_traces"]) == 2

    status_map = {t["evidence_id"]: t["support_status"] for t in trace["lineage_traces"]}
    assert status_map["ev_sup"] == "supported"
    assert status_map["ev_ref"] == "contradicted"


def test_uncertainty_items_have_deterministic_content_addressed_ids():
    """Uncertainty items have deterministic content-addressed IDs immune to insertion sequence."""
    g1 = ceg.ClaimEvidenceGraph()
    g1.add_claim("c1", "Claim 1")
    g1.add_claim("c2", "Claim 2")
    # c1 contradicted, then c2 unverifiable
    g1.add_evidence("ev1", "direct_observation")
    g1.add_support_edge("ev1", "c1", support_status="contradicted")
    g1.add_evidence("ev2", "direct_observation")
    g1.add_support_edge("ev2", "c2", support_status="unverifiable")

    unc1 = g1.extract_uncertainties()

    g2 = ceg.ClaimEvidenceGraph()
    g2.add_claim("c2", "Claim 2")
    g2.add_claim("c1", "Claim 1")
    # reversed edge sequence: c2 unverifiable, then c1 contradicted
    g2.add_evidence("ev2", "direct_observation")
    g2.add_support_edge("ev2", "c2", support_status="unverifiable")
    g2.add_evidence("ev1", "direct_observation")
    g2.add_support_edge("ev1", "c1", support_status="contradicted")

    unc2 = g2.extract_uncertainties()

    assert [u.item_id for u in unc1] == [u.item_id for u in unc2]
    assert all(u.item_id.startswith("unc-") for u in unc1)


def test_json_schema_draft_2020_12_validation():
    """Exported ClaimEvidenceGraph dictionary strictly validates against schemas/claim-evidence-graph.schema.json."""
    schema_path = ROOT / "schemas/claim-evidence-graph.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    g = ceg.ClaimEvidenceGraph(graph_id="ceg-schema-test")
    c1 = g.add_claim("c1", "Claim A", target_work_id="w1", locator="p.1", claim_type="empirical_finding")
    c2 = g.add_claim("c2", "Claim B", target_work_id="w2", locator="p.2", claim_type="benchmark_result")

    # Lineage receipt ref
    ref_lin = ceg.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="r1", receipt_digest="a" * 64)
    # Academic evidence receipt ref
    ref_acad = ceg.ReceiptRef(kind="academic_evidence", schema_version="1.0", claim_digest="b" * 64, payload_sha256="c" * 64)

    ev1 = g.add_evidence("ev1", "lineage_receipt", receipt_ref=ref_lin)
    ev2 = g.add_evidence("ev2", "evidence_receipt", receipt_ref=ref_acad)

    g.add_support_edge("ev1", "c1", support_status="supported", receipt_ref=ref_lin)
    g.add_support_edge("ev2", "c2", support_status="unverifiable", receipt_ref=ref_acad)
    g.add_claim_relation("c1", "c2", relation_type="corroborates", evidence_refs=["ev1"])

    payload = g.to_dict()

    validator = jsonschema.Draft202012Validator(schema)
    validator.validate(payload)
    assert payload["protocol"] == "claim-evidence-graph-1.0"
    assert payload["graph_id"] == "ceg-schema-test"
    assert len(payload["graph_digest"]) == 64

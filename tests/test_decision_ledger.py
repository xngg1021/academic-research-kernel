# -*- coding: utf-8 -*-
"""Deterministic adversarial regression tests for Decision & Negative Result Ledger v1.

Covers:
1. Strict type enforcement and fail-fast validation for decisions, edges, prune states, and corrections.
2. Lexical canonicalization without semantic rewriting (NFC + whitespace compaction).
3. Content-addressed decision and outcome digests.
4. Idempotent registration with conflict rejection (same ID + different payload raises ValueError).
5. Disjoint registration of prune states (conflicting second state is rejected).
6. ReceiptRef strict mutual exclusivity (lineage vs academic_evidence), CEG-byte-compatible.
7. AcademicEvidenceReceipt verified against a real fixture: payload SHA256 physically asserted.
8. Registry key cannot bypass payload hash verification (tampered registered payload is caught).
9. register_receipt deepcopies payloads, preventing external mutation and evidence drift.
10. Frozen dataclasses: registered records are immutable against direct property mutation.
11. Metadata deep-freeze via FrozenDict.
12. Dangling edges: basis, fork, prune, correction referencing unregistered decisions.
13. Self-referential forks, self-pruning, and self-alternative rejected.
14. Circular pruning chains (pruned_by cycles) detected deterministically.
15. Negative results require basis edges (E404) with at least one claim basis (E405).
16. Three-state uncertainty queue with content-addressed deterministic IDs and dedupe.
17. trace_prune_cause returns unsupported_reason for prune decisions lacking claim bases.
18. Insertion-order invariance of ledger_digest.
19. Receipt registration affects ledger_digest; idempotent re-registration is stable.
20. Export immutability: to_dict deepcopies; mutating the export never touches the ledger.
21. Strict JSON Schema draft 2020-12 parity with additionalProperties: false and oneOf receiptRef.
22. Cross-kernel byte compatibility of digest helpers with the Claim-Evidence Graph Kernel.
"""
from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import os
import sys
from pathlib import Path

import jsonschema
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/decision-ledger/scripts"))
sys.path.insert(0, str(ROOT / "skills/claim-evidence-graph/scripts"))

import ledger as dl
import graph as ceg


def _receipt_fixture():
    claim_item = {
        "claim": "Treatment A reduced viral load by 40 percent.",
        "evidence_type": "full_text",
        "locator": "Table 2",
        "source": "w-123",
        "support_status": "supported",
    }
    cd = ceg.canonical_evidence_claim_digest(claim_item)
    receipt = {"schema_version": "1.0", "receipt_id": "ev-001", "claims": [dict(claim_item, claim_digest=cd)]}
    ph = ceg.canonical_academic_receipt_payload_sha256(receipt)
    ref = dl.ReceiptRef(kind="academic_evidence", schema_version="1.0", claim_digest=cd, payload_sha256=ph)
    return claim_item, receipt, ref


def _lineage_fixture():
    lineage = {
        "protocol": "lineage-receipt-1.0",
        "receipt_id": "lin-77",
        "receipt_digest": "a" * 64,
        "timestamp": "2026-09-19T00:00:00Z",
        "target_id": "tgt-1",
    }
    ref = dl.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="lin-77", receipt_digest="a" * 64)
    return lineage, ref


# ---------------------------------------------------------------------------
# 1. Canonicalization and digests
# ---------------------------------------------------------------------------

def test_canonical_text_lexical_only():
    t = dl.canonical_text(" caf\u00e9   test \r\n mixed \t spaces ")
    assert t == "caf\u00e9 test mixed spaces"
    with pytest.raises(TypeError):
        dl.canonical_text(123)


def test_decision_digest_sensitivity():
    d1 = dl.compute_decision_digest("Same text.")
    d2 = dl.compute_decision_digest("  Same   text. \r\n")
    assert d1 == d2  # lexical canonicalization
    assert dl.compute_decision_digest("Same text.", context_work_id="w1") != d1
    assert dl.compute_decision_digest("Same text.", decision_type="commit") != d1
    assert len(d1) == 64


def test_outcome_digest_content_addressing():
    a = dl.compute_outcome_digest("negative", "Did not replicate.")
    b = dl.compute_outcome_digest("negative", "  Did not replicate. \r\n")
    assert a == b
    lineage, ref = _lineage_fixture()
    assert dl.compute_outcome_digest("negative", "x", receipt_ref=ref) != dl.compute_outcome_digest("negative", "x")
    assert dl.compute_outcome_digest("positive", "x") != dl.compute_outcome_digest("negative", "x")


# ---------------------------------------------------------------------------
# 2. Record validation
# ---------------------------------------------------------------------------

def test_decision_type_enforcement():
    with pytest.raises(ValueError, match="Invalid decision_type"):
        dl.DecisionNode(id="d1", title="t", decision_type="quantum")
    with pytest.raises(ValueError, match="decision id"):
        dl.DecisionNode(id="BAD ID!", title="t")
    with pytest.raises(ValueError, match="title"):
        dl.DecisionNode(id="d1", title="   ")


def test_basis_edge_validation():
    with pytest.raises(ValueError, match="basis_kind"):
        dl.DecisionBasisEdge(decision_id="d1", basis_kind="vibes", basis_id="d2")
    with pytest.raises(TypeError):
        dl.DecisionBasisEdge(decision_id="d1", basis_kind="decision", basis_id="d2", receipt_ref="not-a-ref")
    lineage, ref = _lineage_fixture()
    e = dl.DecisionBasisEdge(decision_id="d1", basis_kind="decision", basis_id="d2", receipt_ref=ref)
    assert e.to_dict()["receipt_ref"]["kind"] == "lineage"


def test_fork_edge_validation():
    with pytest.raises(ValueError, match="fork relation"):
        dl.DecisionForkEdge(decision_id="d1", alternative_id="d2", relation="seducing")
    with pytest.raises(ValueError, match="alternative_id"):
        dl.DecisionForkEdge(decision_id="d1", alternative_id="BAD!", relation="considered")


def test_prune_state_validation():
    with pytest.raises(ValueError, match="prune_reason"):
        dl.PruneState(decision_id="d1", status="pruned")
    with pytest.raises(ValueError, match="prune_reason"):
        dl.PruneState(decision_id="d1", status="pruned", prune_reason="vibes")
    with pytest.raises(ValueError, match="Circular pruning"):
        dl.PruneState(decision_id="d1", status="pruned", prune_reason="superseded", pruned_by="d1")
    with pytest.raises(ValueError, match="Self-referential alternative"):
        dl.PruneState(decision_id="d1", status="pruned", prune_reason="superseded", alternative_ref="d1")
    with pytest.raises(ValueError, match="Active decision"):
        dl.PruneState(decision_id="d1", status="active", prune_reason="superseded")
    ok = dl.PruneState(decision_id="d1", status="active")
    assert "prune_reason" not in ok.to_dict()


def test_correction_validation():
    with pytest.raises(ValueError, match="verdict"):
        dl.OutcomeCorrection(correction_id="c1", decision_id="d1", verdict="0.85", rationale="x")
    with pytest.raises(ValueError, match="rationale"):
        dl.OutcomeCorrection(correction_id="c1", decision_id="d1", verdict="negative", rationale="  ")


# ---------------------------------------------------------------------------
# 3. Idempotency and conflicts
# ---------------------------------------------------------------------------

def test_decision_registration_idempotent_and_conflict_rejected():
    g = dl.DecisionLedger()
    a1 = g.add_decision(id="d1", title="Same title", decision_type="explore")
    a2 = g.add_decision(id="d1", title="Same title", decision_type="explore")
    assert a1 is a2
    with pytest.raises(ValueError, match="conflicting payload"):
        g.add_decision(id="d1", title="Different title")


def test_prune_state_conflict_rejected():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.set_prune("d1", "active")
    g.set_prune("d1", "pruned", prune_reason="superseded")
    # identical replay is idempotent (no new event)
    g.set_prune("d1", "pruned", prune_reason="superseded")
    assert len(g.state_history("d1")) == 2
    # conflicting re-prune while still pruned: illegal transition, must reopen first
    with pytest.raises(ValueError, match="Illegal state transition|Degenerate transition"):
        g.set_prune("d1", "pruned", prune_reason="other")


def test_receipt_registration_conflict_rejected_and_deepcopied():
    g = dl.DecisionLedger()
    _, receipt, _ = _receipt_fixture()
    g.register_receipt("r1", receipt)
    g.register_receipt("r1", copy.deepcopy(receipt))  # idempotent
    with pytest.raises(ValueError, match="Conflicting receipt registration"):
        g.register_receipt("r1", {"schema_version": "1.0", "receipt_id": "other", "claims": []})
    # external mutation must not drift into the registry
    receipt["claims"][0]["claim"] = "MUTATED"
    val = g._receipts["r1"]
    assert val["claims"][0]["claim"] != "MUTATED"


# ---------------------------------------------------------------------------
# 4. ReceiptRef contracts
# ---------------------------------------------------------------------------

def test_receipt_ref_mutual_exclusivity():
    with pytest.raises(ValueError, match="academic_evidence fields"):
        dl.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="r", receipt_digest="a" * 64, claim_digest="b" * 64)
    with pytest.raises(ValueError, match="lineage fields"):
        dl.ReceiptRef(kind="academic_evidence", schema_version="1.0", claim_digest="b" * 64, payload_sha256="c" * 64, receipt_id="r")
    with pytest.raises(ValueError, match="receipt_digest format"):
        dl.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="r", receipt_digest="nope")
    with pytest.raises(ValueError, match="Invalid receipt kind"):
        dl.ReceiptRef(kind="quantum", schema_version="1.0")


# ---------------------------------------------------------------------------
# 5. Receipt verification
# ---------------------------------------------------------------------------

def test_academic_receipt_physical_verification():
    _, receipt, ref = _receipt_fixture()
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    g.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g.register_receipt(ref.payload_sha256, receipt)  # CEG-compatible key convention
    ok, errs = g.validate_ledger()
    assert ok, errs
    # tampered payload under the same key is rejected by registration conflict
    tampered = copy.deepcopy(receipt)
    tampered["claims"][0]["claim"] = "TAMPERED"
    with pytest.raises(ValueError, match="Conflicting receipt registration"):
        g.register_receipt(ref.payload_sha256, tampered)
    # registry key cannot bypass hash verification: a fresh ledger where the
    # tampered payload is registered under the ORIGINAL payload-hash key must
    # still fail the physical SHA256 assertion
    g2 = dl.DecisionLedger()
    g2.add_decision(id="d1", title="x")
    g2.add_decision(id="d2", title="y")
    g2.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g2.register_receipt(ref.payload_sha256, tampered)
    ok3, errs3 = g2.validate_ledger()
    assert not ok3 and any("payload SHA256 mismatch" in e for e in errs3)


def test_unregistered_receipt_surfaces_as_uncertainty_not_error():
    _, receipt, ref = _receipt_fixture()
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    g.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    ok, errs = g.validate_ledger()
    assert ok and not errs  # structural validation stays deterministic
    unc = g.export_uncertainties()
    assert any(u.kind == "missing_receipt" and u.needs_human is False for u in unc)


def test_lineage_receipt_positive_assertion():
    lineage, ref = _lineage_fixture()
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    g.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    bad = dict(lineage, receipt_digest="b" * 64)
    g.register_receipt("lin-77", bad)
    ok, errs = g.validate_ledger()
    assert not ok and any("digest mismatch" in e for e in errs)


# ---------------------------------------------------------------------------
# 6. Structural validation
# ---------------------------------------------------------------------------

def _populated_ledger():
    g = dl.DecisionLedger(ledger_id="t")
    for did, title, typ in [
        ("d-a", "Explore A", "explore"),
        ("d-b", "Commit A", "commit"),
        ("d-c", "Branch C", "explore"),
        ("nr-1", "B fails on long docs", "negative_result"),
    ]:
        g.add_decision(id=did, title=title, decision_type=typ)
    g.add_basis("d-b", basis_kind="decision", basis_id="d-a")
    g.add_basis("nr-1", basis_kind="decision", basis_id="d-a")
    g.add_fork("d-b", "d-c", relation="considered")
    g.set_prune("d-c", "pruned", prune_reason="resource_exhausted", pruned_by="d-b", alternative_ref="d-a")
    return g


def test_populated_ledger_valid():
    g = _populated_ledger()
    ok, errs = g.validate_ledger()
    assert ok, errs


def test_dangling_edges_detected():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_basis("d1", basis_kind="decision", basis_id="ghost")
    g.add_fork("ghost2", "d1", relation="considered")
    g.add_outcome_correction("ghost3", verdict="negative", rationale="r")
    ok, errs = g.validate_ledger()
    codes = " ".join(errs)
    assert "E102" in codes and "E202" in codes and "E401" in codes


def test_self_fork_detected():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_fork("d1", "d1", relation="considered")
    ok, errs = g.validate_ledger()
    assert not ok and any("E201" in e for e in errs)


def test_prune_references_must_exist():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.set_prune("d1", "pruned", prune_reason="superseded", pruned_by="ghost", alternative_ref="ghost2")
    ok, errs = g.validate_ledger()
    codes = " ".join(errs)
    assert "E302" in codes and "E303" in codes


def test_circular_pruning_chain_detected():
    g = dl.DecisionLedger()
    for did in ["p1", "p2", "p3"]:
        g.add_decision(id=did, title=did)
    g.set_prune("p1", "pruned", prune_reason="superseded", pruned_by="p2")
    g.set_prune("p2", "pruned", prune_reason="superseded", pruned_by="p3")
    g.set_prune("p3", "pruned", prune_reason="superseded", pruned_by="p1")
    ok, errs = g.validate_ledger()
    assert any("E304" in e and "p1" in e for e in errs)


# ---------------------------------------------------------------------------
# 7. Negative result discipline
# ---------------------------------------------------------------------------

def test_negative_result_requires_basis():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="No evidence", decision_type="negative_result")
    ok, errs = g.validate_ledger()
    assert any("E404" in e for e in errs)


def test_negative_result_only_negative_basis_fails():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_decision(id="nr2", title="B fails", decision_type="negative_result")
    g.add_basis("nr2", basis_kind="negative_result", basis_id="nr1")
    ok, errs = g.validate_ledger()
    assert any("E405" in e for e in errs)
    unc = g.export_uncertainties()
    assert any(u.kind == "unsupported_negative_result" and u.needs_human for u in unc)


def test_negative_result_with_claim_basis_passes():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="positive evidence", decision_type="explore")
    g.add_decision(id="nr1", title="B fails", decision_type="negative_result")
    g.add_basis("nr1", basis_kind="negative_result", basis_id="nr_ghost")
    ok, errs = g.validate_ledger()
    assert any("E102" in e for e in errs)  # dangling first
    g2 = dl.DecisionLedger()
    g2.add_decision(id="d1", title="positive evidence", decision_type="explore")
    g2.add_decision(id="nr1", title="B fails", decision_type="negative_result")
    g2.add_basis("nr1", basis_kind="decision", basis_id="d1")
    ok2, errs2 = g2.validate_ledger()
    assert ok2, errs2


# ---------------------------------------------------------------------------
# 8. Uncertainty queue
# ---------------------------------------------------------------------------

def test_uncertainty_items_deterministic_and_deduped():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="x", decision_type="negative_result")
    g.add_decision(id="nr2", title="x", decision_type="negative_result")
    u1 = g.export_uncertainties()
    u2 = g.export_uncertainties()
    assert [i.item_id for i in u1] == [i.item_id for i in u2]
    ids = [i.item_id for i in u1]
    assert len(ids) == len(set(ids))
    for i in u1:
        assert i.item_id.startswith("unc-") and len(i.item_id) == 20


def test_uncertainty_for_unsupported_pruning():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="judge", title="prune judge")
    g.set_prune("d1", "pruned", prune_reason="other", pruned_by="judge")  # judge has no claim basis
    unc = g.export_uncertainties()
    assert any(u.kind == "unsupported_pruning" and u.needs_human for u in unc)
    tr = g.trace_prune_cause("d1")
    assert tr["unsupported_reason"] and "no Claim basis" in tr["unsupported_reason"]


def test_trace_prune_cause_full_chain():
    g = _populated_ledger()
    tr = g.trace_prune_cause("d-c")
    assert tr["prune_state"]["stop_reason"] == "resource_exhausted"
    assert tr["pruned_by_decision"]["id"] == "d-b"
    assert tr["alternative_decision"]["id"] == "d-a"
    assert tr["unsupported_reason"] is None
    tr_none = g.trace_prune_cause("d-a")  # not pruned
    assert tr_none["prune_state"] is None


# ---------------------------------------------------------------------------
# 9. Immutability
# ---------------------------------------------------------------------------

def test_records_are_frozen():
    g = _populated_ledger()
    node = g.get_decision("d-a")
    with pytest.raises(AttributeError):
        node.title = "hacked"
    with pytest.raises(TypeError):
        node.metadata["injected"] = True
    edge = next(iter(g._bases.values()))
    with pytest.raises(AttributeError):
        edge.basis_id = "other"


def test_export_deep_isolation():
    g = _populated_ledger()
    snap1 = g.to_dict()
    snap1["decisions"][0]["title"] = "tampered"
    snap1["ledger_digest"] = "0" * 64
    snap2 = g.to_dict()
    assert snap2["decisions"][0]["title"] != "tampered"
    assert len(snap2["ledger_digest"]) == 64
    assert snap2 == g.to_dict()


# ---------------------------------------------------------------------------
# 10. Digest discipline
# ---------------------------------------------------------------------------

def test_ledger_digest_order_invariant():
    records = [
        ("add_decision", dict(id="d-z", title="Z last")),
        ("add_decision", dict(id="d-m", title="M middle")),
        ("add_decision", dict(id="d-a", title="A first")),
        ("add_basis", dict(decision_id="d-a", basis_kind="decision", basis_id="d-m")),
        ("add_fork", dict(decision_id="d-a", alternative_id="d-z", relation="considered")),
    ]
    g1 = dl.DecisionLedger(ledger_id="o")
    for fn, kwargs in records:
        getattr(g1, fn)(**kwargs)
    g2 = dl.DecisionLedger(ledger_id="o")
    for fn, kwargs in reversed(records):
        getattr(g2, fn)(**kwargs)
    assert g1.ledger_digest() == g2.ledger_digest()


def test_ledger_digest_receipt_sensitivity():
    lineage, ref = _lineage_fixture()
    g = dl.DecisionLedger(ledger_id="r")
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    g.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    before = g.ledger_digest()
    g.register_receipt("lin-77", lineage)
    # content identity is registry-independent; verification state is separate
    assert g.ledger_digest() == before
    v_before = g.verification_digest()
    assert v_before != before
    g.register_receipt("lin-77", copy.deepcopy(lineage))
    assert g.ledger_digest() == before
    assert g.verification_digest() == v_before


def test_ledger_digest_registry_label_independence():
    lineage, ref = _lineage_fixture()
    g1 = dl.DecisionLedger(ledger_id="r")
    g1.add_decision(id="d1", title="x")
    g1.add_decision(id="d2", title="y")
    g1.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g1.register_receipt("lin-77", lineage)
    g2 = dl.DecisionLedger(ledger_id="r")
    g2.add_decision(id="d1", title="x")
    g2.add_decision(id="d2", title="y")
    g2.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g2.register_receipt("arbitrary-label", copy.deepcopy(lineage))
    # same records + same receipt bytes, different registry labels -> same content identity
    assert g1.ledger_digest() == g2.ledger_digest()
    # verification digests may differ in label, but both are stable and 64-hex
    assert len(g1.verification_digest()) == 64 and len(g2.verification_digest()) == 64


def test_ledger_digest_metadata_sensitivity():
    g1 = dl.DecisionLedger(ledger_id="m")
    g1.add_decision(id="d1", title="x", metadata={"tag": "v1"})
    g2 = dl.DecisionLedger(ledger_id="m")
    g2.add_decision(id="d1", title="x", metadata={"tag": "v2"})
    assert g1.ledger_digest() != g2.ledger_digest()


# ---------------------------------------------------------------------------
# 11. Queries
# ---------------------------------------------------------------------------

def test_outcome_of_latest_correction():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_outcome_correction("d1", verdict="inconclusive", rationale="first look")
    g.add_outcome_correction("d1", verdict="negative", rationale="second look")
    out = g.outcome_of("d1")
    assert out["correction_count"] == 2
    assert out["latest_verdict"] in {"inconclusive", "negative"}
    # both corrections retrievable; latest is deterministic by content id order
    d = g.to_dict()
    assert len(d["corrections"]) == 2


def test_find_negative_results_and_decisions_for():
    g = _populated_ledger()
    negs = g.find_negative_results()
    assert len(negs) == 1 and negs[0]["id"] == "nr-1"
    assert negs[0]["outcome"]["correction_count"] == 0
    users = g.find_decisions_for("d-a", basis_kind="decision")
    assert {u["decision_id"] for u in users} == {"d-b", "nr-1"}


# ---------------------------------------------------------------------------
# 12. Schema parity
# ---------------------------------------------------------------------------

def test_to_dict_matches_json_schema():
    schema = json.loads((ROOT / "schemas" / "decision-ledger-receipt.schema.json").read_text(encoding="utf-8"))
    g = _populated_ledger()
    _, receipt, ref = _receipt_fixture()
    g.add_basis("d-b", basis_kind="decision", basis_id="d-a", receipt_ref=ref)
    g.register_receipt(ref.payload_sha256, receipt)
    lineage, lref = _lineage_fixture()
    g.add_decision(id="d-l", title="lineage decision")
    g.add_basis("d-l", basis_kind="decision", basis_id="d-a", receipt_ref=lref)
    g.register_receipt("lin-77", lineage)
    export = g.to_dict()
    export["uncertainties"] = [u.to_dict() for u in g.export_uncertainties()]
    jsonschema.validate(instance=export, schema=schema)


def test_schema_rejects_unknown_fields():
    schema = json.loads((ROOT / "schemas" / "decision-ledger-receipt.schema.json").read_text(encoding="utf-8"))
    g = _populated_ledger()
    export = g.to_dict()
    export["injected_field"] = "nope"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=export, schema=schema)
    export2 = g.to_dict()
    export2["decisions"][0]["confidence"] = 0.85
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=export2, schema=schema)


# ---------------------------------------------------------------------------
# 13. Cross-kernel byte compatibility with the CEG Kernel
# ---------------------------------------------------------------------------

def test_cross_kernel_digest_helpers_byte_compatible():
    claim_item = {
        "claim": "Treatment A reduced viral load by 40 percent.",
        "evidence_type": "full_text",
        "locator": "Table 2",
        "source": "w-123",
        "support_status": "supported",
    }
    assert dl.canonical_evidence_claim_digest(claim_item) == ceg.canonical_evidence_claim_digest(claim_item)
    receipt = {"schema_version": "1.0", "receipt_id": "ev-001", "claims": [claim_item]}
    assert dl.canonical_academic_receipt_payload_sha256(receipt) == ceg.canonical_academic_receipt_payload_sha256(receipt)


def test_cross_kernel_receipt_contract_verdicts_match():
    _, receipt, ref = _receipt_fixture()
    ok_dl, _ = dl.validate_academic_receipt_contract(ref, receipt)
    ok_ceg, _ = ceg.validate_academic_receipt_contract(ref, receipt)
    assert ok_dl == ok_ceg == True
    tampered = copy.deepcopy(receipt)
    tampered["claims"][0]["claim"] = "TAMPERED"
    bad_ref = dl.ReceiptRef(kind="academic_evidence", schema_version="1.0", claim_digest=ref.claim_digest, payload_sha256=ceg.canonical_academic_receipt_payload_sha256(receipt))
    ok_dl2, _ = dl.validate_academic_receipt_contract(bad_ref, tampered)
    ok_ceg2, _ = ceg.validate_academic_receipt_contract(bad_ref, tampered)
    assert ok_dl2 == ok_ceg2 == False


def test_uncertainty_item_shape_matches_ceg():
    item = dl.UncertaintyItem(item_id="unc-" + "0" * 16, subject_id="s", kind="generic_uncertainty", reason="r", needs_human=True)
    ref_item = ceg.UncertaintyItem(item_id="unc-" + "0" * 16, subject_id="s", kind="generic_uncertainty", reason="r", needs_human=True)
    assert item.to_dict() == ref_item.to_dict()


# ---------------------------------------------------------------------------
# 14. Dataclass surface
# ---------------------------------------------------------------------------

def test_dataclass_frozen_flags():
    assert dataclasses.is_dataclass(dl.DecisionNode)
    assert dl.DecisionNode.__dataclass_params__.frozen is True
    assert dl.DecisionBasisEdge.__dataclass_params__.frozen is True
    assert dl.PruneState.__dataclass_params__.frozen is True
    assert dl.OutcomeCorrection.__dataclass_params__.frozen is True
    assert dl.UncertaintyItem.__dataclass_params__.frozen is True


# ---------------------------------------------------------------------------
# 15. Cross-review hardening (PR #11 review round 1)
# ---------------------------------------------------------------------------

def test_negative_result_self_reference_rejected():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="I failed because I say so", decision_type="negative_result")
    g.add_basis("nr1", basis_kind="decision", basis_id="nr1")
    ok, errs = g.validate_ledger()
    assert not ok and any("E406" in e for e in errs) and any("E405" in e for e in errs)


def test_negative_result_mutual_claim_cycle_rejected():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_decision(id="nr2", title="B fails", decision_type="negative_result")
    g.add_basis("nr1", basis_kind="decision", basis_id="nr2")
    g.add_basis("nr2", basis_kind="decision", basis_id="nr1")
    ok, errs = g.validate_ledger()
    codes = " ".join(errs)
    assert not ok
    assert "E405" in codes and "E103" in codes and "E407" in codes


def test_negative_result_mixed_basis_still_requires_external_claim():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_decision(id="nr2", title="B fails", decision_type="negative_result")
    g.add_decision(id="pos", title="positive evidence")
    g.add_basis("nr1", basis_kind="decision", basis_id="nr2")  # fake claim (negative_result target)
    g.add_basis("nr1", basis_kind="negative_result", basis_id="pos")  # kind mismatch noise
    g.add_basis("nr2", basis_kind="decision", basis_id="pos")  # nr2 properly evidenced
    ok, errs = g.validate_ledger()
    assert not ok and any("E405" in e or "E103" in e for e in errs)
    g2 = dl.DecisionLedger()
    g2.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g2.add_decision(id="pos", title="positive evidence")
    g2.add_basis("nr1", basis_kind="decision", basis_id="pos")  # real external claim
    ok2, errs2 = g2.validate_ledger()
    assert ok2, errs2


def test_outcome_of_reflects_true_insertion_order():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_outcome_correction("d1", verdict="inconclusive", rationale="first")
    g.add_outcome_correction("d1", verdict="negative", rationale="second")
    g.add_outcome_correction("d1", verdict="positive", rationale="third")
    out = g.outcome_of("d1")
    assert out["latest_verdict"] == "positive"
    assert out["correction_count"] == 3
    d = g.to_dict()
    # export order is canonical-JSON (order invariant); sequences are a distinct 1..N set
    seqs = sorted(c["sequence"] for c in d["corrections"])
    assert seqs == [1, 2, 3]


def test_correction_idempotent_replay_keeps_sequence():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    c1 = g.add_outcome_correction("d1", verdict="negative", rationale="r")
    c1b = g.add_outcome_correction("d1", verdict="negative", rationale="r")
    assert c1b.correction_id == c1.correction_id and c1b.sequence == c1.sequence


def test_ledger_digest_never_crashes_on_object_receipts():
    class FakeReceipt:
        def to_dict(self):
            return {"protocol": "lineage-receipt-1.0", "receipt_id": "x", "receipt_digest": "a" * 64}

    lineage, ref = _lineage_fixture()
    g1 = dl.DecisionLedger(ledger_id="obj")
    g1.add_decision(id="d1", title="x")
    g1.add_decision(id="d2", title="y")
    g1.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g1.register_receipt("x", FakeReceipt())
    d1 = g1.ledger_digest()  # must not raise TypeError
    g2 = dl.DecisionLedger(ledger_id="obj")
    g2.add_decision(id="d1", title="x")
    g2.add_decision(id="d2", title="y")
    g2.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g2.register_receipt("x", FakeReceipt().to_dict())
    assert g2.ledger_digest() == d1  # same content, same digest


def test_correction_sequence_breaks_digest_order_invariance_for_history():
    # arrival order of DISTINCT corrections is append history and must matter
    g1 = dl.DecisionLedger(ledger_id="h")
    g1.add_decision(id="d1", title="x")
    g1.add_outcome_correction("d1", verdict="inconclusive", rationale="a")
    g1.add_outcome_correction("d1", verdict="negative", rationale="b")
    g2 = dl.DecisionLedger(ledger_id="h")
    g2.add_decision(id="d1", title="x")
    g2.add_outcome_correction("d1", verdict="negative", rationale="b")
    g2.add_outcome_correction("d1", verdict="inconclusive", rationale="a")
    assert g1.ledger_digest() != g2.ledger_digest()


def test_circular_pruning_reported_once_per_cycle():
    g = dl.DecisionLedger()
    for did in ["p1", "p2", "p3"]:
        g.add_decision(id=did, title=did)
    g.set_prune("p1", "pruned", prune_reason="superseded", pruned_by="p2")
    g.set_prune("p2", "pruned", prune_reason="superseded", pruned_by="p3")
    g.set_prune("p3", "pruned", prune_reason="superseded", pruned_by="p1")
    ok, errs = g.validate_ledger()
    e304 = [e for e in errs if "E304" in e]
    assert len(e304) == 1 and "cycle members" in e304[0]


def test_fork_edge_supports_and_validates_receipt_ref():
    _, receipt, ref = _receipt_fixture()
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    g.add_fork("d2", "d1", relation="considered", receipt_ref=ref)
    g.register_receipt(ref.payload_sha256, receipt)
    ok, errs = g.validate_ledger()
    assert ok, errs
    un = [u.kind for u in g.export_uncertainties()]
    assert "missing_receipt" not in un


def test_to_dict_exports_uncertainties_matching_schema():
    schema = json.loads((ROOT / "schemas" / "decision-ledger-receipt.schema.json").read_text(encoding="utf-8"))
    g = dl.DecisionLedger()
    g.add_decision(id="nr-lonely", title="No evidence", decision_type="negative_result")
    export = g.to_dict()
    assert len(export["uncertainties"]) == 1
    assert export["uncertainties"][0]["kind"] == "decision_without_basis"
    jsonschema.validate(instance=export, schema=schema)


# ---------------------------------------------------------------------------
# 16. Cross-review hardening round 2 (dsv4pro findings)
# ---------------------------------------------------------------------------

def test_frozen_dict_backing_store_rejects_slot_writes():
    fd = dl.FrozenDict({"a": 1})
    h1 = hash(fd)
    with pytest.raises(TypeError):
        fd._data["b"] = 2  # MappingProxyType backing: no reachable mutation path
    assert hash(fd) == h1
    assert fd == {"a": 1}


def test_frozen_dict_hash_stable_and_mapping_semantics():
    fd = dl.FrozenDict({"a": 1})
    assert hash(fd) == hash(dl.FrozenDict({"a": 1}))
    assert dl.FrozenDict({"a": {"x": [1, 2]}}) == {"a": {"x": [1, 2]}}


def test_frozen_dict_mapping_equality_semantics():
    assert dl.FrozenDict({"a": 1}) == {"a": 1}
    assert dl.FrozenDict({"a": 1}) == dl.FrozenDict({"a": 1})
    assert dl.FrozenDict({"a": 1}) != {"a": 2}
    assert dl.FrozenDict({"a": {"x": 1}}) == {"a": {"x": 1}}
    assert (dl.FrozenDict({"a": 1}) == 42) is False


def test_uncertainty_item_id_formula_matches_ceg_kernel():
    import hashlib as _hashlib
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    lref = dl.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="ghost", receipt_digest="a" * 64)
    g.add_basis("d2", "decision", "d1", receipt_ref=lref)
    item = g.export_uncertainties()[0]
    payload = json.dumps(
        {"kind": item.kind, "needs_human": item.needs_human, "reason": item.reason, "subject_id": item.subject_id},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    )
    expected = "unc-" + _hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    assert item.item_id == expected


def test_uncertainty_id_collision_raises_instead_of_merging():
    a = dl.UncertaintyItem(item_id="unc-" + "0" * 16, subject_id="s1", kind="missing_receipt", reason="r1", needs_human=False)
    b = dl.UncertaintyItem(item_id="unc-" + "0" * 16, subject_id="s2", kind="generic_uncertainty", reason="r2", needs_human=True)
    with pytest.raises(ValueError, match="item_id collision"):
        dl._dedupe_uncertainty_items([a, b])
    same = dl.UncertaintyItem(item_id="unc-" + "0" * 16, subject_id="s1", kind="missing_receipt", reason="r1", needs_human=False)
    out = dl._dedupe_uncertainty_items([a, same])
    assert len(out) == 1


# ---------------------------------------------------------------------------
# 17. Basis-transparency: claim chains must ground at receipt anchors
# ---------------------------------------------------------------------------

def _anchored_receipt_fixture():
    import hashlib as hl
    payload = {
        "claim": "Replicated twice on held-out data.",
        "evidence_type": "full_text",
        "locator": "Table 1",
        "source": "w-1",
        "support_status": "supported",
    }
    cd = hl.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    receipt = {"schema_version": "1.0", "receipt_id": "ev-1", "claims": [dict(payload, claim_digest=cd)]}
    ph = hl.sha256(json.dumps(receipt, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    ref = dl.ReceiptRef(kind="academic_evidence", schema_version="1.0", claim_digest=cd, payload_sha256=ph)
    return receipt, ref


def _unc_kinds(g):
    return {u.subject_id: u.kind for u in g.export_uncertainties()}


def test_unanchored_claim_terminal_surfaces():
    g = dl.DecisionLedger()
    g.add_decision(id="bare", title="Bare act")
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_basis("nr1", basis_kind="decision", basis_id="bare")
    ok, errs = g.validate_ledger()
    assert ok and not errs  # structural validity unaffected
    kinds = _unc_kinds(g)
    assert kinds.get("bare") == "unevidenced_claim_basis"


def test_grounded_claim_chain_surfaces_nothing():
    receipt, ref = _anchored_receipt_fixture()
    g = dl.DecisionLedger()
    g.add_decision(id="bare", title="Bare act")
    g.add_decision(id="pos", title="Root evidence")
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_basis("nr1", basis_kind="decision", basis_id="bare")
    g.add_basis("bare", basis_kind="decision", basis_id="pos", receipt_ref=ref)
    g.register_receipt(ref.payload_sha256, receipt)
    kinds = _unc_kinds(g)
    assert not any(t == "unevidenced_claim_basis" for t in kinds.values())


def test_self_anchored_claim_terminal_still_surfaces():
    g = dl.DecisionLedger()
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_decision(id="selfish", title="Self anchor")
    g.add_basis("nr1", basis_kind="decision", basis_id="selfish")
    g.add_basis("selfish", basis_kind="decision", basis_id="selfish")  # self-edges never ground
    kinds = _unc_kinds(g)
    assert kinds.get("selfish") == "unevidenced_claim_basis"


def test_ungrounded_claim_cycle_hard_fails_for_negative_result():
    g = dl.DecisionLedger()
    g.add_decision(id="x1", title="X1")
    g.add_decision(id="x2", title="X2")
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_basis("nr1", basis_kind="decision", basis_id="x1")
    g.add_basis("x1", basis_kind="decision", basis_id="x2")
    g.add_basis("x2", basis_kind="decision", basis_id="x1")
    ok, errs = g.validate_ledger()
    assert not ok and any("E407" in e for e in errs)


def test_ungrounded_claim_cycle_without_negative_result_surfaces_as_uncertainty():
    g = dl.DecisionLedger()
    g.add_decision(id="x1", title="X1")
    g.add_decision(id="x2", title="X2")
    g.add_decision(id="nr1", title="A fails", decision_type="negative_result")
    g.add_decision(id="pos", title="anchor")
    g.add_basis("nr1", basis_kind="decision", basis_id="pos")  # nr itself properly evidenced
    g.add_basis("x1", basis_kind="decision", basis_id="x2")
    g.add_basis("x2", basis_kind="decision", basis_id="x1")
    ok, errs = g.validate_ledger()
    assert ok, errs  # cycle unconnected to any negative result: uncertainty only
    kinds = _unc_kinds(g)
    assert kinds.get("x1") == "unevidenced_claim_basis"
    assert kinds.get("x2") == "unevidenced_claim_basis"


def test_isolated_decisions_produce_no_basis_noise():
    g = dl.DecisionLedger()
    g.add_decision(id="solo", title="Solo")
    g.add_decision(id="solo2", title="Solo 2")
    assert _unc_kinds(g) == {}


# ---------------------------------------------------------------------------
# 18. State Ledger: append-only state events (P1-01 refactor)
# ---------------------------------------------------------------------------

def test_state_event_full_transition_history():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="judge", title="judge")
    g.set_prune("d1", "active")
    g.set_prune("d1", "pruned", prune_reason="resource_exhausted", pruned_by="judge")
    g.set_prune("d1", "active")  # reopened
    g.set_prune("d1", "pruned", prune_reason="contradicted", pruned_by="judge")
    hist = g.state_history("d1")
    assert [h["to_state"] for h in hist] == ["active", "pruned", "reopened", "pruned"]
    assert [h["sequence"] for h in hist] == [1, 2, 3, 4]
    assert hist[1]["from_state"] == "active" and hist[2]["from_state"] == "pruned"
    assert hist[2].get("reason") is None  # reopened reason optional
    assert g.current_state("d1").status == "pruned"


def test_state_event_illegal_transitions_rejected():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    with pytest.raises(ValueError, match="Illegal state transition"):
        g.add_state_event("d1", to_state="reopened")  # genesis must be active|pruned
    g.add_state_event("d1", to_state="active")
    with pytest.raises(ValueError, match="Illegal state transition"):
        g.add_state_event("d1", to_state="reopened")  # active -> reopened not allowed


def test_state_event_genesis_pruned_allowed():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    e = g.add_state_event("d1", to_state="pruned", reason="out_of_scope")
    assert e.from_state is None and e.to_state == "pruned"
    assert g.current_state("d1").status == "pruned"


def test_state_event_reopen_requires_closed_vocab_reason():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.set_prune("d1", "active")
    g.set_prune("d1", "pruned", prune_reason="superseded")
    with pytest.raises(ValueError, match="reopen reason|Invalid reopen"):
        g.add_state_event("d1", to_state="reopened", reason="vibes")
    e = g.add_state_event("d1", to_state="reopened", reason="new_evidence")
    assert e.reason == "new_evidence"


def test_state_event_digest_encodes_arrival_history():
    g1 = dl.DecisionLedger(ledger_id="s")
    g1.add_decision(id="d1", title="x")
    g1.set_prune("d1", "active")
    g1.set_prune("d1", "pruned", prune_reason="superseded")
    g2 = dl.DecisionLedger(ledger_id="s")
    g2.add_decision(id="d1", title="x")
    g2.set_prune("d1", "pruned", prune_reason="superseded")  # genesis pruned
    g2.set_prune("d1", "active")  # reopened... wait pruned->active illegal via wrapper? reopened then
    assert g1.ledger_digest() != g2.ledger_digest()


def test_state_event_idempotent_content_replay():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.add_decision(id="j", title="j")
    e1 = g.add_state_event("d1", to_state="active")
    e1b = g.add_state_event("d1", to_state="active")
    assert e1b.event_id == e1.event_id
    e2 = g.add_state_event("d1", to_state="pruned", reason="superseded", caused_by="j")
    e2b = g.add_state_event("d1", to_state="pruned", reason="superseded", caused_by="j")
    assert e2b.event_id == e2.event_id
    assert len(g.state_history("d1")) == 2


def test_trace_prune_cause_recursive_chain():
    g = dl.DecisionLedger()
    for did in ["d-a", "d-b", "d-c", "judge"]:
        g.add_decision(id=did, title=did)
    g.add_basis("judge", basis_kind="decision", basis_id="d-a")
    g.set_prune("d-c", "pruned", prune_reason="superseded", pruned_by="d-b")
    g.set_prune("d-b", "pruned", prune_reason="resource_exhausted", pruned_by="judge")
    tr = g.trace_prune_cause("d-c")
    assert [l["decision_id"] for l in tr["prune_chain"]] == ["d-c", "d-b"]
    assert tr["prune_chain"][0]["prune_reason"] == "superseded"
    assert tr["pruned_by_decision"]["id"] == "d-b"


def test_prune_cycle_break_after_reopen_clears_current_cycle():
    g = dl.DecisionLedger()
    for did in ["p1", "p2"]:
        g.add_decision(id=did, title=did)
    g.set_prune("p1", "pruned", prune_reason="superseded", pruned_by="p2")
    g.set_prune("p2", "pruned", prune_reason="superseded", pruned_by="p1")
    ok, errs = g.validate_ledger()
    assert any("E304" in e for e in errs)
    # reopen p1 breaks the CURRENT cycle
    g.set_prune("p1", "active")
    ok2, errs2 = g.validate_ledger()
    assert not any("E304" in e for e in errs2)


def test_e304_tail_nodes_not_reported_as_cycle_members():
    g = dl.DecisionLedger()
    for did in ["a1", "b1", "c1"]:
        g.add_decision(id=did, title=did)
    g.set_prune("a1", "pruned", prune_reason="superseded", pruned_by="b1")
    g.set_prune("b1", "pruned", prune_reason="superseded", pruned_by="c1")
    g.set_prune("c1", "pruned", prune_reason="superseded", pruned_by="b1")
    ok, errs = g.validate_ledger()
    e304 = [e for e in errs if "E304" in e]
    assert len(e304) == 1
    members = e304[0].split("members:")[1]
    assert "a1" not in members and "b1" in members and "c1" in members


# ---------------------------------------------------------------------------
# 19. from_dict replay loader (P2-07)
# ---------------------------------------------------------------------------

def test_from_dict_round_trip_content_ledger():
    g = _populated_ledger()
    g.add_outcome_correction("d-a", verdict="negative", rationale="did not replicate")
    g.set_prune("d-a", "active")
    g.set_prune("d-a", "pruned", prune_reason="contradicted", pruned_by="d-b")
    export = g.to_dict()
    g2 = dl.DecisionLedger.from_dict(export)
    assert g2.ledger_digest() == g.ledger_digest()
    assert g2.to_dict() == g.to_dict()
    assert g2.state_history("d-a") == g.state_history("d-a")
    assert g2.outcome_of("d-a") == g.outcome_of("d-a")


def test_from_dict_round_trip_with_receipt_registry():
    lineage, ref = _lineage_fixture()
    g = dl.DecisionLedger(ledger_id="with-receipts")
    g.add_decision(id="d1", title="x")
    g.add_decision(id="d2", title="y")
    g.add_basis("d2", basis_kind="decision", basis_id="d1", receipt_ref=ref)
    g.register_receipt("lin-77", lineage)
    export = g.to_dict()
    assert export["verification_manifest"] == {"lin-77": dl.canonical_ledger_payload_sha256(dl._jsonable(lineage))}
    # With receipt_registry passed to from_dict, full round trip succeeds including verification_digest
    g2 = dl.DecisionLedger.from_dict(export, receipt_registry={"lin-77": lineage})
    assert g2.ledger_digest() == g.ledger_digest()
    assert g2.verification_digest() == g.verification_digest()
    assert g2.to_dict() == g.to_dict()
    assert [u.to_dict() for u in g2.export_uncertainties()] == export["uncertainties"]


def test_schema_validates_state_transition_automaton():
    schema = json.loads((ROOT / "schemas" / "decision-ledger-receipt.schema.json").read_text(encoding="utf-8"))
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.set_prune("d1", "active")
    g.set_prune("d1", "pruned", prune_reason="superseded")
    export = g.to_dict()
    jsonschema.validate(instance=export, schema=schema)
    # Tamper: illegal transition in schema (active -> reopened)
    bad_export = copy.deepcopy(export)
    bad_export["state_events"][1]["to_state"] = "reopened"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_export, schema=schema)
    # Tamper: genesis reopened
    bad_export2 = copy.deepcopy(export)
    bad_export2["state_events"][0]["to_state"] = "reopened"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_export2, schema=schema)


def test_from_dict_rejects_tampered_export():
    g = _populated_ledger()
    export = g.to_dict()
    export["decisions"][0]["title"] = "TAMPERED"
    with pytest.raises(ValueError, match="tampering detected|digest mismatch"):
        dl.DecisionLedger.from_dict(export)


def test_from_dict_rejects_identity_field_forgery_even_if_raw_digest_recomputed():
    g = _populated_ledger()
    export = g.to_dict()
    # Attacker tries to forge event_id and recomputes ledger_digest to bypass Gate 1
    export["state_events"][0]["event_id"] = "evt-" + "f" * 32
    raw_payload = {
        "protocol": export["protocol"],
        "ledger_id": export["ledger_id"],
        "decisions": sorted(export["decisions"], key=lambda x: x["id"]),
        "bases": sorted(export["bases"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        "forks": sorted(export["forks"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        "state_events": sorted(export["state_events"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        "corrections": sorted(export["corrections"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
    }
    forged_digest = dl.hashlib.sha256(dl._canonical_json_bytes(raw_payload)).hexdigest().lower()
    export["ledger_digest"] = forged_digest
    export["verification_digest"] = dl.hashlib.sha256(dl._canonical_json_bytes({
        "ledger_digest": forged_digest, "receipts": export["verification_manifest"]
    })).hexdigest().lower()
    # Gate 1 passes, but Gate 2 catches event_id forgery during replay
    with pytest.raises(ValueError, match="event_id mismatch"):
        dl.DecisionLedger.from_dict(export)


def test_from_dict_rejects_uncertainty_queue_tampering():
    g = dl.DecisionLedger()
    g.add_decision(id="nr-lonely", title="no evidence", decision_type="negative_result")
    export = g.to_dict()
    assert len(export["uncertainties"]) >= 1
    # Tamper 1: strip all uncertainties
    tampered1 = copy.deepcopy(export)
    tampered1["uncertainties"] = []
    with pytest.raises(ValueError, match="uncertainty queue mismatch"):
        dl.DecisionLedger.from_dict(tampered1)
    # Tamper 2: flip needs_human from True to False
    tampered2 = copy.deepcopy(export)
    tampered2["uncertainties"][0]["needs_human"] = False
    with pytest.raises(ValueError, match="uncertainty queue mismatch"):
        dl.DecisionLedger.from_dict(tampered2)


def test_from_dict_rejects_verification_manifest_tampering():
    g = _populated_ledger()
    export = g.to_dict()
    export["verification_manifest"]["forged_receipt"] = "a" * 64
    with pytest.raises(ValueError, match="verification manifest mismatch"):
        dl.DecisionLedger.from_dict(export)


def test_from_dict_rejects_protocol_mismatch_and_missing_keys():
    g = _populated_ledger()
    export = g.to_dict()
    bad = dict(export, protocol="decision-ledger-9.9")
    with pytest.raises(ValueError, match="protocol mismatch"):
        dl.DecisionLedger.from_dict(bad)
    with pytest.raises(ValueError, match="missing required key"):
        dl.DecisionLedger.from_dict({"protocol": "decision-ledger-1.0"})


def test_from_dict_rejects_corrupted_state_sequence():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    g.set_prune("d1", "active")
    g.set_prune("d1", "pruned", prune_reason="superseded")
    export = g.to_dict()
    export["state_events"][1]["from_state"] = "reopened"  # impossible chain
    # Gate 1 catches tampering; if bypass attempted, Gate 2 catches from_state mismatch
    with pytest.raises(ValueError, match="tampering detected|from_state|Illegal state transition"):
        dl.DecisionLedger.from_dict(export)


def test_jsonable_fails_closed_on_foreign_objects_and_cycles():
    class Foreign:
        pass
    with pytest.raises(TypeError, match="Unsupported payload type"):
        dl._jsonable(Foreign())
    cyc = {}
    cyc["self"] = cyc
    with pytest.raises(ValueError, match="Cyclic"):
        dl._jsonable(cyc)
    # Non-finite float fail-closed
    with pytest.raises(ValueError, match="Non-finite float"):
        dl._jsonable(float("nan"))
    with pytest.raises(ValueError, match="Non-finite float"):
        dl._jsonable(float("inf"))
    with pytest.raises(ValueError, match="Non-finite float"):
        dl._jsonable(float("-inf"))
    # Non-string mapping key fail-closed
    with pytest.raises(TypeError, match="Mapping key must be str"):
        dl._jsonable({1: "int_key"})
    g = dl.DecisionLedger()
    with pytest.raises(TypeError):
        g.register_receipt("x", Foreign())
    with pytest.raises(ValueError, match="Cyclic"):
        g.register_receipt("x", cyc)
    with pytest.raises(ValueError, match="Non-finite float"):
        g.register_receipt("x", {"metric": float("nan")})
    with pytest.raises(TypeError, match="Mapping key must be str"):
        g.register_receipt("x", {42: "bad_key"})


def test_correction_id_width_and_collision_defense():
    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="x")
    c = g.add_outcome_correction("d1", verdict="negative", rationale="r")
    assert c.correction_id.startswith("corr-") and len(c.correction_id) == 37
    # idempotent replay identical content
    c2 = g.add_outcome_correction("d1", verdict="negative", rationale="r")
    assert c2.correction_id == c.correction_id and c2.sequence == c.sequence


def test_metadata_json_domain_fail_closed_at_constructor_time():
    """Metadata must fail closed on non-JSON domain values at construction time."""
    g = dl.DecisionLedger()
    # NaN and Inf in metadata
    with pytest.raises(ValueError, match="Non-finite float"):
        g.add_decision("d_nan", "Title", metadata={"bad": float("nan")})
    with pytest.raises(ValueError, match="Non-finite float"):
        g.add_decision("d_inf", "Title", metadata={"bad": float("inf")})

    # Non-string key in metadata
    with pytest.raises(TypeError, match="Metadata mapping key must be str|FrozenDict key must be str"):
        g.add_decision("d_int_key", "Title", metadata={1: "val"})

    # Foreign custom object
    class CustomObj:
        pass
    with pytest.raises(TypeError, match="Unsupported metadata value type"):
        g.add_decision("d_custom", "Title", metadata={"obj": CustomObj()})

    # Sets / frozensets (non-JSON)
    with pytest.raises(TypeError, match="Unsupported metadata value type"):
        g.add_decision("d_set", "Title", metadata={"tags": {"a", "b"}})

    # Cyclic container in metadata
    cyc: dict = {}
    cyc["inner"] = cyc
    with pytest.raises(ValueError, match="Cyclic container"):
        g.add_decision("d_cyc", "Title", metadata=cyc)

    # Valid metadata works and is deeply frozen
    d = g.add_decision("d_valid", "Title", metadata={"key": "val", "num": 42, "ratio": 3.14, "flag": True, "nest": {"a": [1, 2]}})
    assert isinstance(d.metadata, dl.FrozenDict)
    with pytest.raises(TypeError):
        d.metadata["key"] = "tamper"

    # Edge and event metadata constructors also fail-closed
    with pytest.raises(ValueError, match="Non-finite float"):
        g.add_basis("d_valid", "decision", "d_valid", metadata={"f": float("nan")})
    with pytest.raises(TypeError, match="Metadata mapping key must be str|FrozenDict key must be str"):
        g.add_fork("d_valid", "d_valid", metadata={99: "err"})
    with pytest.raises(TypeError, match="Unsupported metadata value type"):
        g.add_state_event("d_valid", "pruned", metadata={"set": {1, 2}})
    with pytest.raises(ValueError, match="Non-finite float"):
        g.add_outcome_correction("d_valid", verdict="negative", rationale="r", metadata={"bad": float("nan")})


def test_from_dict_verifies_missing_receipt_uncertainty_against_manifest():
    """from_dict without receipt_registry strictly verifies missing_receipt uncertainties using verification_manifest."""
    lin = {"protocol": "lineage-receipt-1.0", "receipt_id": "lin-present", "receipt_digest": "a" * 64}
    ref_present = dl.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="lin-present", receipt_digest="a" * 64)
    ref_missing = dl.ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="lin-missing", receipt_digest="b" * 64)

    g = dl.DecisionLedger()
    g.add_decision(id="d1", title="D1")
    g.add_decision(id="d2", title="D2")
    g.add_decision(id="d3", title="D3")
    g.add_basis("d2", "decision", "d1", receipt_ref=ref_present)
    g.add_basis("d3", "decision", "d1", receipt_ref=ref_missing)
    g.register_receipt("lin-present", lin)

    export = g.to_dict()
    assert "lin-present" in export["verification_manifest"]
    assert "lin-missing" not in export["verification_manifest"]

    # Export uncertainties has exactly one missing_receipt (basis:d3>d1)
    missing_items = [u for u in export["uncertainties"] if u["kind"] == "missing_receipt"]
    assert len(missing_items) == 1
    assert missing_items[0]["subject_id"] == "basis:d3>d1"

    # Replay without receipt_registry succeeds and strictly validates the missing_receipt uncertainty
    replayed = dl.DecisionLedger.from_dict(export)
    assert replayed.ledger_digest() == g.ledger_digest()

    # Tampering 1: Delete the missing_receipt uncertainty from export
    tampered1 = copy.deepcopy(export)
    tampered1["uncertainties"] = [u for u in tampered1["uncertainties"] if u["kind"] != "missing_receipt"]
    with pytest.raises(ValueError, match="Export uncertainty queue mismatch"):
        dl.DecisionLedger.from_dict(tampered1)

    # Tampering 2: Alter subject_id on missing_receipt
    tampered2 = copy.deepcopy(export)
    for u in tampered2["uncertainties"]:
        if u["kind"] == "missing_receipt":
            u["subject_id"] = "basis:d2>d1"
    with pytest.raises(ValueError, match="Export uncertainty queue mismatch"):
        dl.DecisionLedger.from_dict(tampered2)

    # Tampering 3: Change needs_human on missing_receipt
    tampered3 = copy.deepcopy(export)
    for u in tampered3["uncertainties"]:
        if u["kind"] == "missing_receipt":
            u["needs_human"] = True
    with pytest.raises(ValueError, match="Export uncertainty queue mismatch"):
        dl.DecisionLedger.from_dict(tampered3)


def test_repeated_identical_outcome_after_intervening_outcome():
    """An outcome identical to a past outcome must be recorded as a new event if intervening outcomes occurred."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Evaluate model")
    c1 = g.add_outcome_correction("d1", "negative", "initial failure")
    c2 = g.add_outcome_correction("d1", "positive", "fixed after rework")
    # Repeated identical payload to c1 after c2:
    c3 = g.add_outcome_correction("d1", "negative", "initial failure")
    assert c3.correction_id != c1.correction_id
    assert c3.sequence == 3
    assert g.outcome_of("d1")["latest_verdict"] == "negative"
    assert g.outcome_of("d1")["latest_correction_id"] == c3.correction_id
    assert g.outcome_of("d1")["correction_count"] == 3

    # Immediate repetition of c3 is strictly idempotent
    c4 = g.add_outcome_correction("d1", "negative", "initial failure")
    assert c4.correction_id == c3.correction_id
    assert c4.sequence == 3
    assert g.outcome_of("d1")["correction_count"] == 3

    # Replay round-trip preserves all 3 corrections
    export = g.to_dict()
    assert len(export["corrections"]) == 3
    replayed = dl.DecisionLedger.from_dict(export)
    assert replayed.outcome_of("d1")["latest_verdict"] == "negative"
    assert replayed.outcome_of("d1")["correction_count"] == 3


def test_from_dict_structural_validation_gate():
    """from_dict must execute validate_ledger and fail closed on structural flaws."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "D1", decision_type="explore")
    g.add_decision("d2", "D2", decision_type="explore")
    g.add_basis("d2", "decision", "d1")
    export = g.to_dict()

    # Tamper with basis_kind to 'negative_result' (E103 target type mismatch)
    tampered = copy.deepcopy(export)
    tampered["bases"][0]["basis_kind"] = "negative_result"
    # Recalculate digests to bypass Gate 1, Gate 2, and Gate 3
    tampered["ledger_digest"] = dl.hashlib.sha256(
        dl._canonical_json_bytes({
            "protocol": tampered["protocol"],
            "ledger_id": tampered["ledger_id"],
            "decisions": sorted(tampered["decisions"], key=lambda x: x["id"]),
            "bases": sorted(tampered["bases"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
            "forks": sorted(tampered["forks"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
            "state_events": sorted(tampered["state_events"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
            "corrections": sorted(tampered["corrections"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        })
    ).hexdigest().lower()
    tampered["verification_digest"] = dl.hashlib.sha256(
        dl._canonical_json_bytes({"ledger_digest": tampered["ledger_digest"], "receipts": tampered["verification_manifest"]})
    ).hexdigest().lower()
    tampered["uncertainties"] = [
        u.to_dict() for u in dl.DecisionLedger(ledger_id=g.ledger_id).export_uncertainties()
    ]
    with pytest.raises(ValueError, match="structural validation|E103"):
        dl.DecisionLedger.from_dict(tampered)


def test_from_dict_rejects_unknown_top_level_fields():
    """from_dict strictly rejects unknown top-level keys matching additionalProperties: false."""
    g = dl.DecisionLedger()
    export = g.to_dict()
    export["unexpected_extra_key"] = "forbidden"
    with pytest.raises(ValueError, match="Unexpected top-level fields"):
        dl.DecisionLedger.from_dict(export)


def test_reopened_status_and_properties():
    """current_state reflects reopened status with is_active=True and is_reopened=True."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Route A")
    g.set_prune("d1", "pruned", prune_reason="superseded")
    p1 = g.current_state("d1")
    assert p1.status == "pruned"
    assert p1.is_pruned is True
    assert p1.is_active is False

    g.set_prune("d1", "reopened")
    p2 = g.current_state("d1")
    assert p2.status == "reopened"
    assert p2.is_reopened is True
    assert p2.is_active is True
    assert p2.is_pruned is False


def test_set_prune_active_conflicting_parameters_rejected():
    """Re-activating an active decision with conflicting parameters must raise ValueError."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Route A")
    g.set_prune("d1", "active", metadata={"priority": "high"})

    # Identical active call is idempotent
    g.set_prune("d1", "active", metadata={"priority": "high"})

    # Conflicting active call fails closed
    with pytest.raises(ValueError, match="already active|conflicting"):
        g.set_prune("d1", "active", metadata={"priority": "low"})


def test_basis_kind_decision_and_normalization():
    """basis_kind='decision' works natively and 'claim' is strictly rejected."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Source")
    g.add_decision("d2", "Target 1")
    e1 = g.add_basis("d2", "decision", "d1")
    assert e1.basis_kind == "decision"
    with pytest.raises(ValueError, match="Invalid basis_kind: 'claim'"):
        g.add_basis("d2", "claim", "d1")
    found = g.find_decisions_for("d1", basis_kind="decision")
    assert len(found) == 1


def test_register_receipt_canonical_bytes_conflict_rejection():
    """register_receipt rejects conflicting registrations differing only in canonical JSON encoding."""
    g = dl.DecisionLedger()
    g.register_receipt("r1", {"metric": 1})
    # Float vs int: in python 1 == 1.0, but in canonical JSON bytes '1' != '1.0'
    with pytest.raises(ValueError, match="Conflicting receipt registration"):
        g.register_receipt("r1", {"metric": 1.0})


def test_package_exports_state_events():
    """__init__.py must export DecisionStateEvent and canonical_state_event_tuple."""
    import importlib
    pkg = importlib.import_module("skills.decision-ledger.scripts")
    assert hasattr(pkg, "DecisionStateEvent")
    assert hasattr(pkg, "canonical_state_event_tuple")
    assert hasattr(pkg, "RouteStatus")


def test_route_status_natural_scientific_api():
    """record_route_status and trace_stop_reason provide human-readable scientific API."""
    g = dl.DecisionLedger()
    g.add_decision("d-commit", "Adopt Model A", decision_type="commit")
    g.add_negative_result("nr-fails", "Baseline B fails on long context")
    nr = g.get_decision("nr-fails")
    assert nr.is_negative_result is True
    assert nr.entry_kind == "negative_result"
    assert nr.decision_action is None
    cm = g.get_decision("d-commit")
    assert cm.entry_kind == "decision"
    assert cm.decision_action == "commit"

    # Stop a route using human scientific vocabulary
    st = g.record_route_status("nr-fails", status="pruned", stop_reason="resource_exhausted", closed_by="d-commit")
    assert isinstance(st, dl.RouteStatus)
    assert st.stop_reason == "resource_exhausted"
    assert st.closed_by == "d-commit"
    assert st.is_pruned is True

    # Trace stop reason
    trace = g.trace_stop_reason("nr-fails")
    assert trace["route_status"]["stop_reason"] == "resource_exhausted"
    assert len(trace["stop_chain"]) == 1
    assert trace["stop_chain"][0]["closed_by"] == "d-commit"


def test_sequence_minimum_and_schema_entry_kind_contract():
    """sequence must be >= 1 for state events and corrections; entry_kind is enforced."""
    with pytest.raises(ValueError, match="'sequence' must be an integer >= 1"):
        dl.DecisionStateEvent(event_id="evt-" + "1" * 32, decision_id="d1", from_state=None, to_state="active", sequence=0)
    with pytest.raises(ValueError, match="'sequence' must be an integer >= 1"):
        dl.OutcomeCorrection(correction_id="corr-" + "1" * 32, decision_id="d1", verdict="positive", rationale="works", sequence=0)

    evt = dl.DecisionStateEvent(event_id="evt-" + "1" * 32, decision_id="d1", from_state=None, to_state="active", sequence=1)
    assert evt.sequence == 1
    corr = dl.OutcomeCorrection(correction_id="corr-" + "1" * 32, decision_id="d1", verdict="positive", rationale="works", sequence=1)
    assert corr.sequence == 1


def test_from_dict_without_legacy_decision_type():
    """Schema allows omitting decision_type in favor of entry_kind/decision_action; from_dict must not KeyError."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Try estimator A", decision_action="explore")
    g.add_negative_result("nr1", "Estimator B fails on long context")
    g.add_basis("nr1", "decision", "d1")
    exp = g.to_dict()

    # Omit legacy decision_type entirely
    for d in exp["decisions"]:
        d.pop("decision_type", None)

    # Recompute raw digest over the modified payload so Gate 1 passes
    raw_payload = {
        "protocol": exp["protocol"],
        "ledger_id": exp["ledger_id"],
        "decisions": sorted(exp["decisions"], key=lambda x: x["id"]),
        "bases": sorted(exp["bases"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        "forks": sorted(exp["forks"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        "state_events": sorted(exp["state_events"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
        "corrections": sorted(exp["corrections"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False)),
    }
    exp["ledger_digest"] = hashlib.sha256(dl._canonical_json_bytes(raw_payload)).hexdigest().lower()
    vd_payload = {"ledger_digest": exp["ledger_digest"], "receipts": exp["verification_manifest"]}
    exp["verification_digest"] = hashlib.sha256(dl._canonical_json_bytes(vd_payload)).hexdigest().lower()

    # Validate against schema
    schema = json.loads((ROOT / "schemas" / "decision-ledger-receipt.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=exp, schema=schema)

    # Replay in runtime
    loaded = dl.DecisionLedger.from_dict(exp)
    d1 = loaded.get_decision("d1")
    assert d1.entry_kind == "decision"
    assert d1.decision_action == "explore"
    nr1 = loaded.get_decision("nr1")
    assert nr1.is_negative_result is True
    assert nr1.entry_kind == "negative_result"


def test_add_outcome_correction_failure_atomicity():
    """Failed outcome correction must not increment sequence counter."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Test Decision")
    assert g._next_correction_sequence == 1

    with pytest.raises(ValueError, match="Invalid verdict"):
        g.add_outcome_correction("d1", verdict="bogus_verdict", rationale="reason")

    # Counter remains at 1
    assert g._next_correction_sequence == 1

    # Next successful call starts strictly at sequence 1
    corr = g.add_outcome_correction("d1", verdict="positive", rationale="sound result")
    assert corr.sequence == 1
    assert g._next_correction_sequence == 2


def test_add_outcome_correction_collision_defense_fail_closed():
    """Conflicting payload with identical truncated ID must raise ValueError (fail-closed)."""
    g = dl.DecisionLedger()
    g.add_decision("d1", "Decision 1")

    # Precompute the ID for sequence 1
    content_tuple = (
        "d1",
        "positive",
        "sound rationale",
        dl.canonical_receipt_ref_tuple(None),
        "",
        1,
        dl._meta_canonical_json(dl._frozen_meta(None)),
    )
    target_id = "corr-" + hashlib.sha256(dl._canonical_json_bytes(list(content_tuple))).hexdigest()[:32]

    # Plant colliding fake correction with same ID but different verdict/rationale
    fake_corr = dl.OutcomeCorrection(
        correction_id=target_id,
        decision_id="d1",
        verdict="negative",
        rationale="colliding different payload",
        sequence=1,
    )
    g._corrections[target_id] = fake_corr

    with pytest.raises(ValueError, match="Hash collision detected for outcome correction"):
        g.add_outcome_correction("d1", verdict="positive", rationale="sound rationale")


def test_schema_reopened_forbids_caused_by_and_alternative_ref():
    """Schema must reject reopened state events carrying caused_by or alternative_ref."""
    schema = json.loads((ROOT / "schemas" / "decision-ledger-receipt.schema.json").read_text(encoding="utf-8"))
    g = dl.DecisionLedger()
    g.add_decision("d1", "Test")
    g.record_route_status("d1", status="pruned", stop_reason="resource_exhausted")
    g.record_route_status("d1", status="reopened")
    exp = g.to_dict()

    # Valid export passes schema
    jsonschema.validate(instance=exp, schema=schema)

    # Illegally adding caused_by to reopened event must fail schema validation
    reopened_ev = [ev for ev in exp["state_events"] if ev["to_state"] == "reopened"][0]
    reopened_ev["caused_by"] = "d2"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=exp, schema=schema)

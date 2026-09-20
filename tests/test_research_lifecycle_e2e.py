"""End-to-End Killer Demo: Full Scholarly Research-State Lifecycle.

Demonstrates the unified pipeline connecting skills to the kernel:
1. Literature Identification -> ResearchObject Registration
2. Empirical Source Verification -> EvidenceReceipt -> CEG Claim & Evidence Anchor
3. Quantitative Recomputation -> Statistical Discrepancy Evidence
4. Explicit Decision Commitment -> DecisionNode with Basis to Evidence
5. Long-context Estimator Failure -> Negative Result Node & Stop Event
6. Re-evaluation & Outcome Correction -> Positive Verdict & Reopened State Event
7. Full Deterministic Export -> Clean Rehydration & Bitwise Replay Parity.
"""

import copy
import json
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "claim-evidence-graph" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "decision-ledger" / "scripts"))

from ingestion import (
    ArtifactEnvelope,
    IngestionEngine,
    IngestionKernelState,
)
from shared_contracts.evidence import ReceiptRef
import graph as ceg_mod
import ledger as ledger_mod


def test_full_research_state_lifecycle_e2e():
    engine = IngestionEngine()
    state = IngestionKernelState(
        ceg=ceg_mod.ClaimEvidenceGraph(),
        ledger=ledger_mod.DecisionLedger(),
    )

    # -------------------------------------------------------------------------
    # Step 1: Ingest EvidenceReceipt from academic-source-verification
    # -------------------------------------------------------------------------
    source_receipt = {
        "schema_version": "1.0",
        "query": "DOI:10.1037/bul0000209",
        "claims": [{
            "claim": "Interleaving practice boosts test retention by 42%",
            "evidence_type": "data_point",
            "locator": "table-2",
            "source": "DOI:10.1037/bul0000209",
            "support_status": "supported",
        }],
    }
    env1 = ArtifactEnvelope.create(
        payload=source_receipt,
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
        subject_refs=["work:doi:10.1037/bul0000209"],
    )
    receipt1 = engine.ingest(env1, state=state)
    assert receipt1.status == "accepted"
    assert len(receipt1.ceg_nodes) == 2  # 1 claim, 1 evidence anchor
    assert "work:doi:10.1037/bul0000209" in state.objects
    claim_id = receipt1.ceg_nodes[0]
    evidence_id = receipt1.ceg_nodes[1]

    # -------------------------------------------------------------------------
    # Step 2: Quantitative audit recomputation finds discrepancy on another stat
    # -------------------------------------------------------------------------
    audit_data = {
        "paper_title": "Interleaving Meta-Analysis",
        "assertions": [{
            "statistic": "Welch t-test",
            "reported_value": "p = 0.04",
            "recomputed_value": "p = 0.08",
            "discrepancy_detected": True,
            "locator": "p. 1045",
        }],
    }
    env2 = ArtifactEnvelope.create(
        payload=audit_data,
        producer_skill="quantitative-paper-audit",
        producer_version="1.0.0",
        artifact_kind="computed_evidence",
        payload_schema="quantitative-audit-1.0",
    )
    receipt2 = engine.ingest(env2, state=state, bindings={"claim_id": claim_id})
    assert receipt2.status == "accepted"
    assert len(receipt2.ceg_edges) == 1

    # -------------------------------------------------------------------------
    # Step 3: Explicit Researcher Decision grounded on verified evidence
    # -------------------------------------------------------------------------
    d1 = state.ledger.add_decision(
        id="dec-interleaving-strategy",
        title="Deploy interleaving curriculum for semester cohort",
        decision_action="commit",
        context_work_id="work.curriculum.2026",
    )
    # Researcher records negative result on long-tail sub-population
    nr1 = state.ledger.add_negative_result(
        id="nr-long-text-failure",
        title="Interleaving fails on expository technical prose",
    )
    # Ground negative result in decision to satisfy E404 invariant
    state.ledger.add_basis(
        decision_id="nr-long-text-failure",
        basis_kind="decision",
        basis_id="dec-interleaving-strategy",
    )

    # -------------------------------------------------------------------------
    # Step 4: Prune strategy due to negative sub-result, then reopen with correction
    # -------------------------------------------------------------------------
    state.ledger.record_route_status(
        decision_id="dec-interleaving-strategy",
        status="pruned",
        stop_reason="contradicted",
    )
    assert state.ledger.current_state("dec-interleaving-strategy").status == "pruned"

    # Outcome correction is appended (never in-place update)
    corr = state.ledger.add_outcome_correction(
        decision_id="dec-interleaving-strategy",
        verdict="positive",
        rationale="Sub-population partitioned; strategy verified effective for mathematical domains",
        locator="sec-curriculum-appendix",
    )
    state.ledger.record_route_status(
        decision_id="dec-interleaving-strategy",
        status="reopened",
    )
    assert state.ledger.current_state("dec-interleaving-strategy").status == "reopened"

    # -------------------------------------------------------------------------
    # Step 5: Export full kernel state and verify mathematical replay parity
    # -------------------------------------------------------------------------
    initial_digests = state.compute_digests()
    ceg_export = state.ceg.to_dict()
    ledger_export = state.ledger.to_dict()

    # Rehydrate in clean instances
    reloaded_ceg = ceg_mod.ClaimEvidenceGraph()
    for k, r in state.receipts.items():
        reloaded_ceg.register_receipt(k, r)
    for c in ceg_export["claims"]:
        reloaded_ceg.add_claim(c["id"], c["text"], target_work_id=c.get("target_work_id"), locator=c.get("locator"))
    for ev in ceg_export.get("evidence_anchors", []):
        ref_obj = ReceiptRef(**ev["receipt_ref"]) if ev.get("receipt_ref") else None
        reloaded_ceg.add_evidence(
            ev["id"],
            ev["anchor_type"],
            source_work_id=ev.get("source_work_id"),
            locator=ev.get("locator"),
            receipt_ref=ref_obj,
            metadata=ev.get("metadata"),
        )
    for edge in ceg_export["support_edges"]:
        reloaded_ceg.add_support_edge(edge["evidence_id"], edge["claim_id"], edge["support_status"], metadata=edge.get("metadata"))

    reloaded_ledger = ledger_mod.DecisionLedger.from_dict(ledger_export)

    # Cryptographic digests match exactly
    assert reloaded_ceg.graph_digest() == initial_digests["ceg_digest"]
    assert reloaded_ledger.ledger_digest() == initial_digests["ledger_digest"]

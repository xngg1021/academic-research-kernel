"""Tests for the Research Artifact Ingestion Bridge and adapters."""

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
    create_default_registry,
)
from shared_contracts.evidence import compute_sha256, canonical_json_bytes

import graph as ceg_mod
import ledger as ledger_mod


def test_registry_adapter_coverage():
    reg = create_default_registry()
    matrix = reg.export_matrix()
    adapter_ids = [m["adapter_id"] for m in matrix]
    assert "adapter-academic-source-verification" in adapter_ids
    assert "adapter-research-object-identity" in adapter_ids
    assert "adapter-claim-evidence-graph" in adapter_ids
    assert "adapter-decision-ledger" in adapter_ids
    assert "adapter-quantitative-paper-audit" in adapter_ids
    assert "adapter-research-reproducibility" in adapter_ids
    assert "adapter-cross-review-five" in adapter_ids
    assert "adapter-systematic-review" in adapter_ids
    assert "adapter-literature-analysis" in adapter_ids
    assert "adapter-literature-watch" in adapter_ids
    assert "adapter-retraction-watch" in adapter_ids
    assert "adapter-math-computation" in adapter_ids
    assert "adapter-academic-writing" in adapter_ids
    assert "adapter-opaque-fallback" in adapter_ids


def test_tier1_academic_source_verification_ingest():
    engine = IngestionEngine()
    state = IngestionKernelState(
        ceg=ceg_mod.ClaimEvidenceGraph(),
        ledger=ledger_mod.DecisionLedger(),
    )
    # Add an initial decision to receive basis bindings
    state.ledger.add_decision("dec-1", "Investigate Interleaving Effect", decision_action="explore")

    claim_payload = {
        "claim": "Interleaving practice boosts test retention by 42%",
        "evidence_type": "data_point",
        "locator": "table-2",
        "source": "DOI:10.1037/bul0000209",
        "support_status": "supported",
    }
    evidence_receipt = {
        "schema_version": "1.0",
        "query": "DOI:10.1037/bul0000209",
        "claims": [claim_payload],
    }

    envelope = ArtifactEnvelope.create(
        payload=evidence_receipt,
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
        subject_refs=["work:doi:10.1037/bul0000209"],
    )

    receipt = engine.ingest(envelope, state=state, bindings={"decision_id": "dec-1"})
    assert receipt.status == "accepted"
    assert receipt.validation_state["valid"] is True
    assert len(receipt.ceg_nodes) == 2  # 1 claim + 1 evidence
    assert len(receipt.ceg_edges) == 1  # 1 support edge
    assert len(receipt.ledger_bindings) == 1

    # Verify CEG and Ledger digests exist and graph is valid
    assert "ceg_digest" in receipt.output_digests
    assert "ledger_digest" in receipt.output_digests
    ceg_valid, _ = state.ceg.validate_graph()
    assert ceg_valid is True

    # Idempotent re-ingestion
    receipt2 = engine.ingest(envelope, state=state, bindings={"decision_id": "dec-1"})
    assert receipt2.receipt_id == receipt.receipt_id
    assert receipt2.output_digests == receipt.output_digests


def test_tier2_quantitative_audit_never_auto_decides():
    engine = IngestionEngine()
    ceg = ceg_mod.ClaimEvidenceGraph()
    ceg.add_claim("c-stat", "Reported t-test is statistically significant")
    state = IngestionKernelState(ceg=ceg, ledger=ledger_mod.DecisionLedger())

    audit_payload = {
        "paper_title": "Sample Paper",
        "assertions": [{
            "statistic": "t-test",
            "reported_value": "p = 0.04",
            "recomputed_value": "p = 0.08",
            "discrepancy_detected": True,
        }],
    }
    envelope = ArtifactEnvelope.create(
        payload=audit_payload,
        producer_skill="quantitative-paper-audit",
        producer_version="1.0.0",
        artifact_kind="computed_evidence",
        payload_schema="quantitative-audit-1.0",
    )

    receipt = engine.ingest(envelope, state=state, bindings={"claim_id": "c-stat"})
    assert receipt.status == "accepted"
    # An edge should be created refuting the claim
    assert len(receipt.ceg_edges) == 1
    # Crucial assertion: no automatic decisions were created in the ledger
    assert len(state.ledger.to_dict()["decisions"]) == 0


def test_tier3_opaque_stays_opaque():
    engine = IngestionEngine()
    state = IngestionKernelState(
        ceg=ceg_mod.ClaimEvidenceGraph(),
        ledger=ledger_mod.DecisionLedger(),
    )

    manuscript = {
        "title": "A Breakthrough Discovery in Cognitive Memory",
        "text": "We definitely prove that all prior models are wrong. We decide to discard hypothesis B.",
    }
    envelope = ArtifactEnvelope.create(
        payload=manuscript,
        producer_skill="academic-writing",
        producer_version="1.0.0",
        artifact_kind="opaque_manuscript",
        payload_schema="manuscript-opaque-1.0",
    )

    receipt = engine.ingest(envelope, state=state)
    assert receipt.status == "accepted"
    # OPAQUE GUARANTEE: Zero claims, zero evidences, and zero decisions extracted from text!
    assert len(receipt.ceg_nodes) == 0
    assert len(receipt.ceg_edges) == 0
    assert len(receipt.ledger_bindings) == 0
    assert len(state.ceg.to_dict()["claims"]) == 0
    assert len(state.ledger.to_dict()["decisions"]) == 0
    # Object registered for provenance
    assert envelope.artifact_id in state.objects


def test_transactional_batch_atomicity_on_failure():
    engine = IngestionEngine()
    state = IngestionKernelState(
        ceg=ceg_mod.ClaimEvidenceGraph(),
        ledger=ledger_mod.DecisionLedger(),
    )

    valid_env = ArtifactEnvelope.create(
        payload={"query": "test", "claims": []},
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )

    # Corrupted envelope with invalid payload SHA
    bad_env = ArtifactEnvelope(
        protocol="artifact-envelope-1.0",
        artifact_id="art-" + "f" * 32,
        artifact_kind="evidence_receipt",
        producer={"skill": "academic-source-verification", "version": "1.0.0"},
        payload_schema="evidence-receipt-1.0",
        payload_sha256="0" * 64,  # forged SHA
        payload={"schema_version": "1.0", "claims": []},
    )

    receipts, final_state = engine.batch_ingest(
        envelopes=[valid_env, bad_env],
        state=state,
        atomic=True,
    )

    # Batch must be rejected atomically
    assert all(r.status == "rejected" for r in receipts)
    assert len(final_state.objects) == 0
    assert len(final_state.ceg.to_dict()["claims"]) == 0

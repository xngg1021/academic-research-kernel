"""Adversarial and metamorphic tests for the Research Artifact Ingestion Bridge."""

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
from shared_contracts.evidence import compute_sha256, canonical_json_bytes
import graph as ceg_mod
import ledger as ledger_mod


def test_tampered_payload_hash_rejected():
    """Forged payload_sha256 must fail-closed immediately at envelope construction."""
    with pytest.raises(ValueError, match="Payload hash mismatch"):
        ArtifactEnvelope(
            protocol="artifact-envelope-1.0",
            artifact_id="art-" + "0" * 32,
            artifact_kind="evidence_receipt",
            producer={"skill": "academic-source-verification", "version": "1.0.0"},
            payload_schema="evidence-receipt-1.0",
            payload_sha256="f" * 64,  # forged
            payload={"schema_version": "1.0", "claims": []},
        )


def test_tampered_artifact_id_rejected():
    """Forged artifact_id mismatching payload digest must fail-closed immediately."""
    payload = {"schema_version": "1.0", "claims": []}
    real_sha = compute_sha256(canonical_json_bytes(payload))
    with pytest.raises(ValueError, match="artifact_id content-addressing mismatch"):
        ArtifactEnvelope(
            protocol="artifact-envelope-1.0",
            artifact_id="art-" + "0" * 32,  # forged ID
            artifact_kind="evidence_receipt",
            producer={"skill": "academic-source-verification", "version": "1.0.0"},
            payload_schema="evidence-receipt-1.0",
            payload_sha256=real_sha,
            payload=payload,
        )


def test_cross_state_cache_isolation():
    """Ingesting into State A must never pollute State B or return cached receipt without applying to B."""
    engine = IngestionEngine()
    state_a = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph())
    state_b = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph())

    env = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "DOI:10.1000/1",
            "identifiers": {"doi": "10.1000/1"},
            "sources": [],
            "claims": [{
                "claim": "Finding in A",
                "evidence_type": "computed",
                "source": "DOI:10.1000/1",
                "support_status": "supported",
            }],
            "generated_at": "2026-09-20T00:00:00Z",
        },
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )

    r_a = engine.ingest(env, state=state_a)
    assert r_a.status == "accepted"
    assert len(state_a.ceg.claims) == 1

    # Ingesting same artifact into fresh state_b must apply mutations into state_b!
    assert len(state_b.ceg.claims) == 0
    r_b = engine.ingest(env, state=state_b)
    assert r_b.status == "accepted"
    assert len(state_b.ceg.claims) == 1
    assert state_b.ceg.graph_digest() == state_a.ceg.graph_digest()


def test_binding_sensitivity_cache():
    """Same artifact ingested with different bindings must re-execute rather than returning stale cached receipt."""
    engine = IngestionEngine()
    state = IngestionKernelState(
        ceg=ceg_mod.ClaimEvidenceGraph(),
        ledger=ledger_mod.DecisionLedger(),
    )
    state.ledger.add_decision("dec-1", "First Decision", decision_action="explore")
    state.ledger.add_decision("dec-2", "Second Decision", decision_action="explore")

    env = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "DOI:10.1000/1",
            "identifiers": {"doi": "10.1000/1"},
            "sources": [],
            "claims": [{
                "claim": "Dual bound claim",
                "evidence_type": "computed",
                "source": "DOI:10.1000/1",
                "support_status": "supported",
            }],
            "generated_at": "2026-09-20T00:00:00Z",
        },
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )

    r1 = engine.ingest(env, state=state, bindings={"action": "add_outcome_correction", "decision_id": "dec-1", "verdict": "positive", "rationale": "r1"})
    assert len(r1.ledger_bindings) == 1
    assert r1.ledger_bindings[0]["decision_id"] == "dec-1"

    # Ingest with binding to dec-2: must NOT return cached receipt for dec-1
    r2 = engine.ingest(env, state=state, bindings={"action": "add_outcome_correction", "decision_id": "dec-2", "verdict": "positive", "rationale": "r2"})
    assert len(r2.ledger_bindings) == 1
    assert r2.ledger_bindings[0]["decision_id"] == "dec-2"
    assert r2.receipt_id != r1.receipt_id


def test_research_object_collision_defense_fail_closed():
    """ResearchObject ID collision with conflicting payload must fail-closed."""
    engine = IngestionEngine()
    state = IngestionKernelState()

    env1 = ArtifactEnvelope.create(
        payload={
            "object_id": "obj-dataset-1",
            "object_type": "Dataset",
            "title": "Version 1",
            "identifiers": [],
            "manifestations": [],
            "relations": [],
            "lineage": [],
            "source_observations": [],
            "uncertainty": [],
        },
        producer_skill="research-object-identity",
        producer_version="1.0.0",
        artifact_kind="research_object",
        payload_schema="research-object-1.0",
    )
    r1 = engine.ingest(env1, state=state)
    assert r1.status == "accepted"

    # Conflicting payload for same object_id
    env2 = ArtifactEnvelope.create(
        payload={
            "object_id": "obj-dataset-1",
            "object_type": "Dataset",
            "title": "Conflicting Version 2",
            "identifiers": [],
            "manifestations": [],
            "relations": [],
            "lineage": [],
            "source_observations": [],
            "uncertainty": [],
        },
        producer_skill="research-object-identity",
        producer_version="1.0.0",
        artifact_kind="research_object",
        payload_schema="research-object-1.0",
    )
    r2 = engine.ingest(env2, state=state)
    assert r2.status == "rejected"
    assert "ResearchObject ID collision" in r2.failure_reason


def test_ceg_snapshot_lossless_round_trip():
    """CEG snapshot adapter must losslessly preserve claims, evidences, edges, relations, and digest."""
    cg = ceg_mod.ClaimEvidenceGraph(graph_id="source-graph")
    cg.add_claim("c-1", "Claim 1", target_work_id="work-1")
    cg.add_claim("c-2", "Claim 2", target_work_id="work-1")
    cg.add_evidence("ev-1", "direct_observation", locator="p. 1")
    cg.add_support_edge("ev-1", "c-1", "supported")
    cg.add_claim_relation("c-1", "c-2", "corroborates")
    orig_export = cg.to_dict()
    orig_digest = cg.graph_digest()

    engine = IngestionEngine()
    state = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph(graph_id="source-graph"))
    env = ArtifactEnvelope.create(
        payload=orig_export,
        producer_skill="claim-evidence-graph",
        producer_version="1.0.0",
        artifact_kind="ceg_snapshot",
        payload_schema="claim-evidence-graph-1.0",
    )
    receipt = engine.ingest(env, state=state)
    assert receipt.status == "accepted"

    re_exported = state.ceg.to_dict()
    assert state.ceg.graph_digest() == orig_digest
    assert len(re_exported["claims"]) == len(orig_export["claims"])
    assert len(re_exported["evidence_anchors"]) == len(orig_export["evidence_anchors"])
    assert len(re_exported["support_edges"]) == len(orig_export["support_edges"])
    assert len(re_exported["claim_relations"]) == len(orig_export["claim_relations"])


def test_ledger_snapshot_lossless_round_trip():
    """DecisionLedger snapshot adapter must losslessly preserve decisions, bases, forks, events, corrections, and digest."""
    ledger = ledger_mod.DecisionLedger(ledger_id="source-ledger")
    ledger.add_decision("dec-1", "Root Decision", decision_action="explore")
    ledger.add_decision("dec-2", "Child Decision", decision_action="commit")
    ledger.add_decision("alt-a", "Alternative A", decision_action="explore")
    ledger.add_basis("dec-2", "decision", "dec-1")
    ledger.add_fork("dec-1", "alt-a", "considered")
    ledger.add_state_event("dec-1", "active")
    ledger.add_state_event("dec-1", "pruned", reason="contradicted")
    ledger.add_outcome_correction("dec-1", "positive", "Outcome verified")
    orig_export = ledger.to_dict()
    orig_digest = ledger.ledger_digest()

    engine = IngestionEngine()
    state = IngestionKernelState(ledger=ledger_mod.DecisionLedger(ledger_id="source-ledger"))
    env = ArtifactEnvelope.create(
        payload=orig_export,
        producer_skill="decision-ledger",
        producer_version="1.0.0",
        artifact_kind="ledger_snapshot",
        payload_schema="decision-ledger-1.0",
    )
    receipt = engine.ingest(env, state=state)
    assert receipt.status == "accepted"

    re_exported = state.ledger.to_dict()
    assert state.ledger.ledger_digest() == orig_digest
    assert len(re_exported["decisions"]) == len(orig_export["decisions"])
    assert len(re_exported["bases"]) == len(orig_export["bases"])
    assert len(re_exported["forks"]) == len(orig_export["forks"])
    assert len(re_exported["state_events"]) == len(orig_export["state_events"])
    assert len(re_exported["corrections"]) == len(orig_export["corrections"])


def test_metamorphic_order_invariance_for_independent_artifacts():
    """Ingesting independent artifacts in different order results in identical CEG digest."""
    env_a = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "A",
            "claims": [{"claim": "Finding Alpha", "evidence_type": "computed", "source": "srcA", "support_status": "supported"}],
        },
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )
    env_b = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "B",
            "claims": [{"claim": "Finding Beta", "evidence_type": "computed", "source": "srcB", "support_status": "supported"}],
        },
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )

    # Ingestion order: A then B
    engine1 = IngestionEngine()
    state1 = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph())
    engine1.ingest(env_a, state=state1)
    engine1.ingest(env_b, state=state1)
    digest1 = state1.ceg.graph_digest()

    # Ingestion order: B then A
    engine2 = IngestionEngine()
    state2 = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph())
    engine2.ingest(env_b, state=state2)
    engine2.ingest(env_a, state=state2)
    digest2 = state2.ceg.graph_digest()

    assert digest1 == digest2

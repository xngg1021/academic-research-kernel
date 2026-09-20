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
    engine = IngestionEngine()
    state = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph())

    # Build envelope with tampered payload_sha256
    env = ArtifactEnvelope(
        protocol="artifact-envelope-1.0",
        artifact_id="art-" + "0" * 32,
        artifact_kind="evidence_receipt",
        producer={"skill": "academic-source-verification", "version": "1.0.0"},
        payload_schema="evidence-receipt-1.0",
        payload_sha256="f" * 64,  # forged
        payload={"schema_version": "1.0", "claims": []},
    )
    receipt = engine.ingest(env, state=state)
    assert receipt.status == "rejected"
    assert receipt.validation_state["valid"] is False
    assert any("SHA-256 mismatch" in e for e in receipt.validation_state["errors"])


def test_artifact_id_collision_fail_closed():
    engine = IngestionEngine()
    state = IngestionKernelState()

    env1 = ArtifactEnvelope.create(
        payload={"schema_version": "1.0", "query": "DOI:10.1000/1", "claims": []},
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )
    receipt1 = engine.ingest(env1, state=state)
    assert receipt1.status == "accepted"

    # Attacker crafts different payload but forces the same artifact_id
    diff_payload = {"schema_version": "1.0", "query": "DOI:10.1000/2", "claims": []}
    env_colliding = ArtifactEnvelope(
        protocol="artifact-envelope-1.0",
        artifact_id=env1.artifact_id,
        artifact_kind="evidence_receipt",
        producer={"skill": "academic-source-verification", "version": "1.0.0"},
        payload_schema="evidence-receipt-1.0",
        payload_sha256=compute_sha256(canonical_json_bytes(diff_payload)),
        payload=diff_payload,
    )

    with pytest.raises(ValueError, match="Hash collision detected for artifact"):
        engine.ingest(env_colliding, state=state)


def test_metamorphic_order_invariance_for_independent_artifacts():
    """Ingesting independent artifacts in different order results in identical CEG digest."""
    env_a = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "A",
            "claims": [{"claim": "Finding Alpha", "evidence_type": "data_point", "support_status": "supported"}],
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
            "claims": [{"claim": "Finding Beta", "evidence_type": "data_point", "support_status": "supported"}],
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

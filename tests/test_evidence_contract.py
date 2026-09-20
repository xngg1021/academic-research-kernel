"""Tests for shared Evidence Contract and Receipt Verification primitives."""

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "research-object-identity" / "scripts"))

import provenance

from shared_contracts.evidence import (
    ReceiptRef,
    canonical_receipt_ref_tuple,
    canonical_academic_receipt_payload_sha256,
    validate_lineage_receipt_contract,
    validate_academic_receipt_contract,
    verify_receipt_reference,
    canonical_json_bytes,
    canonical_text,
    compute_sha256,
    VALID_RECEIPT_KINDS,
)


def _lineage_fixture():
    graph = provenance.LineageGraph()
    graph.add_entity("target", "generic_entity")
    receipt = provenance.trace_origin(
        graph, "target", check_on_disk_hashes=False
    ).to_dict()
    ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id=receipt["receipt_id"],
        receipt_digest=receipt["receipt_digest"],
    )
    return receipt, ref


def _resign_lineage_receipt(receipt, check_on_disk_hashes=False):
    edge_key = lambda edge: (
        edge.get("type", ""),
        edge.get("source_id", ""),
        edge.get("target_id", ""),
        edge.get("activity_id") or "",
        canonical_json_bytes(edge.get("metadata", {})),
    )
    lineage_payload = {
        "protocol": "lineage-receipt-1.0",
        "target_id": receipt["target_id"],
        "root_ancestors": sorted(receipt["root_ancestors"]),
        "entities": sorted(receipt["entities"], key=lambda item: item["id"]),
        "activities": sorted(receipt["activities"], key=lambda item: item["id"]),
        "edges": sorted(receipt["edges"], key=edge_key),
        "trace_steps": receipt.get("trace_steps", []),
    }
    lineage_digest = compute_sha256(canonical_json_bytes(lineage_payload))
    receipt["lineage_digest"] = lineage_digest
    receipt["content_digest"] = lineage_digest
    verification_payload = {
        "lineage_digest": lineage_digest,
        "target_id": receipt["target_id"],
        "verification_status": receipt["verification_status"],
        "topology_status": receipt["topology_status"],
        "content_verification": receipt["content_verification"],
        "error_detail": receipt.get("error_detail") or "",
        "check_on_disk_hashes": check_on_disk_hashes,
    }
    receipt_digest = compute_sha256(canonical_json_bytes(verification_payload))
    receipt["receipt_digest"] = receipt_digest
    receipt["receipt_id"] = f"rec-{receipt_digest[:32]}"
    return ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id=receipt["receipt_id"],
        receipt_digest=receipt_digest,
    )


def test_shared_receipt_ref_lineage_validation():
    # Valid lineage ref
    ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id="rec-1234567890abcdef",
        receipt_digest="a" * 64,
        locator="https://example.org/p1",
    )
    assert ref.kind == "lineage"
    assert ref.receipt_id == "rec-1234567890abcdef"
    assert ref.receipt_digest == "a" * 64

    # Rejects invalid schema version
    with pytest.raises(ValueError, match="Invalid schema_version"):
        ReceiptRef(kind="lineage", schema_version="2.0", receipt_id="r1", receipt_digest="a" * 64)

    # Rejects missing ID or digest
    with pytest.raises(ValueError, match="requires non-empty 'receipt_id'"):
        ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="", receipt_digest="a" * 64)

    with pytest.raises(ValueError, match="requires non-empty 'receipt_digest'"):
        ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="r1", receipt_digest="")

    # Rejects academic fields
    with pytest.raises(ValueError, match="must not contain academic_evidence fields"):
        ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="r1", receipt_digest="a" * 64, claim_digest="b" * 64)

    # Rejects empty locator
    with pytest.raises(ValueError, match="locator must be a non-empty string"):
        ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id="r1", receipt_digest="a" * 64, locator="")


def test_shared_receipt_ref_academic_evidence_validation():
    # Valid academic evidence ref
    ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest="c" * 64,
        payload_sha256="d" * 64,
    )
    assert ref.kind == "academic_evidence"
    assert ref.claim_digest == "c" * 64
    assert ref.payload_sha256 == "d" * 64

    # Rejects lineage fields
    with pytest.raises(ValueError, match="must not contain lineage fields"):
        ReceiptRef(
            kind="academic_evidence",
            schema_version="1.0",
            claim_digest="c" * 64,
            payload_sha256="d" * 64,
            receipt_id="r1",
        )


def test_validate_lineage_receipt_contract():
    valid_receipt, ref = _lineage_fixture()
    ok, err = validate_lineage_receipt_contract(ref, valid_receipt)
    assert ok is True
    assert err is None

    # Protocol mismatch
    bad_proto = dict(valid_receipt, protocol="wrong")
    ok, err = validate_lineage_receipt_contract(ref, bad_proto)
    assert ok is False
    assert "protocol" in err

    # Digest mismatch
    bad_dig = dict(valid_receipt, receipt_digest="f" * 64)
    ok, err = validate_lineage_receipt_contract(ref, bad_dig)
    assert ok is False
    assert "digest mismatch" in err

    # Matching reference fields cannot bless altered lineage content.
    tampered = dict(valid_receipt)
    tampered["target_id"] = "different-target"
    ok, err = validate_lineage_receipt_contract(ref, tampered)
    assert ok is False
    assert "content digest mismatch" in err


def test_lineage_hashes_cannot_bless_a_dangling_edge_as_intact():
    receipt, _ = _lineage_fixture()
    receipt["edges"].append({
        "type": "used",
        "source_id": "missing-activity",
        "target_id": "target",
    })
    ref = _resign_lineage_receipt(receipt)

    ok, error = validate_lineage_receipt_contract(ref, receipt)

    assert ok is False
    assert "topology status mismatch" in error


@pytest.mark.parametrize("tamper", ["roots", "steps"])
def test_lineage_replay_rejects_resigned_roots_and_trace_steps(tamper):
    graph = provenance.LineageGraph()
    graph.add_entity("source", "data_snapshot")
    graph.add_entity("result", "statistic_artifact")
    graph.add_activity(
        "run",
        "statistical_analysis",
        timestamp="2026-09-20T00:00:00Z",
    )
    graph.record_used("run", "source")
    graph.record_generated("run", "result")
    receipt = provenance.trace_origin(
        graph,
        "result",
        check_on_disk_hashes=False,
    ).to_dict()
    if tamper == "roots":
        receipt["root_ancestors"] = ["result"]
    else:
        receipt["trace_steps"][0]["outputs"] = ["source"]
    ref = _resign_lineage_receipt(receipt)

    ok, error = validate_lineage_receipt_contract(ref, receipt)

    assert ok is False
    assert "root ancestors mismatch" in error or "trace steps" in error


def test_validate_academic_receipt_contract():
    claim = {
        "claim": "Interleaving enhances retention",
        "evidence_type": "computed",
        "locator": "p. 1042",
        "source": "DOI:10.1037/bul0000209",
        "support_status": "supported",
    }
    claims_list = [claim]
    payload = {
        "schema_version": "1.0",
        "claims": claims_list,
    }
    p_sha = compute_sha256(canonical_json_bytes(payload))
    c_dig = compute_sha256(canonical_json_bytes(claim))

    ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=c_dig,
        payload_sha256=p_sha,
    )

    ok, err = validate_academic_receipt_contract(ref, payload)
    assert ok is True
    assert err is None

    # Tampered payload SHA
    tampered_ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=c_dig,
        payload_sha256="0" * 64,
    )
    ok, err = validate_academic_receipt_contract(tampered_ref, payload)
    assert ok is False
    assert "payload SHA256 mismatch" in err


def test_academic_receipt_rejects_weaker_decision_claim_digest():
    claim = {
        "claim": "A fully qualified finding",
        "evidence_type": "computed",
        "locator": "table 2",
        "source": "doi:10.1000/example",
        "support_status": "contradicted",
    }
    payload = {"schema_version": "1.0", "claims": [claim]}
    weak_digest = compute_sha256(canonical_json_bytes({
        "text": claim["claim"],
        "decision_type": "claim",
        "locator": claim["locator"],
    }))
    ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=weak_digest,
        payload_sha256=compute_sha256(canonical_json_bytes(payload)),
    )

    ok, error = validate_academic_receipt_contract(ref, payload)

    assert ok is False
    assert "claim digest mismatch" in error


def test_verify_receipt_reference_dispatcher():
    lineage_receipt, lineage_ref = _lineage_fixture()
    ok, _ = verify_receipt_reference(lineage_ref, lineage_receipt)
    assert ok is True

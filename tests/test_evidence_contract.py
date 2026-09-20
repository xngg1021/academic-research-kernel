"""Tests for shared Evidence Contract and Receipt Verification primitives."""

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

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
    ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id="rec-100",
        receipt_digest="e" * 64,
    )
    valid_receipt = {
        "protocol": "lineage-receipt-1.0",
        "receipt_id": "rec-100",
        "receipt_digest": "e" * 64,
    }
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


def test_validate_academic_receipt_contract():
    claim = {
        "claim": "Interleaving enhances retention",
        "evidence_type": "data_point",
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


def test_verify_receipt_reference_dispatcher():
    lineage_ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id="rec-1",
        receipt_digest="1" * 64,
    )
    ok, _ = verify_receipt_reference(lineage_ref, {
        "protocol": "lineage-receipt-1.0",
        "receipt_id": "rec-1",
        "receipt_digest": "1" * 64,
    })
    assert ok is True

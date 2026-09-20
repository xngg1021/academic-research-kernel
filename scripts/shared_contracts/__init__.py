"""Shared Evidence Contract & Receipt Verification primitives for academic-research-kernel."""

from .evidence import (
    ReceiptRef,
    LineageVerificationContext,
    canonical_receipt_ref_tuple,
    canonical_academic_receipt_payload_sha256,
    canonical_evidence_claim_digest,
    validate_lineage_receipt_contract,
    validate_academic_receipt_contract,
    verify_receipt_reference,
    canonical_json_bytes,
    canonical_text,
    compute_sha256,
    VALID_RECEIPT_KINDS,
    SHA256_REGEX,
)

__all__ = [
    "ReceiptRef",
    "LineageVerificationContext",
    "canonical_receipt_ref_tuple",
    "canonical_academic_receipt_payload_sha256",
    "canonical_evidence_claim_digest",
    "validate_lineage_receipt_contract",
    "validate_academic_receipt_contract",
    "verify_receipt_reference",
    "canonical_json_bytes",
    "canonical_text",
    "compute_sha256",
    "VALID_RECEIPT_KINDS",
    "SHA256_REGEX",
]

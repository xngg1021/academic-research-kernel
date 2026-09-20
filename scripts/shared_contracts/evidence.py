"""Shared Evidence Contract & Receipt Verification Primitives.

This module provides the canonical, cross-capability implementation of receipt
references, serialization, and contract verification across ResearchObject
Identity, Claim-Evidence Graph, and Decision Ledger.
"""

from __future__ import annotations

import collections.abc
from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Dict, Iterator, Mapping, Optional, Tuple, Union

VALID_RECEIPT_KINDS = frozenset({"lineage", "academic_evidence"})
VALID_EVIDENCE_TYPES = frozenset({"metadata", "citation_count", "update_signal", "full_text", "computed"})
SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


class FrozenJSONMap(collections.abc.Mapping):
    """Deeply immutable mapping restricted to the canonical JSON value domain.

    ``dataclass(frozen=True)`` only prevents rebinding an attribute; a nested
    ``dict`` or ``list`` would otherwise remain mutable after its identity was
    verified.  This container recursively freezes mappings and sequences while
    retaining a lossless ``to_dict`` representation for schemas and hashing.
    """

    __slots__ = ("_data",)

    def __init__(self, value: Optional[Mapping[str, Any]] = None):
        if value is None:
            value = {}
        if not isinstance(value, collections.abc.Mapping):
            raise TypeError("FrozenJSONMap requires a mapping")
        frozen: Dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSON object keys must be strings, got {type(key).__name__}")
            frozen[key] = freeze_json(item)
        # Canonical serialization is also the fail-closed check for NaN/Inf.
        canonical_json_bytes({k: _thaw_val(v) for k, v in frozen.items()})
        object.__setattr__(self, "_data", MappingProxyType(frozen))

    def __setattr__(self, key: str, value: Any) -> None:
        raise TypeError("FrozenJSONMap does not support attribute mutation")

    def __delattr__(self, key: str) -> None:
        raise TypeError("FrozenJSONMap does not support attribute mutation")

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FrozenJSONMap":
        return self

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, collections.abc.Mapping):
            return False
        return self.to_dict() == _thaw_val(other)

    def __repr__(self) -> str:
        return f"FrozenJSONMap({self.to_dict()!r})"

    def to_dict(self) -> Dict[str, Any]:
        return {key: _thaw_val(value) for key, value in self._data.items()}


def freeze_json(value: Any) -> Any:
    """Recursively freeze a JSON-domain value and reject custom mutable objects."""
    if isinstance(value, FrozenJSONMap):
        return value
    if hasattr(value, "to_dict"):
        return freeze_json(value.to_dict())
    if isinstance(value, collections.abc.Mapping):
        return FrozenJSONMap(value)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        # Reject non-finite floats through the canonical serializer.
        canonical_json_bytes(value)
        return value
    raise TypeError(f"Value of type {type(value).__name__!r} is outside the JSON domain")


def canonical_text(text: str) -> str:
    """Normalize text deterministically (NFKC unicode, stripped)."""
    import unicodedata
    return unicodedata.normalize("NFKC", str(text)).strip()


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize object to strictly canonical UTF-8 JSON bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def compute_sha256(data: Union[str, bytes]) -> str:
    """Compute lowercase hex SHA-256 digest of string or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest().lower()


def _thaw_val(val: Any) -> Any:
    """Recursively convert custom dictionary/mapping types to standard dict/list."""
    if hasattr(val, "to_dict"):
        return val.to_dict()
    if isinstance(val, collections.abc.Mapping):
        return {k: _thaw_val(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_thaw_val(v) for v in val]
    return val


def _meta_canonical_json(m: Mapping[str, Any]) -> str:
    """Serialize metadata dictionary to canonical JSON string."""
    thawed = _thaw_val(m)
    return json.dumps(thawed, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class ReceiptRef:
    """Strongly typed receipt reference with strict kind-field mutual exclusivity."""

    kind: str
    schema_version: str
    receipt_id: Optional[str] = None
    receipt_digest: Optional[str] = None
    claim_digest: Optional[str] = None
    payload_sha256: Optional[str] = None
    locator: Optional[str] = None

    def __post_init__(self):
        if self.kind not in VALID_RECEIPT_KINDS:
            raise ValueError(f"Invalid receipt kind: {self.kind!r}. Must be one of {sorted(VALID_RECEIPT_KINDS)}")

        if self.kind == "lineage":
            if self.schema_version != "lineage-receipt-1.0":
                raise ValueError(
                    f"Invalid schema_version for lineage receipt: {self.schema_version!r}. Must be 'lineage-receipt-1.0'."
                )
            if not self.receipt_id:
                raise ValueError("Lineage ReceiptRef requires non-empty 'receipt_id'.")
            if not self.receipt_digest:
                raise ValueError("Lineage ReceiptRef requires non-empty 'receipt_digest'.")
            r_dig = self.receipt_digest.strip().lower()
            if not SHA256_REGEX.match(r_dig):
                raise ValueError(f"Invalid receipt_digest format: {self.receipt_digest!r}. Must be 64 lowercase hex digits.")
            object.__setattr__(self, "receipt_digest", r_dig)
            if self.claim_digest is not None or self.payload_sha256 is not None:
                raise ValueError("Lineage ReceiptRef must not contain academic_evidence fields (claim_digest or payload_sha256).")

        elif self.kind == "academic_evidence":
            if self.schema_version != "1.0":
                raise ValueError(
                    f"Invalid schema_version for academic_evidence receipt: {self.schema_version!r}. Must be '1.0'."
                )
            if not self.claim_digest:
                raise ValueError("AcademicEvidence ReceiptRef requires non-empty 'claim_digest'.")
            if not self.payload_sha256:
                raise ValueError("AcademicEvidence ReceiptRef requires non-empty 'payload_sha256'.")
            c_dig = self.claim_digest.strip().lower()
            if not SHA256_REGEX.match(c_dig):
                raise ValueError(f"Invalid claim_digest format: {self.claim_digest!r}. Must be 64 lowercase hex digits.")
            object.__setattr__(self, "claim_digest", c_dig)
            p_dig = self.payload_sha256.strip().lower()
            if not SHA256_REGEX.match(p_dig):
                raise ValueError(f"Invalid payload_sha256 format: {self.payload_sha256!r}. Must be 64 lowercase hex digits.")
            object.__setattr__(self, "payload_sha256", p_dig)
            if self.receipt_id is not None or self.receipt_digest is not None:
                raise ValueError("AcademicEvidence ReceiptRef must not contain lineage fields (receipt_id or receipt_digest).")

        if self.locator is not None:
            if not isinstance(self.locator, str) or not (1 <= len(self.locator) <= 2048):
                raise ValueError("locator must be a non-empty string of at most 2048 characters.")

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "kind": self.kind,
            "schema_version": self.schema_version,
        }
        if self.receipt_id:
            d["receipt_id"] = self.receipt_id
        if self.receipt_digest:
            d["receipt_digest"] = self.receipt_digest
        if self.claim_digest:
            d["claim_digest"] = self.claim_digest
        if self.payload_sha256:
            d["payload_sha256"] = self.payload_sha256
        if self.locator:
            d["locator"] = self.locator
        return d


def canonical_receipt_ref_tuple(ref: Optional[ReceiptRef]) -> Tuple[str, ...]:
    """Serialize ReceiptRef to a canonical tuple for cryptographic edge identities."""
    if not ref:
        return ()
    return (
        ref.kind,
        ref.schema_version,
        ref.receipt_id or "",
        ref.receipt_digest or "",
        ref.claim_digest or "",
        ref.payload_sha256 or "",
        ref.locator or "",
    )


def canonical_academic_receipt_payload_sha256(receipt_dict: Mapping[str, Any]) -> str:
    """Compute physical payload_sha256 for AcademicEvidenceReceipt per PR #9.

    Reconstructs the precise bytes that the academic-source-verification engine
    hashed, verifying cryptographic proof of source verification.
    """
    thawed = _thaw_val(receipt_dict)
    if not isinstance(thawed, dict):
        thawed = dict(thawed)
    return hashlib.sha256(canonical_json_bytes(thawed)).hexdigest().lower()


def canonical_evidence_claim_digest(claim_item: Mapping[str, Any]) -> str:
    """Compute digest of an exact claim entry inside an AcademicEvidenceReceipt."""
    payload = {
        "claim": claim_item.get("claim", ""),
        "evidence_type": claim_item.get("evidence_type", ""),
        "locator": claim_item.get("locator", ""),
        "source": claim_item.get("source", ""),
        "support_status": claim_item.get("support_status", ""),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().lower()


def validate_lineage_receipt_integrity(receipt_obj: Any) -> Tuple[bool, Optional[str]]:
    """Recompute both identities of a serialized LineageReceipt.

    Historical v1 receipts did not serialize ``check_on_disk_hashes`` even
    though it participates in ``receipt_digest``.  Verification therefore
    tries both legitimate boolean modes and still rejects every other digest.
    """
    value = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
    if not isinstance(value, collections.abc.Mapping):
        return False, "Lineage receipt must be an object/mapping"
    data = _thaw_val(value)
    try:
        edge_key = lambda edge: (
            edge.get("type", ""),
            edge.get("source_id", ""),
            edge.get("target_id", ""),
            edge.get("activity_id") or "",
            canonical_json_bytes(edge.get("metadata", {})),
        )
        lineage_payload = {
            "protocol": "lineage-receipt-1.0",
            "target_id": data["target_id"],
            "root_ancestors": sorted(data["root_ancestors"]),
            "entities": sorted(data["entities"], key=lambda item: item["id"]),
            "activities": sorted(data["activities"], key=lambda item: item["id"]),
            "edges": sorted(data["edges"], key=edge_key),
            "trace_steps": data.get("trace_steps", []),
        }
        recomputed_lineage = compute_sha256(canonical_json_bytes(lineage_payload))
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"Lineage receipt cannot be canonically replayed: {exc}"

    declared_lineage = str(data.get("lineage_digest", "")).lower()
    missing_input_form = (
        declared_lineage == "0" * 64
        and data.get("verification_status") == "missing_input"
        and data.get("topology_status") == "missing_input"
        and data.get("content_verification") == "unchecked"
        and not data.get("root_ancestors")
        and not data.get("entities")
        and not data.get("activities")
        and not data.get("edges")
        and not data.get("trace_steps")
    )
    lineage_digest = declared_lineage if missing_input_form else recomputed_lineage
    if declared_lineage != lineage_digest:
        return False, (
            f"Lineage content digest mismatch: declared {declared_lineage!r}, "
            f"recomputed {lineage_digest!r}"
        )
    if data.get("content_digest") is not None and str(data["content_digest"]).lower() != lineage_digest:
        return False, "Lineage content_digest alias does not match lineage_digest"

    receipt_base = {
        "lineage_digest": lineage_digest,
        "target_id": data["target_id"],
        "verification_status": data["verification_status"],
        "topology_status": data["topology_status"],
        "content_verification": data["content_verification"],
        "error_detail": data.get("error_detail") or "",
    }
    possible = {
        compute_sha256(canonical_json_bytes(dict(receipt_base, check_on_disk_hashes=mode)))
        for mode in (False, True)
    }
    declared_receipt = str(data.get("receipt_digest", "")).lower()
    if declared_receipt not in possible:
        return False, "Lineage verification receipt_digest does not match either valid verification mode"
    if data.get("receipt_id") != f"rec-{declared_receipt[:32]}":
        return False, "Lineage receipt_id is not derived from receipt_digest"
    return True, None


def validate_lineage_receipt_contract(ref: ReceiptRef, receipt_obj: Any) -> Tuple[bool, Optional[str]]:
    """Strictly assert lineage-receipt-1.0 protocol, exact receipt_id, and exact receipt_digest."""
    r_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
    if not isinstance(r_dict, (dict, collections.abc.Mapping)) or r_dict.get("protocol") != "lineage-receipt-1.0":
        return False, "Lineage receipt invalid protocol: expected 'lineage-receipt-1.0'"
    if r_dict.get("receipt_id") != ref.receipt_id:
        return False, f"Lineage receipt ID mismatch: expected {ref.receipt_id!r}, got {r_dict.get('receipt_id')!r}"
    if str(r_dict.get("receipt_digest", "")).lower() != str(ref.receipt_digest).lower():
        return False, f"Lineage receipt digest mismatch: expected {ref.receipt_digest!r}, got {r_dict.get('receipt_digest')!r}"
    return validate_lineage_receipt_integrity(r_dict)


def validate_academic_receipt_contract(ref: ReceiptRef, receipt_obj: Any) -> Tuple[bool, Optional[str]]:
    """Strictly assert academic_evidence physical payload SHA256 and claim_digest membership."""
    val_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
    if not isinstance(val_dict, (dict, collections.abc.Mapping)):
        return False, "AcademicEvidence receipt must be a dict or mapping"
    thawed = _thaw_val(val_dict)
    actual_sha = canonical_academic_receipt_payload_sha256(thawed)
    if actual_sha != ref.payload_sha256:
        return False, f"AcademicEvidence payload SHA256 mismatch: expected {ref.payload_sha256}, got actual hash {actual_sha}"
    if thawed.get("schema_version") != "1.0" or not isinstance(thawed.get("claims"), (list, tuple)):
        return False, "AcademicEvidence receipt structural violation: missing schema_version=1.0 or claims list"

    matched_claim = False
    for claim in thawed["claims"]:
        if not isinstance(claim, (dict, collections.abc.Mapping)):
            continue
        c_dict = claim if isinstance(claim, dict) else dict(claim)
        if c_dict.get("evidence_type") not in VALID_EVIDENCE_TYPES:
            continue
        # Check standard CEG claim digest
        if canonical_evidence_claim_digest(c_dict) == ref.claim_digest:
            matched_claim = True
            break
        # Check decision claim digest (text + locator)
        d_payload = {
            "text": canonical_text(c_dict.get("text", c_dict.get("claim", ""))),
            "decision_type": "claim",
        }
        if c_dict.get("context_work_id"):
            d_payload["context_work_id"] = c_dict["context_work_id"]
        if c_dict.get("locator"):
            d_payload["locator"] = c_dict["locator"]
        if hashlib.sha256(canonical_json_bytes(d_payload)).hexdigest().lower() == ref.claim_digest:
            matched_claim = True
            break

    if not matched_claim:
        return False, f"AcademicEvidence claim digest mismatch: claim_digest {ref.claim_digest} not found in legitimate receipt claims"
    return True, None


def verify_receipt_reference(ref: ReceiptRef, receipt_obj: Any) -> Tuple[bool, Optional[str]]:
    """Verify any ReceiptRef against a physical receipt instance based on kind."""
    if ref.kind == "lineage":
        return validate_lineage_receipt_contract(ref, receipt_obj)
    if ref.kind == "academic_evidence":
        return validate_academic_receipt_contract(ref, receipt_obj)
    return False, f"Unsupported receipt kind: {ref.kind!r}"

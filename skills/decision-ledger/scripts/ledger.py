# -*- coding: utf-8 -*-
"""Decision & Negative Result Ledger Kernel v1.

Deterministic, append-only ledger for research decisions, negative results,
prune causality, and outcome corrections. Directly consumes the same receipt
contracts as the Claim-Evidence Graph Kernel (LineageReceipt and
AcademicEvidenceReceipt via a byte-compatible ReceiptRef).

Core Invariants:
1. Append-only history with no destructive mutation:
   Decisions, bases, forks, prune states, and outcome corrections are
   immutable records; outcome changes are recorded as new correction events
   (content-addressed), never as in-place updates.
2. Rejection of Truth Authority and subjective scores:
   No confidence values, no utility scores, no ranking numbers. Verdicts are
   discrete enumerations; reasons are closed vocabularies plus free-text
   rationale. The ledger records choices and evidence, it never judges truth.
3. Strongly typed ReceiptRef with strict mutual exclusivity:
   LineageReceipt requires lineage-receipt-1.0, receipt_id, receipt_digest
   (no academic fields). AcademicEvidenceReceipt requires 1.0, claim_digest,
   payload_sha256 (no lineage fields). The contract is byte-compatible with
   the Claim-Evidence Graph Kernel.
4. Strict actual payload verification:
   AcademicEvidenceReceipt payload SHA256 is physically recomputed and
   asserted; LineageReceipt protocol/id/digest are positively asserted.
   External registries cannot bypass verification.
5. Deeply frozen records & immutable metadata mapping:
   Every record is a frozen dataclass and every metadata mapping is a
   FrozenDict, preventing nested mutation drift. Receipt registration
   deepcopies payloads preventing external mutation.
6. Negative results are evidence-bearing claims of absence:
   A negative_result decision must carry at least one basis edge that cites
   a Claim node (or the negative result itself must be consumable as a claim
   basis by downstream kernels). A negative result supported only by other
   negative results is a contradiction-free circular void and fails
   validation (E405).
7. Prune causality is first-class and acyclic:
   A pruned decision records a closed-vocabulary reason, the pruning
   decision, and the chosen alternative. pruned_by chains must be acyclic
   (circular pruning fails validation). A pruning decision must cite at
   least one Claim basis; otherwise the uncertainty queue surfaces it for
   human review.
8. Three-state uncertainty queue discipline:
   unverifiable / unresolved / missing are surfaced as deterministic
   content-addressed UncertaintyItem records; the queue never blocks
   deterministic validation of the structural graph.
9. Order-invariant ledger digest:
   Full canonical sorting across all records; insertion order never affects
   ledger_digest. Registered receipts contribute canonical payload hashes.
10. Lexical canonicalization only:
   NFC normalization and whitespace compaction; decision titles are never
   rewritten or paraphrased semantically.
"""
from __future__ import annotations

import collections
import collections.abc
import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

PROTOCOL = "decision-ledger-1.0"

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")
ID_REGEX = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

VALID_DECISION_TYPES: set = {"explore", "commit", "abandon", "revise", "negative_result"}
VALID_BASIS_KINDS: set = {"claim", "negative_result"}
VALID_FORK_RELATIONS: set = {"considered", "explored", "deferred", "rejected"}
VALID_PRUNE_STATUSES: set = {"active", "pruned"}
VALID_PRUNE_REASONS: set = {
    "resource_exhausted",
    "superseded",
    "contradicted",
    "out_of_scope",
    "duplicate",
    "external_constraint",
    "investigator_error",
    "other",
}
VALID_VERDICTS: set = {"positive", "negative", "inconclusive", "unverifiable"}
VALID_RECEIPT_KINDS: set = {"academic_evidence", "lineage"}
VALID_UNCERTAINTY_KINDS: set = {
    "decision_without_basis",
    "unsupported_negative_result",
    "missing_receipt",
    "unsupported_pruning",
    "generic_uncertainty",
}

__all__ = [
    "PROTOCOL",
    "FrozenDict",
    "ReceiptRef",
    "DecisionNode",
    "DecisionBasisEdge",
    "DecisionForkEdge",
    "PruneState",
    "OutcomeCorrection",
    "UncertaintyItem",
    "DecisionLedger",
    "canonical_text",
    "compute_decision_digest",
    "compute_outcome_digest",
    "canonical_basis_tuple",
    "canonical_fork_tuple",
    "canonical_receipt_ref_tuple",
    "canonical_ledger_payload_sha256",
    "canonical_academic_receipt_payload_sha256",
    "canonical_evidence_claim_digest",
    "validate_lineage_receipt_contract",
    "validate_academic_receipt_contract",
]


# ---------------------------------------------------------------------------
# Canonicalization helpers (byte-compatible with the CEG Kernel)
# ---------------------------------------------------------------------------

def canonical_text(text: str) -> str:
    """Lexical canonicalization: NFC + line-ending unification + whitespace compaction.

    Never rewrites or paraphrases the content semantically.
    """
    if not isinstance(text, str):
        raise TypeError(f"canonical_text expects str, got {type(text).__name__}")
    normalized = unicodedata.normalize("NFC", text)
    normalized = " ".join(normalized.splitlines())
    return re.sub(r"\s+", " ", normalized).strip()


def _canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def compute_decision_digest(
    text: str,
    context_work_id: Optional[str] = None,
    locator: Optional[str] = None,
    decision_type: str = "explore",
) -> str:
    """Content-addressed digest of a decision (normalized title + coordinates + type)."""
    payload = {
        "version": 1,
        "text": canonical_text(text),
        "context_work_id": context_work_id,
        "locator": locator,
        "decision_type": decision_type,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()


def compute_outcome_digest(
    verdict: str,
    rationale: str,
    receipt_ref: Optional["ReceiptRef"] = None,
    locator: Optional[str] = None,
) -> str:
    """Content-addressed digest of an outcome correction event."""
    payload = {
        "version": 1,
        "verdict": verdict,
        "rationale": canonical_text(rationale),
        "receipt": canonical_receipt_ref_tuple(receipt_ref),
        "locator": locator,
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()


def canonical_ledger_payload_sha256(payload_dict: Mapping[str, Any]) -> str:
    """Canonical SHA256 of an arbitrary JSON-able ledger payload (sorted keys)."""
    return hashlib.sha256(_canonical_json_bytes(payload_dict)).hexdigest().lower()


def canonical_academic_receipt_payload_sha256(receipt_dict: Mapping[str, Any]) -> str:
    """Compute canonical SHA256 of AcademicEvidenceReceipt payload matching schema.

    Byte-compatible with Claim-Evidence Graph Kernel v1.
    """
    return hashlib.sha256(_canonical_json_bytes(receipt_dict)).hexdigest().lower()


def canonical_evidence_claim_digest(claim_item: Mapping[str, Any]) -> str:
    """Canonical digest of an evidence claim record inside an AcademicEvidenceReceipt.

    Byte-compatible with Claim-Evidence Graph Kernel v1: digest is computed
    over a fixed five-field projection (claim, evidence_type, locator,
    source, support_status) with sorted keys.
    """
    payload = {
        "claim": claim_item.get("claim", ""),
        "evidence_type": claim_item.get("evidence_type", ""),
        "locator": claim_item.get("locator", ""),
        "source": claim_item.get("source", ""),
        "support_status": claim_item.get("support_status", ""),
    }
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()


# ---------------------------------------------------------------------------
# Deeply frozen mapping
# ---------------------------------------------------------------------------

def _freeze_val(val: Any) -> Any:
    if isinstance(val, FrozenDict):
        return val
    if isinstance(val, collections.abc.Mapping):
        return FrozenDict(val)
    if isinstance(val, (list, tuple)):
        return tuple(_freeze_val(item) for item in val)
    if isinstance(val, (set, frozenset)):
        return frozenset(_freeze_val(item) for item in val)
    return val


def _thaw_val(val: Any) -> Any:
    if isinstance(val, FrozenDict):
        return val.to_dict()
    if isinstance(val, tuple):
        return [_thaw_val(item) for item in val]
    if isinstance(val, frozenset):
        return sorted(_thaw_val(item) for item in val)  # type: ignore[arg-type]
    return val


class FrozenDict(collections.abc.Mapping):
    """Immutable mapping with deep freezing and cached structural hash."""

    __slots__ = ("_data", "_hash")

    def __init__(self, mapping_or_iterable: Any = None):
        if mapping_or_iterable is None:
            source: Mapping[str, Any] = {}
        elif isinstance(mapping_or_iterable, collections.abc.Mapping):
            source = mapping_or_iterable
        else:
            source = dict(mapping_or_iterable)
        frozen = {str(k): _freeze_val(v) for k, v in source.items()}
        object.__setattr__(self, "_data", frozen)
        object.__setattr__(self, "_hash", None)

    def __setattr__(self, key: str, value: Any):
        raise TypeError(f"'{self.__class__.__name__}' object does not support mutation.")

    def __delattr__(self, key: str):
        raise TypeError(f"'{self.__class__.__name__}' object does not support mutation.")

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __hash__(self) -> int:
        cached = object.__getattribute__(self, "_hash")
        if cached is None:
            h = hash(frozenset(self._data.items()))
            object.__setattr__(self, "_hash", h)
            cached = h
        return cached

    def __setitem__(self, key: Any, value: Any):
        raise TypeError(f"'{self.__class__.__name__}' object does not support item assignment (deeply frozen record).")

    def __delitem__(self, key: Any):
        raise TypeError(f"'{self.__class__.__name__}' object does not support item deletion (deeply frozen record).")

    def clear(self):
        raise TypeError(f"'{self.__class__.__name__}' object does not support mutation.")

    def update(self, *args, **kwargs):
        raise TypeError(f"'{self.__class__.__name__}' object does not support mutation.")

    def pop(self, *args, **kwargs):
        raise TypeError(f"'{self.__class__.__name__}' object does not support mutation.")

    def to_dict(self) -> Dict[str, Any]:
        return {k: _thaw_val(v) for k, v in self._data.items()}

    def __repr__(self) -> str:
        return f"FrozenDict({self.to_dict()!r})"


# ---------------------------------------------------------------------------
# Receipt contracts (byte-compatible with the CEG Kernel)
# ---------------------------------------------------------------------------

def validate_lineage_receipt_contract(ref: "ReceiptRef", receipt_obj: Any) -> Tuple[bool, Optional[str]]:
    """Strictly assert lineage-receipt-1.0 protocol, exact receipt_id, and exact receipt_digest."""
    r_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
    if not isinstance(r_dict, (dict, collections.abc.Mapping)) or r_dict.get("protocol") != "lineage-receipt-1.0":
        return False, "Lineage receipt invalid protocol: expected 'lineage-receipt-1.0'"
    if r_dict.get("receipt_id") != ref.receipt_id:
        return False, f"Lineage receipt ID mismatch: expected {ref.receipt_id!r}, got {r_dict.get('receipt_id')!r}"
    if str(r_dict.get("receipt_digest", "")).lower() != str(ref.receipt_digest).lower():
        return False, f"Lineage receipt digest mismatch: expected {ref.receipt_digest!r}, got {r_dict.get('receipt_digest')!r}"
    return True, None


def validate_academic_receipt_contract(ref: "ReceiptRef", receipt_obj: Any) -> Tuple[bool, Optional[str]]:
    """Strictly assert schema_version=1.0, physical payload SHA256, and exact claim match.

    The claim must be a legitimate evidence record (evidence_type within the
    schema's evidence-type vocabulary) whose canonical digest equals the
    referenced claim_digest. Byte-compatible with Claim-Evidence Graph Kernel v1.
    """
    val_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
    if not isinstance(val_dict, (dict, collections.abc.Mapping)):
        return False, "AcademicEvidence invalid representation: must be a dict"
    thawed = val_dict if isinstance(val_dict, dict) else dict(val_dict)
    actual_sha = canonical_academic_receipt_payload_sha256(thawed)
    if actual_sha != ref.payload_sha256:
        return False, f"AcademicEvidence payload SHA256 mismatch: expected {ref.payload_sha256}, got actual hash {actual_sha}"
    if thawed.get("schema_version") != "1.0" or not isinstance(thawed.get("claims"), (list, tuple)):
        return False, "AcademicEvidence receipt structural violation: missing schema_version=1.0 or claims list"

    matching_claim = False
    for c_item in thawed.get("claims", []):
        if not isinstance(c_item, (dict, collections.abc.Mapping)):
            continue
        c_dict = c_item if isinstance(c_item, dict) else dict(c_item)
        if c_dict.get("evidence_type") not in {"metadata", "citation_count", "update_signal", "full_text", "computed"}:
            continue
        if canonical_evidence_claim_digest(c_dict) == ref.claim_digest:
            matching_claim = True
            break
    if not matching_claim:
        return False, f"AcademicEvidence claim digest mismatch: claim_digest {ref.claim_digest} not found in legitimate receipt claims"
    return True, None


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
                raise ValueError(f"Invalid schema_version for lineage receipt: {self.schema_version!r}. Must be 'lineage-receipt-1.0'.")
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
                raise ValueError(f"Invalid schema_version for academic_evidence receipt: {self.schema_version!r}. Must be '1.0'.")
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


def _check_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"'{field_name}' must be a non-empty string.")
    if not ID_REGEX.match(value):
        raise ValueError(f"Invalid {field_name}: {value!r}. Must match {ID_REGEX.pattern} (max 64 chars).")
    return value


def _frozen_meta(metadata: Optional[Mapping[str, Any]]) -> FrozenDict:
    return FrozenDict(metadata) if metadata else FrozenDict()


def _meta_canonical_json(metadata: FrozenDict) -> str:
    return json.dumps(metadata.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


# ---------------------------------------------------------------------------
# Immutable records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DecisionNode:
    """A research decision: an explore/commit/abandon/revise act or a negative result."""

    id: str
    title: str
    decision_type: str = "explore"
    context_work_id: Optional[str] = None
    locator: Optional[str] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)
    normalized_title: str = field(init=False)
    decision_digest: str = field(init=False)

    def __post_init__(self):
        _check_id(self.id, "decision id")
        if self.decision_type not in VALID_DECISION_TYPES:
            raise ValueError(f"Invalid decision_type: {self.decision_type!r}. Must be one of {sorted(VALID_DECISION_TYPES)}")
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("Decision 'title' must be a non-empty string.")
        norm_title = canonical_text(self.title)
        object.__setattr__(self, "normalized_title", norm_title)
        digest = compute_decision_digest(
            text=norm_title,
            context_work_id=self.context_work_id,
            locator=self.locator,
            decision_type=self.decision_type,
        )
        object.__setattr__(self, "decision_digest", digest)
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "normalized_title": self.normalized_title,
            "decision_type": self.decision_type,
            "decision_digest": self.decision_digest,
        }
        if self.context_work_id:
            d["context_work_id"] = self.context_work_id
        if self.locator:
            d["locator"] = self.locator
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


@dataclass(frozen=True)
class DecisionBasisEdge:
    """A directed edge: a decision was made on the basis of a claim or a negative result."""

    decision_id: str
    basis_kind: str
    basis_id: str
    receipt_ref: Optional[ReceiptRef] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.decision_id, "decision_id")
        if self.basis_kind not in VALID_BASIS_KINDS:
            raise ValueError(f"Invalid basis_kind: {self.basis_kind!r}. Must be one of {sorted(VALID_BASIS_KINDS)}")
        _check_id(self.basis_id, "basis_id")
        if self.receipt_ref is not None and not isinstance(self.receipt_ref, ReceiptRef):
            raise TypeError("receipt_ref must be a ReceiptRef instance or None.")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "basis_kind": self.basis_kind,
            "basis_id": self.basis_id,
        }
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_basis_tuple(edge: DecisionBasisEdge) -> Tuple[str, ...]:
    return (
        edge.decision_id,
        edge.basis_kind,
        edge.basis_id,
    ) + canonical_receipt_ref_tuple(edge.receipt_ref) + (_meta_canonical_json(edge.metadata),)


@dataclass(frozen=True)
class DecisionForkEdge:
    """A directed edge between decision branches (alternatives considered at a fork)."""

    decision_id: str
    alternative_id: str
    relation: str = "considered"
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.decision_id, "decision_id")
        _check_id(self.alternative_id, "alternative_id")
        if self.relation not in VALID_FORK_RELATIONS:
            raise ValueError(f"Invalid fork relation: {self.relation!r}. Must be one of {sorted(VALID_FORK_RELATIONS)}")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "alternative_id": self.alternative_id,
            "relation": self.relation,
        }
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_fork_tuple(edge: DecisionForkEdge) -> Tuple[str, ...]:
    return (
        edge.decision_id,
        edge.alternative_id,
        edge.relation,
        _meta_canonical_json(edge.metadata),
    )


@dataclass(frozen=True)
class PruneState:
    """Lifecycle state of a decision branch: active, or pruned with closed-vocabulary reason."""

    decision_id: str
    status: str
    prune_reason: Optional[str] = None
    pruned_by: Optional[str] = None
    alternative_ref: Optional[str] = None
    receipt_ref: Optional[ReceiptRef] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.decision_id, "decision_id")
        if self.status not in VALID_PRUNE_STATUSES:
            raise ValueError(f"Invalid prune status: {self.status!r}. Must be one of {sorted(VALID_PRUNE_STATUSES)}")
        if self.status == "pruned":
            if not self.prune_reason:
                raise ValueError("Pruned decision requires a non-empty 'prune_reason'.")
            if self.prune_reason not in VALID_PRUNE_REASONS:
                raise ValueError(f"Invalid prune_reason: {self.prune_reason!r}. Must be one of {sorted(VALID_PRUNE_REASONS)}")
            if self.pruned_by is not None:
                _check_id(self.pruned_by, "pruned_by")
                if self.pruned_by == self.decision_id:
                    raise ValueError(f"Circular pruning: decision '{self.decision_id}' cannot prune itself.")
            if self.alternative_ref is not None:
                _check_id(self.alternative_ref, "alternative_ref")
                if self.alternative_ref == self.decision_id:
                    raise ValueError(f"Self-referential alternative: decision '{self.decision_id}' cannot be its own alternative.")
        else:
            if self.prune_reason is not None or self.pruned_by is not None or self.alternative_ref is not None:
                raise ValueError("Active decision must not carry prune_reason/pruned_by/alternative_ref fields.")
        if self.receipt_ref is not None and not isinstance(self.receipt_ref, ReceiptRef):
            raise TypeError("receipt_ref must be a ReceiptRef instance or None.")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "status": self.status,
        }
        if self.prune_reason:
            d["prune_reason"] = self.prune_reason
        if self.pruned_by:
            d["pruned_by"] = self.pruned_by
        if self.alternative_ref:
            d["alternative_ref"] = self.alternative_ref
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_prune_tuple(state: PruneState) -> Tuple[str, ...]:
    return (
        state.decision_id,
        state.status,
        state.prune_reason or "",
        state.pruned_by or "",
        state.alternative_ref or "",
    ) + canonical_receipt_ref_tuple(state.receipt_ref) + (_meta_canonical_json(state.metadata),)


@dataclass(frozen=True)
class OutcomeCorrection:
    """An append-only outcome verdict for a decision (never an in-place update)."""

    correction_id: str
    decision_id: str
    verdict: str
    rationale: str
    outcome_digest: str = field(init=False)
    receipt_ref: Optional[ReceiptRef] = None
    locator: Optional[str] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.correction_id, "correction_id")
        _check_id(self.decision_id, "decision_id")
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(f"Invalid verdict: {self.verdict!r}. Must be one of {sorted(VALID_VERDICTS)}")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("Outcome correction requires a non-empty 'rationale'.")
        if self.receipt_ref is not None and not isinstance(self.receipt_ref, ReceiptRef):
            raise TypeError("receipt_ref must be a ReceiptRef instance or None.")
        digest = compute_outcome_digest(
            verdict=self.verdict,
            rationale=self.rationale,
            receipt_ref=self.receipt_ref,
            locator=self.locator,
        )
        object.__setattr__(self, "outcome_digest", digest)
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "correction_id": self.correction_id,
            "decision_id": self.decision_id,
            "verdict": self.verdict,
            "rationale": self.rationale,
            "outcome_digest": self.outcome_digest,
        }
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if self.locator:
            d["locator"] = self.locator
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_correction_tuple(c: OutcomeCorrection) -> Tuple[str, ...]:
    return (
        c.correction_id,
        c.decision_id,
        c.verdict,
        canonical_text(c.rationale),
        c.outcome_digest,
    ) + canonical_receipt_ref_tuple(c.receipt_ref) + (c.locator or "", _meta_canonical_json(c.metadata))


@dataclass(frozen=True)
class UncertaintyItem:
    """A three-state uncertainty queue item (content-addressed deterministic id).

    Shape-compatible with the Claim-Evidence Graph Kernel's UncertaintyItem.
    """

    item_id: str
    subject_id: str
    kind: str
    reason: str
    needs_human: bool
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        if self.kind not in VALID_UNCERTAINTY_KINDS:
            raise ValueError(f"Invalid uncertainty kind: {self.kind!r}. Must be one of {sorted(VALID_UNCERTAINTY_KINDS)}")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "item_id": self.item_id,
            "subject_id": self.subject_id,
            "kind": self.kind,
            "reason": self.reason,
            "needs_human": self.needs_human,
        }
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


# ---------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------

class DecisionLedger:
    """Deterministic append-only Decision & Negative Result Ledger.

    Nodes and edges are immutable; duplicates with conflicting payloads are
    rejected; identical registrations are idempotent. The ledger digest is
    order-invariant.
    """

    def __init__(self, ledger_id: str = "ledger-default"):
        if not isinstance(ledger_id, str) or not ledger_id.strip():
            raise ValueError("ledger_id must be a non-empty string.")
        self.ledger_id = ledger_id
        self._decisions: Dict[str, DecisionNode] = {}
        self._bases: Dict[Tuple[str, ...], DecisionBasisEdge] = {}
        self._forks: Dict[Tuple[str, ...], DecisionForkEdge] = {}
        self._prune_states: Dict[str, PruneState] = {}
        self._corrections: Dict[str, OutcomeCorrection] = {}
        self._receipts: Dict[str, Any] = {}

    # -- registration -------------------------------------------------------

    def register_receipt(self, receipt_id: str, receipt_data: Any):
        """Register a receipt payload with deepcopy and conflict rejection.

        For academic_evidence references the canonical payload SHA256 acts as
        the lookup key (mirroring the CEG Kernel); for lineage references the
        receipt_id acts as the lookup key.
        """
        if not isinstance(receipt_id, str) or not receipt_id.strip():
            raise ValueError("receipt_id must be a non-empty string.")
        rid = receipt_id.strip()
        snapshot = copy.deepcopy(receipt_data)
        if rid in self._receipts:
            existing = self._receipts[rid]
            ex_dict = existing.to_dict() if hasattr(existing, "to_dict") else existing
            new_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
            if ex_dict != new_dict:
                raise ValueError(f"Conflicting receipt registration for {rid!r}: existing data differs from new registration.")
            return
        self._receipts[rid] = snapshot

    def _register_node(self, store: Dict[str, Any], obj: Any, obj_id: str, label: str):
        existing = store.get(obj_id)
        if existing is not None:
            if existing.to_dict() != obj.to_dict():
                raise ValueError(f"Duplicate {label} registration with conflicting payload: {obj_id!r}")
            return existing
        store[obj_id] = obj
        return obj

    def add_decision(
        self,
        id: str,
        title: str,
        decision_type: str = "explore",
        context_work_id: Optional[str] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionNode:
        node = DecisionNode(
            id=id,
            title=title,
            decision_type=decision_type,
            context_work_id=context_work_id,
            locator=locator,
            metadata=metadata or {},
        )
        return self._register_node(self._decisions, node, id, "decision")

    def add_basis(
        self,
        decision_id: str,
        basis_kind: str,
        basis_id: str,
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionBasisEdge:
        edge = DecisionBasisEdge(
            decision_id=decision_id,
            basis_kind=basis_kind,
            basis_id=basis_id,
            receipt_ref=receipt_ref,
            metadata=metadata or {},
        )
        key = canonical_basis_tuple(edge)
        existing = self._bases.get(key)
        if existing is not None:
            return existing
        self._bases[key] = edge
        return edge

    def add_fork(
        self,
        decision_id: str,
        alternative_id: str,
        relation: str = "considered",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionForkEdge:
        edge = DecisionForkEdge(
            decision_id=decision_id,
            alternative_id=alternative_id,
            relation=relation,
            metadata=metadata or {},
        )
        key = canonical_fork_tuple(edge)
        existing = self._forks.get(key)
        if existing is not None:
            return existing
        self._forks[key] = edge
        return edge

    def set_prune(
        self,
        decision_id: str,
        status: str,
        prune_reason: Optional[str] = None,
        pruned_by: Optional[str] = None,
        alternative_ref: Optional[str] = None,
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PruneState:
        state = PruneState(
            decision_id=decision_id,
            status=status,
            prune_reason=prune_reason,
            pruned_by=pruned_by,
            alternative_ref=alternative_ref,
            receipt_ref=receipt_ref,
            metadata=metadata or {},
        )
        existing = self._prune_states.get(decision_id)
        if existing is not None:
            if canonical_prune_tuple(existing) != canonical_prune_tuple(state):
                raise ValueError(f"Conflicting prune state for decision {decision_id!r}: the ledger is append-only, one state per decision.")
            return existing
        self._prune_states[decision_id] = state
        return state

    def add_outcome_correction(
        self,
        decision_id: str,
        verdict: str,
        rationale: str,
        receipt_ref: Optional[ReceiptRef] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OutcomeCorrection:
        probe = OutcomeCorrection(
            correction_id="probe",
            decision_id=decision_id,
            verdict=verdict,
            rationale=rationale,
            receipt_ref=receipt_ref,
            locator=locator,
            metadata=metadata or {},
        )
        content_key = canonical_correction_tuple(probe)[1:]  # everything except the provisional id
        content_id = "corr-" + hashlib.sha256(_canonical_json_bytes(list(content_key))).hexdigest()[:16]
        probe = OutcomeCorrection(
            correction_id=content_id,
            decision_id=decision_id,
            verdict=verdict,
            rationale=rationale,
            receipt_ref=receipt_ref,
            locator=locator,
            metadata=metadata or {},
        )
        existing = self._corrections.get(content_id)
        if existing is not None:
            return existing
        self._corrections[content_id] = probe
        return probe

    # -- queries -------------------------------------------------------------

    def get_decision(self, decision_id: str) -> Optional[DecisionNode]:
        return self._decisions.get(decision_id)

    def outcome_of(self, decision_id: str) -> Dict[str, Any]:
        """Latest outcome verdict for a decision (corrections sorted by content id)."""
        related = sorted(
            (c for c in self._corrections.values() if c.decision_id == decision_id),
            key=lambda c: c.correction_id,
        )
        return {
            "decision_id": decision_id,
            "correction_count": len(related),
            "latest_correction_id": related[-1].correction_id if related else None,
            "latest_verdict": related[-1].verdict if related else None,
        }

    def find_negative_results(self) -> List[Dict[str, Any]]:
        """All negative_result decisions with their outcome summaries, sorted by id."""
        out = []
        for node in sorted(self._decisions.values(), key=lambda d: d.id):
            if node.decision_type != "negative_result":
                continue
            entry = node.to_dict()
            entry["outcome"] = self.outcome_of(node.id)
            out.append(entry)
        return out

    def find_decisions_for(self, basis_id: str, basis_kind: Optional[str] = None) -> List[Dict[str, Any]]:
        """All basis edges citing a given claim/negative-result, sorted deterministically."""
        out = []
        for edge in sorted(self._bases.values(), key=canonical_basis_tuple):
            if edge.basis_id != basis_id:
                continue
            if basis_kind is not None and edge.basis_kind != basis_kind:
                continue
            out.append(edge.to_dict())
        return out

    def trace_prune_cause(self, decision_id: str) -> Dict[str, Any]:
        """Causal trace of why a branch was pruned: reason, pruning decision, its bases.

        unsupported_reason is a deterministic free-text explanation when the
        pruning decision lacks any Claim basis; None when properly supported.
        """
        state = self._prune_states.get(decision_id)
        result: Dict[str, Any] = {
            "decision_id": decision_id,
            "prune_state": state.to_dict() if state else None,
            "pruned_by_decision": None,
            "alternative_decision": None,
            "pruned_by_bases": [],
            "unsupported_reason": None,
        }
        if state is None or state.status != "pruned":
            return result
        if state.pruned_by:
            node = self._decisions.get(state.pruned_by)
            result["pruned_by_decision"] = node.to_dict() if node else None
            bases = sorted(
                (e.to_dict() for e in self._bases.values() if e.decision_id == state.pruned_by),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            )
            result["pruned_by_bases"] = bases
            claim_bases = [b for b in bases if b["basis_kind"] == "claim"]
            if not claim_bases:
                result["unsupported_reason"] = (
                    f"Pruning decision '{state.pruned_by}' cites no Claim basis; "
                    "the prune cause rests on unrecorded judgment and needs human review."
                )
        if state.alternative_ref:
            alt = self._decisions.get(state.alternative_ref)
            result["alternative_decision"] = alt.to_dict() if alt else None
        return result

    # -- validation ------------------------------------------------------------

    def _resolve_receipt(self, ref: ReceiptRef) -> Optional[Any]:
        """Resolve a ReceiptRef to a registered receipt payload (CEG-compatible lookup).

        lineage refs resolve by receipt_id; academic_evidence refs resolve by
        payload_sha256 key first, then by canonical payload hash scan.
        """
        if ref.kind == "lineage":
            return self._receipts.get(ref.receipt_id)
        if ref.payload_sha256 in self._receipts:
            return self._receipts[ref.payload_sha256]
        for reg_val in self._receipts.values():
            val_dict = reg_val if isinstance(reg_val, dict) else (reg_val.to_dict() if hasattr(reg_val, "to_dict") else {})
            if canonical_academic_receipt_payload_sha256(val_dict) == ref.payload_sha256:
                return val_dict
        return None

    def _validate_receipt_ref(self, ref: Optional[ReceiptRef], subject: str, errors: List[str]):
        if ref is None:
            return
        receipt_obj = self._resolve_receipt(ref)
        if receipt_obj is None:
            return  # not resolvable here; surfaces as missing_receipt uncertainty
        if ref.kind == "lineage":
            ok, err = validate_lineage_receipt_contract(ref, receipt_obj)
        else:
            ok, err = validate_academic_receipt_contract(ref, receipt_obj)
        if not ok:
            errors.append(f"{subject}: receipt contract violation: {err}")

    def validate_ledger(self) -> Tuple[bool, List[str]]:
        """Structural validation. Returns (ok, sorted unique errors)."""
        errors: List[str] = []

        # Dangling basis edges
        for edge in sorted(self._bases.values(), key=canonical_basis_tuple):
            if edge.decision_id not in self._decisions:
                errors.append(f"E101 dangling basis edge: decision '{edge.decision_id}' is not registered")
            if edge.basis_id not in self._decisions:
                errors.append(f"E102 dangling basis edge: basis '{edge.basis_id}' ({edge.basis_kind}) is not a registered decision")
            self._validate_receipt_ref(edge.receipt_ref, f"basis:{edge.decision_id}>{edge.basis_id}", errors)

        # Dangling fork edges + self forks
        for edge in sorted(self._forks.values(), key=canonical_fork_tuple):
            if edge.decision_id == edge.alternative_id:
                errors.append(f"E201 self-fork edge: decision '{edge.decision_id}' cannot be its own alternative")
                continue
            if edge.decision_id not in self._decisions:
                errors.append(f"E202 dangling fork edge: decision '{edge.decision_id}' is not registered")
            if edge.alternative_id not in self._decisions:
                errors.append(f"E203 dangling fork edge: alternative '{edge.alternative_id}' is not registered")

        # Prune states
        for state in sorted(self._prune_states.values(), key=canonical_prune_tuple):
            if state.decision_id not in self._decisions:
                errors.append(f"E301 prune state for unregistered decision '{state.decision_id}'")
            if state.status == "pruned":
                if state.pruned_by and state.pruned_by not in self._decisions:
                    errors.append(f"E302 pruning decision '{state.pruned_by}' is not registered")
                if state.alternative_ref and state.alternative_ref not in self._decisions:
                    errors.append(f"E303 alternative '{state.alternative_ref}' is not registered")
            self._validate_receipt_ref(state.receipt_ref, f"prune:{state.decision_id}", errors)

        # Circular pruning chains (pruned_by graph must be acyclic)
        pruned_by: Dict[str, str] = {
            s.decision_id: s.pruned_by
            for s in self._prune_states.values()
            if s.status == "pruned" and s.pruned_by
        }
        for start in sorted(pruned_by):
            seen = {start}
            cur = pruned_by.get(start)
            while cur is not None:
                if cur in seen:
                    errors.append(f"E304 circular pruning chain detected at '{cur}' (starting from '{start}')")
                    break
                seen.add(cur)
                cur = pruned_by.get(cur)

        # Corrections reference registered decisions
        for corr in sorted(self._corrections.values(), key=canonical_correction_tuple):
            if corr.decision_id not in self._decisions:
                errors.append(f"E401 outcome correction '{corr.correction_id}' references unregistered decision '{corr.decision_id}'")
            self._validate_receipt_ref(corr.receipt_ref, f"correction:{corr.correction_id}", errors)

        # Negative results must be evidence-bearing (E404/E405)
        for node in sorted(self._decisions.values(), key=lambda d: d.id):
            if node.decision_type != "negative_result":
                continue
            bases = [e for e in self._bases.values() if e.decision_id == node.id]
            if not bases:
                errors.append(f"E404 negative result '{node.id}' carries no basis edge (assertion of absence needs evidence)")
                continue
            claim_bases = [e for e in bases if e.basis_kind == "claim"]
            if not claim_bases:
                errors.append(f"E405 negative result '{node.id}' is supported only by other negative results (no positive evidence base)")

        unique = sorted(set(errors))
        return (len(unique) == 0, unique)

    # -- uncertainty queue -------------------------------------------------

    def export_uncertainties(self) -> List[UncertaintyItem]:
        """Deterministic three-state uncertainty queue (content-addressed ids)."""
        items: List[UncertaintyItem] = []

        def add(kind: str, subject_id: str, reason: str, needs_human: bool):
            payload = {"kind": kind, "subject_id": subject_id, "reason": canonical_text(reason)}
            item_id = "unc-" + hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()[:16]
            items.append(UncertaintyItem(item_id=item_id, subject_id=subject_id, kind=kind, reason=reason, needs_human=needs_human))

        # Missing registered receipts on any receipt-bearing record
        def missing(ref: Optional[ReceiptRef], subject_id: str):
            if ref is not None and self._resolve_receipt(ref) is None:
                add(
                    "missing_receipt",
                    subject_id,
                    f"Receipt reference (kind={ref.kind}) is not resolvable in the ledger registry.",
                    False,
                )

        for edge in self._bases.values():
            missing(edge.receipt_ref, f"basis:{edge.decision_id}>{edge.basis_id}")
        for state in self._prune_states.values():
            missing(state.receipt_ref, f"prune:{state.decision_id}")
        for corr in self._corrections.values():
            missing(corr.receipt_ref, f"correction:{corr.correction_id}")

        # Negative results without proper positive evidence base
        for node in self._decisions.values():
            if node.decision_type != "negative_result":
                continue
            bases = [e for e in self._bases.values() if e.decision_id == node.id]
            if not bases:
                add(
                    "decision_without_basis",
                    node.id,
                    f"Negative result '{node.id}' carries no basis edge; the assertion of absence is unevidenced.",
                    True,
                )
            elif not any(e.basis_kind == "claim" for e in bases):
                add(
                    "unsupported_negative_result",
                    node.id,
                    f"Negative result '{node.id}' cites only other negative results; no positive evidence base exists.",
                    True,
                )

        # Pruning decisions without any claim basis
        for state in self._prune_states.values():
            if state.status != "pruned" or not state.pruned_by:
                continue
            claim_bases = [
                e for e in self._bases.values()
                if e.decision_id == state.pruned_by and e.basis_kind == "claim"
            ]
            if not claim_bases:
                add(
                    "unsupported_pruning",
                    state.decision_id,
                    f"Pruning decision '{state.pruned_by}' cites no Claim basis; the prune cause needs human review.",
                    True,
                )

        # Dedupe (content-addressed ids guarantee uniqueness) and sort
        unique: Dict[str, UncertaintyItem] = {i.item_id: i for i in items}
        return [unique[k] for k in sorted(unique)]

    # -- export ------------------------------------------------------------

    def ledger_digest(self) -> str:
        """Order-invariant digest over all records and registered receipt payloads."""
        payload = {
            "protocol": PROTOCOL,
            "ledger_id": self.ledger_id,
            "decisions": sorted((d.to_dict() for d in self._decisions.values()), key=lambda x: x["id"]),
            "bases": sorted(
                (e.to_dict() for e in self._bases.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "forks": sorted(
                (e.to_dict() for e in self._forks.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "prune_states": sorted(
                (s.to_dict() for s in self._prune_states.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "corrections": sorted(
                (c.to_dict() for c in self._corrections.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "receipts": {
                rid: canonical_ledger_payload_sha256(r)
                for rid, r in sorted(self._receipts.items())
            },
        }
        return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()

    def to_dict(self) -> Dict[str, Any]:
        """Export an immutable deep representation with the order-invariant digest."""
        d: Dict[str, Any] = {
            "protocol": PROTOCOL,
            "ledger_id": self.ledger_id,
            "ledger_digest": self.ledger_digest(),
            "decisions": [self._decisions[k].to_dict() for k in sorted(self._decisions)],
            "bases": [self._bases[k].to_dict() for k in sorted(self._bases)],
            "forks": [self._forks[k].to_dict() for k in sorted(self._forks)],
            "prune_states": [self._prune_states[k].to_dict() for k in sorted(self._prune_states)],
            "corrections": [self._corrections[k].to_dict() for k in sorted(self._corrections)],
        }
        return copy.deepcopy(d)

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
   A negative_result decision must carry at least one claim-kind basis edge
   whose target is ANOTHER non-negative_result decision (E405/E406). Claim
   bases reference decisions as recorded research acts; evidence chains are
   transitive through the target's own bases and must ground at a
   receipt-anchored terminal, otherwise they surface via the uncertainty
   queue. Self-references and negative_result targets are rejected as
   circular evidence fabrication.
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
   Full canonical sorting across all records; container insertion order never
   affects ledger_digest. Registered receipts contribute canonical payload
   hashes. The one deliberate exception is the ledger-assigned `sequence`
   counter on outcome corrections: it records true append history, so two
   ledgers differing only in correction arrival order legitimately digest
   differently, while idempotent replays digest identically.
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
from types import MappingProxyType
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
VALID_DECISION_STATES: set = {"active", "pruned", "reopened"}
VALID_REOPEN_REASONS: set = {
    "new_evidence",
    "scope_change",
    "investigator_reconsideration",
    "error_correction",
    "other",
}
VALID_STATE_TRANSITIONS: Dict[Optional[str], set] = {
    None: {"active", "pruned"},          # genesis
    "active": {"pruned"},
    "pruned": {"reopened"},
    "reopened": {"pruned"},
}
VALID_VERDICTS: set = {"positive", "negative", "inconclusive", "unverifiable"}
VALID_RECEIPT_KINDS: set = {"academic_evidence", "lineage"}
VALID_UNCERTAINTY_KINDS: set = {
    "decision_without_basis",
    "unsupported_negative_result",
    "missing_receipt",
    "unsupported_pruning",
    "unevidenced_claim_basis",
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
    "DecisionStateEvent",
    "OutcomeCorrection",
    "UncertaintyItem",
    "DecisionLedger",
    "canonical_text",
    "compute_decision_digest",
    "compute_outcome_digest",
    "canonical_basis_tuple",
    "canonical_fork_tuple",
    "canonical_state_event_tuple",
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


def _jsonable(obj: Any, _seen: Optional[set] = None) -> Any:
    """Deterministically convert a registered payload to JSON-able structures.

    Strictly bounded domain: JSON primitives, mappings, lists/tuples, and
    objects exposing to_dict() (unwrapped recursively). Everything else FAILS
    CLOSED (TypeError): no repr() fallback (non-deterministic across
    processes, and an arbitrary code path on foreign objects). Cyclic
    containers are rejected (ValueError).
    """
    if _seen is None:
        _seen = set()
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    oid = id(obj)
    if oid in _seen:
        raise ValueError("Cyclic container in receipt payload: canonical serialization refuses cyclic references.")
    if isinstance(obj, collections.abc.Mapping):
        _seen.add(oid)
        try:
            return {str(k): _jsonable(v, _seen) for k, v in obj.items()}
        finally:
            _seen.discard(oid)
    if isinstance(obj, (list, tuple)):
        _seen.add(oid)
        try:
            return [_jsonable(v, _seen) for v in obj]
        finally:
            _seen.discard(oid)
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        _seen.add(oid)
        try:
            return _jsonable(to_dict(), _seen)
        finally:
            _seen.discard(oid)
    raise TypeError(
        f"Unsupported payload type {type(obj).__name__!r} for canonical serialization: "
        "only JSON primitives, mappings, sequences, and objects with to_dict() are allowed."
    )


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
    """Immutable mapping with deep freezing.

    The backing store is a MappingProxyType created at construction time; no
    mutable dict reference ever leaves the object, so there is NO reachable
    path — ordinary, reflective, or slot-based — to rewrite an entry. The
    hash is recomputed from current content on every call (entries are
    small), so the hash unconditionally reflects the content.
    """

    __slots__ = ("_data",)

    def __init__(self, mapping_or_iterable: Any = None):
        if mapping_or_iterable is None:
            source: Mapping[str, Any] = {}
        elif isinstance(mapping_or_iterable, collections.abc.Mapping):
            source = mapping_or_iterable
        else:
            source = dict(mapping_or_iterable)
        frozen = {str(k): _freeze_val(v) for k, v in source.items()}
        object.__setattr__(self, "_data", MappingProxyType(frozen))

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
        return hash(frozenset(self._data.items()))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, collections.abc.Mapping):
            return NotImplemented
        return len(self._data) == len(other) and all(
            k in other and _thaw_val(v) == _thaw_val(other[k]) for k, v in self._data.items()
        )

    def __ne__(self, other: Any) -> bool:
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

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
    receipt_ref: Optional[ReceiptRef] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.decision_id, "decision_id")
        _check_id(self.alternative_id, "alternative_id")
        if self.relation not in VALID_FORK_RELATIONS:
            raise ValueError(f"Invalid fork relation: {self.relation!r}. Must be one of {sorted(VALID_FORK_RELATIONS)}")
        if self.receipt_ref is not None and not isinstance(self.receipt_ref, ReceiptRef):
            raise TypeError("receipt_ref must be a ReceiptRef instance or None.")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "alternative_id": self.alternative_id,
            "relation": self.relation,
        }
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_fork_tuple(edge: DecisionForkEdge) -> Tuple[str, ...]:
    return (
        edge.decision_id,
        edge.alternative_id,
        edge.relation,
    ) + canonical_receipt_ref_tuple(edge.receipt_ref) + (_meta_canonical_json(edge.metadata),)


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
class DecisionStateEvent:
    """An append-only state transition event for a decision (the State Ledger本体).

    History is a sequence of these events; the current lifecycle state of a
    decision is always DERIVED by replaying its events. `from_state` is None
    only for the genesis event. `reason` is required when to_state='pruned'
    (closed vocabulary VALID_PRUNE_REASONS) and optional when
    to_state='reopened' (closed vocabulary VALID_REOPEN_REASONS). `sequence`
    is a ledger-assigned monotonic insertion counter (1-based).
    """

    event_id: str
    decision_id: str
    from_state: Optional[str]
    to_state: str
    sequence: int = 0
    reason: Optional[str] = None
    caused_by: Optional[str] = None
    alternative_ref: Optional[str] = None
    receipt_ref: Optional[ReceiptRef] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.event_id, "event_id")
        _check_id(self.decision_id, "decision_id")
        if self.from_state is not None and self.from_state not in VALID_DECISION_STATES:
            raise ValueError(f"Invalid from_state: {self.from_state!r}. Must be None or one of {sorted(VALID_DECISION_STATES)}")
        if self.to_state not in VALID_DECISION_STATES:
            raise ValueError(f"Invalid to_state: {self.to_state!r}. Must be one of {sorted(VALID_DECISION_STATES)}")
        if self.from_state is not None and self.from_state == self.to_state:
            raise ValueError(f"Degenerate transition {self.from_state!r} -> {self.to_state!r} is not a state event.")
        if self.to_state == "pruned":
            if not self.reason:
                raise ValueError("Pruned state event requires a non-empty 'reason'.")
            if self.reason not in VALID_PRUNE_REASONS:
                raise ValueError(f"Invalid prune reason: {self.reason!r}. Must be one of {sorted(VALID_PRUNE_REASONS)}")
        else:
            if self.reason is not None:
                if self.to_state != "reopened":
                    raise ValueError(f"'reason' is only allowed for pruned or reopened states, got to_state={self.to_state!r}.")
                if self.reason not in VALID_REOPEN_REASONS:
                    raise ValueError(f"Invalid reopen reason: {self.reason!r}. Must be one of {sorted(VALID_REOPEN_REASONS)}")
            if self.to_state == "active" and (self.caused_by is not None or self.alternative_ref is not None):
                raise ValueError("Genesis active event must not carry caused_by/alternative_ref.")
        if self.caused_by is not None:
            _check_id(self.caused_by, "caused_by")
            if self.caused_by == self.decision_id:
                raise ValueError(f"Circular state causation: decision '{self.decision_id}' cannot be caused by itself.")
        if self.alternative_ref is not None:
            _check_id(self.alternative_ref, "alternative_ref")
            if self.alternative_ref == self.decision_id:
                raise ValueError(f"Self-referential alternative: decision '{self.decision_id}' cannot be its own alternative.")
        if self.receipt_ref is not None and not isinstance(self.receipt_ref, ReceiptRef):
            raise TypeError("receipt_ref must be a ReceiptRef instance or None.")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("'sequence' must be a non-negative integer.")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "event_id": self.event_id,
            "decision_id": self.decision_id,
            "to_state": self.to_state,
            "sequence": self.sequence,
        }
        if self.from_state is not None:
            d["from_state"] = self.from_state
        if self.reason:
            d["reason"] = self.reason
        if self.caused_by:
            d["caused_by"] = self.caused_by
        if self.alternative_ref:
            d["alternative_ref"] = self.alternative_ref
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_state_event_tuple(e: DecisionStateEvent) -> Tuple[str, ...]:
    return canonical_state_event_tuple_from(
        e.decision_id, e.from_state, e.to_state, e.reason, e.caused_by, e.alternative_ref, e.receipt_ref, dict(e.metadata)
    )


def canonical_state_event_tuple_from(
    decision_id: str,
    from_state: Optional[str],
    to_state: str,
    reason: Optional[str],
    caused_by: Optional[str],
    alternative_ref: Optional[str],
    receipt_ref: Optional[ReceiptRef],
    metadata: Mapping[str, Any],
) -> Tuple[str, ...]:
    return (
        decision_id,
        from_state or "",
        to_state,
        reason or "",
        caused_by or "",
        alternative_ref or "",
    ) + canonical_receipt_ref_tuple(receipt_ref) + (_meta_canonical_json(_frozen_meta(metadata)),)


@dataclass(frozen=True)
class OutcomeCorrection:
    """An append-only outcome verdict for a decision (never an in-place update).

    sequence is a ledger-assigned monotonic insertion counter (1-based) that
    reflects true insertion order; content addressing remains purely
    content-based so identical content stays idempotent.
    """

    correction_id: str
    decision_id: str
    verdict: str
    rationale: str
    outcome_digest: str = field(init=False)
    receipt_ref: Optional[ReceiptRef] = None
    locator: Optional[str] = None
    sequence: int = 0
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.correction_id, "correction_id")
        _check_id(self.decision_id, "decision_id")
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(f"Invalid verdict: {self.verdict!r}. Must be one of {sorted(VALID_VERDICTS)}")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("Outcome correction requires a non-empty 'rationale'.")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise ValueError("'sequence' must be a non-negative integer.")
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
            "sequence": self.sequence,
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


def _dedupe_uncertainty_items(items: List["UncertaintyItem"]) -> List["UncertaintyItem"]:
    """Dedupe uncertainty items by content-addressed id with collision defense.

    Two items sharing an id but differing in (subject_id, kind, reason,
    needs_human) mean the 64-bit truncated hash collided across distinct
    payloads; that is raised instead of silently merging findings.
    """
    unique: Dict[str, Any] = {}
    for it in items:
        payload_key = (it.subject_id, it.kind, it.reason, it.needs_human)
        prev = unique.get(it.item_id)
        if prev is None:
            unique[it.item_id] = (payload_key, it)
        elif prev[0] != payload_key:
            raise ValueError(f"Uncertainty item_id collision for {it.item_id!r}: distinct payloads truncated to the same id.")
    return [unique[k][1] for k in sorted(unique)]


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
        self._state_events: List[DecisionStateEvent] = []
        self._corrections: Dict[str, OutcomeCorrection] = {}
        self._receipts: Dict[str, Any] = {}
        self._next_correction_sequence = 1
        self._next_state_sequence = 1

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
        # Fail fast: only JSON-domain payloads (or to_dict() objects) may enter
        # the registry; anything else would poison canonical digests later.
        _jsonable(snapshot)
        if rid in self._receipts:
            existing = self._receipts[rid]
            ex_dict = existing.to_dict() if hasattr(existing, "to_dict") else existing
            new_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
            if ex_dict != new_dict:
                raise ValueError(f"Conflicting receipt registration for {rid!r}: existing data differs from new registration.")
            return
        self._receipts[rid] = snapshot
        # Resolve-by-content note: references carry no registry key of their
        # own (mirroring the CEG Kernel). At validation time a lineage ref is
        # looked up by receipt_id and an academic ref by its payload_sha256
        # key first, then by a canonical payload-hash scan over all entries.
        # The registration key here is therefore only a registry label; the
        # receipt_id vs payload_sha256 distinction lives in _resolve_receipt.

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
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionForkEdge:
        edge = DecisionForkEdge(
            decision_id=decision_id,
            alternative_id=alternative_id,
            relation=relation,
            receipt_ref=receipt_ref,
            metadata=metadata or {},
        )
        key = canonical_fork_tuple(edge)
        existing = self._forks.get(key)
        if existing is not None:
            return existing
        self._forks[key] = edge
        return edge

    def add_state_event(
        self,
        decision_id: str,
        to_state: str,
        reason: Optional[str] = None,
        caused_by: Optional[str] = None,
        alternative_ref: Optional[str] = None,
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionStateEvent:
        """Append a state transition event (the State Ledger本体).

        The transition must be legal from the decision's current replayed
        state (VALID_STATE_TRANSITIONS): genesis -> active|pruned,
        active -> pruned, pruned -> reopened, reopened -> pruned.
        Repeating the EXACT current state with an identical payload is an
        idempotent no-op (returns the latest event, appends nothing);
        identical transitions at different history positions are distinct
        events (event_id binds content+sequence).
        """
        latest = self._latest_event(decision_id)
        if latest is not None and latest.to_state == to_state:
            if (
                latest.reason == reason
                and latest.caused_by == caused_by
                and latest.alternative_ref == alternative_ref
                and latest.receipt_ref == receipt_ref
                and dict(latest.metadata) == dict(metadata or {})
            ):
                return latest  # idempotent no-op: current state already matches payload
        current_from: Optional[str] = latest.to_state if latest is not None else None
        if to_state not in VALID_STATE_TRANSITIONS.get(current_from, set()):
            raise ValueError(
                f"Illegal state transition for decision {decision_id!r}: "
                f"{current_from!r} -> {to_state!r}. Legal transitions: "
                f"{sorted(VALID_STATE_TRANSITIONS.get(current_from, set()))}"
            )
        if current_from == to_state:
            raise ValueError(
                f"Degenerate transition {current_from!r} -> {to_state!r} for decision {decision_id!r} "
                "with a differing payload is not a state event."
            )
        assigned = self._next_state_sequence
        content_key = canonical_state_event_tuple_from(
            decision_id, current_from, to_state, reason, caused_by, alternative_ref, receipt_ref, metadata or {}
        )
        event_id = "evt-" + hashlib.sha256(
            _canonical_json_bytes({"content": list(content_key), "sequence": assigned})
        ).hexdigest()[:32]
        event = DecisionStateEvent(
            event_id=event_id,
            decision_id=decision_id,
            from_state=current_from,
            to_state=to_state,
            reason=reason,
            caused_by=caused_by,
            alternative_ref=alternative_ref,
            receipt_ref=receipt_ref,
            sequence=assigned,
            metadata=metadata or {},
        )
        self._state_events.append(event)
        self._next_state_sequence += 1
        return event

    def _latest_event(self, decision_id: str) -> Optional[DecisionStateEvent]:
        """Latest state event for a decision by (sequence, event_id) order."""
        best: Optional[DecisionStateEvent] = None
        for e in self._state_events:
            if e.decision_id != decision_id:
                continue
            if best is None or (e.sequence, e.event_id) > (best.sequence, best.event_id):
                best = e
        return best

    def current_state(self, decision_id: str) -> Optional[PruneState]:
        """Derived current lifecycle state of a decision (replayed from events)."""
        events = sorted(
            (e for e in self._state_events if e.decision_id == decision_id),
            key=lambda e: (e.sequence, e.event_id),
        )
        if not events:
            return None
        latest = events[-1]
        status = "pruned" if latest.to_state == "pruned" else "active"
        return PruneState(
            decision_id=decision_id,
            status=status,
            prune_reason=latest.reason if latest.to_state == "pruned" else None,
            pruned_by=latest.caused_by if latest.to_state == "pruned" else None,
            alternative_ref=latest.alternative_ref if latest.to_state == "pruned" else None,
            receipt_ref=latest.receipt_ref if latest.to_state == "pruned" else None,
            metadata=dict(latest.metadata),
        )

    def state_history(self, decision_id: str) -> List[Dict[str, Any]]:
        """Full append-only state transition history of a decision (replayed)."""
        return [
            e.to_dict()
            for e in sorted(
                (e for e in self._state_events if e.decision_id == decision_id),
                key=lambda e: (e.sequence, e.event_id),
            )
        ]

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
        """Compatibility wrapper: append a state event and return the derived view.

        status='active' with no history registers a genesis active event;
        status='active' on a pruned decision appends a reopened event;
        status='pruned' appends a pruned event. Repeated identical calls
        replay idempotently.
        """
        if status not in VALID_PRUNE_STATUSES:
            raise ValueError(f"Invalid prune status: {status!r}. Must be one of {sorted(VALID_PRUNE_STATUSES)}")
        if status == "active":
            if prune_reason is not None or pruned_by is not None or alternative_ref is not None:
                raise ValueError("Active decision must not carry prune_reason/pruned_by/alternative_ref fields.")
            current = self.current_state(decision_id)
            if current is None:
                self.add_state_event(decision_id, to_state="active", receipt_ref=receipt_ref, metadata=metadata)
            elif current.status == "pruned":
                self.add_state_event(decision_id, to_state="reopened", receipt_ref=receipt_ref, metadata=metadata)
            # already active: idempotent no-op
        else:
            current = self.current_state(decision_id)
            if (
                current is not None
                and current.status == "pruned"
                and current.prune_reason == prune_reason
                and current.pruned_by == pruned_by
                and current.alternative_ref == alternative_ref
                and current.receipt_ref == receipt_ref
                and dict(current.metadata) == dict(metadata or {})
            ):
                return current  # idempotent replay: already pruned with identical payload
            self.add_state_event(
                decision_id,
                to_state="pruned",
                reason=prune_reason,
                caused_by=pruned_by,
                alternative_ref=alternative_ref,
                receipt_ref=receipt_ref,
                metadata=metadata,
            )
        view = self.current_state(decision_id)
        assert view is not None
        return view

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
        content_id = "corr-" + hashlib.sha256(_canonical_json_bytes(list(content_key))).hexdigest()[:32]
        existing = self._corrections.get(content_id)
        if existing is not None:
            if canonical_correction_tuple(existing)[1:] == content_key:
                return existing  # identical content is idempotent
            raise ValueError(f"Correction content-id collision for {content_id!r}: distinct payloads truncated to the same id.")
        assigned = self._next_correction_sequence
        self._next_correction_sequence += 1
        corr = OutcomeCorrection(
            correction_id=content_id,
            decision_id=decision_id,
            verdict=verdict,
            rationale=rationale,
            receipt_ref=receipt_ref,
            locator=locator,
            sequence=assigned,
            metadata=metadata or {},
        )
        self._corrections[content_id] = corr
        return corr

    # -- queries -------------------------------------------------------------

    def get_decision(self, decision_id: str) -> Optional[DecisionNode]:
        return self._decisions.get(decision_id)

    def outcome_of(self, decision_id: str) -> Dict[str, Any]:
        """Latest outcome verdict for a decision (true insertion order via sequence)."""
        related = sorted(
            (c for c in self._corrections.values() if c.decision_id == decision_id),
            key=lambda c: (c.sequence, c.correction_id),
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

    def _current_prune_graph(self) -> Dict[str, PruneState]:
        """Derived map of currently-pruned decisions to their derived state views."""
        latest: Dict[str, DecisionStateEvent] = {}
        for e in self._state_events:
            prev = latest.get(e.decision_id)
            if prev is None or (e.sequence, e.event_id) > (prev.sequence, prev.event_id):
                latest[e.decision_id] = e
        out: Dict[str, PruneState] = {}
        for did, e in latest.items():
            if e.to_state == "pruned":
                out[did] = PruneState(
                    decision_id=did,
                    status="pruned",
                    prune_reason=e.reason,
                    pruned_by=e.caused_by,
                    alternative_ref=e.alternative_ref,
                    receipt_ref=e.receipt_ref,
                    metadata=dict(e.metadata),
                )
        return out

    def trace_prune_cause(self, decision_id: str) -> Dict[str, Any]:
        """Recursive causal trace of why a branch was pruned.

        Returns the derived current prune state and the full prune_chain:
        each link lists the pruned decision, its closed-vocabulary reason,
        the pruning decision and that decision's claim bases. The chain
        stops at an unpruned decision, an unregistered reference, or a
        detected cycle (cycle_break flag). unsupported_reason is a
        deterministic free-text explanation when the pruning decision lacks
        any Claim basis; None when properly supported.
        """
        graph = self._current_prune_graph()
        state = graph.get(decision_id)
        result: Dict[str, Any] = {
            "decision_id": decision_id,
            "prune_state": state.to_dict() if state else None,
            "pruned_by_decision": None,
            "alternative_decision": None,
            "pruned_by_bases": [],
            "prune_chain": [],
            "unsupported_reason": None,
        }
        if state is None:
            return result

        visited: set = set()
        cur: Optional[str] = decision_id
        while cur is not None and cur in graph and cur not in visited:
            visited.add(cur)
            link_state = graph[cur]
            link: Dict[str, Any] = {
                "decision_id": cur,
                "prune_reason": link_state.prune_reason,
                "pruned_by": link_state.pruned_by,
                "alternative_ref": link_state.alternative_ref,
            }
            result["prune_chain"].append(link)
            cur = link_state.pruned_by
        if cur is not None and cur in visited:
            result["cycle_break"] = cur

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

        # Dangling basis edges + strongly typed basis targets
        for edge in sorted(self._bases.values(), key=canonical_basis_tuple):
            if edge.decision_id not in self._decisions:
                errors.append(f"E101 dangling basis edge: decision '{edge.decision_id}' is not registered")
            target = self._decisions.get(edge.basis_id)
            if target is None:
                errors.append(f"E102 dangling basis edge: basis '{edge.basis_id}' ({edge.basis_kind}) is not a registered decision")
            else:
                if edge.basis_kind == "negative_result" and target.decision_type != "negative_result":
                    errors.append(f"E103 basis kind mismatch: negative_result basis '{edge.basis_id}' targets a '{target.decision_type}' decision")
                if edge.basis_kind == "claim" and target.decision_type == "negative_result":
                    errors.append(f"E103 basis kind mismatch: claim basis '{edge.basis_id}' targets a negative_result decision")
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
            self._validate_receipt_ref(edge.receipt_ref, f"fork:{edge.decision_id}>{edge.alternative_id}", errors)

        # Prune states (derived from append-only state events)
        for event in sorted(self._state_events, key=canonical_state_event_tuple):
            if event.decision_id not in self._decisions:
                errors.append(f"E301 state event '{event.event_id}' for unregistered decision '{event.decision_id}'")
            if event.to_state == "pruned":
                if event.caused_by and event.caused_by not in self._decisions:
                    errors.append(f"E302 pruning decision '{event.caused_by}' is not registered")
                if event.alternative_ref and event.alternative_ref not in self._decisions:
                    errors.append(f"E303 alternative '{event.alternative_ref}' is not registered")
            self._validate_receipt_ref(event.receipt_ref, f"state_event:{event.event_id}", errors)

        # Circular pruning chains on the DERIVED current prune graph
        # (path-indexed: tail nodes entering a cycle are not cycle members)
        pruned_by_graph: Dict[str, str] = {
            s.decision_id: s.pruned_by
            for s in self._current_prune_graph().values()
            if s.pruned_by
        }
        reported_cycle_nodes: set = set()
        for start in sorted(pruned_by_graph):
            if start in reported_cycle_nodes:
                continue
            path: Dict[str, int] = {}
            cur: Optional[str] = start
            while cur is not None and cur in pruned_by_graph and cur not in path and cur not in reported_cycle_nodes:
                path[cur] = len(path)
                cur = pruned_by_graph.get(cur)
            if cur is not None and cur in path:
                cycle = [n for n, i in sorted(path.items(), key=lambda kv: kv[1]) if i >= path[cur]]
                k = cycle.index(min(cycle))
                cycle = cycle[k:] + cycle[:k]
                errors.append(f"E304 circular pruning chain detected (cycle members: {', '.join(cycle)})")
                reported_cycle_nodes.update(cycle)

        # Corrections reference registered decisions
        for corr in sorted(self._corrections.values(), key=canonical_correction_tuple):
            if corr.decision_id not in self._decisions:
                errors.append(f"E401 outcome correction '{corr.correction_id}' references unregistered decision '{corr.decision_id}'")
            self._validate_receipt_ref(corr.receipt_ref, f"correction:{corr.correction_id}", errors)

        # Negative results must be evidence-bearing (E404/E405)
        # A negative result may only rest on claim-type bases that reference
        # OTHER (non-negative-result) decisions: a self-reference or a
        # mutual negative_result<->claim cycle would fabricate positive
        # evidence out of the assertions of absence themselves.
        neg_ids = {n.id for n in self._decisions.values() if n.decision_type == "negative_result"}
        for node in sorted(self._decisions.values(), key=lambda d: d.id):
            if node.decision_type != "negative_result":
                continue
            bases = [e for e in self._bases.values() if e.decision_id == node.id]
            if not bases:
                errors.append(f"E404 negative result '{node.id}' carries no basis edge (assertion of absence needs evidence)")
                continue
            # self-referential basis is circular evidence fabrication
            if any(e.basis_kind == "claim" and e.basis_id == node.id for e in bases):
                errors.append(f"E406 negative result '{node.id}' cites itself as claim evidence (circular evidence fabrication)")
            claim_bases = [
                e for e in bases
                if e.basis_kind == "claim" and e.basis_id != node.id and e.basis_id not in neg_ids
            ]
            if not claim_bases:
                if any(e.basis_kind == "claim" and e.basis_id in neg_ids for e in bases):
                    errors.append(f"E405 negative result '{node.id}' is supported only by other negative results (no positive evidence base)")
                elif not any(e.basis_kind == "claim" for e in bases):
                    errors.append(f"E405 negative result '{node.id}' is supported only by other negative results (no positive evidence base)")

        # E407: a negative result whose claim-basis closure contains a cycle
        # can never ground at a receipt anchor; that is a deterministic
        # structural fact, so it hard-fails instead of only surfacing in the
        # uncertainty queue.
        claim_succ_v: Dict[str, set] = {}
        for e in self._bases.values():
            if e.basis_kind == "claim" and e.basis_id != e.decision_id:
                claim_succ_v.setdefault(e.decision_id, set()).add(e.basis_id)

        def _closure_has_cycle(root: str) -> bool:
            visited: set = set()
            on_path: set = set()
            stack: List[Tuple[str, Iterator[str]]] = [(root, iter(sorted(claim_succ_v.get(root, ()))))]
            on_path.add(root)
            while stack:
                top, it = stack[-1]
                advanced = False
                for nxt in it:
                    if nxt in on_path:
                        return True
                    if nxt not in visited:
                        visited.add(nxt)
                        on_path.add(nxt)
                        stack.append((nxt, iter(sorted(claim_succ_v.get(nxt, ())))))
                        advanced = True
                        break
                if not advanced:
                    on_path.discard(top)
                    stack.pop()
            return False

        for node in sorted(self._decisions.values(), key=lambda d: d.id):
            if node.decision_type == "negative_result" and _closure_has_cycle(node.id):
                errors.append(f"E407 negative result '{node.id}': claim-basis closure contains a cycle that can never ground at a receipt anchor")

        unique = sorted(set(errors))
        return (len(unique) == 0, unique)

    # -- uncertainty queue -------------------------------------------------

    def export_uncertainties(self) -> List[UncertaintyItem]:
        """Deterministic three-state uncertainty queue (content-addressed ids)."""
        items: List[UncertaintyItem] = []

        # Uncertainty item_id derivation is byte-compatible with the CEG
        # Kernel: sha256 over {kind, needs_human, reason, subject_id} sorted
        # keys, truncated to 16 hex chars, prefixed with "unc-". Cross-kernel
        # queue merging (PR #12) then sees identical ids for identical items.
        def add(kind: str, subject_id: str, reason: str, needs_human: bool):
            payload = json.dumps(
                {
                    "kind": kind,
                    "needs_human": needs_human,
                    "reason": canonical_text(reason),
                    "subject_id": subject_id,
                },
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            )
            item_id = "unc-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
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
        for edge in self._forks.values():
            missing(edge.receipt_ref, f"fork:{edge.decision_id}>{edge.alternative_id}")
        for event in self._state_events:
            missing(event.receipt_ref, f"state_event:{event.event_id}")
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

        # Pruning decisions without any claim basis (derived current prune graph)
        for state in self._current_prune_graph().values():
            if not state.pruned_by:
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

        # Unevidenced claim-basis chains (basis-transparency rule): a
        # claim-kind basis edge is valid only when the evidence chain it
        # starts grounds at a receipt-anchored terminal. Chains are
        # transitive through the target's own claim bases; self-edges never
        # count as evidence. A terminal without receipt anchoring, or a
        # cycle that never grounds, surfaces for human review.
        claim_succ: Dict[str, set] = {}
        claim_edges: List[Tuple[str, str, DecisionBasisEdge]] = []
        for e in self._bases.values():
            if e.basis_kind == "claim" and e.basis_id != e.decision_id:
                claim_succ.setdefault(e.decision_id, set()).add(e.basis_id)
                claim_edges.append((e.decision_id, e.basis_id, e))

        def _in_cycle(node: str) -> bool:
            seen: set = set()
            stack = list(claim_succ.get(node, ()))
            while stack:
                cur = stack.pop()
                if cur == node:
                    return True
                if cur in seen:
                    continue
                seen.add(cur)
                stack.extend(claim_succ.get(cur, ()))
            return False

        terminal_targets = sorted({v for _u, v, _e in claim_edges if not (claim_succ.get(v, set()) - {v})})
        for v in terminal_targets:
            if _in_cycle(v):
                continue
            anchored = any(e.receipt_ref is not None for u, vv, e in claim_edges if vv == v)
            if not anchored:
                citing = sorted(u for u, vv, _e in claim_edges if vv == v)
                add(
                    "unevidenced_claim_basis",
                    v,
                    f"Claim-basis chain grounds at '{v}' (cited by {', '.join(citing)}) without any receipt anchoring.",
                    True,
                )
        for v in sorted({v for v in claim_succ if _in_cycle(v)}):
            add(
                "unevidenced_claim_basis",
                v,
                f"Claim-basis chain through '{v}' never grounds (cycle); no receipt anchoring exists.",
                True,
            )

        # Dedupe (content-addressed ids guarantee uniqueness) and sort
        return _dedupe_uncertainty_items(items)

    # -- export ------------------------------------------------------------

    def ledger_digest(self) -> str:
        """Order-invariant CONTENT identity digest over all ledger records.

        Hashes only decisions, bases, forks, state events, and outcome
        corrections. The local receipt registry (a verification cache with
        caller-chosen labels) never enters the content identity: ReceiptRef
        records already carry receipt_digest/payload_sha256, so the same
        records with the same evidence digests always digest identically
        regardless of how the local registry is labelled. Container insertion
        order never affects the digest; the ledger-assigned `sequence`
        counters on corrections and state events are the single intentional
        exception (they encode true append history).
        """
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
            "state_events": sorted(
                (s.to_dict() for s in self._state_events),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "corrections": sorted(
                (c.to_dict() for c in self._corrections.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
        }
        return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()

    def verification_digest(self) -> str:
        """Digest of the ledger content identity plus the local receipt registry.

        Separated from ledger_digest so the registry's caller-chosen labels
        and cache state are never conflated with content identity. Exported
        alongside ledger_digest so a verifier can distinguish content from
        verification state.
        """
        manifest = {
            rid: canonical_ledger_payload_sha256(_jsonable(r))
            for rid, r in sorted(self._receipts.items())
        }
        payload = {"ledger_digest": self.ledger_digest(), "receipts": manifest}
        return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()

    def to_dict(self) -> Dict[str, Any]:
        """Export an immutable deep representation with content identity and verification digests."""
        d: Dict[str, Any] = {
            "protocol": PROTOCOL,
            "ledger_id": self.ledger_id,
            "ledger_digest": self.ledger_digest(),
            "verification_digest": self.verification_digest(),
            "decisions": [self._decisions[k].to_dict() for k in sorted(self._decisions)],
            "bases": [self._bases[k].to_dict() for k in sorted(self._bases)],
            "forks": [self._forks[k].to_dict() for k in sorted(self._forks)],
            "state_events": [e.to_dict() for e in sorted(self._state_events, key=lambda x: (x.sequence, x.event_id))],
            "corrections": [self._corrections[k].to_dict() for k in sorted(self._corrections)],
            "uncertainties": [u.to_dict() for u in self.export_uncertainties()],
        }
        return copy.deepcopy(d)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DecisionLedger":
        """Strict replay loader: rebuild a ledger from a to_dict() export.

        Re-validates the export contract, replays every record through the
        kernel constructors (which re-validate), restores ledger-assigned
        sequence counters, and fails closed on any ledger_digest mismatch.
        The receipt registry (verification cache) is intentionally NOT part
        of the export: verification_digest is preserved for reference but the
        registry starts empty and callers re-register receipts to re-verify.
        """
        if not isinstance(data, collections.abc.Mapping):
            raise TypeError("from_dict expects a mapping produced by DecisionLedger.to_dict().")
        for key in ("protocol", "ledger_id", "ledger_digest", "decisions", "bases", "forks", "state_events", "corrections"):
            if key not in data:
                raise ValueError(f"Export contract violation: missing required key {key!r}.")
        if data["protocol"] != PROTOCOL:
            raise ValueError(f"Export protocol mismatch: expected {PROTOCOL!r}, got {data['protocol']!r}.")
        ledger = cls(ledger_id=data["ledger_id"])

        def _ref(d: Any) -> Optional[ReceiptRef]:
            if d is None:
                return None
            if not isinstance(d, collections.abc.Mapping):
                raise ValueError("receipt_ref must be a mapping or null.")
            return ReceiptRef(
                kind=d["kind"],
                schema_version=d["schema_version"],
                receipt_id=d.get("receipt_id"),
                receipt_digest=d.get("receipt_digest"),
                claim_digest=d.get("claim_digest"),
                payload_sha256=d.get("payload_sha256"),
                locator=d.get("locator"),
            )

        for d in data["decisions"]:
            ledger.add_decision(
                id=d["id"],
                title=d["title"],
                decision_type=d["decision_type"],
                context_work_id=d.get("context_work_id"),
                locator=d.get("locator"),
                metadata=d.get("metadata") or {},
            )
        for e in data["bases"]:
            ledger.add_basis(
                decision_id=e["decision_id"],
                basis_kind=e["basis_kind"],
                basis_id=e["basis_id"],
                receipt_ref=_ref(e.get("receipt_ref")),
                metadata=e.get("metadata") or {},
            )
        for e in data["forks"]:
            ledger.add_fork(
                decision_id=e["decision_id"],
                alternative_id=e["alternative_id"],
                relation=e["relation"],
                receipt_ref=_ref(e.get("receipt_ref")),
                metadata=e.get("metadata") or {},
            )
        # State events replay in sequence order, preserving original sequences.
        for e in sorted(data["state_events"], key=lambda x: x.get("sequence", 0)):
            # Transition legality is re-checked against the replayed history.
            from_state = e.get("from_state")
            current = ledger.current_state(e["decision_id"])
            current_from: Optional[str] = None
            if current is not None:
                hist = ledger.state_history(e["decision_id"])
                if hist:
                    current_from = hist[-1]["to_state"]
            if current_from != from_state:
                raise ValueError(
                    f"Export replay violation: state event {e['event_id']!r} declares from_state={from_state!r} "
                    f"but replayed history is at {current_from!r}."
                )
            ledger.add_state_event(
                decision_id=e["decision_id"],
                to_state=e["to_state"],
                reason=e.get("reason"),
                caused_by=e.get("caused_by"),
                alternative_ref=e.get("alternative_ref"),
                receipt_ref=_ref(e.get("receipt_ref")),
                metadata=e.get("metadata") or {},
            )
        # Corrections replay in sequence order.
        for c in sorted(data["corrections"], key=lambda x: x.get("sequence", 0)):
            ledger.add_outcome_correction(
                decision_id=c["decision_id"],
                verdict=c["verdict"],
                rationale=c["rationale"],
                receipt_ref=_ref(c.get("receipt_ref")),
                locator=c.get("locator"),
                metadata=c.get("metadata") or {},
            )
        recomputed = ledger.ledger_digest()
        if recomputed != str(data["ledger_digest"]).lower():
            raise ValueError(
                f"Export digest mismatch on replay: declared {data['ledger_digest']!r}, recomputed {recomputed!r}."
            )
        return ledger

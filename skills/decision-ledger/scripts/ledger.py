# -*- coding: utf-8 -*-
"""Research Decision Log (Decision & Negative Result Ledger v1).

Deterministic, append-only event log for research decisions, failed attempts,
route abandonment reasons, and outcome changes. Directly consumes the same
receipt contracts as the Claim-Evidence Graph Kernel (LineageReceipt and
AcademicEvidenceReceipt via a byte-compatible ReceiptRef).

Core Principles:
1. Append-only event history:
   Decisions, bases, forks, state events, and outcome corrections are immutable
   records; outcome changes are recorded as new correction events with monotonic
   sequences, never as in-place updates.
2. Discrete, objective verdicts without subjective scoring:
   No pseudo-confidence scores, utility metrics, or subjective ratings.
   Verdicts are discrete enumerations (positive, negative, inconclusive, unverifiable).
3. Strongly typed ReceiptRef with strict mutual exclusivity:
   LineageReceipt requires lineage-receipt-1.0, receipt_id, receipt_digest.
   AcademicEvidenceReceipt requires 1.0, claim_digest, payload_sha256.
4. Physical payload verification:
   AcademicEvidenceReceipt payload SHA256 is physically recomputed and asserted.
   LineageReceipt protocol/id/digest are positively asserted.
5. Deeply frozen records & immutable metadata mapping:
   Every record is a frozen dataclass and every metadata mapping is a FrozenDict,
   failing closed at construction time on non-JSON domain values.
6. Negative results require positive evidence bases:
   A negative_result decision must cite at least one decision-kind basis edge
   whose target is another (non-negative_result) decision (E405/E406).
7. Route abandonment reasons are explicit and acyclic:
   Pruned/closed routes record a closed-vocabulary reason, the pruning decision,
   and alternative routes. Abandonment causation chains are strictly acyclic.
8. Unresolved items surfaced as structured uncertainty items:
   Missing evidence or unanchored chains surface as deterministic UncertaintyItem
   records without blocking structural validation.
9. Order-invariant content identity digest:
   Full canonical sorting across all records. State events and outcome corrections
   carry monotonic sequence counters recording chronological arrival order.
10. Lexical canonicalization only:
   NFC normalization and whitespace compaction; decision titles are never rewritten.
"""
from __future__ import annotations

import collections
import collections.abc
import copy
import hashlib
import json
import math
import re
import unicodedata
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, Iterator, List, Mapping, Optional, Tuple

PROTOCOL = "decision-ledger-1.0"

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")
ID_REGEX = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

VALID_ENTRY_KINDS: set = {"decision", "negative_result"}
VALID_DECISION_ACTIONS: set = {"explore", "commit", "abandon", "revise"}
VALID_DECISION_TYPES: set = {"explore", "commit", "abandon", "revise", "negative_result"}
VALID_BASIS_KINDS: set = {"decision", "negative_result"}
VALID_FORK_RELATIONS: set = {"considered", "explored", "deferred", "rejected"}
VALID_PRUNE_STATUSES: set = {"active", "pruned", "reopened"}
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

ALLOWED_TOP_LEVEL_KEYS: set = {
    "protocol",
    "ledger_id",
    "ledger_digest",
    "verification_digest",
    "verification_manifest",
    "decisions",
    "bases",
    "forks",
    "state_events",
    "corrections",
    "uncertainties",
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
    """Canonical SHA256 of a receipt payload used by the verification manifest.

    Lineage receipt timestamps are emission metadata and participate in neither
    ``receipt_id`` nor ``receipt_digest``. Excluding them here gives the ledger
    the same timestamp-equivalence rule as the ingestion receipt registry.
    """
    payload = _jsonable(payload_dict)
    if isinstance(payload, dict) and payload.get("protocol") == "lineage-receipt-1.0":
        payload = dict(payload)
        payload.pop("timestamp", None)
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()


def _jsonable(obj: Any, _seen: Optional[set] = None) -> Any:
    """Deterministically convert a registered payload to JSON-able structures.

    Strictly bounded domain: JSON primitives (str, int, finite float, bool, None),
    mappings with strictly string keys, lists/tuples, and objects exposing
    to_dict() (unwrapped recursively). Everything else FAILS CLOSED (TypeError /
    ValueError): no repr() fallback, no non-finite floats (NaN/Inf), no non-string
    mapping keys, and cyclic containers are rejected.
    """
    if _seen is None:
        _seen = set()
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"Non-finite float {obj!r} is not permitted in canonical payloads.")
        return obj
    oid = id(obj)
    if oid in _seen:
        raise ValueError("Cyclic container in receipt payload: canonical serialization refuses cyclic references.")
    if isinstance(obj, collections.abc.Mapping):
        _seen.add(oid)
        try:
            res: Dict[str, Any] = {}
            for k, v in obj.items():
                if not isinstance(k, str):
                    raise TypeError(f"Mapping key must be str, got {type(k).__name__!r}: {k!r}")
                res[k] = _jsonable(v, _seen)
            return res
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
        "only JSON primitives, mappings with string keys, sequences, and objects with to_dict() are allowed."
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
# Deeply frozen mapping with strict JSON-domain validation
# ---------------------------------------------------------------------------

def _validate_json_metadata_value(val: Any, _seen: Optional[set] = None) -> Any:
    """Validate that val is strictly in the canonical JSON domain, freezing recursively.

    Allowed:
    - str, int, bool, None
    - finite float (math.isfinite)
    - Mapping with strictly str keys (frozen into FrozenDict)
    - list or tuple of valid JSON values (frozen into tuple)
    Rejected (TypeError / ValueError):
    - Non-finite float (NaN, Inf, -Inf) -> ValueError
    - Non-string mapping keys -> TypeError
    - Sets, frozensets, custom objects, functions, generators -> TypeError
    - Cyclic containers -> ValueError
    """
    if _seen is None:
        _seen = set()
    if isinstance(val, (str, int, bool)) or val is None:
        return val
    if isinstance(val, float):
        if not math.isfinite(val):
            raise ValueError(f"Non-finite float {val!r} is not permitted in metadata.")
        return val
    oid = id(val)
    if oid in _seen:
        raise ValueError("Cyclic container detected in metadata.")
    if isinstance(val, FrozenDict):
        return val
    if isinstance(val, collections.abc.Mapping):
        _seen.add(oid)
        try:
            frozen_map: Dict[str, Any] = {}
            for k, v in val.items():
                if not isinstance(k, str):
                    raise TypeError(f"Metadata mapping key must be str, got {type(k).__name__!r}: {k!r}")
                frozen_map[k] = _validate_json_metadata_value(v, _seen)
            return FrozenDict(frozen_map)
        finally:
            _seen.discard(oid)
    if isinstance(val, (list, tuple)):
        _seen.add(oid)
        try:
            return tuple(_validate_json_metadata_value(item, _seen) for item in val)
        finally:
            _seen.discard(oid)
    raise TypeError(
        f"Unsupported metadata value type {type(val).__name__!r}: "
        "only JSON primitives (str, int, finite float, bool, null), sequences, and string-keyed mappings are allowed."
    )


def _thaw_val(val: Any) -> Any:
    if isinstance(val, FrozenDict):
        return val.to_dict()
    if isinstance(val, tuple):
        return [_thaw_val(item) for item in val]
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
        frozen: Dict[str, Any] = {}
        for k, v in source.items():
            if not isinstance(k, str):
                raise TypeError(f"FrozenDict key must be str, got {type(k).__name__!r}: {k!r}")
            frozen[k] = _validate_json_metadata_value(v)
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

    def __deepcopy__(self, memo: Dict[int, Any]) -> "FrozenDict":
        # Every reachable child is already recursively frozen, so sharing the
        # value across transactional clones is safe and avoids MappingProxyType
        # pickle failures.
        return self

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


def _frozen_meta(metadata: Optional[Mapping[str, Any]]) -> FrozenDict:
    """Validate and deeply freeze record metadata. Fails closed on non-JSON domain."""
    if metadata is None:
        return FrozenDict()
    if not isinstance(metadata, collections.abc.Mapping):
        raise TypeError(f"metadata must be a mapping or None, got {type(metadata).__name__!r}.")
    if isinstance(metadata, FrozenDict):
        return metadata
    return FrozenDict(metadata)


# ---------------------------------------------------------------------------
# Receipt contracts (byte-compatible with the CEG Kernel)
# ---------------------------------------------------------------------------

try:
    from shared_contracts.evidence import (
        ReceiptRef,
        canonical_receipt_ref_tuple,
        canonical_academic_receipt_payload_sha256,
        canonical_evidence_claim_digest,
        validate_lineage_receipt_contract,
        validate_academic_receipt_contract,
        verify_receipt_reference,
    )
except ImportError:
    import sys
    from pathlib import Path
    _repo_root = Path(__file__).resolve().parent.parent.parent.parent
    if str(_repo_root / "scripts") not in sys.path:
        sys.path.insert(0, str(_repo_root / "scripts"))
    from shared_contracts.evidence import (
        ReceiptRef,
        canonical_receipt_ref_tuple,
        canonical_academic_receipt_payload_sha256,
        canonical_evidence_claim_digest,
        validate_lineage_receipt_contract,
        validate_academic_receipt_contract,
        verify_receipt_reference,
    )


def _check_id(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"'{field_name}' must be a non-empty string.")
    if not ID_REGEX.match(value):
        raise ValueError(f"Invalid {field_name}: {value!r}. Must match {ID_REGEX.pattern} (max 64 chars).")
    return value


def _meta_canonical_json(metadata: FrozenDict) -> str:
    return json.dumps(metadata.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


# ---------------------------------------------------------------------------
# Immutable records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DecisionNode:
    """A research decision or recorded failed attempt (negative result)."""

    id: str
    title: str
    decision_type: str = "explore"
    entry_kind: str = "decision"
    decision_action: Optional[str] = None
    context_work_id: Optional[str] = None
    locator: Optional[str] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)
    normalized_title: str = field(init=False)
    decision_digest: str = field(init=False)

    @property
    def is_negative_result(self) -> bool:
        return self.entry_kind == "negative_result"

    def __post_init__(self):
        _check_id(self.id, "decision id")
        if self.decision_type not in VALID_DECISION_TYPES:
            raise ValueError(f"Invalid decision_type: {self.decision_type!r}. Must be one of {sorted(VALID_DECISION_TYPES)}")
        # Disambiguate entry_kind vs decision_action
        if self.entry_kind == "negative_result" or self.decision_type == "negative_result":
            object.__setattr__(self, "entry_kind", "negative_result")
            object.__setattr__(self, "decision_action", None)
            object.__setattr__(self, "decision_type", "negative_result")
        else:
            object.__setattr__(self, "entry_kind", "decision")
            action = self.decision_action or self.decision_type or "explore"
            if action not in VALID_DECISION_ACTIONS:
                raise ValueError(f"Invalid decision_action: {action!r}. Must be one of {sorted(VALID_DECISION_ACTIONS)}")
            object.__setattr__(self, "decision_action", action)
            object.__setattr__(self, "decision_type", action)
        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("Decision 'title' must be a non-empty string.")
        if len(self.title) > 512:
            raise ValueError("Decision 'title' must not exceed 512 characters.")
        if self.context_work_id is not None:
            _check_id(self.context_work_id, "context_work_id")
        if self.locator is not None:
            if not isinstance(self.locator, str) or not (1 <= len(self.locator) <= 2048):
                raise ValueError("locator must be a non-empty string of at most 2048 characters.")
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
            "entry_kind": self.entry_kind,
            "decision_digest": self.decision_digest,
        }
        if self.decision_action is not None:
            d["decision_action"] = self.decision_action
        if self.decision_type is not None:
            d["decision_type"] = self.decision_type
        if self.context_work_id:
            d["context_work_id"] = self.context_work_id
        if self.locator:
            d["locator"] = self.locator
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_decision_export(item: Any) -> Dict[str, Any]:
    """Authoritative canonical representation of a decision in ledger digests.

    Decoupled from legacy wire artifacts (e.g. redundant decision_type or null
    decision_action on negative results) so that content identity represents
    pure scholarly decisions and assertions.
    """
    if isinstance(item, DecisionNode):
        d_id = item.id
        title = item.title
        norm_title = item.normalized_title
        entry_kind = item.entry_kind
        action = item.decision_action
        digest = item.decision_digest
        context_work_id = item.context_work_id
        locator = item.locator
        meta = item.metadata.to_dict() if hasattr(item.metadata, "to_dict") else dict(item.metadata or {})
    else:
        d_id = item["id"]
        title = item["title"]
        norm_title = canonical_text(title)
        entry_kind = item.get("entry_kind") or ("negative_result" if item.get("decision_type") == "negative_result" else "decision")
        action = item.get("decision_action")
        if action is None and entry_kind != "negative_result":
            action = item.get("decision_type") or "explore"
        digest = item.get("decision_digest") or compute_decision_digest(
            norm_title,
            item.get("context_work_id"),
            item.get("locator"),
            decision_type="negative_result" if entry_kind == "negative_result" else action,
        )
        context_work_id = item.get("context_work_id")
        locator = item.get("locator")
        meta = dict(item.get("metadata") or {})

    res = {
        "id": d_id,
        "title": title,
        "normalized_title": norm_title,
        "entry_kind": entry_kind,
        "decision_digest": digest,
    }
    if action is not None:
        res["decision_action"] = action
    if context_work_id:
        res["context_work_id"] = context_work_id
    if locator:
        res["locator"] = locator
    if meta:
        res["metadata"] = _frozen_meta(meta).to_dict()
    return res


def canonical_raw_record(d: Mapping[str, Any]) -> Dict[str, Any]:
    """Normalize raw export records so empty optional protocol fields do not perturb digests.

    User metadata is strictly isolated: empty metadata {} is omitted, but non-empty
    metadata preserves all internal keys and values untouched.
    """
    res: Dict[str, Any] = {}
    for k, v in d.items():
        if k == "metadata":
            if v and isinstance(v, collections.abc.Mapping) and len(v) > 0:
                res["metadata"] = _frozen_meta(v).to_dict()
            continue
        if v is None:
            continue
        if v == "" and k in (
            "locator",
            "context_work_id",
            "caused_by",
            "alternative_ref",
            "stop_reason",
            "closed_by",
            "reason",
        ):
            continue
        if k == "receipt_ref" and isinstance(v, collections.abc.Mapping):
            res["receipt_ref"] = canonical_raw_record(v)
        else:
            res[k] = v
    return res


@dataclass(frozen=True)
class DecisionBasisEdge:
    """A directed edge: a decision was made on the basis of another decision or a negative result."""

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
class RouteStatus:
    """Lifecycle status of a research route: active, reopened, or stopped with explicit reason."""

    decision_id: str
    status: str
    stop_reason: Optional[str] = None
    closed_by: Optional[str] = None
    alternative_ref: Optional[str] = None
    receipt_ref: Optional[ReceiptRef] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)
    prune_reason: Optional[str] = None
    pruned_by: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "reopened")

    @property
    def is_pruned(self) -> bool:
        return self.status == "pruned"

    @property
    def is_reopened(self) -> bool:
        return self.status == "reopened"

    def __post_init__(self):
        _check_id(self.decision_id, "decision_id")
        reason = self.stop_reason or self.prune_reason
        caused = self.closed_by or self.pruned_by
        object.__setattr__(self, "stop_reason", reason)
        object.__setattr__(self, "prune_reason", reason)
        object.__setattr__(self, "closed_by", caused)
        object.__setattr__(self, "pruned_by", caused)

        if self.status not in VALID_PRUNE_STATUSES:
            raise ValueError(f"Invalid route status: {self.status!r}. Must be one of {sorted(VALID_PRUNE_STATUSES)}")
        if self.status == "pruned":
            if not self.stop_reason:
                raise ValueError("Stopped/pruned route requires a non-empty 'stop_reason' / 'prune_reason'.")
            if self.stop_reason not in VALID_PRUNE_REASONS:
                raise ValueError(f"Invalid stop_reason / prune_reason: {self.stop_reason!r}. Must be one of {sorted(VALID_PRUNE_REASONS)}")
            if self.closed_by is not None:
                _check_id(self.closed_by, "closed_by")
                if self.closed_by == self.decision_id:
                    raise ValueError(f"Circular closure / Circular pruning: decision '{self.decision_id}' cannot prune itself.")
            if self.alternative_ref is not None:
                _check_id(self.alternative_ref, "alternative_ref")
                if self.alternative_ref == self.decision_id:
                    raise ValueError(f"Self-referential alternative: route '{self.decision_id}' cannot be its own alternative.")
        else:
            if self.stop_reason is not None or self.closed_by is not None or self.alternative_ref is not None:
                raise ValueError(f"Active decision must not carry stop_reason/prune_reason/closed_by/alternative_ref fields.")
        if self.receipt_ref is not None and not isinstance(self.receipt_ref, ReceiptRef):
            raise TypeError("receipt_ref must be a ReceiptRef instance or None.")
        object.__setattr__(self, "metadata", _frozen_meta(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "status": self.status,
        }
        if self.stop_reason:
            d["stop_reason"] = self.stop_reason
        if self.closed_by:
            d["closed_by"] = self.closed_by
        if self.alternative_ref:
            d["alternative_ref"] = self.alternative_ref
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


PruneState = RouteStatus


def canonical_prune_tuple(state: RouteStatus) -> Tuple[str, ...]:
    return (
        state.decision_id,
        state.status,
        state.stop_reason or "",
        state.closed_by or "",
        state.alternative_ref or "",
    ) + canonical_receipt_ref_tuple(state.receipt_ref) + (_meta_canonical_json(state.metadata),)


@dataclass(frozen=True)
class DecisionStateEvent:
    """An append-only state transition event for a decision.

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
    sequence: int = 1
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
            if self.reason is not None and self.to_state == "active":
                raise ValueError(f"State transition to 'active' cannot take a reason (reason was {self.reason!r}).")
            if self.reason is not None and self.to_state == "reopened":
                if self.reason not in VALID_REOPEN_REASONS:
                    raise ValueError(f"Invalid reopen reason: {self.reason!r}. Must be one of {sorted(VALID_REOPEN_REASONS)}")
            if self.caused_by is not None or self.alternative_ref is not None:
                raise ValueError(f"Only 'pruned' transitions may carry caused_by/alternative_ref.")
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
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValueError("'sequence' must be an integer >= 1.")
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
    sequence: int = 1
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        _check_id(self.correction_id, "correction_id")
        _check_id(self.decision_id, "decision_id")
        if self.verdict not in VALID_VERDICTS:
            raise ValueError(f"Invalid verdict: {self.verdict!r}. Must be one of {sorted(VALID_VERDICTS)}")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise ValueError("Outcome correction requires a non-empty 'rationale'.")
        if len(self.rationale) > 4096:
            raise ValueError("Outcome correction 'rationale' must not exceed 4096 characters.")
        if self.locator is not None:
            if not isinstance(self.locator, str) or not (1 <= len(self.locator) <= 2048):
                raise ValueError("locator must be a non-empty string of at most 2048 characters.")
        if not isinstance(self.sequence, int) or self.sequence < 1:
            raise ValueError("'sequence' must be an integer >= 1.")
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

def canonical_payload_from_export(data: Mapping[str, Any]) -> Dict[str, Any]:
    """Compute the canonical payload over an export mapping using canonical representations."""
    return {
        "protocol": data["protocol"],
        "ledger_id": data["ledger_id"],
        "decisions": sorted((canonical_decision_export(d) for d in data["decisions"]), key=lambda x: x["id"]),
        "bases": sorted(
            (canonical_raw_record(d) for d in data["bases"]),
            key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
        ),
        "forks": sorted(
            (canonical_raw_record(d) for d in data["forks"]),
            key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
        ),
        "state_events": sorted(
            (canonical_raw_record(d) for d in data["state_events"]),
            key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
        ),
        "corrections": sorted(
            (canonical_raw_record(d) for d in data["corrections"]),
            key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
        ),
    }


class DecisionLedger:
    """Deterministic append-only Decision & Negative Result Ledger.

    Nodes and edges are immutable; duplicates with conflicting payloads are
    rejected; identical registrations are idempotent. The ledger digest is
    order-invariant.
    """

    def __init__(self, ledger_id: str = "default-ledger"):
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
        self._bases_by_decision: Dict[str, List[DecisionBasisEdge]] = collections.defaultdict(list)
        self._bases_by_target: Dict[str, List[DecisionBasisEdge]] = collections.defaultdict(list)
        self._state_events_by_decision: Dict[str, List[DecisionStateEvent]] = collections.defaultdict(list)
        self._corrections_by_decision: Dict[str, List[OutcomeCorrection]] = collections.defaultdict(list)
        self._academic_hash_index: Dict[str, Any] = {}

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
            ex_payload = _jsonable(ex_dict)
            new_payload = _jsonable(new_dict)
            if isinstance(ex_payload, dict) and ex_payload.get("protocol") == "lineage-receipt-1.0":
                ex_payload = dict(ex_payload)
                ex_payload.pop("timestamp", None)
            if isinstance(new_payload, dict) and new_payload.get("protocol") == "lineage-receipt-1.0":
                new_payload = dict(new_payload)
                new_payload.pop("timestamp", None)
            if _canonical_json_bytes(ex_payload) != _canonical_json_bytes(new_payload):
                raise ValueError(f"Conflicting receipt registration for {rid!r}: existing data differs from new registration.")
            return
        self._receipts[rid] = snapshot
        snap_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
        if isinstance(snap_dict, dict):
            try:
                p_hash = canonical_academic_receipt_payload_sha256(snap_dict)
                self._academic_hash_index[p_hash] = snapshot
            except Exception:
                pass

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
        entry_kind: str = "decision",
        decision_action: Optional[str] = None,
        context_work_id: Optional[str] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionNode:
        node = DecisionNode(
            id=id,
            title=title,
            decision_type=decision_type,
            entry_kind=entry_kind,
            decision_action=decision_action,
            context_work_id=context_work_id,
            locator=locator,
            metadata=metadata or {},
        )
        return self._register_node(self._decisions, node, id, "decision")

    def add_negative_result(
        self,
        id: str,
        title: str,
        context_work_id: Optional[str] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionNode:
        """First-class helper to record a failed attempt / negative result."""
        return self.add_decision(
            id=id,
            title=title,
            decision_type="negative_result",
            entry_kind="negative_result",
            decision_action=None,
            context_work_id=context_work_id,
            locator=locator,
            metadata=metadata,
        )

    def add_basis(
        self,
        decision_id: str,
        basis_kind: str,
        basis_id: str,
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DecisionBasisEdge:
        if basis_kind not in VALID_BASIS_KINDS:
            raise ValueError(f"Invalid basis_kind: {basis_kind!r}. Must be one of {sorted(VALID_BASIS_KINDS)}")
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
        self._bases_by_decision[decision_id].append(edge)
        self._bases_by_target[basis_id].append(edge)
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
        self._state_events_by_decision[decision_id].append(event)
        self._next_state_sequence += 1
        return event

    def _latest_event(self, decision_id: str) -> Optional[DecisionStateEvent]:
        """Latest state event for a decision by sequence order."""
        events = self._state_events_by_decision.get(decision_id)
        return events[-1] if events else None

    def current_state(self, decision_id: str) -> Optional[PruneState]:
        """Derived current lifecycle state of a decision (replayed from events)."""
        latest = self._latest_event(decision_id)
        if latest is None:
            return None
        return PruneState(
            decision_id=decision_id,
            status=latest.to_state,
            prune_reason=latest.reason if latest.to_state == "pruned" else None,
            pruned_by=latest.caused_by if latest.to_state == "pruned" else None,
            alternative_ref=latest.alternative_ref if latest.to_state == "pruned" else None,
            receipt_ref=latest.receipt_ref if latest.to_state == "pruned" else None,
            metadata=dict(latest.metadata),
        )

    def state_history(self, decision_id: str) -> List[Dict[str, Any]]:
        """Full append-only state transition history of a decision (replayed)."""
        events = self._state_events_by_decision.get(decision_id, [])
        return [e.to_dict() for e in events]

    def record_route_status(
        self,
        decision_id: str,
        status: str,
        stop_reason: Optional[str] = None,
        closed_by: Optional[str] = None,
        alternative_ref: Optional[str] = None,
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
        # compatibility keyword arguments:
        prune_reason: Optional[str] = None,
        pruned_by: Optional[str] = None,
    ) -> RouteStatus:
        """Record the lifecycle status of a route (active, reopened, or stopped/pruned)."""
        reason = stop_reason or prune_reason
        caused = closed_by or pruned_by
        if status not in VALID_PRUNE_STATUSES:
            raise ValueError(f"Invalid route status: {status!r}. Must be one of {sorted(VALID_PRUNE_STATUSES)}")
        if status in ("active", "reopened"):
            if reason is not None or caused is not None or alternative_ref is not None:
                raise ValueError(f"{status.capitalize()} decision must not carry stop_reason/closed_by/alternative_ref fields.")
            current = self.current_state(decision_id)
            if current is None:
                self.add_state_event(decision_id, to_state="active", receipt_ref=receipt_ref, metadata=metadata)
            elif current.status == "pruned":
                self.add_state_event(decision_id, to_state="reopened", receipt_ref=receipt_ref, metadata=metadata)
            else:
                # Already active or reopened: verify strict idempotence
                latest_ev = self._latest_event(decision_id)
                if (
                    latest_ev is not None
                    and latest_ev.receipt_ref == receipt_ref
                    and dict(latest_ev.metadata) == dict(metadata or {})
                ):
                    return current
                raise ValueError(
                    f"Decision '{decision_id}' is already {current.status}; "
                    "cannot re-activate with conflicting receipt_ref or metadata."
                )
        else:
            current = self.current_state(decision_id)
            if (
                current is not None
                and current.status == "pruned"
                and (current.stop_reason == reason or current.prune_reason == reason)
                and (current.closed_by == caused or current.pruned_by == caused)
                and current.alternative_ref == alternative_ref
                and current.receipt_ref == receipt_ref
                and dict(current.metadata) == dict(metadata or {})
            ):
                return current  # idempotent replay: already pruned with identical payload
            self.add_state_event(
                decision_id,
                to_state="pruned",
                reason=reason,
                caused_by=caused,
                alternative_ref=alternative_ref,
                receipt_ref=receipt_ref,
                metadata=metadata,
            )
        view = self.current_state(decision_id)
        assert view is not None
        return view

    set_prune = record_route_status

    def _latest_correction(self, decision_id: str) -> Optional[OutcomeCorrection]:
        """Latest outcome correction for a decision by sequence order."""
        corrs = self._corrections_by_decision.get(decision_id)
        return corrs[-1] if corrs else None

    def add_outcome_correction(
        self,
        decision_id: str,
        verdict: str,
        rationale: str,
        receipt_ref: Optional[ReceiptRef] = None,
        locator: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> OutcomeCorrection:
        _check_id(decision_id, "decision_id")
        latest = self._latest_correction(decision_id)
        if (
            latest is not None
            and latest.verdict == verdict
            and latest.rationale == rationale
            and latest.receipt_ref == receipt_ref
            and latest.locator == locator
            and dict(latest.metadata) == dict(metadata or {})
        ):
            return latest  # idempotent: latest correction is already identical

        assigned = self._next_correction_sequence
        content_tuple = (
            decision_id,
            verdict,
            rationale,
            canonical_receipt_ref_tuple(receipt_ref),
            locator or "",
            assigned,
            _meta_canonical_json(_frozen_meta(metadata)),
        )
        correction_id = "corr-" + hashlib.sha256(_canonical_json_bytes(list(content_tuple))).hexdigest()[:32]
        corr = OutcomeCorrection(
            correction_id=correction_id,
            decision_id=decision_id,
            verdict=verdict,
            rationale=rationale,
            receipt_ref=receipt_ref,
            locator=locator,
            sequence=assigned,
            metadata=metadata or {},
        )
        # Collision defense: verify identical payload or fail-closed
        if correction_id in self._corrections:
            existing = self._corrections[correction_id]
            if existing.to_dict() != corr.to_dict():
                raise ValueError(
                    f"Hash collision detected for outcome correction '{correction_id}': "
                    "different payload with identical truncated ID. Rejecting modification (fail-closed)."
                )
            return existing

        # Only commit state and increment sequence after construction and collision check succeed
        self._next_correction_sequence += 1
        self._corrections[correction_id] = corr
        self._corrections_by_decision[decision_id].append(corr)
        return corr

    # -- queries -------------------------------------------------------------

    def get_decision(self, decision_id: str) -> Optional[DecisionNode]:
        return self._decisions.get(decision_id)

    def outcome_of(self, decision_id: str) -> Dict[str, Any]:
        """Latest outcome verdict for a decision (true insertion order via sequence)."""
        related = self._corrections_by_decision.get(decision_id, [])
        return {
            "decision_id": decision_id,
            "correction_count": len(related),
            "latest_correction_id": related[-1].correction_id if related else None,
            "latest_verdict": related[-1].verdict if related else None,
        }

    def get_corrections(self, decision_id: str) -> List[OutcomeCorrection]:
        """All outcome corrections recorded for a decision, in sequence order."""
        return list(self._corrections_by_decision.get(decision_id, []))

    def get_state_history(self, decision_id: str) -> List[Dict[str, Any]]:
        """All state events for a decision, matching state_history()."""
        return self.state_history(decision_id)

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
        """All basis edges citing a given decision/negative-result, sorted deterministically."""
        candidates = self._bases_by_target.get(basis_id, [])
        out = []
        for edge in sorted(candidates, key=canonical_basis_tuple):
            if basis_kind is not None and edge.basis_kind != basis_kind:
                continue
            out.append(edge.to_dict())
        return out

    def bases_of(self, decision_id: str) -> List[Dict[str, Any]]:
        """All upstream basis edges owned by ``decision_id``, sorted deterministically."""
        return [
            edge.to_dict()
            for edge in sorted(
                self._bases_by_decision.get(decision_id, []),
                key=canonical_basis_tuple,
            )
        ]

    def _current_prune_graph(self) -> Dict[str, RouteStatus]:
        """Derived map of currently stopped/pruned decisions to their derived state views."""
        out: Dict[str, RouteStatus] = {}
        for did, events in self._state_events_by_decision.items():
            if events and events[-1].to_state == "pruned":
                e = events[-1]
                out[did] = RouteStatus(
                    decision_id=did,
                    status="pruned",
                    stop_reason=e.reason,
                    closed_by=e.caused_by,
                    alternative_ref=e.alternative_ref,
                    receipt_ref=e.receipt_ref,
                    metadata=dict(e.metadata),
                )
        return out

    def trace_stop_reason(self, decision_id: str) -> Dict[str, Any]:
        """Recursive causal trace of why a research route was stopped.

        Returns the derived current route status and the full stop_chain:
        each link lists the stopped route, its closed-vocabulary reason,
        the closure decision and that decision's decision bases.
        """
        graph = self._current_prune_graph()
        state = graph.get(decision_id)
        result: Dict[str, Any] = {
            "decision_id": decision_id,
            "route_status": state.to_dict() if state else None,
            "prune_state": state.to_dict() if state else None,
            "closed_by_decision": None,
            "pruned_by_decision": None,
            "alternative_decision": None,
            "closed_by_bases": [],
            "pruned_by_bases": [],
            "stop_chain": [],
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
                "stop_reason": link_state.stop_reason,
                "prune_reason": link_state.stop_reason,
                "closed_by": link_state.closed_by,
                "pruned_by": link_state.closed_by,
                "alternative_ref": link_state.alternative_ref,
            }
            result["stop_chain"].append(link)
            result["prune_chain"].append(link)
            cur = link_state.closed_by
        if cur is not None and cur in visited:
            result["cycle_break"] = cur

        target_closure = state.closed_by
        if target_closure:
            node = self._decisions.get(target_closure)
            result["closed_by_decision"] = node.to_dict() if node else None
            result["pruned_by_decision"] = node.to_dict() if node else None
            bases = sorted(
                (e.to_dict() for e in self._bases_by_decision.get(target_closure, [])),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            )
            result["closed_by_bases"] = bases
            result["pruned_by_bases"] = bases
            decision_bases = [b for b in bases if b["basis_kind"] == "decision"]
            if not decision_bases:
                result["unsupported_reason"] = (
                    f"Closure decision '{target_closure}' cites no decision basis (no Claim basis); "
                    "the stop cause rests on unrecorded judgment and needs human review."
                )
        if state.alternative_ref:
            alt = self._decisions.get(state.alternative_ref)
            result["alternative_decision"] = alt.to_dict() if alt else None
        return result

    trace_prune_cause = trace_stop_reason

    # -- validation & graph analysis -------------------------------------------

    def _build_graph_analysis(self) -> Dict[str, Any]:
        """Single-pass graph analysis: adjacency, cycle nodes (via Tarjan's SCC), and cycle reachability."""
        succ: Dict[str, set] = collections.defaultdict(set)
        for edge in self._bases.values():
            if edge.basis_kind == "decision" and edge.basis_id != edge.decision_id:
                succ[edge.decision_id].add(edge.basis_id)

        index = 0
        indices: Dict[str, int] = {}
        lowlink: Dict[str, int] = {}
        on_stack: set = set()
        stack: List[str] = []
        cycle_nodes: set = set()

        for start in sorted(succ.keys()):
            if start not in indices:
                call_stack: List[Tuple[str, Iterator[str]]] = [(start, iter(sorted(succ.get(start, ()))))]
                indices[start] = lowlink[start] = index
                index += 1
                stack.append(start)
                on_stack.add(start)

                while call_stack:
                    u, it = call_stack[-1]
                    advanced = False
                    for v in it:
                        if v not in indices:
                            indices[v] = lowlink[v] = index
                            index += 1
                            stack.append(v)
                            on_stack.add(v)
                            call_stack.append((v, iter(sorted(succ.get(v, ())))))
                            advanced = True
                            break
                        elif v in on_stack:
                            lowlink[u] = min(lowlink[u], indices[v])
                    if not advanced:
                        call_stack.pop()
                        if call_stack:
                            parent = call_stack[-1][0]
                            lowlink[parent] = min(lowlink[parent], lowlink[u])
                        if lowlink[u] == indices[u]:
                            scc: List[str] = []
                            while True:
                                w = stack.pop()
                                on_stack.remove(w)
                                scc.append(w)
                                if w == u:
                                    break
                            if len(scc) > 1 or (len(scc) == 1 and scc[0] in succ.get(scc[0], ())):
                                cycle_nodes.update(scc)

        cycle_reachable: set = set(cycle_nodes)
        rev_succ: Dict[str, set] = collections.defaultdict(set)
        for u, neighbors in succ.items():
            for v in neighbors:
                rev_succ[v].add(u)
        bfs = collections.deque(cycle_nodes)
        while bfs:
            curr = bfs.popleft()
            for prev in rev_succ.get(curr, ()):
                if prev not in cycle_reachable:
                    cycle_reachable.add(prev)
                    bfs.append(prev)

        return {
            "succ": succ,
            "cycle_nodes": cycle_nodes,
            "cycle_reachable": cycle_reachable,
        }

    def _resolve_receipt(self, ref: ReceiptRef) -> Optional[Any]:
        """Resolve a ReceiptRef to a registered receipt payload (CEG-compatible lookup).

        lineage refs resolve by receipt_id; academic_evidence refs resolve by
        payload_sha256 in strictly O(1) time via the academic hash index.
        """
        if ref.kind == "lineage":
            return self._receipts.get(ref.receipt_id)
        if ref.payload_sha256 in self._receipts:
            return self._receipts[ref.payload_sha256]
        return self._academic_hash_index.get(ref.payload_sha256)

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
                if edge.basis_kind == "decision" and target.decision_type == "negative_result":
                    errors.append(f"E103 basis kind mismatch: decision basis '{edge.basis_id}' targets a negative_result decision")
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
        pruned_by_graph: Dict[str, str] = {
            s.decision_id: s.closed_by
            for s in self._current_prune_graph().values()
            if s.closed_by
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

        # Negative results must be evidence-bearing (E404/E405/E406/E407)
        neg_ids = {n.id for n in self._decisions.values() if n.decision_type == "negative_result"}
        analysis = self._build_graph_analysis()

        for node in sorted(self._decisions.values(), key=lambda d: d.id):
            if node.decision_type != "negative_result":
                continue
            bases = self._bases_by_decision.get(node.id, [])
            if not bases:
                errors.append(f"E404 negative result '{node.id}' carries no basis edge (assertion of absence needs evidence)")
                continue
            if any(e.basis_kind == "decision" and e.basis_id == node.id for e in bases):
                errors.append(f"E406 negative result '{node.id}' cites itself as evidence (circular evidence fabrication)")
            decision_bases = [
                e for e in bases
                if e.basis_kind == "decision" and e.basis_id != node.id and e.basis_id not in neg_ids
            ]
            if not decision_bases:
                errors.append(f"E405 negative result '{node.id}' is supported only by other negative results (no positive evidence base)")
            if node.id in analysis["cycle_reachable"]:
                errors.append(f"E407 negative result '{node.id}': claim-basis closure contains a cycle that can never ground at a receipt anchor")

        unique = sorted(set(errors))
        return (len(unique) == 0, unique)

    # -- uncertainty queue -------------------------------------------------

    def export_uncertainties(self, manifest_override: Optional[Mapping[str, str]] = None) -> List[UncertaintyItem]:
        """Deterministic three-state uncertainty queue (content-addressed ids)."""
        items: List[UncertaintyItem] = []

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
            if ref is None:
                return
            resolvable = self._resolve_receipt(ref) is not None
            if not resolvable and manifest_override is not None:
                if ref.kind == "lineage":
                    resolvable = bool(ref.receipt_id and ref.receipt_id in manifest_override)
                elif ref.kind == "academic_evidence":
                    if ref.payload_sha256:
                        resolvable = (
                            ref.payload_sha256 in manifest_override
                            or ref.payload_sha256 in manifest_override.values()
                        )
            if not resolvable:
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
            bases = self._bases_by_decision.get(node.id, [])
            if not bases:
                add(
                    "decision_without_basis",
                    node.id,
                    f"Negative result '{node.id}' carries no basis edge; the assertion of absence is unevidenced.",
                    True,
                )
            elif not any(e.basis_kind == "decision" for e in bases):
                add(
                    "unsupported_negative_result",
                    node.id,
                    f"Negative result '{node.id}' cites only other negative results; no positive evidence base exists.",
                    True,
                )

        # Stopped routes without any decision basis (derived current route graph)
        for state in self._current_prune_graph().values():
            if not state.closed_by:
                continue
            decision_bases = [
                e for e in self._bases_by_decision.get(state.closed_by, [])
                if e.basis_kind == "decision"
            ]
            if not decision_bases:
                add(
                    "unsupported_pruning",
                    state.decision_id,
                    f"Pruning decision '{state.closed_by}' cites no decision basis (no Claim basis); the prune cause needs human review.",
                    True,
                )

        # Single-pass graph analysis for terminal reachability and cycles
        analysis = self._build_graph_analysis()
        claim_succ = analysis["succ"]
        claim_edges = [(e.decision_id, e.basis_id, e) for e in self._bases.values() if e.basis_kind == "decision"]
        cycle_nodes = analysis["cycle_nodes"]

        terminal_targets = sorted({v for _u, v, _e in claim_edges if not (claim_succ.get(v, set()) - {v})})
        for v in terminal_targets:
            if v in cycle_nodes:
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
        for v in sorted({v for v in claim_succ if v in cycle_nodes}):
            add(
                "unevidenced_claim_basis",
                v,
                f"Claim-basis chain through '{v}' never grounds (cycle); no receipt anchoring exists.",
                True,
            )

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
            "decisions": sorted((canonical_decision_export(d) for d in self._decisions.values()), key=lambda x: x["id"]),
            "bases": sorted(
                (canonical_raw_record(e.to_dict()) for e in self._bases.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "forks": sorted(
                (canonical_raw_record(e.to_dict()) for e in self._forks.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "state_events": sorted(
                (canonical_raw_record(s.to_dict()) for s in self._state_events),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
            "corrections": sorted(
                (canonical_raw_record(c.to_dict()) for c in self._corrections.values()),
                key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
            ),
        }
        return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()

    def _compute_verification_manifest(self) -> Dict[str, str]:
        """Compute the canonical verification manifest (receipt_id -> payload_sha256)."""
        return {
            rid: canonical_ledger_payload_sha256(_jsonable(r))
            for rid, r in sorted(self._receipts.items())
        }

    def verification_digest(self) -> str:
        """Digest of the ledger content identity plus the local receipt registry.

        Separated from ledger_digest so the registry's caller-chosen labels
        and cache state are never conflated with content identity. Exported
        alongside ledger_digest so a verifier can distinguish content from
        verification state.
        """
        manifest = self._compute_verification_manifest()
        payload = {"ledger_digest": self.ledger_digest(), "receipts": manifest}
        return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest().lower()

    def to_dict(self) -> Dict[str, Any]:
        """Export an immutable deep representation with content identity and verification digests."""
        ld = self.ledger_digest()
        manifest = self._compute_verification_manifest()
        vd_payload = {"ledger_digest": ld, "receipts": manifest}
        vd = hashlib.sha256(_canonical_json_bytes(vd_payload)).hexdigest().lower()
        d: Dict[str, Any] = {
            "protocol": PROTOCOL,
            "ledger_id": self.ledger_id,
            "ledger_digest": ld,
            "verification_digest": vd,
            "verification_manifest": manifest,
            "decisions": [self._decisions[k].to_dict() for k in sorted(self._decisions)],
            "bases": [self._bases[k].to_dict() for k in sorted(self._bases)],
            "forks": [self._forks[k].to_dict() for k in sorted(self._forks)],
            "state_events": [e.to_dict() for e in sorted(self._state_events, key=lambda x: (x.sequence, x.event_id))],
            "corrections": [c.to_dict() for c in sorted(self._corrections.values(), key=lambda x: (x.sequence, x.correction_id))],
            "uncertainties": [u.to_dict() for u in self.export_uncertainties()],
        }
        return copy.deepcopy(d)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        receipt_registry: Optional[Mapping[str, Any]] = None,
    ) -> "DecisionLedger":
        """Strict replay loader: rebuild a ledger from a to_dict() export.

        Four-gate verification for complete fail-closed defense:
        1. Raw digest verification: computes the canonical ledger payload directly
           over declared records in `data`. Any tampering with exported fields
           (event_id, sequence, decision_digest, normalized_title, correction_id,
           outcome_digest, etc.) immediately fails against `ledger_digest`.
        2. Replay & invariant verification: replays records through constructors,
           which re-evaluate transition legality, sequence progression, and
           identity derivation. Every replayed record is verified to match the
           declared record exactly.
        3. Verification manifest & uncertainty queue gates:
           - Declared `verification_manifest` is verified against `verification_digest`.
           - If `receipt_registry` is provided, receipts are registered and
             `verification_digest` is re-asserted.
           - Uncertainty queue is recomputed and strictly compared to declared
             uncertainties (no uncertainties, including missing_receipt, skipped).
        4. Structural graph validation: validate_ledger() is executed on the replayed
           ledger; exports with cycles, dangling edges, or invalid evidence fail closed.
        """
        if not isinstance(data, collections.abc.Mapping):
            raise TypeError("from_dict expects a mapping produced by DecisionLedger.to_dict().")
        unexpected = set(data.keys()) - ALLOWED_TOP_LEVEL_KEYS
        if unexpected:
            raise ValueError(f"Unexpected top-level fields in export: {sorted(unexpected)}")
        for key in (
            "protocol",
            "ledger_id",
            "ledger_digest",
            "verification_digest",
            "verification_manifest",
            "decisions",
            "bases",
            "forks",
            "state_events",
            "corrections",
            "uncertainties",
        ):
            if key not in data:
                raise ValueError(f"Export contract violation: missing required key {key!r}.")
        if data["protocol"] != PROTOCOL:
            raise ValueError(f"Export protocol mismatch: expected {PROTOCOL!r}, got {data['protocol']!r}.")

        # Gate 1: raw content digest over declared records
        raw_payload = canonical_payload_from_export(data)
        raw_digest = hashlib.sha256(_canonical_json_bytes(raw_payload)).hexdigest().lower()
        if raw_digest != str(data["ledger_digest"]).lower():
            raise ValueError(
                f"Export content tampering detected: raw payload digest {raw_digest!r} "
                f"does not match declared ledger_digest {data['ledger_digest']!r}."
            )

        # Gate 2: verification manifest vs verification digest
        v_manifest = data.get("verification_manifest", {})
        if not isinstance(v_manifest, collections.abc.Mapping):
            raise ValueError("Export verification_manifest must be an object/mapping.")
        v_payload = {
            "ledger_digest": str(data["ledger_digest"]).lower(),
            "receipts": v_manifest,
        }
        v_digest = hashlib.sha256(_canonical_json_bytes(v_payload)).hexdigest().lower()
        if v_digest != str(data["verification_digest"]).lower():
            raise ValueError(
                f"Export verification manifest mismatch: recomputed verification digest {v_digest!r} "
                f"does not match declared verification_digest {data['verification_digest']!r}."
            )

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

        # Replay decisions and assert identity fields match
        for d in data["decisions"]:
            node = ledger.add_decision(
                id=d["id"],
                title=d["title"],
                decision_type=d.get("decision_type") or d.get("decision_action") or ("negative_result" if d.get("entry_kind") == "negative_result" else "explore"),
                entry_kind=d.get("entry_kind", "decision"),
                decision_action=d.get("decision_action"),
                context_work_id=d.get("context_work_id"),
                locator=d.get("locator"),
                metadata=d.get("metadata") or {},
            )
            if node.normalized_title != d.get("normalized_title"):
                raise ValueError(
                    f"Replayed decision normalized_title mismatch for {d['id']!r}: "
                    f"declared {d.get('normalized_title')!r}, recomputed {node.normalized_title!r}."
                )
            if node.decision_digest != d.get("decision_digest"):
                raise ValueError(
                    f"Replayed decision digest mismatch for {d['id']!r}: "
                    f"declared {d.get('decision_digest')!r}, recomputed {node.decision_digest!r}."
                )

        # Replay bases
        for e in data["bases"]:
            ledger.add_basis(
                decision_id=e["decision_id"],
                basis_kind=e["basis_kind"],
                basis_id=e["basis_id"],
                receipt_ref=_ref(e.get("receipt_ref")),
                metadata=e.get("metadata") or {},
            )

        # Replay forks
        for e in data["forks"]:
            ledger.add_fork(
                decision_id=e["decision_id"],
                alternative_id=e["alternative_id"],
                relation=e["relation"],
                receipt_ref=_ref(e.get("receipt_ref")),
                metadata=e.get("metadata") or {},
            )

        # Replay state events in sequence order and assert identity fields match
        for e in sorted(data["state_events"], key=lambda x: x.get("sequence", 0)):
            from_state = e.get("from_state")
            current = ledger.current_state(e["decision_id"])
            current_from: Optional[str] = None
            if current is not None:
                hist = ledger.state_history(e["decision_id"])
                if hist:
                    current_from = hist[-1]["to_state"]
            if current_from != from_state:
                raise ValueError(
                    f"Export replay violation: state event {e.get('event_id')!r} declares from_state={from_state!r} "
                    f"but replayed history is at {current_from!r}."
                )
            ev = ledger.add_state_event(
                decision_id=e["decision_id"],
                to_state=e["to_state"],
                reason=e.get("reason"),
                caused_by=e.get("caused_by"),
                alternative_ref=e.get("alternative_ref"),
                receipt_ref=_ref(e.get("receipt_ref")),
                metadata=e.get("metadata") or {},
            )
            if ev.event_id != e.get("event_id"):
                raise ValueError(
                    f"Replayed state event event_id mismatch for {e['decision_id']!r}: "
                    f"declared {e.get('event_id')!r}, recomputed {ev.event_id!r}."
                )
            if ev.sequence != e.get("sequence"):
                raise ValueError(
                    f"Replayed state event sequence mismatch for {e.get('event_id')!r}: "
                    f"declared {e.get('sequence')!r}, recomputed {ev.sequence!r}."
                )

        # Replay corrections in sequence order and assert identity fields match
        for c in sorted(data["corrections"], key=lambda x: x.get("sequence", 0)):
            corr = ledger.add_outcome_correction(
                decision_id=c["decision_id"],
                verdict=c["verdict"],
                rationale=c["rationale"],
                receipt_ref=_ref(c.get("receipt_ref")),
                locator=c.get("locator"),
                metadata=c.get("metadata") or {},
            )
            if corr.correction_id != c.get("correction_id"):
                raise ValueError(
                    f"Replayed correction correction_id mismatch for {c['decision_id']!r}: "
                    f"declared {c.get('correction_id')!r}, recomputed {corr.correction_id!r}."
                )
            if corr.sequence != c.get("sequence"):
                raise ValueError(
                    f"Replayed correction sequence mismatch for {c.get('correction_id')!r}: "
                    f"declared {c.get('sequence')!r}, recomputed {corr.sequence!r}."
                )
            if corr.outcome_digest != c.get("outcome_digest"):
                raise ValueError(
                    f"Replayed correction outcome_digest mismatch for {c.get('correction_id')!r}: "
                    f"declared {c.get('outcome_digest')!r}, recomputed {corr.outcome_digest!r}."
                )

        # Check replayed ledger_digest
        recomputed = ledger.ledger_digest()
        if recomputed != str(data["ledger_digest"]).lower():
            raise ValueError(
                f"Export digest mismatch on replay: declared {data['ledger_digest']!r}, recomputed {recomputed!r}."
            )

        # Optional receipt registry population
        if receipt_registry is not None:
            for rid, r in sorted(receipt_registry.items()):
                ledger.register_receipt(rid, r)
            if ledger.verification_digest() != str(data["verification_digest"]).lower():
                raise ValueError(
                    f"Provided receipt_registry verification digest mismatch: recomputed {ledger.verification_digest()!r} "
                    f"does not match declared verification_digest {data['verification_digest']!r}."
                )

        # Gate 3: Full uncertainty queue verification (no uncertainties skipped)
        declared_unc = sorted(data["uncertainties"], key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False))
        recomputed_unc = sorted(
            (
                u.to_dict()
                for u in ledger.export_uncertainties(
                    manifest_override=v_manifest if receipt_registry is None else None
                )
            ),
            key=lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
        )
        if declared_unc != recomputed_unc:
            raise ValueError(
                f"Export uncertainty queue mismatch: declared {len(declared_unc)} items, "
                f"recomputed {len(recomputed_unc)} items. Uncertainty records cannot be modified or suppressed."
            )

        # Gate 4: Structural validation on replayed ledger
        valid, errors = ledger.validate_ledger()
        if not valid:
            raise ValueError(f"Replayed ledger failed structural validation: {'; '.join(errors)}")

        return ledger

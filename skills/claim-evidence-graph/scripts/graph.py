# -*- coding: utf-8 -*-
"""Claim-Evidence Graph Kernel v1.

Deterministic, content-addressed scientific assertion and evidence graph.
Directly consumes ResearchObject, AcademicEvidenceReceipt, and LineageReceipt.

Core Invariants:
1. Separation of causal provenance DAG from semantic assertion graph:
   Semantic relation cycles (e.g. A contradicts B and B contradicts A) are valid and preserved.
2. Rejection of Truth Authority and subjective scores:
   No artificial confidence scores (e.g. 0.85); discrete verdicts and explicit uncertainty queue.
3. Strongly typed ReceiptRef with strict mutual exclusivity:
   LineageReceipt requires lineage-receipt-1.0, receipt_id, receipt_digest (no academic fields).
   AcademicEvidenceReceipt requires 1.0, claim_digest, payload_sha256 (no lineage fields).
4. Strict actual payload verification:
   AcademicEvidenceReceipt payload SHA256 is physically recomputed and asserted (no bypass via registry key).
   Exact claim_digest must match a valid claim record with legitimate evidence_type.
5. Strict LineageReceipt positive assertion:
   Asserts protocol='lineage-receipt-1.0', exact receipt_id, and exact receipt_digest.
6. Lexical canonicalization only:
   NFC normalization and whitespace compaction; never rewrites or paraphrases claim text.
7. Deeply frozen records & immutable metadata mapping:
   Nodes, edges, and metadata are deeply immutable (FrozenDict), preventing nested mutation drift.
   Receipt registration deepcopies payloads preventing external mutation.
8. Semantic anchor-type and receipt-kind alignment:
   lineage_receipt anchors strictly require lineage receipts; evidence_receipt anchors require academic receipts.
9. Trace provenance strict receipt verification:
   External receipt registries cannot override verified internal receipts; all traced receipts re-validate contract.
10. Order-invariant graph digest & content-addressed uncertainty items:
   Full canonical sorting across nodes and edges; missing registered receipts surface as missing_receipt uncertainties.
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
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Set, Tuple

__all__ = [
    "FrozenDict",
    "ReceiptRef",
    "Claim",
    "EvidenceAnchor",
    "EvidenceSupportEdge",
    "ClaimRelationEdge",
    "UncertaintyItem",
    "ClaimEvidenceGraph",
    "canonical_claim_text",
    "compute_claim_digest",
    "canonical_receipt_ref_tuple",
    "canonical_support_edge_tuple",
    "canonical_claim_relation_tuple",
    "canonical_academic_receipt_payload_sha256",
    "canonical_evidence_claim_digest",
    "validate_lineage_receipt_contract",
    "validate_academic_receipt_contract",
]

VALID_CLAIM_TYPES: Set[str] = {
    "empirical_finding",
    "theoretical_claim",
    "benchmark_result",
    "methodological_assertion",
    "generic_claim",
}

VALID_ANCHOR_TYPES: Set[str] = {
    "lineage_receipt",
    "evidence_receipt",
    "table_cell",
    "figure_artifact",
    "direct_observation",
}

VALID_SUPPORT_STATUSES: Set[str] = {
    "supported",
    "contradicted",
    "unverifiable",
    "out_of_scope",
}

VALID_CLAIM_RELATIONS: Set[str] = {
    "contradicts",
    "corroborates",
    "cites",
    "refines",
    "depends_on",
}

VALID_RECEIPT_KINDS: Set[str] = {
    "academic_evidence",
    "lineage",
}

VALID_EVIDENCE_TYPES: Set[str] = {
    "metadata",
    "citation_count",
    "update_signal",
    "full_text",
    "computed",
}

VALID_UNCERTAINTY_KINDS: Set[str] = {
    "unverifiable_claim",
    "unresolved_contradiction",
    "missing_receipt",
    "ambiguous_locator",
    "generic_uncertainty",
}

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


def _freeze_val(val: Any) -> Any:
    if isinstance(val, (dict, collections.abc.Mapping)):
        return FrozenDict(val)
    if isinstance(val, (list, tuple, set)):
        return tuple(_freeze_val(item) for item in val)
    return val


def _thaw_val(val: Any) -> Any:
    if isinstance(val, FrozenDict):
        return val.to_dict()
    if isinstance(val, (tuple, list, set)):
        return [_thaw_val(item) for item in val]
    return val


class FrozenDict(collections.abc.Mapping):
    """Deeply immutable mapping supporting hashing and preventing nested mutation."""

    def __init__(self, mapping_or_iterable: Any = None):
        self._store: Dict[str, Any] = {}
        if mapping_or_iterable:
            if isinstance(mapping_or_iterable, collections.abc.Mapping):
                items = mapping_or_iterable.items()
            else:
                items = list(mapping_or_iterable)
            for k, v in items:
                self._store[str(k)] = _freeze_val(v)

    def __getitem__(self, key: str) -> Any:
        return self._store[key]

    def __len__(self) -> int:
        return len(self._store)

    def __iter__(self) -> Iterator[str]:
        return iter(self._store)

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._store.items())))

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
        return {k: _thaw_val(v) for k, v in self._store.items()}

    def __repr__(self) -> str:
        return f"FrozenDict({self._store!r})"


def canonical_claim_text(text: str) -> str:
    """Normalize claim text via Unicode NFC and whitespace compaction without paraphrasing."""
    if not text:
        return ""
    norm = unicodedata.normalize("NFC", str(text))
    norm = re.sub(r"[\r\n\t]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def compute_claim_digest(text: str, target_work_id: Optional[str] = None, locator: Optional[str] = None, claim_type: str = "empirical_finding") -> str:
    """Compute deterministic content-addressed SHA256 digest identifying a specific claim occurrence."""
    norm_txt = canonical_claim_text(text)
    payload = {
        "claim_type": claim_type,
        "locator": locator or "",
        "target_work_id": target_work_id or "",
        "text": norm_txt,
    }
    canon_bytes = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest().lower()


def canonical_academic_receipt_payload_sha256(receipt_dict: Dict[str, Any]) -> str:
    """Compute canonical SHA256 of AcademicEvidenceReceipt payload matching schema."""
    canon_bytes = json.dumps(
        receipt_dict,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest().lower()


def canonical_evidence_claim_digest(claim_item: Dict[str, Any]) -> str:
    """Compute digest of an exact claim entry inside an AcademicEvidenceReceipt."""
    payload = {
        "claim": claim_item.get("claim", ""),
        "evidence_type": claim_item.get("evidence_type", ""),
        "locator": claim_item.get("locator", ""),
        "source": claim_item.get("source", ""),
        "support_status": claim_item.get("support_status", ""),
    }
    canon_bytes = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canon_bytes).hexdigest().lower()


try:
    from shared_contracts.evidence import (
        ReceiptRef,
        canonical_receipt_ref_tuple,
        canonical_academic_receipt_payload_sha256,
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
        validate_lineage_receipt_contract,
        validate_academic_receipt_contract,
        verify_receipt_reference,
    )


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    target_work_id: Optional[str] = None
    locator: Optional[str] = None
    claim_type: str = "empirical_finding"
    entities: Tuple[str, ...] = field(default_factory=tuple)
    metadata: FrozenDict = field(default_factory=FrozenDict)
    normalized_text: str = field(init=False)
    claim_digest: str = field(init=False)

    def __post_init__(self):
        if self.claim_type not in VALID_CLAIM_TYPES:
            raise ValueError(f"Invalid claim_type: {self.claim_type!r}. Must be one of {sorted(VALID_CLAIM_TYPES)}")
        norm_txt = canonical_claim_text(self.text)
        object.__setattr__(self, "normalized_text", norm_txt)
        digest = compute_claim_digest(
            text=norm_txt,
            target_work_id=self.target_work_id,
            locator=self.locator,
            claim_type=self.claim_type,
        )
        object.__setattr__(self, "claim_digest", digest)
        ents = tuple(sorted(list(set(self.entities))))
        object.__setattr__(self, "entities", ents)
        object.__setattr__(self, "metadata", FrozenDict(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "normalized_text": self.normalized_text,
            "claim_type": self.claim_type,
            "claim_digest": self.claim_digest,
        }
        if self.target_work_id:
            d["target_work_id"] = self.target_work_id
        if self.locator:
            d["locator"] = self.locator
        if self.entities:
            d["entities"] = list(self.entities)
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


@dataclass(frozen=True)
class EvidenceAnchor:
    id: str
    anchor_type: str
    source_work_id: Optional[str] = None
    locator: Optional[str] = None
    receipt_ref: Optional[ReceiptRef] = None
    content_sha256: Optional[str] = None
    excerpt: Optional[str] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        if self.anchor_type not in VALID_ANCHOR_TYPES:
            raise ValueError(f"Invalid anchor_type: {self.anchor_type!r}. Must be one of {sorted(VALID_ANCHOR_TYPES)}")
        if self.content_sha256 is not None:
            c_sha = self.content_sha256.strip().lower()
            if not SHA256_REGEX.match(c_sha):
                raise ValueError(f"Invalid content_sha256 format: {self.content_sha256!r}")
            object.__setattr__(self, "content_sha256", c_sha)

        # Semantic anchor-type and receipt-kind alignment
        if self.anchor_type == "lineage_receipt":
            if not self.receipt_ref or self.receipt_ref.kind != "lineage":
                raise ValueError("EvidenceAnchor with anchor_type='lineage_receipt' requires a ReceiptRef with kind='lineage'.")
        elif self.anchor_type == "evidence_receipt":
            if not self.receipt_ref or self.receipt_ref.kind != "academic_evidence":
                raise ValueError("EvidenceAnchor with anchor_type='evidence_receipt' requires a ReceiptRef with kind='academic_evidence'.")

        object.__setattr__(self, "metadata", FrozenDict(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "id": self.id,
            "anchor_type": self.anchor_type,
        }
        if self.source_work_id:
            d["source_work_id"] = self.source_work_id
        if self.locator:
            d["locator"] = self.locator
        if self.receipt_ref:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if self.content_sha256:
            d["content_sha256"] = self.content_sha256
        if self.excerpt:
            d["excerpt"] = self.excerpt
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


@dataclass(frozen=True)
class EvidenceSupportEdge:
    evidence_id: str
    claim_id: str
    support_status: str
    receipt_ref: Optional[ReceiptRef] = None
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        if self.support_status not in VALID_SUPPORT_STATUSES:
            raise ValueError(f"Invalid support_status: {self.support_status!r}. Must be one of {sorted(VALID_SUPPORT_STATUSES)}")
        object.__setattr__(self, "metadata", FrozenDict(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "support_status": self.support_status,
        }
        if self.receipt_ref:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_support_edge_tuple(edge: EvidenceSupportEdge) -> Tuple[Any, ...]:
    meta_json = json.dumps(edge.metadata.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return (
        edge.evidence_id,
        edge.claim_id,
        edge.support_status,
        canonical_receipt_ref_tuple(edge.receipt_ref),
        meta_json,
    )


@dataclass(frozen=True)
class ClaimRelationEdge:
    source_claim_id: str
    target_claim_id: str
    relation_type: str
    evidence_refs: Tuple[str, ...] = field(default_factory=tuple)
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        if self.relation_type not in VALID_CLAIM_RELATIONS:
            raise ValueError(f"Invalid relation_type: {self.relation_type!r}. Must be one of {sorted(VALID_CLAIM_RELATIONS)}")
        ev_tuple = tuple(sorted(list(set(self.evidence_refs))))
        object.__setattr__(self, "evidence_refs", ev_tuple)
        object.__setattr__(self, "metadata", FrozenDict(self.metadata))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "source_claim_id": self.source_claim_id,
            "target_claim_id": self.target_claim_id,
            "relation_type": self.relation_type,
        }
        if self.evidence_refs:
            d["evidence_refs"] = list(self.evidence_refs)
        if len(self.metadata) > 0:
            d["metadata"] = self.metadata.to_dict()
        return d


def canonical_claim_relation_tuple(edge: ClaimRelationEdge) -> Tuple[Any, ...]:
    meta_json = json.dumps(edge.metadata.to_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return (
        edge.source_claim_id,
        edge.target_claim_id,
        edge.relation_type,
        edge.evidence_refs,
        meta_json,
    )


@dataclass(frozen=True)
class UncertaintyItem:
    item_id: str
    subject_id: str
    kind: str
    reason: str
    needs_human: bool
    metadata: FrozenDict = field(default_factory=FrozenDict)

    def __post_init__(self):
        if self.kind not in VALID_UNCERTAINTY_KINDS:
            raise ValueError(f"Invalid uncertainty kind: {self.kind!r}. Must be one of {sorted(VALID_UNCERTAINTY_KINDS)}")
        object.__setattr__(self, "metadata", FrozenDict(self.metadata))

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


class ClaimEvidenceGraph:
    """Deterministic scientific assertion and evidence graph container."""

    def __init__(self, graph_id: str = "ceg-default"):
        self.graph_id: str = str(graph_id).strip()
        self.claims: Dict[str, Claim] = {}
        self.evidence_anchors: Dict[str, EvidenceAnchor] = {}
        self.support_edges: List[EvidenceSupportEdge] = []
        self.claim_relations: List[ClaimRelationEdge] = []
        self._all_node_ids: Dict[str, str] = {}
        self._support_edge_keys: Set[Tuple[Any, ...]] = set()
        self._claim_relation_keys: Set[Tuple[Any, ...]] = set()
        self._receipt_registry: Dict[str, Any] = {}

    def register_receipt(self, receipt_id: str, receipt_data: Any):
        """Register an AcademicEvidenceReceipt or LineageReceipt with deepcopy and conflict rejection."""
        rid = str(receipt_id).strip()
        snapshot = copy.deepcopy(receipt_data)
        if rid in self._receipt_registry:
            existing = self._receipt_registry[rid]
            ex_dict = existing.to_dict() if hasattr(existing, "to_dict") else existing
            new_dict = snapshot.to_dict() if hasattr(snapshot, "to_dict") else snapshot
            if ex_dict != new_dict:
                raise ValueError(f"Conflicting receipt registration for {rid!r}: existing data differs from new registration.")
            return
        self._receipt_registry[rid] = snapshot

    def add_claim(
        self,
        id: str,
        text: str,
        target_work_id: Optional[str] = None,
        locator: Optional[str] = None,
        claim_type: str = "empirical_finding",
        entities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Claim:
        cid = str(id).strip()
        if cid in self._all_node_ids and self._all_node_ids[cid] != "claim":
            raise ValueError(f"Namespace collision: ID {cid!r} is already registered as an evidence anchor.")

        new_claim = Claim(
            id=cid,
            text=text,
            target_work_id=target_work_id,
            locator=locator,
            claim_type=claim_type,
            entities=tuple(entities or []),
            metadata=FrozenDict(metadata or {}),
        )

        if cid in self.claims:
            existing = self.claims[cid]
            if (
                existing.normalized_text != new_claim.normalized_text
                or existing.target_work_id != new_claim.target_work_id
                or existing.locator != new_claim.locator
                or existing.claim_type != new_claim.claim_type
                or existing.entities != new_claim.entities
                or existing.metadata != new_claim.metadata
            ):
                raise ValueError(
                    f"Conflicting claim registration for ID {cid!r}: "
                    f"existing={existing.to_dict()}, new={new_claim.to_dict()}"
                )
            return existing

        self.claims[cid] = new_claim
        self._all_node_ids[cid] = "claim"
        return new_claim

    def add_evidence(
        self,
        id: str,
        anchor_type: str,
        source_work_id: Optional[str] = None,
        locator: Optional[str] = None,
        receipt_ref: Optional[ReceiptRef] = None,
        content_sha256: Optional[str] = None,
        excerpt: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceAnchor:
        eid = str(id).strip()
        if eid in self._all_node_ids and self._all_node_ids[eid] != "evidence":
            raise ValueError(f"Namespace collision: ID {eid!r} is already registered as a claim.")

        new_ev = EvidenceAnchor(
            id=eid,
            anchor_type=anchor_type,
            source_work_id=source_work_id,
            locator=locator,
            receipt_ref=receipt_ref,
            content_sha256=content_sha256,
            excerpt=excerpt,
            metadata=FrozenDict(metadata or {}),
        )

        if eid in self.evidence_anchors:
            existing = self.evidence_anchors[eid]
            ex_ref = existing.receipt_ref.to_dict() if existing.receipt_ref else None
            new_ref = new_ev.receipt_ref.to_dict() if new_ev.receipt_ref else None
            if (
                existing.anchor_type != new_ev.anchor_type
                or existing.source_work_id != new_ev.source_work_id
                or existing.locator != new_ev.locator
                or ex_ref != new_ref
                or existing.content_sha256 != new_ev.content_sha256
                or existing.excerpt != new_ev.excerpt
                or existing.metadata != new_ev.metadata
            ):
                raise ValueError(
                    f"Conflicting evidence registration for ID {eid!r}: "
                    f"existing={existing.to_dict()}, new={new_ev.to_dict()}"
                )
            return existing

        self.evidence_anchors[eid] = new_ev
        self._all_node_ids[eid] = "evidence"
        return new_ev

    def add_support_edge(
        self,
        evidence_id: str,
        claim_id: str,
        support_status: str,
        receipt_ref: Optional[ReceiptRef] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> EvidenceSupportEdge:
        eid = str(evidence_id).strip()
        cid = str(claim_id).strip()
        edge = EvidenceSupportEdge(
            evidence_id=eid,
            claim_id=cid,
            support_status=support_status,
            receipt_ref=receipt_ref,
            metadata=FrozenDict(metadata or {}),
        )
        k = canonical_support_edge_tuple(edge)
        if k not in self._support_edge_keys:
            self._support_edge_keys.add(k)
            self.support_edges.append(edge)
        return edge

    def add_claim_relation(
        self,
        source_claim_id: str,
        target_claim_id: str,
        relation_type: str,
        evidence_refs: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClaimRelationEdge:
        sid = str(source_claim_id).strip()
        tid = str(target_claim_id).strip()
        edge = ClaimRelationEdge(
            source_claim_id=sid,
            target_claim_id=tid,
            relation_type=relation_type,
            evidence_refs=tuple(evidence_refs or []),
            metadata=FrozenDict(metadata or {}),
        )
        k = canonical_claim_relation_tuple(edge)
        if k not in self._claim_relation_keys:
            self._claim_relation_keys.add(k)
            self.claim_relations.append(edge)
        return edge

    def validate_graph(self) -> Tuple[bool, List[str]]:
        """Strict structural integrity and receipt payload verification."""
        errors: List[str] = []

        # 1. Support edges integrity
        for edge in self.support_edges:
            if edge.evidence_id not in self.evidence_anchors:
                errors.append(f"Dangling support edge: evidence anchor {edge.evidence_id!r} not found in graph.")
            if edge.claim_id not in self.claims:
                errors.append(f"Dangling support edge: target claim {edge.claim_id!r} not found in graph.")

        # 2. Claim relations integrity
        for edge in self.claim_relations:
            if edge.source_claim_id not in self.claims:
                errors.append(f"Dangling claim relation: source claim {edge.source_claim_id!r} not found in graph.")
            if edge.target_claim_id not in self.claims:
                errors.append(f"Dangling claim relation: target claim {edge.target_claim_id!r} not found in graph.")
            for ev_id in edge.evidence_refs:
                if ev_id not in self.evidence_anchors:
                    errors.append(f"Dangling evidence reference {ev_id!r} in claim relation ({edge.source_claim_id} -> {edge.target_claim_id}).")

        # 3. Receipt reference verification across both EvidenceAnchors and SupportEdges
        all_refs: List[Tuple[str, ReceiptRef]] = []
        for eid, ev in self.evidence_anchors.items():
            if ev.receipt_ref:
                all_refs.append((f"evidence {eid!r}", ev.receipt_ref))
        for i, edge in enumerate(self.support_edges):
            if edge.receipt_ref:
                all_refs.append((f"support_edge[{i}] ({edge.evidence_id}->{edge.claim_id})", edge.receipt_ref))

        for owner_desc, ref in all_refs:
            if ref.kind == "lineage":
                if ref.receipt_id in self._receipt_registry:
                    registered = self._receipt_registry[ref.receipt_id]
                    ok, err_msg = validate_lineage_receipt_contract(ref, registered)
                    if not ok:
                        errors.append(f"{err_msg} on {owner_desc}")
            elif ref.kind == "academic_evidence":
                matched_receipt = None
                if ref.payload_sha256 in self._receipt_registry:
                    matched_receipt = self._receipt_registry[ref.payload_sha256]
                else:
                    for reg_val in self._receipt_registry.values():
                        val_dict = reg_val if isinstance(reg_val, dict) else (reg_val.to_dict() if hasattr(reg_val, "to_dict") else {})
                        if canonical_academic_receipt_payload_sha256(val_dict) == ref.payload_sha256:
                            matched_receipt = val_dict
                            break

                if matched_receipt is not None:
                    ok, err_msg = validate_academic_receipt_contract(ref, matched_receipt)
                    if not ok:
                        errors.append(f"{err_msg} on {owner_desc}")

        return (len(errors) == 0, errors)

    def find_support(self, claim_id: str) -> List[Dict[str, Any]]:
        """Deterministic retrieval of supporting evidence anchors and corroborating claims."""
        cid = str(claim_id).strip()
        results: List[Dict[str, Any]] = []

        for edge in self.support_edges:
            if edge.claim_id == cid and edge.support_status == "supported":
                ev = self.evidence_anchors.get(edge.evidence_id)
                results.append({
                    "type": "evidence_support",
                    "evidence_id": edge.evidence_id,
                    "anchor_type": ev.anchor_type if ev else None,
                    "locator": ev.locator if ev else None,
                    "excerpt": ev.excerpt if ev else None,
                    "receipt_ref": edge.receipt_ref.to_dict() if edge.receipt_ref else (ev.receipt_ref.to_dict() if ev and ev.receipt_ref else None),
                })

        for edge in self.claim_relations:
            if edge.target_claim_id == cid and edge.relation_type == "corroborates":
                c = self.claims.get(edge.source_claim_id)
                results.append({
                    "type": "claim_corroboration",
                    "source_claim_id": edge.source_claim_id,
                    "relation_type": edge.relation_type,
                    "text": c.text if c else None,
                    "locator": c.locator if c else None,
                })

        results.sort(key=lambda x: (x["type"], x.get("evidence_id") or x.get("source_claim_id") or ""))
        return results

    def find_contradictions(self, claim_id: str) -> List[Dict[str, Any]]:
        """Deterministic retrieval of directly contradictory claims and refuting evidence anchors."""
        cid = str(claim_id).strip()
        contradictions: List[Dict[str, Any]] = []

        seen_conflicts: Set[str] = set()
        for edge in self.claim_relations:
            if (edge.target_claim_id == cid or edge.source_claim_id == cid) and edge.relation_type == "contradicts":
                other_id = edge.source_claim_id if edge.target_claim_id == cid else edge.target_claim_id
                if other_id in seen_conflicts:
                    continue
                seen_conflicts.add(other_id)
                other_claim = self.claims.get(other_id)
                contradictions.append({
                    "contradiction_mode": "claim_conflict",
                    "conflicting_claim_id": other_id,
                    "text": other_claim.text if other_claim else None,
                    "locator": other_claim.locator if other_claim else None,
                    "evidence_refs": list(edge.evidence_refs),
                })

        for edge in self.support_edges:
            if edge.claim_id == cid and edge.support_status == "contradicted":
                ev = self.evidence_anchors.get(edge.evidence_id)
                contradictions.append({
                    "contradiction_mode": "evidence_refutation",
                    "evidence_id": edge.evidence_id,
                    "anchor_type": ev.anchor_type if ev else None,
                    "locator": ev.locator if ev else None,
                    "excerpt": ev.excerpt if ev else None,
                    "receipt_ref": edge.receipt_ref.to_dict() if edge.receipt_ref else (ev.receipt_ref.to_dict() if ev and ev.receipt_ref else None),
                })

        contradictions.sort(key=lambda x: (x["contradiction_mode"], x.get("conflicting_claim_id") or x.get("evidence_id") or ""))
        return contradictions

    def trace_claim_provenance(
        self,
        claim_id: str,
        receipt_registry: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Deterministically trace from a high-level Claim through EvidenceAnchors to registered LineageReceipts.

        Injected external registries cannot override verified internal receipts.
        Every consumed receipt is strictly re-validated against lineage-receipt-1.0 contract.
        """
        cid = str(claim_id).strip()
        reg = dict(self._receipt_registry)
        if receipt_registry:
            for k, v in receipt_registry.items():
                if k in self._receipt_registry:
                    existing = self._receipt_registry[k]
                    ex_dict = existing.to_dict() if hasattr(existing, "to_dict") else existing
                    new_dict = v.to_dict() if hasattr(v, "to_dict") else v
                    if ex_dict != new_dict:
                        raise ValueError(f"Conflicting receipt_registry injected for {k!r}: cannot override verified internal receipt.")
                reg[k] = copy.deepcopy(v)

        if cid not in self.claims:
            return {
                "status": "unavailable",
                "reason": f"Claim {cid!r} not found in graph",
                "claim_id": cid,
            }

        target_claim = self.claims[cid]
        claim_support_edges = [e for e in self.support_edges if e.claim_id == cid]

        lineage_traces: List[Dict[str, Any]] = []
        for edge in claim_support_edges:
            ev = self.evidence_anchors.get(edge.evidence_id)
            ref = edge.receipt_ref or (ev.receipt_ref if ev else None)
            if ref and ref.kind == "lineage":
                rid = ref.receipt_id
                if not rid or rid not in reg:
                    lineage_traces.append({
                        "evidence_id": edge.evidence_id,
                        "support_status": edge.support_status,
                        "receipt_id": rid,
                        "status": "unavailable",
                        "reason": f"LineageReceipt {rid!r} not found in registry",
                    })
                    continue

                receipt_obj = reg[rid]
                ok, err_msg = validate_lineage_receipt_contract(ref, receipt_obj)
                if not ok:
                    lineage_traces.append({
                        "evidence_id": edge.evidence_id,
                        "support_status": edge.support_status,
                        "receipt_id": rid,
                        "status": "invalid_receipt",
                        "reason": err_msg,
                    })
                    continue

                r_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
                lineage_traces.append({
                    "evidence_id": edge.evidence_id,
                    "support_status": edge.support_status,
                    "receipt_id": rid,
                    "status": "available",
                    "verification_status": r_dict.get("verification_status"),
                    "topology_status": r_dict.get("topology_status"),
                    "content_verification": r_dict.get("content_verification"),
                    "root_ancestors": r_dict.get("root_ancestors", []),
                    "trace_steps": r_dict.get("trace_steps", []),
                })

        return {
            "status": "traced",
            "claim_id": cid,
            "claim_text": target_claim.text,
            "claim_digest": target_claim.claim_digest,
            "connected_evidence_count": len(claim_support_edges),
            "lineage_traces": lineage_traces,
        }

    def extract_uncertainties(self) -> List[UncertaintyItem]:
        """Systematically extract uncertainty items under explicit three-state discipline with deterministic IDs."""
        raw_items: List[Tuple[str, str, str, bool]] = []

        # 1. Unverifiable claims
        for edge in self.support_edges:
            if edge.support_status == "unverifiable":
                raw_items.append((
                    edge.claim_id,
                    "unverifiable_claim",
                    f"Evidence {edge.evidence_id!r} support for claim {edge.claim_id!r} is unobservable/unverifiable.",
                    False,
                ))

        # 2. Contradictions
        for edge in self.claim_relations:
            if edge.relation_type == "contradicts":
                raw_items.append((
                    edge.target_claim_id,
                    "unresolved_contradiction",
                    f"Claim {edge.source_claim_id!r} contradicts claim {edge.target_claim_id!r}.",
                    True,
                ))

        for edge in self.support_edges:
            if edge.support_status == "contradicted":
                raw_items.append((
                    edge.claim_id,
                    "unresolved_contradiction",
                    f"Evidence {edge.evidence_id!r} refutes claim {edge.claim_id!r}.",
                    True,
                ))

        # 3. Missing referenced receipts in registry
        all_refs: List[Tuple[str, ReceiptRef]] = []
        for eid, ev in self.evidence_anchors.items():
            if ev.receipt_ref:
                all_refs.append((eid, ev.receipt_ref))
        for edge in self.support_edges:
            if edge.receipt_ref:
                all_refs.append((edge.evidence_id, edge.receipt_ref))

        for subj_id, ref in all_refs:
            found = False
            if ref.kind == "lineage" and ref.receipt_id:
                if ref.receipt_id in self._receipt_registry:
                    found = True
            elif ref.kind == "academic_evidence" and ref.payload_sha256:
                if ref.payload_sha256 in self._receipt_registry:
                    found = True
                else:
                    for reg_v in self._receipt_registry.values():
                        val_dict = reg_v if isinstance(reg_v, dict) else (reg_v.to_dict() if hasattr(reg_v, "to_dict") else {})
                        if canonical_academic_receipt_payload_sha256(val_dict) == ref.payload_sha256:
                            found = True
                            break
            if not found:
                ident = ref.receipt_id or ref.payload_sha256 or "unidentified"
                raw_items.append((
                    subj_id,
                    "missing_receipt",
                    f"Referenced {ref.kind} receipt {ident!r} is not loaded in local receipt registry.",
                    False,
                ))

        unique_raw = sorted(list(set(raw_items)), key=lambda x: (x[1], x[0], x[2]))
        items: List[UncertaintyItem] = []
        for subject_id, kind, reason, needs_human in unique_raw:
            unc_key = json.dumps({
                "kind": kind,
                "needs_human": needs_human,
                "reason": reason,
                "subject_id": subject_id,
            }, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            unc_digest = hashlib.sha256(unc_key.encode("utf-8")).hexdigest()[:16]
            items.append(UncertaintyItem(
                item_id=f"unc-{unc_digest}",
                subject_id=subject_id,
                kind=kind,
                reason=reason,
                needs_human=needs_human,
            ))

        items.sort(key=lambda x: x.item_id)
        return items

    def graph_digest(self) -> str:
        """Compute canonical, content-addressed SHA256 digest invariant to node/edge insertion orders."""
        canon_claims = sorted([c.to_dict() for c in self.claims.values()], key=lambda x: x["id"])
        canon_evidence = sorted([e.to_dict() for e in self.evidence_anchors.values()], key=lambda x: x["id"])
        canon_support = sorted(
            [e.to_dict() for e in self.support_edges],
            key=lambda x: canonical_support_edge_tuple(EvidenceSupportEdge(
                evidence_id=x["evidence_id"],
                claim_id=x["claim_id"],
                support_status=x["support_status"],
                receipt_ref=ReceiptRef(**x["receipt_ref"]) if x.get("receipt_ref") else None,
                metadata=FrozenDict(x.get("metadata", {})),
            )),
        )
        canon_relations = sorted(
            [e.to_dict() for e in self.claim_relations],
            key=lambda x: canonical_claim_relation_tuple(ClaimRelationEdge(
                source_claim_id=x["source_claim_id"],
                target_claim_id=x["target_claim_id"],
                relation_type=x["relation_type"],
                evidence_refs=tuple(x.get("evidence_refs", [])),
                metadata=FrozenDict(x.get("metadata", {})),
            )),
        )
        canon_uncertainties = sorted([u.to_dict() for u in self.extract_uncertainties()], key=lambda x: x["item_id"])

        payload = {
            "protocol": "claim-evidence-graph-1.0",
            "graph_id": self.graph_id,
            "claims": canon_claims,
            "evidence_anchors": canon_evidence,
            "support_edges": canon_support,
            "claim_relations": canon_relations,
            "uncertainties": canon_uncertainties,
        }
        canon_bytes = json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(canon_bytes).hexdigest().lower()

    def to_dict(self) -> Dict[str, Any]:
        """Deepcopy and serialize strictly matching schemas/claim-evidence-graph.schema.json."""
        canon_claims = sorted([c.to_dict() for c in self.claims.values()], key=lambda x: x["id"])
        canon_evidence = sorted([e.to_dict() for e in self.evidence_anchors.values()], key=lambda x: x["id"])
        canon_support = sorted(
            [e.to_dict() for e in self.support_edges],
            key=lambda x: canonical_support_edge_tuple(EvidenceSupportEdge(
                evidence_id=x["evidence_id"],
                claim_id=x["claim_id"],
                support_status=x["support_status"],
                receipt_ref=ReceiptRef(**x["receipt_ref"]) if x.get("receipt_ref") else None,
                metadata=FrozenDict(x.get("metadata", {})),
            )),
        )
        canon_relations = sorted(
            [e.to_dict() for e in self.claim_relations],
            key=lambda x: canonical_claim_relation_tuple(ClaimRelationEdge(
                source_claim_id=x["source_claim_id"],
                target_claim_id=x["target_claim_id"],
                relation_type=x["relation_type"],
                evidence_refs=tuple(x.get("evidence_refs", [])),
                metadata=FrozenDict(x.get("metadata", {})),
            )),
        )
        canon_uncertainties = sorted([u.to_dict() for u in self.extract_uncertainties()], key=lambda x: x["item_id"])

        return {
            "protocol": "claim-evidence-graph-1.0",
            "graph_id": self.graph_id,
            "graph_digest": self.graph_digest(),
            "claims": [copy.deepcopy(c) for c in canon_claims],
            "evidence_anchors": [copy.deepcopy(e) for e in canon_evidence],
            "support_edges": [copy.deepcopy(s) for s in canon_support],
            "claim_relations": [copy.deepcopy(r) for r in canon_relations],
            "uncertainties": [copy.deepcopy(u) for u in canon_uncertainties],
        }

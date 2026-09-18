# -*- coding: utf-8 -*-
"""Claim-Evidence Graph Kernel v1.

Deterministic, content-addressed scientific assertion and evidence graph.
Directly consumes ResearchObject, AcademicEvidenceReceipt, and LineageReceipt.

Core Invariants:
1. Separation of causal provenance DAG from semantic assertion graph:
   Semantic relation cycles (e.g. A contradicts B and B contradicts A) are valid and preserved.
2. Rejection of Truth Authority and subjective scores:
   No artificial confidence scores (e.g. 0.85); discrete verdicts and explicit uncertainty queue.
3. Strongly typed ReceiptRef:
   Unambiguous binding to LineageReceipt (receipt_id/digest) and AcademicEvidenceReceipt (claim_digest/payload).
4. Lexical canonicalization only:
   NFC normalization and whitespace compaction; never rewrites or paraphrases claim text.
5. Deterministic, offline graph traversals:
   Zero LLM, zero network, zero hidden runtime singletons; explicit receipt registry injection.
6. Order-invariant graph digest:
   Full canonical sorting across nodes and edges with allow_nan=False.
"""
from __future__ import annotations

import collections
import copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

__all__ = [
    "ReceiptRef",
    "Claim",
    "EvidenceAnchor",
    "EvidenceSupportEdge",
    "ClaimRelationEdge",
    "UncertaintyItem",
    "ClaimEvidenceGraph",
    "canonical_claim_text",
    "compute_claim_digest",
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

VALID_UNCERTAINTY_KINDS: Set[str] = {
    "unverifiable_claim",
    "unresolved_contradiction",
    "missing_receipt",
    "ambiguous_locator",
    "generic_uncertainty",
}

SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")


def canonical_claim_text(text: str) -> str:
    """Normalize claim text via Unicode NFC and whitespace compaction without paraphrasing."""
    if not text:
        return ""
    # 1. Unicode NFC normalization
    norm = unicodedata.normalize("NFC", str(text))
    # 2. Normalize line breaks and compact whitespace
    norm = re.sub(r"[\r\n\t]+", " ", norm)
    norm = re.sub(r"\s+", " ", norm).strip()
    return norm


def compute_claim_digest(text: str, target_work_id: Optional[str] = None, locator: Optional[str] = None, claim_type: str = "empirical_finding") -> str:
    """Compute content-addressed SHA256 digest identifying a specific claim occurrence."""
    norm_txt = canonical_claim_text(text)
    payload = f"{norm_txt}|{target_work_id or ''}|{locator or ''}|{claim_type}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest().lower()


@dataclass
class ReceiptRef:
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
        if self.receipt_digest is not None:
            self.receipt_digest = self.receipt_digest.strip().lower()
            if not SHA256_REGEX.match(self.receipt_digest):
                raise ValueError(f"Invalid receipt_digest SHA256: {self.receipt_digest!r}")
        if self.claim_digest is not None:
            self.claim_digest = self.claim_digest.strip().lower()
            if not SHA256_REGEX.match(self.claim_digest):
                raise ValueError(f"Invalid claim_digest SHA256: {self.claim_digest!r}")
        if self.payload_sha256 is not None:
            self.payload_sha256 = self.payload_sha256.strip().lower()
            if not SHA256_REGEX.match(self.payload_sha256):
                raise ValueError(f"Invalid payload_sha256 SHA256: {self.payload_sha256!r}")

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


@dataclass
class Claim:
    id: str
    text: str
    target_work_id: Optional[str] = None
    locator: Optional[str] = None
    claim_type: str = "empirical_finding"
    entities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    normalized_text: str = field(init=False)
    claim_digest: str = field(init=False)

    def __post_init__(self):
        if self.claim_type not in VALID_CLAIM_TYPES:
            raise ValueError(f"Invalid claim_type: {self.claim_type!r}. Must be one of {sorted(VALID_CLAIM_TYPES)}")
        self.normalized_text = canonical_claim_text(self.text)
        self.claim_digest = compute_claim_digest(
            text=self.normalized_text,
            target_work_id=self.target_work_id,
            locator=self.locator,
            claim_type=self.claim_type,
        )
        self.entities = sorted(list(set(self.entities)))
        self.metadata = copy.deepcopy(self.metadata)

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
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


@dataclass
class EvidenceAnchor:
    id: str
    anchor_type: str
    source_work_id: Optional[str] = None
    locator: Optional[str] = None
    receipt_ref: Optional[ReceiptRef] = None
    content_sha256: Optional[str] = None
    excerpt: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.anchor_type not in VALID_ANCHOR_TYPES:
            raise ValueError(f"Invalid anchor_type: {self.anchor_type!r}. Must be one of {sorted(VALID_ANCHOR_TYPES)}")
        if self.content_sha256 is not None:
            self.content_sha256 = self.content_sha256.strip().lower()
            if not SHA256_REGEX.match(self.content_sha256):
                raise ValueError(f"Invalid content_sha256 format: {self.content_sha256!r}")
        self.metadata = copy.deepcopy(self.metadata)

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
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


@dataclass
class EvidenceSupportEdge:
    evidence_id: str
    claim_id: str
    support_status: str
    receipt_ref: Optional[ReceiptRef] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.support_status not in VALID_SUPPORT_STATUSES:
            raise ValueError(f"Invalid support_status: {self.support_status!r}. Must be one of {sorted(VALID_SUPPORT_STATUSES)}")
        self.metadata = copy.deepcopy(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "support_status": self.support_status,
        }
        if self.receipt_ref:
            d["receipt_ref"] = self.receipt_ref.to_dict()
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


@dataclass
class ClaimRelationEdge:
    source_claim_id: str
    target_claim_id: str
    relation_type: str
    evidence_refs: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.relation_type not in VALID_CLAIM_RELATIONS:
            raise ValueError(f"Invalid relation_type: {self.relation_type!r}. Must be one of {sorted(VALID_CLAIM_RELATIONS)}")
        self.evidence_refs = sorted(list(set(self.evidence_refs)))
        self.metadata = copy.deepcopy(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "source_claim_id": self.source_claim_id,
            "target_claim_id": self.target_claim_id,
            "relation_type": self.relation_type,
        }
        if self.evidence_refs:
            d["evidence_refs"] = list(self.evidence_refs)
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


@dataclass
class UncertaintyItem:
    item_id: str
    subject_id: str
    kind: str
    reason: str
    needs_human: bool
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.kind not in VALID_UNCERTAINTY_KINDS:
            raise ValueError(f"Invalid uncertainty kind: {self.kind!r}. Must be one of {sorted(VALID_UNCERTAINTY_KINDS)}")
        self.metadata = copy.deepcopy(self.metadata)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "item_id": self.item_id,
            "subject_id": self.subject_id,
            "kind": self.kind,
            "reason": self.reason,
            "needs_human": self.needs_human,
        }
        if self.metadata:
            d["metadata"] = copy.deepcopy(self.metadata)
        return d


class ClaimEvidenceGraph:
    """Deterministic scientific assertion and evidence graph container."""

    def __init__(self, graph_id: str = "ceg-default"):
        self.graph_id: str = str(graph_id).strip()
        self.claims: Dict[str, Claim] = {}
        self.evidence_anchors: Dict[str, EvidenceAnchor] = {}
        self.support_edges: List[EvidenceSupportEdge] = []
        self.claim_relations: List[ClaimRelationEdge] = []
        self.uncertainties: List[UncertaintyItem] = []
        self._all_node_ids: Dict[str, str] = {}  # id -> "claim" | "evidence"
        self._support_edge_keys: Set[Tuple[str, str, str, str]] = set()
        self._claim_relation_keys: Set[Tuple[str, str, str, str]] = set()
        self._receipt_registry: Dict[str, Any] = {}

    def register_receipt(self, receipt_id: str, receipt_data: Any):
        """Register an AcademicEvidenceReceipt or LineageReceipt for offline provenance traversal."""
        rid = str(receipt_id).strip()
        self._receipt_registry[rid] = receipt_data

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
            entities=entities or [],
            metadata=metadata or {},
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
            metadata=metadata or {},
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
            metadata=metadata or {},
        )
        meta_json = json.dumps(edge.metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        k = (eid, cid, support_status, meta_json)
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
            evidence_refs=evidence_refs or [],
            metadata=metadata or {},
        )
        meta_json = json.dumps(edge.metadata, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        ev_key = ",".join(edge.evidence_refs)
        k = (sid, tid, relation_type, f"{ev_key}#{meta_json}")
        if k not in self._claim_relation_keys:
            self._claim_relation_keys.add(k)
            self.claim_relations.append(edge)
        return edge

    def validate_graph(self) -> Tuple[bool, List[str]]:
        """Strict structural integrity validation (allows semantic cycles; rejects dangling edges and receipt mismatches)."""
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

        # 3. Receipt reference integrity
        for eid, ev in self.evidence_anchors.items():
            if ev.receipt_ref:
                ref = ev.receipt_ref
                if ref.receipt_id and ref.receipt_id in self._receipt_registry:
                    registered = self._receipt_registry[ref.receipt_id]
                    # Verify receipt_digest if provided
                    if ref.receipt_digest:
                        reg_digest = getattr(registered, "receipt_digest", None)
                        if isinstance(registered, dict):
                            reg_digest = registered.get("receipt_digest")
                        if reg_digest and reg_digest.lower() != ref.receipt_digest.lower():
                            errors.append(f"Receipt digest mismatch for evidence {eid!r}: expected {ref.receipt_digest}, got {reg_digest}")

        return (len(errors) == 0, errors)

    def find_support(self, claim_id: str) -> List[Dict[str, Any]]:
        """Deterministic retrieval of supporting evidence anchors and corroborating claims."""
        cid = str(claim_id).strip()
        results: List[Dict[str, Any]] = []

        # 1. Evidence anchors with support_status == 'supported'
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

        # 2. Corroborating claims
        for edge in self.claim_relations:
            if edge.target_claim_id == cid and edge.relation_type in ("corroborates", "refines"):
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

        # 1. Direct ClaimRelationEdge with relation_type == 'contradicts'
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

        # 2. EvidenceSupportEdge with support_status == 'contradicted'
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

        Retrieves claimed raw data inputs and execution pipeline steps without hidden runtimes.
        """
        cid = str(claim_id).strip()
        reg = dict(self._receipt_registry)
        if receipt_registry:
            reg.update(receipt_registry)

        if cid not in self.claims:
            return {
                "status": "unavailable",
                "reason": f"Claim {cid!r} not found in graph",
                "claim_id": cid,
            }

        target_claim = self.claims[cid]
        anchors_in_claim = [
            self.evidence_anchors[e.evidence_id]
            for e in self.support_edges
            if e.claim_id == cid and e.evidence_id in self.evidence_anchors
        ]

        lineage_traces: List[Dict[str, Any]] = []
        for anc in anchors_in_claim:
            if anc.receipt_ref and anc.receipt_ref.kind == "lineage":
                rid = anc.receipt_ref.receipt_id
                if not rid or rid not in reg:
                    lineage_traces.append({
                        "evidence_id": anc.id,
                        "receipt_id": rid,
                        "status": "unavailable",
                        "reason": f"LineageReceipt {rid!r} not found in registry",
                    })
                    continue

                receipt_obj = reg[rid]
                r_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
                lineage_traces.append({
                    "evidence_id": anc.id,
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
            "connected_evidence_count": len(anchors_in_claim),
            "lineage_traces": lineage_traces,
        }

    def extract_uncertainties(self) -> List[UncertaintyItem]:
        """Systematically extract uncertainty items under explicit three-state discipline."""
        items: List[UncertaintyItem] = []
        uid_seq = 1

        # 1. Unverifiable claims (machine-unobservable != human-required; needs_human=False)
        for edge in self.support_edges:
            if edge.support_status == "unverifiable":
                items.append(UncertaintyItem(
                    item_id=f"unc-{uid_seq:04d}",
                    subject_id=edge.claim_id,
                    kind="unverifiable_claim",
                    reason=f"Evidence {edge.evidence_id!r} support for claim {edge.claim_id!r} is unobservable/unverifiable.",
                    needs_human=False,
                ))
                uid_seq += 1

        # 2. Contradictions (direct conflict requires reviewer/human arbitration; needs_human=True)
        for edge in self.claim_relations:
            if edge.relation_type == "contradicts":
                items.append(UncertaintyItem(
                    item_id=f"unc-{uid_seq:04d}",
                    subject_id=edge.target_claim_id,
                    kind="unresolved_contradiction",
                    reason=f"Claim {edge.source_claim_id!r} contradicts claim {edge.target_claim_id!r}.",
                    needs_human=True,
                ))
                uid_seq += 1

        for edge in self.support_edges:
            if edge.support_status == "contradicted":
                items.append(UncertaintyItem(
                    item_id=f"unc-{uid_seq:04d}",
                    subject_id=edge.claim_id,
                    kind="unresolved_contradiction",
                    reason=f"Evidence {edge.evidence_id!r} refutes claim {edge.claim_id!r}.",
                    needs_human=True,
                ))
                uid_seq += 1

        items.sort(key=lambda x: (x.kind, x.subject_id, x.item_id))
        return items

    def graph_digest(self) -> str:
        """Compute canonical, content-addressed SHA256 digest invariant to node/edge insertion orders."""
        canon_claims = sorted([c.to_dict() for c in self.claims.values()], key=lambda x: x["id"])
        canon_evidence = sorted([e.to_dict() for e in self.evidence_anchors.values()], key=lambda x: x["id"])
        canon_support = sorted(
            [e.to_dict() for e in self.support_edges],
            key=lambda x: (x["evidence_id"], x["claim_id"], x["support_status"]),
        )
        canon_relations = sorted(
            [e.to_dict() for e in self.claim_relations],
            key=lambda x: (x["source_claim_id"], x["target_claim_id"], x["relation_type"]),
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
            key=lambda x: (x["evidence_id"], x["claim_id"], x["support_status"]),
        )
        canon_relations = sorted(
            [e.to_dict() for e in self.claim_relations],
            key=lambda x: (x["source_claim_id"], x["target_claim_id"], x["relation_type"]),
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

"""Deterministic Adapters for 13 scholarly skills into the research-state kernel."""

from __future__ import annotations

from abc import ABC, abstractmethod
import collections.abc
import copy
import re
import unicodedata
from typing import Any, Dict, List, Mapping, Optional, Tuple, Set

from shared_contracts.evidence import (
    ReceiptRef,
    _thaw_val,
    canonical_academic_receipt_payload_sha256,
    canonical_evidence_claim_digest,
    canonical_json_bytes,
    canonical_text,
    compute_sha256,
    validate_academic_receipt_contract,
    validate_lineage_receipt_contract,
    validate_lineage_receipt_integrity,
)
from .models import ArtifactEnvelope, IngestionKernelState, IngestionReceipt


_DOMAIN_DERIVED_UNCERTAINTY_KINDS = {
    "unverifiable_claim",
    "unresolved_contradiction",
    "missing_receipt",
    "ambiguous_locator",
    "decision_without_basis",
    "unsupported_negative_result",
    "unsupported_pruning",
    "unevidenced_claim_basis",
}


def _canonical_item_set(items: List[Mapping[str, Any]]) -> Set[bytes]:
    return {canonical_json_bytes(item) for item in items}


def _snapshot_fast_forwards(
    current: Mapping[str, Any],
    incoming: Mapping[str, Any],
    collection_fields: Tuple[str, ...],
) -> bool:
    """Return whether an incoming canonical snapshot only appends state."""
    return all(
        _canonical_item_set(list(current.get(field, [])))
        <= _canonical_item_set(list(incoming.get(field, [])))
        for field in collection_fields
    )


def _compute_ceg_claim_digest(
    text: str,
    target_work_id: Optional[str],
    locator: Optional[str],
    claim_type: str = "empirical_finding",
) -> str:
    """Mirror the CEG semantic claim-identity contract without evidence fields."""
    normalised_text = unicodedata.normalize("NFC", str(text or ""))
    normalised_text = re.sub(r"[\r\n\t]+", " ", normalised_text)
    normalised_text = re.sub(r"\s+", " ", normalised_text).strip()
    return compute_sha256(canonical_json_bytes({
        "claim_type": claim_type,
        "locator": locator or "",
        "target_work_id": target_work_id or "",
        "text": normalised_text,
    }))


def _domain_derived_uncertainties(
    state: IngestionKernelState,
) -> List[Dict[str, Any]]:
    """Return the current CEG/Ledger uncertainty projection with ownership tags."""
    derived: List[Any] = []
    if state.ceg is not None:
        derived.extend(state.ceg.extract_uncertainties())
    if state.ledger is not None:
        derived.extend(state.ledger.export_uncertainties())

    values: List[Dict[str, Any]] = []
    for item in derived:
        raw = item.to_dict() if hasattr(item, "to_dict") else _thaw_val(item)
        raw = copy.deepcopy(raw)
        metadata = dict(raw.get("metadata") or {})
        metadata["kernel_origin"] = "domain_derived"
        raw["metadata"] = metadata
        values.append(raw)
    return values


class IngestionPlan:
    """Pre-computed, side-effect-free plan of mutations to be applied to the kernel."""

    def __init__(
        self,
        envelope: ArtifactEnvelope,
        adapter_id: str,
        adapter_version: str,
        valid: bool,
        errors: List[str],
    ):
        self.envelope = envelope
        self.adapter_id = adapter_id
        self.adapter_version = adapter_version
        self.valid = valid
        self.errors = list(errors)
        self.created_objects: Dict[str, Dict[str, Any]] = {}
        self.ceg_claims: List[Dict[str, Any]] = []
        self.ceg_evidences: List[Dict[str, Any]] = []
        self.ceg_edges: List[Dict[str, Any]] = []
        self.ceg_relations: List[Dict[str, Any]] = []
        self.ledger_decisions: List[Dict[str, Any]] = []
        self.ledger_bases: List[Dict[str, Any]] = []
        self.ledger_forks: List[Dict[str, Any]] = []
        self.ledger_state_events: List[Dict[str, Any]] = []
        self.ledger_outcome_corrections: List[Dict[str, Any]] = []
        self.uncertainties: List[Dict[str, Any]] = []
        self.ignored_fields: List[str] = []
        self.registered_receipts: Dict[str, Any] = {}
        self.ceg_snapshot: Any = None
        self.ledger_snapshot: Any = None

    def has_ceg_mutations(self) -> bool:
        return bool(
            self.ceg_snapshot is not None
            or self.ceg_claims
            or self.ceg_evidences
            or self.ceg_edges
            or self.ceg_relations
        )

    def has_ledger_mutations(self) -> bool:
        return bool(
            self.ledger_snapshot is not None
            or self.ledger_decisions
            or self.ledger_bases
            or self.ledger_forks
            or self.ledger_state_events
            or self.ledger_outcome_corrections
        )


class BaseArtifactAdapter(ABC):
    """Abstract base class for deterministic scholarly artifact adapters."""

    adapter_id: str
    adapter_version: str
    accepted_producers: Set[str]
    accepted_schemas: Set[str]
    is_lossless: bool
    tier: int  # 1 = native receipt, 2 = structured artifact, 3 = opaque artifact
    accepted_binding_fields: Set[str] = set()
    required_binding_fields: Set[str] = set()

    def normalize_bindings(
        self,
        bindings: Optional[Mapping[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Validate and canonicalise only fields that can affect this adapter."""
        if bindings is None:
            return None
        if not isinstance(bindings, collections.abc.Mapping):
            raise TypeError("bindings must be a mapping or None")
        values = _thaw_val(bindings)
        if not values:
            return None
        unknown = set(values) - self.accepted_binding_fields
        if unknown:
            raise ValueError(
                f"Unsupported binding fields for {self.adapter_id}: {sorted(unknown)}"
            )
        missing = self.required_binding_fields - set(values)
        if missing:
            raise ValueError(
                f"Missing required binding fields for {self.adapter_id}: {sorted(missing)}"
            )
        return {key: values[key] for key in sorted(values)}

    @abstractmethod
    def probe(self, envelope: ArtifactEnvelope) -> bool:
        """Return True if this adapter can ingest the given envelope."""
        pass

    @abstractmethod
    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        """Validate structural compliance and cryptographic signatures of the payload."""
        pass

    @abstractmethod
    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        """Generate a side-effect-free mutation plan."""
        pass

    def apply(self, plan: IngestionPlan, state: IngestionKernelState) -> IngestionReceipt:
        """Apply a validated mutation plan to the kernel state atomically."""
        if not plan.valid:
            return IngestionReceipt.create(
                envelope=plan.envelope,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                status="rejected",
                valid=False,
                errors=plan.errors,
                output_digests=state.compute_digests(),
                failure_reason="; ".join(plan.errors),
                caller_metadata=plan.envelope.caller_metadata,
            )

        if plan.has_ceg_mutations() and state.ceg is None:
            raise ValueError(
                f"Adapter {self.adapter_id} requires a ClaimEvidenceGraph target; "
                "refusing an accepted no-op"
            )
        if plan.has_ledger_mutations() and state.ledger is None:
            raise ValueError(
                f"Adapter {self.adapter_id} requires a DecisionLedger target; "
                "refusing an accepted no-op"
            )

        uncertainty_ids_before = {value["item_id"] for value in state.uncertainties}
        derived_before = _domain_derived_uncertainties(state)
        managed_derived_ids = {item["item_id"] for item in derived_before}
        managed_derived_ids.update(
            value["item_id"]
            for value in state.uncertainties
            if (
                value["kind"] in _DOMAIN_DERIVED_UNCERTAINTY_KINDS
                or value.get("metadata", {}).get("kernel_origin") == "domain_derived"
            )
        )

        # 1. Apply Research Objects with fail-closed collision defense
        for obj_id, obj_data in plan.created_objects.items():
            state.register_object(obj_id, obj_data)

        # 2. Apply registered receipts
        for r_key, r_obj in plan.registered_receipts.items():
            state.register_receipt(r_key, r_obj)

        # 3. Apply CEG nodes, edges, and relations
        created_ceg_nodes = []
        created_ceg_edges = []
        if plan.ceg_snapshot is not None:
            state.ceg = copy.deepcopy(plan.ceg_snapshot)
            state._synchronise_receipts()
            created_ceg_nodes.extend(sorted(state.ceg.claims))
            created_ceg_nodes.extend(sorted(state.ceg.evidence_anchors))
            created_ceg_edges.extend(
                f"{edge.evidence_id}->{edge.claim_id}" for edge in state.ceg.support_edges
            )
        if state.ceg is not None:
            for c in plan.ceg_claims:
                state.ceg.add_claim(
                    id=c["id"],
                    text=c["text"],
                    target_work_id=c.get("target_work_id"),
                    locator=c.get("locator"),
                    claim_type=c.get("claim_type", "empirical_finding"),
                    entities=c.get("entities", ()),
                    metadata=c.get("metadata"),
                )
                created_ceg_nodes.append(c["id"])

            for ev in plan.ceg_evidences:
                state.ceg.add_evidence(
                    id=ev["id"],
                    anchor_type=ev["anchor_type"],
                    source_work_id=ev.get("source_work_id") or ev.get("target_work_id"),
                    locator=ev.get("locator"),
                    receipt_ref=ev.get("receipt_ref"),
                    content_sha256=ev.get("content_sha256"),
                    excerpt=ev.get("excerpt"),
                    metadata=ev.get("metadata"),
                )
                created_ceg_nodes.append(ev["id"])

            for edge in plan.ceg_edges:
                meta = {"rationale": edge["rationale"]} if "rationale" in edge else edge.get("metadata")
                edge_obj = state.ceg.add_support_edge(
                    evidence_id=edge["evidence_id"],
                    claim_id=edge["claim_id"],
                    support_status=edge["support_status"],
                    receipt_ref=edge.get("receipt_ref"),
                    metadata=meta,
                )
                created_ceg_edges.append(f"{edge['evidence_id']}->{edge['claim_id']}")

            for r in getattr(plan, "ceg_relations", []):
                state.ceg.add_claim_relation(
                    source_claim_id=r["source_claim_id"],
                    target_claim_id=r["target_claim_id"],
                    relation_type=r.get("relation_type") or r.get("relation_kind", "corroborates"),
                    evidence_refs=tuple(r.get("evidence_refs", ())),
                    metadata=r.get("metadata"),
                )

        # 4. Apply Ledger decisions, bases, forks, state events, and corrections
        applied_ledger_bindings = []
        if plan.ledger_snapshot is not None:
            state.ledger = copy.deepcopy(plan.ledger_snapshot)
            state._synchronise_receipts()
            for basis in state.ledger.to_dict().get("bases", []):
                applied_ledger_bindings.append({
                    "decision_id": basis["decision_id"],
                    "binding_kind": basis["basis_kind"],
                    "basis_id": basis["basis_id"],
                })
        if state.ledger is not None:
            for dec in plan.ledger_decisions:
                state.ledger.add_decision(
                    id=dec["id"],
                    title=dec["title"],
                    decision_type=dec.get("decision_type") or dec.get("decision_action") or ("negative_result" if dec.get("entry_kind") == "negative_result" else "explore"),
                    entry_kind=dec.get("entry_kind", "decision"),
                    decision_action=dec.get("decision_action"),
                    context_work_id=dec.get("context_work_id"),
                    locator=dec.get("locator"),
                    metadata=dec.get("metadata") or {},
                )

            for b in plan.ledger_bases:
                state.ledger.add_basis(
                    decision_id=b["decision_id"],
                    basis_kind=b["basis_kind"],
                    basis_id=b["basis_id"],
                    receipt_ref=b.get("receipt_ref"),
                    metadata=b.get("metadata") or {},
                )
                applied_ledger_bindings.append({
                    "decision_id": b["decision_id"],
                    "binding_kind": b["basis_kind"],
                    "basis_id": b["basis_id"],
                })

            for f in getattr(plan, "ledger_forks", []):
                ref = f.get("receipt_ref")
                f_ref = ReceiptRef(**ref) if isinstance(ref, dict) else ref
                state.ledger.add_fork(
                    decision_id=f["decision_id"],
                    alternative_id=f["alternative_id"],
                    relation=f.get("relation", "considered"),
                    receipt_ref=f_ref,
                    metadata=f.get("metadata") or {},
                )

            for ev in getattr(plan, "ledger_state_events", []):
                ref = ev.get("receipt_ref")
                ev_ref = ReceiptRef(**ref) if isinstance(ref, dict) else ref
                state.ledger.add_state_event(
                    decision_id=ev["decision_id"],
                    to_state=ev["to_state"],
                    reason=ev.get("reason"),
                    caused_by=ev.get("caused_by"),
                    alternative_ref=ev.get("alternative_ref"),
                    receipt_ref=ev_ref,
                    metadata=ev.get("metadata") or {},
                )

            for corr in getattr(plan, "ledger_outcome_corrections", []):
                ref = corr.get("receipt_ref")
                c_ref = ReceiptRef(**ref) if isinstance(ref, dict) else ref
                corr_res = state.ledger.add_outcome_correction(
                    decision_id=corr["decision_id"],
                    verdict=corr["verdict"],
                    rationale=corr["rationale"],
                    receipt_ref=c_ref,
                    locator=corr.get("locator"),
                    metadata=corr.get("metadata") or {},
                )
                applied_ledger_bindings.append({
                    "decision_id": corr["decision_id"],
                    "binding_kind": "outcome_correction",
                    "basis_id": corr_res.correction_id,
                })

        # 5. Synchronise the domain-derived projection while retaining
        # adapter-declared uncertainties as append-only observations.
        receipt_uncertainties: List[Dict[str, Any]] = []
        receipt_uncertainty_ids: Set[str] = set()

        derived_uncertainties = _domain_derived_uncertainties(state)
        current_derived_ids = {item["item_id"] for item in derived_uncertainties}
        managed_derived_ids.update(current_derived_ids)
        state.uncertainties = [
            value
            for value in state.uncertainties
            if value["item_id"] not in managed_derived_ids
        ]

        for u in plan.uncertainties:
            raw = _thaw_val(u)
            # Snapshot adapters expose the same derived queue in their wire
            # format. The freshly recomputed, ownership-tagged projection is
            # authoritative and prevents stale snapshot entries persisting.
            if raw["item_id"] in current_derived_ids:
                continue
            state.add_uncertainty(raw)
            if raw["item_id"] not in receipt_uncertainty_ids:
                receipt_uncertainties.append(raw)
                receipt_uncertainty_ids.add(raw["item_id"])

        for raw in derived_uncertainties:
            state.add_uncertainty(raw)
            item_id = raw["item_id"]
            if (
                item_id not in uncertainty_ids_before
                and item_id not in receipt_uncertainty_ids
            ):
                receipt_uncertainties.append(raw)
                receipt_uncertainty_ids.add(item_id)

        valid, invariant_errors = state.validate_invariants()
        if not valid:
            raise ValueError(
                "Post-apply kernel invariant failure: " + "; ".join(invariant_errors)
            )

        return IngestionReceipt.create(
            envelope=plan.envelope,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            status="accepted",
            valid=True,
            errors=[],
            output_digests=state.compute_digests(),
            created_or_reused_objects=list(plan.created_objects.keys()),
            ceg_nodes=created_ceg_nodes,
            ceg_edges=created_ceg_edges,
            ledger_bindings=applied_ledger_bindings,
            uncertainties=receipt_uncertainties,
            ignored_fields=plan.ignored_fields,
            caller_metadata=plan.envelope.caller_metadata,
        )


# ===========================================================================
# Tier 1: Native Structured Receipts
# ===========================================================================

class AcademicSourceVerificationAdapter(BaseArtifactAdapter):
    """Adapter for academic-source-verification EvidenceReceipts."""

    adapter_id = "adapter-academic-source-verification"
    adapter_version = "1.0.0"
    accepted_producers = {"academic-source-verification"}
    accepted_schemas = {"evidence-receipt-1.0", "academic-evidence-1.0"}
    is_lossless = True
    tier = 1
    accepted_binding_fields = {"action", "decision_id", "verdict", "rationale"}
    required_binding_fields = {"action", "decision_id", "verdict"}

    def normalize_bindings(
        self,
        bindings: Optional[Mapping[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        values = super().normalize_bindings(bindings)
        if values is None:
            return None
        if values["action"] != "add_outcome_correction":
            raise ValueError(
                "academic-source-verification binding action must be "
                "'add_outcome_correction'"
            )
        for key in ("decision_id", "verdict"):
            if not isinstance(values[key], str) or not values[key].strip():
                raise ValueError(f"bindings.{key} must be a non-empty string")
        if "rationale" in values and (
            not isinstance(values["rationale"], str) or not values["rationale"].strip()
        ):
            raise ValueError("bindings.rationale must be a non-empty string when supplied")
        return values

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return (
            envelope.producer.get("skill") in self.accepted_producers
            or envelope.artifact_kind == "evidence_receipt"
            or envelope.payload_schema in self.accepted_schemas
        )

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if p.get("schema_version") != "1.0":
            errors.append("AcademicEvidence receipt missing schema_version='1.0'")
        if "claims" not in p or not isinstance(p["claims"], (list, tuple)):
            errors.append("AcademicEvidence receipt missing 'claims' list")
        calc_sha = canonical_academic_receipt_payload_sha256(p)
        if calc_sha != envelope.payload_sha256:
            errors.append(f"Payload SHA-256 mismatch: envelope claims {envelope.payload_sha256}, actual payload computes to {calc_sha}")
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        plan.registered_receipts[envelope.payload_sha256] = p

        # 1. Register Subject Research Object if work reference exists
        target_work = None
        for s_ref in envelope.subject_refs:
            if s_ref.startswith("work:"):
                target_work = s_ref
                break
        if not target_work and p.get("query"):
            target_work = f"work:{canonical_text(p['query'])}"

        if target_work:
            if target_work in state.objects:
                plan.created_objects[target_work] = _thaw_val(state.objects[target_work])
            else:
                plan.created_objects[target_work] = {
                    "id": target_work,
                    "kind": "work",
                }

        # 2. Ingest claims and evidences into CEG
        for idx, c_item in enumerate(p.get("claims", [])):
            c_text = c_item.get("claim", "")
            c_type = c_item.get("evidence_type", "data_point")
            c_loc = c_item.get("locator") or envelope.locator
            c_stat = c_item.get("support_status", "supported")

            # Receipt claim digests identify the claim entry as serialized by
            # the producer. CEG claim nodes additionally bind the effective
            # envelope locator and target work. Evidence anchors also bind the
            # physical receipt so separate retrievals remain independently
            # traceable without polluting the stable ResearchObject identity.
            c_dig = canonical_evidence_claim_digest(c_item)
            claim_node_dig = _compute_ceg_claim_digest(
                c_text,
                target_work,
                c_loc,
                "empirical_finding",
            )
            evidence_node_dig = compute_sha256(canonical_json_bytes({
                "claim_node_digest": claim_node_dig,
                "payload_sha256": envelope.payload_sha256,
                "receipt_claim_digest": c_dig,
            }))
            c_id = f"clm-{claim_node_dig[:32]}"
            ev_id = f"ev-{evidence_node_dig[:32]}"

            plan.ceg_claims.append({
                "id": c_id,
                "text": c_text,
                "target_work_id": target_work,
                "locator": c_loc,
                "claim_type": "empirical_finding",
            })

            ref = ReceiptRef(
                kind="academic_evidence",
                schema_version="1.0",
                claim_digest=c_dig,
                payload_sha256=envelope.payload_sha256,
                locator=c_loc,
            )

            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "evidence_receipt",
                "target_work_id": target_work,
                "locator": c_loc,
                "receipt_ref": ref,
                "metadata": {
                    "evidence_type": c_type,
                    "source": c_item.get("source"),
                    "receipt_query": p.get("query"),
                    "receipt_identifiers": copy.deepcopy(p.get("identifiers", [])),
                },
            })

            plan.ceg_edges.append({
                "evidence_id": ev_id,
                "claim_id": c_id,
                "support_status": c_stat,
                "rationale": f"Extracted from {envelope.producer['skill']} receipt",
            })

            # Explicit Ledger outcome correction binding: only when caller explicitly requests action='add_outcome_correction' with explicit verdict
            if (
                bindings
                and bindings.get("action") == "add_outcome_correction"
                and "decision_id" in bindings
                and "verdict" in bindings
            ):
                plan.ledger_outcome_corrections.append({
                    "decision_id": bindings["decision_id"],
                    "verdict": bindings["verdict"],
                    "rationale": bindings.get("rationale") or f"Explicitly bound to evidence {c_id}",
                    "receipt_ref": ref,
                    "locator": c_loc,
                })

        return plan


class ResearchObjectIdentityAdapter(BaseArtifactAdapter):
    """Adapter for research-object-identity and Lineage receipts."""

    adapter_id = "adapter-research-object-identity"
    adapter_version = "1.0.0"
    accepted_producers = {"research-object-identity"}
    accepted_schemas = {"research-object-1.0", "lineage-receipt-1.0"}
    is_lossless = True
    tier = 1

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return (
            envelope.producer.get("skill") in self.accepted_producers
            or envelope.payload_schema in self.accepted_schemas
        )

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if envelope.payload_schema == "lineage-receipt-1.0" or p.get("protocol") == "lineage-receipt-1.0":
            if not p.get("receipt_id") or not p.get("receipt_digest"):
                errors.append("Lineage receipt requires receipt_id and receipt_digest")
            integrity_ok, integrity_error = validate_lineage_receipt_integrity(p)
            if not integrity_ok and integrity_error:
                errors.append(integrity_error)
        else:
            obj_id = p.get("object_id") or p.get("id")
            obj_type = p.get("object_type") or p.get("kind")
            if not obj_id or not obj_type:
                errors.append("ResearchObject requires 'object_id'/'id' and 'object_type'/'kind'")
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        if p.get("protocol") == "lineage-receipt-1.0":
            plan.registered_receipts[p["receipt_id"]] = copy.deepcopy(p)
            r_ref = ReceiptRef(
                kind="lineage",
                schema_version="lineage-receipt-1.0",
                receipt_id=p["receipt_id"],
                receipt_digest=p["receipt_digest"],
                locator=envelope.locator,
            )
            evidence_digest = compute_sha256(canonical_json_bytes({
                "receipt_id": p["receipt_id"],
                "locator": envelope.locator,
            }))
            ev_id = f"ev-lineage-{evidence_digest[:32]}"
            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "lineage_receipt",
                "locator": envelope.locator,
                "receipt_ref": r_ref,
            })
        else:
            obj_id = p.get("object_id") or p.get("id")
            plan.created_objects[obj_id] = copy.deepcopy(p)
        return plan


class ClaimEvidenceGraphSnapshotAdapter(BaseArtifactAdapter):
    """Adapter for replaying and merging full CEG exports."""

    adapter_id = "adapter-claim-evidence-graph"
    adapter_version = "1.0.0"
    accepted_producers = {"claim-evidence-graph"}
    accepted_schemas = {"ceg-snapshot-1.0", "claim-evidence-graph-1.0"}
    is_lossless = True
    tier = 1

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return (
            envelope.producer.get("skill") in self.accepted_producers
            or envelope.artifact_kind == "ceg_snapshot"
        )

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if p.get("protocol") != "claim-evidence-graph-1.0":
            errors.append("CEG snapshot invalid protocol")
        if "claims" not in p or "evidence_anchors" not in p:
            errors.append("CEG snapshot missing 'claims' or 'evidence_anchors' lists")
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        if state.ceg is None:
            plan.valid = False
            plan.errors.append("CEG snapshot ingestion requires a ClaimEvidenceGraph target")
            return plan
        p = _thaw_val(envelope.payload)
        try:
            replayed = state.ceg.__class__.from_dict(p, receipt_registry=state.receipts)
        except Exception as exc:
            plan.valid = False
            plan.errors.append(f"CEG snapshot replay failed: {exc}")
            return plan

        current = state.ceg.to_dict()
        current_empty = not any(
            current[field]
            for field in ("claims", "evidence_anchors", "support_edges", "claim_relations")
        )
        if not current_empty and current["graph_id"] != p["graph_id"]:
            plan.valid = False
            plan.errors.append("CEG snapshot graph_id conflicts with the non-empty target graph")
            return plan
        if not current_empty and not _snapshot_fast_forwards(
            current,
            p,
            ("claims", "evidence_anchors", "support_edges", "claim_relations"),
        ):
            plan.valid = False
            plan.errors.append("CEG snapshot is divergent; only exact or forward-only snapshots are accepted")
            return plan
        plan.ceg_snapshot = replayed
        for u in p.get("uncertainties", []):
            plan.uncertainties.append(copy.deepcopy(u))
        return plan


class DecisionLedgerSnapshotAdapter(BaseArtifactAdapter):
    """Adapter for replaying and merging Decision Ledger exports."""

    adapter_id = "adapter-decision-ledger"
    adapter_version = "1.0.0"
    accepted_producers = {"decision-ledger"}
    accepted_schemas = {"decision-ledger-1.0"}
    is_lossless = True
    tier = 1

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return (
            envelope.producer.get("skill") in self.accepted_producers
            or envelope.artifact_kind == "decision_ledger_snapshot"
        )

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if p.get("protocol") != "decision-ledger-1.0":
            errors.append("DecisionLedger snapshot invalid protocol")
        if "decisions" not in p:
            errors.append("DecisionLedger snapshot missing 'decisions' list")
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        if state.ledger is None:
            plan.valid = False
            plan.errors.append("DecisionLedger snapshot ingestion requires a DecisionLedger target")
            return plan
        p = _thaw_val(envelope.payload)
        try:
            manifest = p.get("verification_manifest", {})
            if not isinstance(manifest, collections.abc.Mapping):
                raise ValueError("DecisionLedger snapshot verification_manifest must be a mapping")
            missing_receipts = sorted(set(manifest) - set(state.receipts))
            if missing_receipts:
                raise ValueError(
                    "DecisionLedger snapshot is missing declared physical receipts: "
                    + ", ".join(missing_receipts)
                )
            declared_receipts = {
                key: state.receipts[key]
                for key in sorted(manifest)
            }
            replayed = state.ledger.__class__.from_dict(
                p,
                receipt_registry=declared_receipts,
            )
        except Exception as exc:
            plan.valid = False
            plan.errors.append(f"DecisionLedger snapshot replay failed: {exc}")
            return plan

        current = state.ledger.to_dict()
        current_empty = not any(
            current[field]
            for field in ("decisions", "bases", "forks", "state_events", "corrections")
        )
        if not current_empty and current["ledger_id"] != p["ledger_id"]:
            plan.valid = False
            plan.errors.append("DecisionLedger snapshot ledger_id conflicts with the non-empty target ledger")
            return plan
        if not current_empty and not _snapshot_fast_forwards(
            current,
            p,
            ("decisions", "bases", "forks", "state_events", "corrections"),
        ):
            plan.valid = False
            plan.errors.append(
                "DecisionLedger snapshot is divergent; only exact or forward-only snapshots are accepted"
            )
            return plan
        plan.ledger_snapshot = replayed
        for u in p.get("uncertainties", []):
            plan.uncertainties.append(copy.deepcopy(u))
        return plan


# ===========================================================================
# Tier 2: Structured Analytical Artifacts
# ===========================================================================

class QuantitativePaperAuditAdapter(BaseArtifactAdapter):
    """Adapter for quantitative-paper-audit statistical verification outputs."""

    adapter_id = "adapter-quantitative-paper-audit"
    adapter_version = "1.0.0"
    accepted_producers = {"quantitative-paper-audit"}
    accepted_schemas = {"quantitative-audit-1.0"}
    is_lossless = False
    tier = 2
    accepted_binding_fields = {"claim_id"}
    required_binding_fields = {"claim_id"}

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if "assertions" not in p and not any(
            key in p for key in ("reported", "recomputed", "consistent", "discrepancy_detected")
        ):
            errors.append("Quantitative audit payload requires assertions or a direct result")
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        assertions = p.get("assertions")
        if assertions is None:
            assertions = [p]
        for idx, ass in enumerate(assertions):
            stat_name = ass.get("statistic", f"stat_{idx}")
            reported = ass.get("reported_value", ass.get("reported"))
            recomputed = ass.get("recomputed_value", ass.get("recomputed"))
            if "discrepancy_detected" in ass:
                support_status = "contradicted" if ass["discrepancy_detected"] else "supported"
                discrepancy = ass["discrepancy_detected"]
            elif ass.get("consistent") is not None:
                support_status = "supported" if ass["consistent"] else "contradicted"
                discrepancy = not ass["consistent"]
            else:
                support_status = "unverifiable"
                discrepancy = None

            effective_locator = ass.get("locator") or envelope.locator
            evidence_digest = compute_sha256(canonical_json_bytes({
                "artifact_id": envelope.artifact_id,
                "assertion_index": idx,
                "locator": effective_locator,
            }))
            ev_id = f"ev-quant-{evidence_digest[:32]}"
            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "direct_observation",
                "locator": effective_locator,
                "metadata": {
                    "sub_type": "computed_evidence",
                    "statistic": stat_name,
                    "reported": reported,
                    "recomputed": recomputed,
                    "discrepancy": discrepancy,
                    "audit_result": copy.deepcopy(dict(ass)),
                },
            })

            if support_status == "unverifiable":
                plan.uncertainties.append({
                    "item_id": f"unc-quant-{evidence_digest[:32]}",
                    "subject_id": ev_id,
                    "kind": "quantitative_verification_gap",
                    "reason": "Quantitative artifact did not provide an explicit consistency verdict",
                    "needs_human": True,
                })

            # If caller explicitly provided claim binding, attach edge
            if bindings and "claim_id" in bindings:
                plan.ceg_edges.append({
                    "evidence_id": ev_id,
                    "claim_id": bindings["claim_id"],
                    "support_status": support_status,
                    "rationale": f"Quantitative recalculation of {stat_name}",
                })

        return plan


class ResearchReproducibilityAdapter(BaseArtifactAdapter):
    """Adapter for research-reproducibility reproduction receipts."""

    adapter_id = "adapter-research-reproducibility"
    adapter_version = "1.0.0"
    accepted_producers = {"research-reproducibility"}
    accepted_schemas = {"reproduction-receipt-1.0"}
    is_lossless = False
    tier = 2
    accepted_binding_fields = {"claim_id"}
    required_binding_fields = {"claim_id"}

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if "status" not in p and "verdict" not in p:
            errors.append("Reproduction receipt requires 'status' or 'verdict'")
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        raw_status = p["status"]
        evidence_digest = compute_sha256(canonical_json_bytes({
            "artifact_id": envelope.artifact_id,
            "locator": envelope.locator,
        }))
        ev_id = f"ev-repro-{evidence_digest[:32]}"

        if raw_status == "reproducible":
            support_status = "supported"
        elif raw_status == "inconsistent":
            support_status = "contradicted"
        else:
            support_status = "unverifiable"
            plan.uncertainties.append({
                "item_id": f"unc-repro-{evidence_digest[:32]}",
                "subject_id": ev_id,
                "kind": "reproducibility_gap",
                "reason": f"Reproduction audit status: {raw_status}",
                "needs_human": True,
            })

        plan.ceg_evidences.append({
            "id": ev_id,
            "anchor_type": "direct_observation",
            "locator": envelope.locator,
            "metadata": {
                "sub_type": "reproduction_receipt",
                "status": raw_status,
                "receipt": copy.deepcopy(dict(p)),
            },
        })

        if bindings and "claim_id" in bindings:
            plan.ceg_edges.append({
                "evidence_id": ev_id,
                "claim_id": bindings["claim_id"],
                "support_status": support_status,
                "rationale": f"Independent reproduction attempt: {raw_status}",
            })

        return plan


class CrossReviewAdapter(BaseArtifactAdapter):
    """Adapter for cross-review-five multi-agent review findings."""

    adapter_id = "adapter-cross-review-five"
    adapter_version = "1.0.0"
    accepted_producers = {"cross-review-five"}
    accepted_schemas = {"cross-review-finding-1.0", "cross-review-2.0"}
    is_lossless = False
    tier = 2

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if not any(key in p for key in ("findings", "consensus", "contradictions", "singletons")):
            errors.append(
                "Cross-review payload requires 'consensus', 'contradictions', "
                "'singletons', or 'findings'"
            )
        return len(errors) == 0, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        artifact_identity = envelope.artifact_id[4:]
        registry_id = f"review-registry-{artifact_identity}"
        plan.created_objects[registry_id] = {
            "id": registry_id,
            "kind": "cross_review_registry",
            "registry": copy.deepcopy(dict(p)),
        }

        # 1. Consensus issues
        for idx, item in enumerate(p.get("consensus", [])):
            ev_id = f"ev-rev-cons-{artifact_identity}-{idx}"
            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "direct_observation",
                "metadata": {
                    "sub_type": "review_consensus",
                    "issue": item,
                },
            })

        # 2. Contradictions -> evidence + uncertainties
        for idx, item in enumerate(p.get("contradictions", [])):
            ev_id = f"ev-rev-contra-{artifact_identity}-{idx}"
            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "direct_observation",
                "metadata": {
                    "sub_type": "review_contradiction",
                    "issue": item,
                },
            })
            plan.uncertainties.append({
                "item_id": f"unc-contra-{artifact_identity}-{idx}",
                "subject_id": ev_id,
                "kind": "expert_disagreement",
                "reason": str(item.get("summary") or item.get("title") or item),
                "needs_human": True,
            })

        # 3. Singletons -> evidence + uncertainties
        for idx, item in enumerate(p.get("singletons", [])):
            ev_id = f"ev-rev-single-{artifact_identity}-{idx}"
            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "direct_observation",
                "metadata": {
                    "sub_type": "review_singleton",
                    "issue": item,
                },
            })
            plan.uncertainties.append({
                "item_id": f"unc-single-{artifact_identity}-{idx}",
                "subject_id": ev_id,
                "kind": "expert_disagreement",
                "reason": str(item.get("summary") or item.get("title") or item),
                "needs_human": True,
            })

        # 4. Findings (if present)
        for idx, f in enumerate(p.get("findings", [])):
            f_id = f"ev-review-{artifact_identity}-{idx}"
            plan.ceg_evidences.append({
                "id": f_id,
                "anchor_type": "direct_observation",
                "metadata": {
                    "sub_type": "review_finding",
                    "reviewer": f.get("reviewer"),
                    "category": f.get("category"),
                    "summary": f.get("summary"),
                },
            })

        # 5. Dissenting opinions -> uncertainties
        for idx, d in enumerate(p.get("dissenting_opinions", [])):
            plan.uncertainties.append({
                "item_id": f"unc-dissent-{artifact_identity}-{idx}",
                "subject_id": envelope.artifact_id,
                "kind": "expert_disagreement",
                "reason": str(d),
                "needs_human": True,
            })

        mapped = {"consensus", "contradictions", "singletons", "findings", "dissenting_opinions"}
        plan.ignored_fields.extend(f"/{key}" for key in sorted(set(p) - mapped))

        return plan


class SystematicReviewAdapter(BaseArtifactAdapter):
    """Adapter for systematic-review-meta-analysis screening and extraction matrices."""

    adapter_id = "adapter-systematic-review"
    adapter_version = "1.0.0"
    accepted_producers = {"systematic-review-meta-analysis"}
    accepted_schemas = {"screening-matrix-1.0", "meta-analysis-1.0"}
    is_lossless = False
    tier = 2

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        p = envelope.payload
        if not any(key in p for key in ("included_studies", "screening_results", "meta_analysis")):
            return False, [
                "Systematic review payload requires 'included_studies', "
                "'screening_results', or 'meta_analysis'"
            ]
        errors = []
        for idx, result in enumerate(p.get("screening_results", [])):
            decision = result.get("decision")
            if decision is not None and decision not in {"include", "exclude", "maybe"}:
                errors.append(
                    f"screening_results[{idx}].decision must be include, exclude, or maybe"
                )
        return not errors, errors

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        studies = p.get("included_studies", [])
        for idx, s in enumerate(studies):
            source_study_id = s.get("study_id") or (
                "study-" + compute_sha256(canonical_json_bytes(s))[:32]
            )
            extraction_digest = compute_sha256(canonical_json_bytes({
                "artifact_id": envelope.artifact_id,
                "entry_index": idx,
                "study_id": source_study_id,
            }))
            extraction_id = f"study-extraction:{extraction_digest[:32]}"
            plan.created_objects[extraction_id] = dict(
                copy.deepcopy(s),
                id=extraction_id,
                kind="study_extraction",
                study_id=source_study_id,
            )
        for idx, result in enumerate(p.get("screening_results", [])):
            # A study can have multiple reports/records. Prefer the unique
            # screening-record identity and only fall back to study_id for
            # older producer payloads that do not expose record_id.
            source_id = result.get("record_id") or result.get("study_id")
            if not source_id:
                source_id = compute_sha256(canonical_json_bytes(result))[:32]
            # A screening decision and an extracted included-study record are
            # distinct objects even when they share the same study identifier.
            result_id = f"screening:{source_id}"
            plan.created_objects[result_id] = dict(
                copy.deepcopy(result), id=result_id, kind="screening_result"
            )
            if result.get("decision") in {None, "maybe"}:
                plan.uncertainties.append({
                    "item_id": f"unc-screen-{envelope.artifact_id[4:]}-{idx}",
                    "subject_id": result_id,
                    "kind": "screening_ambiguity",
                    "reason": "Screening result has no determinate include/exclude decision",
                    "needs_human": True,
                })
        if "meta_analysis" in p:
            analysis_id = f"meta-{envelope.artifact_id[4:]}"
            plan.created_objects[analysis_id] = {
                "id": analysis_id,
                "kind": "meta_analysis",
                "value": copy.deepcopy(p["meta_analysis"]),
                "protocol_id": p.get("protocol_id"),
            }
        return plan


class LiteratureAnalysisAdapter(BaseArtifactAdapter):
    """Adapter for literature-analysis canonical works and corpus matrices."""

    adapter_id = "adapter-literature-analysis"
    adapter_version = "1.0.0"
    accepted_producers = {"literature-analysis"}
    accepted_schemas = {"canonical-work-1.0", "corpus-matrix-1.0"}
    is_lossless = False
    tier = 2

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        p = envelope.payload
        if envelope.payload_schema == "canonical-work-1.0" and "work_type" in p:
            return True, []
        if "canonical_work" not in p and "works" not in p:
            return False, [
                "Literature analysis payload requires a direct CanonicalWork, "
                "'canonical_work', or 'works'"
            ]
        return True, []

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        if envelope.payload_schema == "canonical-work-1.0" and "work_type" in p:
            works = [p]
        else:
            works = [p["canonical_work"]] if "canonical_work" in p else p.get("works", [])
        for w in works:
            title = canonical_text(w.get("title", ""))
            doi = canonical_text(w.get("doi", "")).lower()
            w_id = (
                w.get("work_id")
                or (f"work:doi:{doi}" if doi else None)
                or (f"work:{title}" if title else None)
                or f"work:{compute_sha256(canonical_json_bytes(w))[:32]}"
            )
            plan.created_objects[w_id] = copy.deepcopy(w)
        return plan


class LiteratureWatchAdapter(BaseArtifactAdapter):
    """Adapter for literature-watch delta monitoring feeds."""

    adapter_id = "adapter-literature-watch"
    adapter_version = "1.0.0"
    accepted_producers = {"literature-watch"}
    accepted_schemas = {"literature-delta-1.0"}
    is_lossless = False
    tier = 2

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        p = envelope.payload
        if "new_citations" not in p and "new_papers" not in p:
            return False, ["Literature watch delta requires 'new_citations' or 'new_papers'"]
        return True, []

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        for p_item in p.get("new_papers", []):
            pid = p_item.get("id") or f"paper-{compute_sha256(canonical_json_bytes(p_item))[:32]}"
            plan.created_objects[pid] = copy.deepcopy(p_item)
        for citation in p.get("new_citations", []):
            cid = citation.get("id") or f"citation-{compute_sha256(canonical_json_bytes(citation))[:32]}"
            plan.created_objects[cid] = dict(copy.deepcopy(citation), id=cid, kind="citation_delta")
        if p.get("truncations"):
            plan.uncertainties.append({
                "item_id": f"unc-literature-{envelope.artifact_id[4:]}",
                "subject_id": envelope.artifact_id,
                "kind": "literature_coverage_gap",
                "reason": "Literature delta reports truncated result coverage",
                "needs_human": True,
                "metadata": {"truncations": copy.deepcopy(p["truncations"])},
            })
        return plan


class RetractionWatchAdapter(BaseArtifactAdapter):
    """Adapter for retraction-watch correction and retraction alerts."""

    adapter_id = "adapter-retraction-watch"
    adapter_version = "1.0.0"
    accepted_producers = {"retraction-watch"}
    accepted_schemas = {"retraction-alert-1.0", "retraction-delta-1.0"}
    is_lossless = False
    tier = 2

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        p = envelope.payload
        if "target_work_id" not in p and "doi" not in p and not envelope.subject_refs:
            return False, [
                "Retraction delta requires 'target_work_id', 'doi', or an envelope subject_ref"
            ]
        return True, []

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        target = p.get("target_work_id")
        if not target and p.get("doi"):
            target = f"doi:{p['doi']}"
        if not target:
            target = envelope.subject_refs[0]
        event_digest = compute_sha256(canonical_json_bytes({
            "artifact_id": envelope.artifact_id,
            "target_work_id": target,
        }))
        event_id = f"publication-status-{event_digest[:32]}"
        plan.created_objects[event_id] = {
            "id": event_id,
            "kind": "publication_status_observation",
            "target_work_id": target,
            "observation": copy.deepcopy(dict(p)),
        }
        current_unknown = (
            p.get("verification_status") in {"retained_prior", "unverified"}
            or ("current_observation" in p and p.get("current_observation") is None)
            or p["is_retracted"] is None
            or p.get("truncated") is True
        )
        current_observation = p.get("current_observation", p["is_retracted"])
        retraction_signal = bool(current_observation or p.get("signals"))
        if current_unknown:
            plan.uncertainties.append({
                "item_id": f"unc-retract-{event_digest[:32]}",
                "subject_id": target,
                "kind": "publication_status_change",
                "reason": (
                    "Publication-status check was truncated and may omit updates"
                    if p.get("truncated") is True
                    else "Current publication status could not be verified"
                ),
                "needs_human": True,
            })
        elif retraction_signal:
            reason = p.get("retraction_reason") or "Retraction/correction signal requires revalidation"
            plan.uncertainties.append({
                "item_id": f"unc-retract-{event_digest[:32]}",
                "subject_id": target,
                "kind": "retraction_alert" if current_observation else "publication_status_change",
                "reason": reason,
                "needs_human": True,
            })
        return plan


class MathComputationAdapter(BaseArtifactAdapter):
    """Adapter for math-computation symbolic and numerical verification receipts."""

    adapter_id = "adapter-math-computation"
    adapter_version = "1.0.0"
    accepted_producers = {"math-computation"}
    accepted_schemas = {"computation-receipt-1.0"}
    is_lossless = False
    tier = 2
    accepted_binding_fields = {"claim_id"}
    required_binding_fields = {"claim_id"}

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        p = envelope.payload
        if "expression" not in p and "result" not in p:
            return False, ["Math computation receipt requires 'expression' or 'result'"]
        return True, []

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        p = envelope.payload
        artifact_identity = envelope.artifact_id[4:]
        ev_id = f"ev-math-{artifact_identity}"
        is_verified = p.get("verified")
        plan.ceg_evidences.append({
            "id": ev_id,
            "anchor_type": "direct_observation",
            "metadata": {
                "sub_type": "computed_evidence",
                "expression": p.get("expression"),
                "result": p.get("result"),
                "verified": is_verified,
            },
        })

        if is_verified is None:
            support_status = "unverifiable"
            plan.uncertainties.append({
                "item_id": f"unc-math-{artifact_identity}",
                "subject_id": ev_id,
                "kind": "computation_unverified",
                "reason": p.get("verification_error") or "Computation artifact omitted a verification result",
                "needs_human": True,
            })
        else:
            support_status = "supported" if is_verified else "contradicted"

        if bindings and "claim_id" in bindings:
            plan.ceg_edges.append({
                "evidence_id": ev_id,
                "claim_id": bindings["claim_id"],
                "support_status": support_status,
                "rationale": "Symbolic/numerical mathematical verification",
            })

        return plan


# ===========================================================================
# Tier 3: Opaque Artifacts (Prose Stays Prose, Opaque Stays Opaque)
# ===========================================================================

class AcademicWritingAdapter(BaseArtifactAdapter):
    """Adapter for academic-writing drafts, manuscripts, and cover letters.

    Strictly preserves prose as opaque artifacts. Never extracts assertions or
    generates automated decisions from prose.
    """

    adapter_id = "adapter-academic-writing"
    adapter_version = "1.0.0"
    accepted_producers = {"academic-writing"}
    accepted_schemas = {"manuscript-opaque-1.0", "submission-package-1.0"}
    is_lossless = False
    tier = 3

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return (
            envelope.producer.get("skill") in self.accepted_producers
            or envelope.artifact_kind == "opaque_manuscript"
        )

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        p = envelope.payload
        if "content" not in p and "text" not in p and "sections" not in p:
            return False, ["Opaque manuscript requires text content or sections"]
        return True, []

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan

        # Register exclusively as an opaque research object存证
        plan.created_objects[envelope.artifact_id] = {
            "id": envelope.artifact_id,
            "kind": "opaque_manuscript",
            "producer": envelope.producer,
            "payload_sha256": envelope.payload_sha256,
            "locator": envelope.locator,
            "subject_refs": list(envelope.subject_refs),
        }
        return plan


class OpaqueFallbackAdapter(BaseArtifactAdapter):
    """Fallback adapter for unknown or non-specialized scholarly artifacts."""

    adapter_id = "adapter-opaque-fallback"
    adapter_version = "1.0.0"
    accepted_producers = set()
    accepted_schemas = set()
    is_lossless = False
    tier = 3

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return True  # Matches anything that wasn't handled by higher-tier adapters

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        return True, []

    def plan(
        self,
        envelope: ArtifactEnvelope,
        state: IngestionKernelState,
        bindings: Optional[Mapping[str, Any]] = None,
    ) -> IngestionPlan:
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, True, [])
        plan.created_objects[envelope.artifact_id] = {
            "id": envelope.artifact_id,
            "kind": "opaque_artifact",
            "artifact_kind": envelope.artifact_kind,
            "producer": envelope.producer,
            "payload_sha256": envelope.payload_sha256,
        }
        return plan

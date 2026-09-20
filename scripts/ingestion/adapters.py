"""Deterministic Adapters for 13 scholarly skills into the research-state kernel."""

from __future__ import annotations

from abc import ABC, abstractmethod
import collections.abc
import copy
import hashlib
from typing import Any, Dict, List, Mapping, Optional, Tuple, Set

from shared_contracts.evidence import (
    ReceiptRef,
    canonical_academic_receipt_payload_sha256,
    canonical_evidence_claim_digest,
    canonical_json_bytes,
    canonical_text,
    compute_sha256,
    validate_academic_receipt_contract,
    validate_lineage_receipt_contract,
)
from .models import ArtifactEnvelope, IngestionKernelState, IngestionReceipt


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
        self.ledger_decisions: List[Dict[str, Any]] = []
        self.ledger_bases: List[Dict[str, Any]] = []
        self.ledger_outcome_corrections: List[Dict[str, Any]] = []
        self.uncertainties: List[Dict[str, Any]] = []
        self.ignored_fields: List[str] = []
        self.registered_receipts: Dict[str, Any] = {}


class BaseArtifactAdapter(ABC):
    """Abstract base class for deterministic scholarly artifact adapters."""

    adapter_id: str
    adapter_version: str
    accepted_producers: Set[str]
    accepted_schemas: Set[str]
    is_lossless: bool
    tier: int  # 1 = native receipt, 2 = structured artifact, 3 = opaque artifact

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
            )

        # 1. Apply Research Objects
        for obj_id, obj_data in plan.created_objects.items():
            state.objects[obj_id] = obj_data

        # 2. Apply registered receipts
        for r_key, r_obj in plan.registered_receipts.items():
            state.receipts[r_key] = r_obj
            if state.ceg is not None:
                state.ceg.register_receipt(r_key, r_obj)
            if state.ledger is not None:
                state.ledger.register_receipt(r_key, r_obj)

        # 3. Apply CEG nodes and edges
        created_ceg_nodes = []
        created_ceg_edges = []
        if state.ceg is not None:
            for c in plan.ceg_claims:
                state.ceg.add_claim(
                    id=c["id"],
                    text=c["text"],
                    target_work_id=c.get("target_work_id"),
                    locator=c.get("locator"),
                    claim_type=c.get("claim_type", "empirical_finding"),
                    entities=c.get("entities", ()),
                )
                created_ceg_nodes.append(c["id"])

            for ev in plan.ceg_evidences:
                state.ceg.add_evidence(
                    id=ev["id"],
                    anchor_type=ev["anchor_type"],
                    source_work_id=ev.get("source_work_id") or ev.get("target_work_id"),
                    locator=ev.get("locator"),
                    receipt_ref=ev.get("receipt_ref"),
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

        # 4. Apply Ledger decisions and corrections
        applied_ledger_bindings = []
        if state.ledger is not None:
            for dec in plan.ledger_decisions:
                state.ledger.add_decision(
                    id=dec["id"],
                    title=dec["title"],
                    decision_action=dec.get("decision_action", "explore"),
                    context_work_id=dec.get("context_work_id"),
                    locator=dec.get("locator"),
                )

            for b in plan.ledger_bases:
                state.ledger.add_basis(
                    decision_id=b["decision_id"],
                    basis_kind=b["basis_kind"],
                    basis_id=b["basis_id"],
                    receipt_ref=b.get("receipt_ref"),
                )
                applied_ledger_bindings.append({
                    "decision_id": b["decision_id"],
                    "binding_kind": b["basis_kind"],
                    "basis_id": b["basis_id"],
                })

            for corr in getattr(plan, "ledger_outcome_corrections", []):
                state.ledger.add_outcome_correction(
                    decision_id=corr["decision_id"],
                    verdict=corr["verdict"],
                    rationale=corr["rationale"],
                    receipt_ref=corr.get("receipt_ref"),
                    locator=corr.get("locator"),
                )
                applied_ledger_bindings.append({
                    "decision_id": corr["decision_id"],
                    "binding_kind": "evidence_receipt",
                    "basis_id": corr.get("locator") or corr["decision_id"],
                })

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
            uncertainties=plan.uncertainties,
            ignored_fields=plan.ignored_fields,
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
        if "claims" not in p or not isinstance(p["claims"], list):
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
            plan.created_objects[target_work] = {
                "id": target_work,
                "kind": "work",
                "source_query": p.get("query"),
                "identifiers": p.get("identifiers", []),
            }

        # 2. Ingest claims and evidences into CEG
        for idx, c_item in enumerate(p.get("claims", [])):
            c_text = c_item.get("claim", "")
            c_type = c_item.get("evidence_type", "data_point")
            c_loc = c_item.get("locator") or envelope.locator
            c_stat = c_item.get("support_status", "supported")

            # Deterministic claim ID
            c_dig = canonical_evidence_claim_digest(c_item)
            c_id = f"clm-{c_dig[:16]}"
            ev_id = f"ev-{c_dig[:16]}"

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
                "metadata": {"evidence_type": c_type, "source": c_item.get("source")},
            })

            plan.ceg_edges.append({
                "evidence_id": ev_id,
                "claim_id": c_id,
                "support_status": c_stat,
                "rationale": f"Extracted from {envelope.producer['skill']} receipt",
            })

            # Optional Ledger outcome correction binding if explicitly provided by caller
            if bindings and "decision_id" in bindings:
                plan.ledger_outcome_corrections.append({
                    "decision_id": bindings["decision_id"],
                    "verdict": "positive" if c_stat == "supported" else "negative",
                    "rationale": f"Verified via academic evidence {c_id}",
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
        elif "id" not in p or "kind" not in p:
            errors.append("ResearchObject requires 'id' and 'kind'")
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
            plan.registered_receipts[p["receipt_id"]] = p
            r_ref = ReceiptRef(
                kind="lineage",
                schema_version="lineage-receipt-1.0",
                receipt_id=p["receipt_id"],
                receipt_digest=p["receipt_digest"],
                locator=envelope.locator,
            )
            if bindings and "decision_id" in bindings:
                plan.ledger_bases.append({
                    "decision_id": bindings["decision_id"],
                    "basis_kind": "lineage_receipt",
                    "basis_id": p["receipt_id"],
                    "receipt_ref": r_ref,
                })
        else:
            plan.created_objects[p["id"]] = copy.deepcopy(p)
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
        if "claims" not in p or ("evidences" not in p and "evidence_anchors" not in p):
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

        p = envelope.payload
        for c in p.get("claims", []):
            plan.ceg_claims.append(c)
        ev_list = p.get("evidence_anchors") or p.get("evidences") or []
        for ev in ev_list:
            plan.ceg_evidences.append(ev)
        for edge in p.get("support_edges", []):
            plan.ceg_edges.append(edge)
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

        p = envelope.payload
        for d in p.get("decisions", []):
            plan.ledger_decisions.append(d)
        for b in p.get("bases", []):
            plan.ledger_bases.append(b)
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

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if "paper_title" not in p and "assertions" not in p:
            errors.append("Quantitative audit payload must contain 'paper_title' or 'assertions'")
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
        assertions = p.get("assertions", [])
        for idx, ass in enumerate(assertions):
            stat_name = ass.get("statistic", f"stat_{idx}")
            reported = ass.get("reported_value")
            recomputed = ass.get("recomputed_value")
            discrepancy = ass.get("discrepancy_detected", False)

            ev_id = f"ev-quant-{envelope.artifact_id[4:12]}-{idx}"
            plan.ceg_evidences.append({
                "id": ev_id,
                "anchor_type": "direct_observation",
                "locator": ass.get("locator") or envelope.locator,
                "metadata": {
                    "sub_type": "computed_evidence",
                    "statistic": stat_name,
                    "reported": reported,
                    "recomputed": recomputed,
                    "discrepancy": discrepancy,
                },
            })

            # If caller explicitly provided claim binding, attach edge
            if bindings and "claim_id" in bindings:
                status = "contradicted" if discrepancy else "supported"
                plan.ceg_edges.append({
                    "evidence_id": ev_id,
                    "claim_id": bindings["claim_id"],
                    "support_status": status,
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

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope) -> Tuple[bool, List[str]]:
        errors = []
        p = envelope.payload
        if "verdict" not in p:
            errors.append("Reproduction receipt requires 'verdict'")
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
        verdict = p.get("verdict", "inconclusive")
        ev_id = f"ev-repro-{envelope.artifact_id[4:16]}"

        plan.ceg_evidences.append({
            "id": ev_id,
            "anchor_type": "direct_observation",
            "locator": envelope.locator,
            "metadata": {
                "sub_type": "reproduction_receipt",
                "verdict": verdict,
                "discrepancies": p.get("discrepancies", []),
            },
        })

        if verdict in ("failed", "inconclusive"):
            plan.uncertainties.append({
                "item_id": f"unc-repro-{envelope.artifact_id[4:16]}",
                "subject_id": ev_id,
                "kind": "reproducibility_gap",
                "reason": f"Reproduction verdict: {verdict}",
                "needs_human": True,
            })

        if bindings and "claim_id" in bindings:
            status = "supported" if verdict == "reproduced" else "contradicted"
            plan.ceg_edges.append({
                "evidence_id": ev_id,
                "claim_id": bindings["claim_id"],
                "support_status": status,
                "rationale": f"Independent reproduction attempt: {verdict}",
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
        if "findings" not in p and "consensus" not in p:
            errors.append("Cross-review payload requires 'findings' or 'consensus'")
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
        findings = p.get("findings", [])
        for idx, f in enumerate(findings):
            f_id = f"ev-review-{envelope.artifact_id[4:12]}-{idx}"
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

        # Dissenting opinions are strictly preserved as uncertainties, never squashed
        dissents = p.get("dissenting_opinions", [])
        for idx, d in enumerate(dissents):
            plan.uncertainties.append({
                "item_id": f"unc-dissent-{envelope.artifact_id[4:12]}-{idx}",
                "subject_id": envelope.artifact_id,
                "kind": "expert_disagreement",
                "reason": str(d),
                "needs_human": True,
            })

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
        if "included_studies" not in p and "screening_results" not in p:
            return False, ["Systematic review payload requires 'included_studies' or 'screening_results'"]
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
        studies = p.get("included_studies", [])
        for idx, s in enumerate(studies):
            s_id = s.get("study_id") or f"study-{idx}"
            plan.created_objects[s_id] = {
                "id": s_id,
                "kind": "study_entry",
                "title": s.get("title"),
                "effect_size": s.get("effect_size"),
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
        if "canonical_work" not in p and "works" not in p:
            return False, ["Literature analysis payload requires 'canonical_work' or 'works'"]
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
        works = [p["canonical_work"]] if "canonical_work" in p else p.get("works", [])
        for w in works:
            w_id = w.get("work_id") or f"work:{canonical_text(w.get('title', ''))}"
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
            pid = p_item.get("id") or f"paper-{compute_sha256(canonical_json_bytes(p_item))[:16]}"
            plan.created_objects[pid] = copy.deepcopy(p_item)
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
        if "target_work_id" not in p and "doi" not in p:
            return False, ["Retraction alert requires 'target_work_id' or 'doi'"]
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
        target = p.get("target_work_id") or f"doi:{p.get('doi')}"
        reason = p.get("retraction_reason") or "Paper retracted or under formal investigation"

        # Signal uncertainty and revalidation needed; never purge historical nodes!
        plan.uncertainties.append({
            "item_id": f"unc-retract-{envelope.artifact_id[4:16]}",
            "subject_id": target,
            "kind": "retraction_alert",
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
        ev_id = f"ev-math-{envelope.artifact_id[4:16]}"
        plan.ceg_evidences.append({
            "id": ev_id,
            "anchor_type": "direct_observation",
            "metadata": {
                "sub_type": "computed_evidence",
                "expression": p.get("expression"),
                "result": p.get("result"),
                "verified": p.get("verified", True),
            },
        })

        if bindings and "claim_id" in bindings:
            plan.ceg_edges.append({
                "evidence_id": ev_id,
                "claim_id": bindings["claim_id"],
                "support_status": "supported" if p.get("verified", True) else "contradicted",
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

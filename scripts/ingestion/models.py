"""Core domain models for the Research Artifact Ingestion Bridge."""

from __future__ import annotations

import collections.abc
import copy
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from shared_contracts.evidence import (
    ReceiptRef,
    canonical_json_bytes,
    compute_sha256,
    _thaw_val,
)


@dataclass(frozen=True)
class ArtifactEnvelope:
    """Standard envelope wrapping an artifact from any skill or external tool."""

    protocol: str
    artifact_id: str
    artifact_kind: str
    producer: Dict[str, str]
    payload_schema: str
    payload_sha256: str
    payload: Dict[str, Any]
    subject_refs: Tuple[str, ...] = field(default_factory=tuple)
    lineage_ref: Optional[ReceiptRef] = None
    locator: Optional[str] = None
    caller_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.protocol != "artifact-envelope-1.0":
            raise ValueError(f"Invalid envelope protocol: {self.protocol!r}. Must be 'artifact-envelope-1.0'.")
        if not re.match(r"^art-[0-9a-f]{32}$", self.artifact_id):
            raise ValueError(f"Invalid artifact_id: {self.artifact_id!r}. Must start with 'art-' followed by 32 hex chars.")
        if not re.match(r"^[0-9a-f]{64}$", self.payload_sha256):
            raise ValueError(f"Invalid payload_sha256: {self.payload_sha256!r}. Must be 64 lowercase hex digits.")
        if not isinstance(self.producer, collections.abc.Mapping) or "skill" not in self.producer or "version" not in self.producer:
            raise ValueError("Envelope 'producer' must be a mapping with 'skill' and 'version'.")
        if not isinstance(self.payload, collections.abc.Mapping):
            raise ValueError("Envelope 'payload' must be a mapping.")
        if self.locator is not None:
            if not isinstance(self.locator, str) or not (1 <= len(self.locator) <= 2048):
                raise ValueError("locator must be a non-empty string of at most 2048 characters.")

        # Cryptographic content-addressing invariant verification
        calc_sha = hashlib.sha256(canonical_json_bytes(_thaw_val(self.payload))).hexdigest().lower()
        if self.payload_sha256 != calc_sha:
            raise ValueError(f"Payload hash mismatch: envelope declares {self.payload_sha256}, actual payload computes to {calc_sha}")
        expected_id = f"art-{calc_sha[:32]}"
        if self.artifact_id != expected_id:
            raise ValueError(f"artifact_id content-addressing mismatch: declares {self.artifact_id}, expected {expected_id}")

    @classmethod
    def create(
        cls,
        payload: Mapping[str, Any],
        producer_skill: str,
        producer_version: str,
        artifact_kind: str,
        payload_schema: str,
        subject_refs: Optional[List[str]] = None,
        lineage_ref: Optional[ReceiptRef] = None,
        locator: Optional[str] = None,
        caller_metadata: Optional[Mapping[str, Any]] = None,
    ) -> ArtifactEnvelope:
        """Deterministically create an envelope, computing payload_sha256 and content-addressed artifact_id."""
        thawed_payload = _thaw_val(payload)
        p_bytes = canonical_json_bytes(thawed_payload)
        p_sha = hashlib.sha256(p_bytes).hexdigest().lower()
        art_id = f"art-{p_sha[:32]}"
        return cls(
            protocol="artifact-envelope-1.0",
            artifact_id=art_id,
            artifact_kind=artifact_kind,
            producer={"skill": producer_skill, "version": producer_version},
            payload_schema=payload_schema,
            payload_sha256=p_sha,
            payload=thawed_payload,
            subject_refs=tuple(subject_refs or []),
            lineage_ref=lineage_ref,
            locator=locator,
            caller_metadata=dict(caller_metadata) if caller_metadata else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "protocol": self.protocol,
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "producer": dict(self.producer),
            "payload_schema": self.payload_schema,
            "payload_sha256": self.payload_sha256,
            "payload": copy.deepcopy(self.payload),
        }
        if self.subject_refs:
            d["subject_refs"] = list(self.subject_refs)
        if self.lineage_ref is not None:
            d["lineage_ref"] = self.lineage_ref.to_dict()
        if self.locator:
            d["locator"] = self.locator
        if self.caller_metadata:
            d["caller_metadata"] = copy.deepcopy(self.caller_metadata)
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ArtifactEnvelope:
        lin_ref = None
        if "lineage_ref" in data and data["lineage_ref"]:
            lin_dict = data["lineage_ref"]
            lin_ref = ReceiptRef(
                kind=lin_dict["kind"],
                schema_version=lin_dict["schema_version"],
                receipt_id=lin_dict.get("receipt_id"),
                receipt_digest=lin_dict.get("receipt_digest"),
                locator=lin_dict.get("locator"),
            )
        return cls(
            protocol=data["protocol"],
            artifact_id=data["artifact_id"],
            artifact_kind=data["artifact_kind"],
            producer=dict(data["producer"]),
            payload_schema=data["payload_schema"],
            payload_sha256=data["payload_sha256"],
            payload=copy.deepcopy(data["payload"]),
            subject_refs=tuple(data.get("subject_refs") or []),
            lineage_ref=lin_ref,
            locator=data.get("locator"),
            caller_metadata=copy.deepcopy(data.get("caller_metadata")),
        )


@dataclass(frozen=True)
class IngestionReceipt:
    """Deterministic cryptographic receipt emitted after an artifact ingestion attempt."""

    protocol: str
    receipt_id: str
    source_artifact_id: str
    source_artifact_sha256: str
    adapter_id: str
    adapter_version: str
    status: str  # "accepted", "rejected", "partial"
    validation_state: Dict[str, Any]
    output_digests: Dict[str, str]
    created_or_reused_objects: Tuple[str, ...] = field(default_factory=tuple)
    ceg_nodes: Tuple[str, ...] = field(default_factory=tuple)
    ceg_edges: Tuple[str, ...] = field(default_factory=tuple)
    ledger_bindings: Tuple[Dict[str, str], ...] = field(default_factory=tuple)
    uncertainties: Tuple[Dict[str, Any], ...] = field(default_factory=tuple)
    ignored_fields: Tuple[str, ...] = field(default_factory=tuple)
    failure_reason: Optional[str] = None
    caller_metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.protocol != "ingestion-receipt-1.0":
            raise ValueError(f"Invalid receipt protocol: {self.protocol!r}. Must be 'ingestion-receipt-1.0'.")
        if not self.receipt_id.startswith("ingest-") or len(self.receipt_id) != 39:
            raise ValueError(f"Invalid receipt_id: {self.receipt_id!r}. Must start with 'ingest-' followed by 32 hex chars.")
        if self.status not in {"accepted", "rejected", "partial"}:
            raise ValueError(f"Invalid status: {self.status!r}. Must be 'accepted', 'rejected', or 'partial'.")

    @classmethod
    def create(
        cls,
        envelope: ArtifactEnvelope,
        adapter_id: str,
        adapter_version: str,
        status: str,
        valid: bool,
        errors: List[str],
        output_digests: Dict[str, str],
        created_or_reused_objects: Optional[List[str]] = None,
        ceg_nodes: Optional[List[str]] = None,
        ceg_edges: Optional[List[str]] = None,
        ledger_bindings: Optional[List[Dict[str, str]]] = None,
        uncertainties: Optional[List[Dict[str, Any]]] = None,
        ignored_fields: Optional[List[str]] = None,
        failure_reason: Optional[str] = None,
        caller_metadata: Optional[Dict[str, Any]] = None,
    ) -> IngestionReceipt:
        """Create a receipt with a deterministic, content-addressed receipt_id."""
        id_inputs = {
            "source_artifact_id": envelope.artifact_id,
            "source_artifact_sha256": envelope.payload_sha256,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "status": status,
            "valid": valid,
            "errors": sorted(errors),
            "output_digests": dict(sorted(output_digests.items())),
            "created_or_reused_objects": sorted(created_or_reused_objects or []),
            "ceg_nodes": sorted(ceg_nodes or []),
            "ceg_edges": sorted(ceg_edges or []),
            "ledger_bindings": sorted(ledger_bindings or [], key=lambda b: (b.get("decision_id", ""), b.get("basis_id", ""))),
            "uncertainties": sorted(uncertainties or [], key=lambda u: u.get("item_id", "")),
            "ignored_fields": sorted(ignored_fields or []),
            "failure_reason": failure_reason or "",
        }
        r_sha = compute_sha256(canonical_json_bytes(id_inputs))
        r_id = f"ingest-{r_sha[:32]}"

        return cls(
            protocol="ingestion-receipt-1.0",
            receipt_id=r_id,
            source_artifact_id=envelope.artifact_id,
            source_artifact_sha256=envelope.payload_sha256,
            adapter_id=adapter_id,
            adapter_version=adapter_version,
            status=status,
            validation_state={"valid": valid, "errors": list(errors)},
            output_digests=dict(output_digests),
            created_or_reused_objects=tuple(created_or_reused_objects or []),
            ceg_nodes=tuple(ceg_nodes or []),
            ceg_edges=tuple(ceg_edges or []),
            ledger_bindings=tuple(ledger_bindings or []),
            uncertainties=tuple(uncertainties or []),
            ignored_fields=tuple(ignored_fields or []),
            failure_reason=failure_reason,
            caller_metadata=caller_metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "protocol": self.protocol,
            "receipt_id": self.receipt_id,
            "source_artifact_id": self.source_artifact_id,
            "source_artifact_sha256": self.source_artifact_sha256,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "status": self.status,
            "validation_state": {
                "valid": self.validation_state["valid"],
                "errors": list(self.validation_state["errors"]),
            },
            "created_or_reused_objects": list(self.created_or_reused_objects),
            "ceg_nodes": list(self.ceg_nodes),
            "ceg_edges": list(self.ceg_edges),
            "ledger_bindings": [dict(b) for b in self.ledger_bindings],
            "uncertainties": [copy.deepcopy(u) for u in self.uncertainties],
            "ignored_fields": list(self.ignored_fields),
            "output_digests": dict(self.output_digests),
        }
        if self.failure_reason:
            d["failure_reason"] = self.failure_reason
        if self.caller_metadata:
            d["caller_metadata"] = copy.deepcopy(self.caller_metadata)
        return d


@dataclass
class IngestionKernelState:
    """Deterministic snapshot of the combined research-state kernel."""

    ceg: Any = None  # ClaimEvidenceGraph instance
    ledger: Any = None  # DecisionLedger instance
    objects: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    receipts: Dict[str, Any] = field(default_factory=dict)
    uncertainties: List[Dict[str, Any]] = field(default_factory=list)
    ingested_artifacts: Dict[str, str] = field(default_factory=dict)
    ingestion_receipts: Dict[str, IngestionReceipt] = field(default_factory=dict)

    def __post_init__(self):
        if self.receipts and self.ceg is not None:
            for k, r in self.receipts.items():
                self.ceg.register_receipt(k, r)

    def clone(self) -> IngestionKernelState:
        """Create a detached deep clone for transaction simulation and rollback."""
        new_ceg = copy.deepcopy(self.ceg) if self.ceg is not None else None
        new_ledger = None
        if self.ledger is not None:
            l_dict = self.ledger.to_dict()
            manifest = l_dict.get("verification_manifest", {})
            relevant_receipts = {
                k: v for k, v in self.receipts.items() if k in manifest
            }
            new_ledger = self.ledger.__class__.from_dict(
                l_dict,
                receipt_registry=relevant_receipts if relevant_receipts else None,
            )

        return IngestionKernelState(
            ceg=new_ceg,
            ledger=new_ledger,
            objects=copy.deepcopy(self.objects),
            receipts=copy.deepcopy(self.receipts),
            uncertainties=copy.deepcopy(self.uncertainties),
            ingested_artifacts=copy.deepcopy(self.ingested_artifacts),
            ingestion_receipts=copy.deepcopy(self.ingestion_receipts),
        )

    def compute_digests(self) -> Dict[str, str]:
        """Compute cryptographic state digests across active kernel primitives."""
        digests: Dict[str, str] = {}
        if self.objects:
            obj_bytes = canonical_json_bytes(
                [self.objects[k] for k in sorted(self.objects.keys())]
            )
            digests["object_registry_digest"] = compute_sha256(obj_bytes)
        if self.ceg is not None:
            digests["ceg_digest"] = self.ceg.graph_digest()
        if self.ledger is not None:
            digests["ledger_digest"] = self.ledger.ledger_digest()
        return digests

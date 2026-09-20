"""Core domain models for the Research Artifact Ingestion Bridge."""

from __future__ import annotations

import collections.abc
import copy
from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type, Union

from shared_contracts.evidence import (
    FrozenJSONMap,
    ReceiptRef,
    _thaw_val,
    canonical_json_bytes,
    compute_sha256,
    freeze_json,
    validate_lineage_receipt_contract,
)
from .contracts import (
    validate_envelope_dict,
    validate_kernel_state_dict,
    validate_receipt_dict,
)


ARTIFACT_ID_RE = re.compile(r"^art-[0-9a-f]{32}$")
INGESTION_RECEIPT_ID_RE = re.compile(r"^ingest-[0-9a-f]{32}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

VALID_KERNEL_UNCERTAINTY_KINDS = frozenset({
    # CEG
    "unverifiable_claim",
    "unresolved_contradiction",
    "missing_receipt",
    "ambiguous_locator",
    # Decision Ledger
    "decision_without_basis",
    "unsupported_negative_result",
    "unsupported_pruning",
    "unevidenced_claim_basis",
    # Ingestion bridge
    "reproducibility_gap",
    "expert_disagreement",
    "screening_ambiguity",
    "literature_coverage_gap",
    "publication_status_change",
    "retraction_alert",
    "computation_unverified",
    "quantitative_verification_gap",
    "generic_uncertainty",
})


def lineage_ref_uncertainty_dict(
    source_artifact_id: str,
    lineage_ref: ReceiptRef,
) -> Dict[str, Any]:
    """Derive the stable kernel uncertainty for an unavailable envelope lineage."""
    digest = compute_sha256(canonical_json_bytes({
        "source_artifact_id": source_artifact_id,
        "lineage_ref": lineage_ref.to_dict(),
    }))
    return {
        "item_id": f"unc-lineage-{digest[:32]}",
        "subject_id": source_artifact_id,
        "kind": "missing_receipt",
        "reason": (
            f"Envelope lineage receipt {lineage_ref.receipt_id!r} is not loaded "
            "in the kernel receipt registry"
        ),
        "needs_human": False,
        "metadata": {
            "kernel_origin": "envelope_lineage",
            "lineage_ref": lineage_ref.to_dict(),
        },
    }


def _raise_schema_errors(kind: str, errors: List[str]) -> None:
    if errors:
        raise ValueError(f"{kind} schema validation failed: {'; '.join(errors)}")


@dataclass(frozen=True)
class ArtifactEnvelope:
    """Deeply immutable envelope wrapping an artifact from any producer."""

    protocol: str
    artifact_id: str
    artifact_kind: str
    producer: Mapping[str, str]
    payload_schema: str
    payload_sha256: str
    payload: Mapping[str, Any]
    subject_refs: Tuple[str, ...] = field(default_factory=tuple)
    lineage_ref: Optional[ReceiptRef] = None
    locator: Optional[str] = None
    caller_metadata: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if self.protocol != "artifact-envelope-1.0":
            raise ValueError("protocol must be 'artifact-envelope-1.0'")
        if not ARTIFACT_ID_RE.fullmatch(str(self.artifact_id)):
            raise ValueError("artifact_id must be 'art-' followed by 32 lowercase hex characters")
        if not SHA256_RE.fullmatch(str(self.payload_sha256)):
            raise ValueError("payload_sha256 must be 64 lowercase hex characters")
        if not isinstance(self.artifact_kind, str) or not re.fullmatch(r"[a-z0-9_.-]{1,64}", self.artifact_kind):
            raise ValueError("artifact_kind must match ^[a-z0-9_.-]{1,64}$")
        if not isinstance(self.payload_schema, str) or not (1 <= len(self.payload_schema) <= 128):
            raise ValueError("payload_schema must be a non-empty string of at most 128 characters")
        if not isinstance(self.producer, collections.abc.Mapping):
            raise ValueError("producer must be a mapping")
        if set(self.producer) != {"skill", "version"}:
            raise ValueError("producer must contain exactly 'skill' and 'version'")
        producer = FrozenJSONMap(self.producer)
        for key, limit in (("skill", 128), ("version", 64)):
            value = producer[key]
            if not isinstance(value, str) or not (1 <= len(value) <= limit):
                raise ValueError(f"producer.{key} must be a non-empty string of at most {limit} characters")
        if not isinstance(self.payload, collections.abc.Mapping):
            raise ValueError("payload must be a mapping")
        payload = FrozenJSONMap(self.payload)

        refs = tuple(self.subject_refs or ())
        if any(not isinstance(ref, str) or not (1 <= len(ref) <= 256) for ref in refs):
            raise ValueError("subject_refs entries must be non-empty strings of at most 256 characters")
        if self.lineage_ref is not None and not isinstance(self.lineage_ref, ReceiptRef):
            raise TypeError("lineage_ref must be a ReceiptRef or None")
        if self.locator is not None and (
            not isinstance(self.locator, str) or not (1 <= len(self.locator) <= 2048)
        ):
            raise ValueError("locator must be a non-empty string of at most 2048 characters")
        caller = None
        if self.caller_metadata is not None:
            if not isinstance(self.caller_metadata, collections.abc.Mapping):
                raise TypeError("caller_metadata must be a mapping or None")
            caller = FrozenJSONMap(self.caller_metadata)

        object.__setattr__(self, "producer", producer)
        object.__setattr__(self, "payload", payload)
        object.__setattr__(self, "subject_refs", refs)
        object.__setattr__(self, "caller_metadata", caller)
        self.assert_integrity()
        _raise_schema_errors("ArtifactEnvelope", validate_envelope_dict(self.to_dict()))

    def assert_integrity(self) -> None:
        """Re-assert content identity at every trust-boundary dispatch."""
        actual = compute_sha256(canonical_json_bytes(_thaw_val(self.payload)))
        if self.payload_sha256 != actual:
            raise ValueError(
                f"Payload hash mismatch: declared {self.payload_sha256}, recomputed {actual}"
            )
        expected_id = f"art-{actual[:32]}"
        if self.artifact_id != expected_id:
            raise ValueError(
                f"artifact_id content-addressing mismatch: declared {self.artifact_id}, expected {expected_id}"
            )

    def ingestion_context_digest(self, bindings: Optional[Mapping[str, Any]] = None) -> str:
        """Hash every mutation-affecting wrapper field and explicit caller binding.

        ``caller_metadata`` is per-call correlation context and must never
        cause an already-applied state mutation to run again.
        """
        context = {
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "producer": _thaw_val(self.producer),
            "payload_schema": self.payload_schema,
            "subject_refs": list(self.subject_refs),
            "lineage_ref": self.lineage_ref.to_dict() if self.lineage_ref else None,
            "locator": self.locator,
            "bindings": _thaw_val(bindings or {}),
        }
        return compute_sha256(canonical_json_bytes(context))

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
    ) -> "ArtifactEnvelope":
        thawed = _thaw_val(payload)
        payload_sha = compute_sha256(canonical_json_bytes(thawed))
        return cls(
            protocol="artifact-envelope-1.0",
            artifact_id=f"art-{payload_sha[:32]}",
            artifact_kind=artifact_kind,
            producer={"skill": producer_skill, "version": producer_version},
            payload_schema=payload_schema,
            payload_sha256=payload_sha,
            payload=thawed,
            subject_refs=tuple(subject_refs or ()),
            lineage_ref=lineage_ref,
            locator=locator,
            caller_metadata=caller_metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "protocol": self.protocol,
            "artifact_id": self.artifact_id,
            "artifact_kind": self.artifact_kind,
            "producer": _thaw_val(self.producer),
            "payload_schema": self.payload_schema,
            "payload_sha256": self.payload_sha256,
            "payload": _thaw_val(self.payload),
        }
        if self.subject_refs:
            data["subject_refs"] = list(self.subject_refs)
        if self.lineage_ref is not None:
            data["lineage_ref"] = self.lineage_ref.to_dict()
        if self.locator is not None:
            data["locator"] = self.locator
        if self.caller_metadata is not None:
            data["caller_metadata"] = _thaw_val(self.caller_metadata)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ArtifactEnvelope":
        if not isinstance(data, collections.abc.Mapping):
            raise TypeError("ArtifactEnvelope.from_dict expects a mapping")
        _raise_schema_errors("ArtifactEnvelope", validate_envelope_dict(data))
        lineage_ref = None
        if data.get("lineage_ref"):
            lineage_ref = ReceiptRef(**dict(data["lineage_ref"]))
        return cls(
            protocol=data["protocol"],
            artifact_id=data["artifact_id"],
            artifact_kind=data["artifact_kind"],
            producer=data["producer"],
            payload_schema=data["payload_schema"],
            payload_sha256=data["payload_sha256"],
            payload=data["payload"],
            subject_refs=tuple(data.get("subject_refs") or ()),
            lineage_ref=lineage_ref,
            locator=data.get("locator"),
            caller_metadata=data.get("caller_metadata"),
        )


@dataclass(frozen=True)
class IngestionReceipt:
    """Deeply immutable, content-addressed result of one ingestion attempt."""

    protocol: str
    receipt_id: str
    source_artifact_id: str
    source_artifact_sha256: str
    adapter_id: str
    adapter_version: str
    status: str
    validation_state: Mapping[str, Any]
    output_digests: Mapping[str, str]
    ingestion_context_digest: Optional[str] = None
    source_lineage_ref: Optional[ReceiptRef] = None
    created_or_reused_objects: Tuple[str, ...] = field(default_factory=tuple)
    ceg_nodes: Tuple[str, ...] = field(default_factory=tuple)
    ceg_edges: Tuple[str, ...] = field(default_factory=tuple)
    ledger_bindings: Tuple[Mapping[str, str], ...] = field(default_factory=tuple)
    uncertainties: Tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    ignored_fields: Tuple[str, ...] = field(default_factory=tuple)
    failure_reason: Optional[str] = None
    caller_metadata: Optional[Mapping[str, Any]] = None

    def __post_init__(self) -> None:
        if self.protocol != "ingestion-receipt-1.0":
            raise ValueError("protocol must be 'ingestion-receipt-1.0'")
        if not INGESTION_RECEIPT_ID_RE.fullmatch(str(self.receipt_id)):
            raise ValueError("receipt_id must be 'ingest-' followed by 32 lowercase hex characters")
        if not ARTIFACT_ID_RE.fullmatch(str(self.source_artifact_id)):
            raise ValueError("source_artifact_id has invalid format")
        if not SHA256_RE.fullmatch(str(self.source_artifact_sha256)):
            raise ValueError("source_artifact_sha256 has invalid format")
        if self.status not in {"accepted", "rejected", "partial"}:
            raise ValueError("status must be accepted, rejected, or partial")
        if self.ingestion_context_digest is not None and not SHA256_RE.fullmatch(
            str(self.ingestion_context_digest)
        ):
            raise ValueError("ingestion_context_digest must be 64 lowercase hex characters")
        if self.status == "accepted" and self.ingestion_context_digest is None:
            raise ValueError("accepted ingestion receipts require ingestion_context_digest")
        if self.source_lineage_ref is not None and not isinstance(
            self.source_lineage_ref, ReceiptRef
        ):
            raise TypeError("source_lineage_ref must be a ReceiptRef or None")

        validation = FrozenJSONMap(self.validation_state)
        output = FrozenJSONMap(self.output_digests)
        bindings = tuple(FrozenJSONMap(value) for value in self.ledger_bindings)
        uncertainties = tuple(FrozenJSONMap(value) for value in self.uncertainties)
        caller = FrozenJSONMap(self.caller_metadata) if self.caller_metadata is not None else None
        object.__setattr__(self, "validation_state", validation)
        object.__setattr__(self, "output_digests", output)
        object.__setattr__(self, "created_or_reused_objects", tuple(self.created_or_reused_objects))
        object.__setattr__(self, "ceg_nodes", tuple(self.ceg_nodes))
        object.__setattr__(self, "ceg_edges", tuple(self.ceg_edges))
        object.__setattr__(self, "ledger_bindings", bindings)
        object.__setattr__(self, "uncertainties", uncertainties)
        object.__setattr__(self, "ignored_fields", tuple(self.ignored_fields))
        object.__setattr__(self, "caller_metadata", caller)

        expected = self._derive_receipt_id(
            source_artifact_id=self.source_artifact_id,
            source_artifact_sha256=self.source_artifact_sha256,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            status=self.status,
            ingestion_context_digest=self.ingestion_context_digest,
            source_lineage_ref=self.source_lineage_ref,
            validation_state=validation,
            output_digests=output,
            created_or_reused_objects=self.created_or_reused_objects,
            ceg_nodes=self.ceg_nodes,
            ceg_edges=self.ceg_edges,
            ledger_bindings=bindings,
            uncertainties=uncertainties,
            ignored_fields=self.ignored_fields,
            failure_reason=self.failure_reason,
            caller_metadata=caller,
        )
        if self.receipt_id != expected:
            raise ValueError(
                f"receipt_id content-addressing mismatch: declared {self.receipt_id}, expected {expected}"
            )
        _raise_schema_errors("IngestionReceipt", validate_receipt_dict(self.to_dict()))

    @staticmethod
    def _identity_payload(
        *,
        source_artifact_id: str,
        source_artifact_sha256: str,
        adapter_id: str,
        adapter_version: str,
        status: str,
        ingestion_context_digest: Optional[str],
        source_lineage_ref: Optional[ReceiptRef],
        validation_state: Mapping[str, Any],
        output_digests: Mapping[str, Any],
        created_or_reused_objects: Tuple[str, ...],
        ceg_nodes: Tuple[str, ...],
        ceg_edges: Tuple[str, ...],
        ledger_bindings: Tuple[Mapping[str, Any], ...],
        uncertainties: Tuple[Mapping[str, Any], ...],
        ignored_fields: Tuple[str, ...],
        failure_reason: Optional[str],
        caller_metadata: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "source_artifact_id": source_artifact_id,
            "source_artifact_sha256": source_artifact_sha256,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "status": status,
            "ingestion_context_digest": ingestion_context_digest or "",
            "source_lineage_ref": (
                source_lineage_ref.to_dict() if source_lineage_ref else None
            ),
            "validation_state": _thaw_val(validation_state),
            "output_digests": dict(sorted(_thaw_val(output_digests).items())),
            "created_or_reused_objects": sorted(created_or_reused_objects),
            "ceg_nodes": sorted(ceg_nodes),
            "ceg_edges": sorted(ceg_edges),
            "ledger_bindings": sorted(
                (_thaw_val(value) for value in ledger_bindings),
                key=lambda value: canonical_json_bytes(value),
            ),
            "uncertainties": sorted(
                (_thaw_val(value) for value in uncertainties),
                key=lambda value: canonical_json_bytes(value),
            ),
            "ignored_fields": sorted(ignored_fields),
            "failure_reason": failure_reason or "",
            # Caller metadata is correlation context, not mutation content; it
            # is preserved on the receipt but intentionally excluded from the
            # receipt's content-addressed identity.
        }

    @classmethod
    def _derive_receipt_id(cls, **kwargs: Any) -> str:
        digest = compute_sha256(canonical_json_bytes(cls._identity_payload(**kwargs)))
        return f"ingest-{digest[:32]}"

    @classmethod
    def create(
        cls,
        envelope: ArtifactEnvelope,
        adapter_id: str,
        adapter_version: str,
        status: str,
        valid: bool,
        errors: List[str],
        output_digests: Mapping[str, str],
        ingestion_context_digest: Optional[str] = None,
        created_or_reused_objects: Optional[List[str]] = None,
        ceg_nodes: Optional[List[str]] = None,
        ceg_edges: Optional[List[str]] = None,
        ledger_bindings: Optional[List[Mapping[str, str]]] = None,
        uncertainties: Optional[List[Mapping[str, Any]]] = None,
        ignored_fields: Optional[List[str]] = None,
        failure_reason: Optional[str] = None,
        caller_metadata: Optional[Mapping[str, Any]] = None,
    ) -> "IngestionReceipt":
        validation_state = {"valid": valid, "errors": list(errors)}
        values = {
            "source_artifact_id": envelope.artifact_id,
            "source_artifact_sha256": envelope.payload_sha256,
            "adapter_id": adapter_id,
            "adapter_version": adapter_version,
            "status": status,
            "ingestion_context_digest": ingestion_context_digest,
            "source_lineage_ref": envelope.lineage_ref,
            "validation_state": validation_state,
            "output_digests": output_digests,
            "created_or_reused_objects": tuple(created_or_reused_objects or ()),
            "ceg_nodes": tuple(ceg_nodes or ()),
            "ceg_edges": tuple(ceg_edges or ()),
            "ledger_bindings": tuple(ledger_bindings or ()),
            "uncertainties": tuple(uncertainties or ()),
            "ignored_fields": tuple(ignored_fields or ()),
            "failure_reason": failure_reason,
            "caller_metadata": caller_metadata,
        }
        receipt_id = cls._derive_receipt_id(**values)
        return cls(
            protocol="ingestion-receipt-1.0",
            receipt_id=receipt_id,
            **values,
        )

    def to_dict(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "protocol": self.protocol,
            "receipt_id": self.receipt_id,
            "source_artifact_id": self.source_artifact_id,
            "source_artifact_sha256": self.source_artifact_sha256,
            "adapter_id": self.adapter_id,
            "adapter_version": self.adapter_version,
            "status": self.status,
            "validation_state": _thaw_val(self.validation_state),
            "created_or_reused_objects": list(self.created_or_reused_objects),
            "ceg_nodes": list(self.ceg_nodes),
            "ceg_edges": list(self.ceg_edges),
            "ledger_bindings": [_thaw_val(value) for value in self.ledger_bindings],
            "uncertainties": [_thaw_val(value) for value in self.uncertainties],
            "ignored_fields": list(self.ignored_fields),
            "output_digests": _thaw_val(self.output_digests),
        }
        if self.ingestion_context_digest is not None:
            data["ingestion_context_digest"] = self.ingestion_context_digest
        if self.source_lineage_ref is not None:
            data["source_lineage_ref"] = self.source_lineage_ref.to_dict()
        if self.failure_reason is not None:
            data["failure_reason"] = self.failure_reason
        if self.caller_metadata is not None:
            data["caller_metadata"] = _thaw_val(self.caller_metadata)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IngestionReceipt":
        if not isinstance(data, collections.abc.Mapping):
            raise TypeError("IngestionReceipt.from_dict expects a mapping")
        _raise_schema_errors("IngestionReceipt", validate_receipt_dict(data))
        return cls(
            protocol=data["protocol"],
            receipt_id=data["receipt_id"],
            source_artifact_id=data["source_artifact_id"],
            source_artifact_sha256=data["source_artifact_sha256"],
            adapter_id=data["adapter_id"],
            adapter_version=data["adapter_version"],
            status=data["status"],
            ingestion_context_digest=data.get("ingestion_context_digest"),
            source_lineage_ref=(
                ReceiptRef(**data["source_lineage_ref"])
                if data.get("source_lineage_ref")
                else None
            ),
            validation_state=data.get("validation_state", {"valid": False, "errors": []}),
            output_digests=data["output_digests"],
            created_or_reused_objects=tuple(data.get("created_or_reused_objects") or ()),
            ceg_nodes=tuple(data.get("ceg_nodes") or ()),
            ceg_edges=tuple(data.get("ceg_edges") or ()),
            ledger_bindings=tuple(data.get("ledger_bindings") or ()),
            uncertainties=tuple(data.get("uncertainties") or ()),
            ignored_fields=tuple(data.get("ignored_fields") or ()),
            failure_reason=data.get("failure_reason"),
            caller_metadata=data.get("caller_metadata"),
        )

    def with_caller_metadata(
        self, caller_metadata: Optional[Mapping[str, Any]]
    ) -> "IngestionReceipt":
        """Return this content-addressed result with fresh call correlation context."""
        data = self.to_dict()
        if caller_metadata is None:
            data.pop("caller_metadata", None)
        else:
            data["caller_metadata"] = _thaw_val(caller_metadata)
        return IngestionReceipt.from_dict(data)


def _normalise_uncertainty(value: Mapping[str, Any]) -> FrozenJSONMap:
    if not isinstance(value, collections.abc.Mapping):
        raise TypeError("Kernel uncertainty must be a mapping")
    allowed = {"item_id", "subject_id", "kind", "reason", "needs_human", "metadata"}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"Unknown uncertainty fields: {sorted(unknown)}")
    required = {"item_id", "subject_id", "kind", "reason", "needs_human"}
    missing = required - set(value)
    if missing:
        raise ValueError(f"Missing uncertainty fields: {sorted(missing)}")
    for key in ("item_id", "subject_id", "reason"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"uncertainty.{key} must be a non-empty string")
    if value["kind"] not in VALID_KERNEL_UNCERTAINTY_KINDS:
        raise ValueError(
            f"Invalid kernel uncertainty kind {value['kind']!r}; "
            f"expected one of {sorted(VALID_KERNEL_UNCERTAINTY_KINDS)}"
        )
    if not isinstance(value["needs_human"], bool):
        raise ValueError("uncertainty.needs_human must be a boolean")
    if "metadata" in value and not isinstance(value["metadata"], collections.abc.Mapping):
        raise ValueError("uncertainty.metadata must be an object")
    return FrozenJSONMap(value)


def _receipt_conflict_payload(value: Any) -> Any:
    """Return identity-bearing data for duplicate receipt registration.

    A lineage receipt timestamp is excluded from both of its declared
    identities. Repeated producer runs may therefore emit the same receipt at
    different times without constituting conflicting physical evidence.
    """
    payload = _thaw_val(value)
    if isinstance(payload, dict) and payload.get("protocol") == "lineage-receipt-1.0":
        payload = dict(payload)
        payload.pop("timestamp", None)
    return payload


@dataclass
class IngestionKernelState:
    """Combined deterministic kernel state with strict snapshot round-tripping."""

    ceg: Any = None
    ledger: Any = None
    objects: Dict[str, Mapping[str, Any]] = field(default_factory=dict)
    receipts: Dict[str, Any] = field(default_factory=dict)
    uncertainties: List[Mapping[str, Any]] = field(default_factory=list)
    ingested_artifacts: Dict[str, str] = field(default_factory=dict)
    ingestion_receipts: Dict[str, IngestionReceipt] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.objects = {
            str(key): FrozenJSONMap(_thaw_val(value)) for key, value in self.objects.items()
        }
        self.receipts = {
            str(key): FrozenJSONMap(_thaw_val(value))
            for key, value in self.receipts.items()
        }
        existing_uncertainties = list(self.uncertainties)
        self.uncertainties = []
        for value in existing_uncertainties:
            self.add_uncertainty(value)
        self.ingested_artifacts = dict(self.ingested_artifacts)
        self.ingestion_receipts = {
            str(key): (
                value if isinstance(value, IngestionReceipt) else IngestionReceipt.from_dict(value)
            )
            for key, value in self.ingestion_receipts.items()
        }
        self._synchronise_receipts()

    def _synchronise_receipts(self) -> None:
        for key, value in self.receipts.items():
            if self.ceg is not None:
                self.ceg.register_receipt(key, value)
            if self.ledger is not None:
                self.ledger.register_receipt(key, value)

    def register_object(self, object_id: str, value: Mapping[str, Any]) -> None:
        frozen = FrozenJSONMap(_thaw_val(value))
        existing = self.objects.get(object_id)
        if (
            existing is not None
            and canonical_json_bytes(_thaw_val(existing))
            != canonical_json_bytes(_thaw_val(frozen))
        ):
            existing_raw = _thaw_val(existing)
            incoming_raw = _thaw_val(frozen)
            is_work_placeholder = existing_raw == {
                "id": object_id,
                "kind": "work",
            }
            is_canonical_work = (
                isinstance(incoming_raw, dict)
                and all(
                    key in incoming_raw
                    for key in ("work_type", "title", "authors")
                )
            )
            if is_work_placeholder and is_canonical_work:
                self.objects[object_id] = frozen
                return
            raise ValueError(
                f"ResearchObject ID collision for {object_id!r}: existing object differs"
            )
        self.objects[object_id] = frozen

    def register_receipt(self, key: str, value: Any) -> None:
        snapshot = FrozenJSONMap(_thaw_val(value))
        if key in self.receipts:
            existing = _receipt_conflict_payload(self.receipts[key])
            incoming = _receipt_conflict_payload(snapshot)
            if canonical_json_bytes(existing) != canonical_json_bytes(incoming):
                raise ValueError(f"Conflicting physical receipt registration for {key!r}")
            # Keep the first physical emission. Timestamp-only variants share
            # the exact same verified receipt identity and need no re-register.
            return
        self.receipts[key] = snapshot
        if self.ceg is not None:
            self.ceg.register_receipt(key, snapshot)
        if self.ledger is not None:
            self.ledger.register_receipt(key, snapshot)

    def add_uncertainty(self, value: Mapping[str, Any]) -> None:
        frozen = _normalise_uncertainty(value)
        item_id = frozen["item_id"]
        for existing in self.uncertainties:
            if existing["item_id"] == item_id:
                if _thaw_val(existing) != _thaw_val(frozen):
                    raise ValueError(f"Uncertainty ID collision for {item_id!r}")
                return
        self.uncertainties.append(frozen)
        self.uncertainties.sort(key=lambda item: item["item_id"])

    def clone(self) -> "IngestionKernelState":
        """Detached transactional clone without replaying the complete ledger."""
        return IngestionKernelState(
            ceg=copy.deepcopy(self.ceg),
            ledger=copy.deepcopy(self.ledger),
            objects=copy.deepcopy(self.objects),
            receipts=copy.deepcopy(self.receipts),
            uncertainties=copy.deepcopy(self.uncertainties),
            ingested_artifacts=copy.deepcopy(self.ingested_artifacts),
            ingestion_receipts=copy.deepcopy(self.ingestion_receipts),
        )

    def validate_invariants(self) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        try:
            self._synchronise_receipts()
        except Exception as exc:
            errors.append(f"receipt registry mismatch: {exc}")
        if self.ceg is not None:
            valid, graph_errors = self.ceg.validate_graph()
            if not valid:
                errors.extend(f"CEG: {error}" for error in graph_errors)
        if self.ledger is not None:
            valid, ledger_errors = self.ledger.validate_ledger()
            if not valid:
                errors.extend(f"Ledger: {error}" for error in ledger_errors)
        try:
            normalised = [_normalise_uncertainty(value) for value in self.uncertainties]
            ids = [value["item_id"] for value in normalised]
            if len(ids) != len(set(ids)):
                errors.append("Kernel uncertainty item_id values must be unique")
        except Exception as exc:
            errors.append(f"Uncertainty state: {exc}")
        for artifact_id, payload_sha in self.ingested_artifacts.items():
            if not ARTIFACT_ID_RE.fullmatch(artifact_id) or not SHA256_RE.fullmatch(payload_sha):
                errors.append(f"Invalid ingested artifact identity {artifact_id!r}")

        ceg_node_ids = set()
        ceg_edge_ids = set()
        if self.ceg is not None:
            ceg_data = self.ceg.to_dict()
            ceg_node_ids.update(item["id"] for item in ceg_data.get("claims", []))
            ceg_node_ids.update(
                item["id"] for item in ceg_data.get("evidence_anchors", [])
            )
            ceg_edge_ids.update(
                compute_sha256(canonical_json_bytes(item))
                for item in ceg_data.get("support_edges", [])
            )

        ledger_decisions: Dict[str, str] = {}
        ledger_bases: set[Tuple[str, str, str, str]] = set()
        ledger_forks: Dict[Tuple[str, str], str] = {}
        ledger_state_events: Dict[Tuple[str, str], str] = {}
        ledger_corrections: Dict[Tuple[str, str], str] = {}
        if self.ledger is not None:
            ledger_data = self.ledger.to_dict()
            ledger_decisions.update({
                item["id"]: compute_sha256(canonical_json_bytes(item))
                for item in ledger_data.get("decisions", [])
            })
            for item in ledger_data.get("bases", []):
                ledger_bases.add((
                    item["decision_id"],
                    item["basis_kind"],
                    item["basis_id"],
                    compute_sha256(canonical_json_bytes(item)),
                ))
            for item in ledger_data.get("forks", []):
                record_digest = compute_sha256(canonical_json_bytes(item))
                ledger_forks[(item["decision_id"], record_digest)] = record_digest
            for item in ledger_data.get("state_events", []):
                ledger_state_events[(
                    item["decision_id"],
                    item["event_id"],
                )] = compute_sha256(canonical_json_bytes(item))
            for item in ledger_data.get("corrections", []):
                ledger_corrections[(
                    item["decision_id"],
                    item["correction_id"],
                )] = compute_sha256(canonical_json_bytes(item))

        for cache_key, receipt in self.ingestion_receipts.items():
            expected_sha = self.ingested_artifacts.get(receipt.source_artifact_id)
            if expected_sha is None:
                errors.append(
                    f"Ingestion receipt cache {cache_key!r} references unregistered artifact "
                    f"{receipt.source_artifact_id!r}"
                )
            elif expected_sha != receipt.source_artifact_sha256:
                errors.append(
                    f"Ingestion receipt cache {cache_key!r} payload SHA conflicts with artifact registry"
                )
            if receipt.status != "accepted":
                errors.append(
                    f"Ingestion receipt cache {cache_key!r} contains a non-accepted receipt"
                )
            elif receipt.ingestion_context_digest is None:
                errors.append(
                    f"Ingestion receipt cache {cache_key!r} lacks an ingestion context digest"
                )
            else:
                expected_cache_key = (
                    f"{receipt.source_artifact_id}:"
                    f"{receipt.ingestion_context_digest}"
                )
                if cache_key != expected_cache_key:
                    errors.append(
                        f"Ingestion receipt cache key {cache_key!r} does not match "
                        f"the receipt context {expected_cache_key!r}"
                    )

            for object_id in receipt.created_or_reused_objects:
                if object_id not in self.objects:
                    errors.append(
                        f"Ingestion receipt cache {cache_key!r} references missing "
                        f"ResearchObject {object_id!r}"
                    )
            for node_id in receipt.ceg_nodes:
                if node_id not in ceg_node_ids:
                    errors.append(
                        f"Ingestion receipt cache {cache_key!r} references missing "
                        f"CEG node {node_id!r}"
                    )
            for edge_id in receipt.ceg_edges:
                if edge_id not in ceg_edge_ids:
                    errors.append(
                        f"Ingestion receipt cache {cache_key!r} references missing "
                        f"CEG edge {edge_id!r}"
                    )
            if (
                receipt.adapter_id == "adapter-decision-ledger"
                and not receipt.ledger_bindings
            ):
                errors.append(
                    f"Ingestion receipt cache {cache_key!r} lacks Decision Ledger "
                    "mutation references"
                )
            for raw_binding in receipt.ledger_bindings:
                binding = _thaw_val(raw_binding)
                decision_id = binding.get("decision_id")
                binding_kind = binding.get("binding_kind")
                basis_id = binding.get("basis_id")
                record_digest = binding.get("record_digest")
                if binding_kind == "ledger_decision":
                    retained = (
                        decision_id == basis_id
                        and ledger_decisions.get(decision_id)
                        == record_digest
                    )
                elif binding_kind == "ledger_fork":
                    retained = ledger_forks.get((decision_id, basis_id)) == record_digest
                elif binding_kind == "ledger_state_event":
                    retained = (
                        ledger_state_events.get((decision_id, basis_id))
                        == record_digest
                    )
                elif binding_kind == "outcome_correction":
                    retained = (
                        ledger_corrections.get((decision_id, basis_id))
                        == record_digest
                    )
                else:
                    retained = (
                        decision_id,
                        binding_kind,
                        basis_id,
                        record_digest,
                    ) in ledger_bases
                if not retained:
                    errors.append(
                        f"Ingestion receipt cache {cache_key!r} references missing "
                        f"Ledger binding {binding!r}"
                    )

            lineage_ref = receipt.source_lineage_ref
            if lineage_ref is not None:
                physical = self.receipts.get(lineage_ref.receipt_id)
                if physical is None:
                    expected_uncertainty = lineage_ref_uncertainty_dict(
                        receipt.source_artifact_id,
                        lineage_ref,
                    )["item_id"]
                    if expected_uncertainty not in {
                        value["item_id"] for value in self.uncertainties
                    }:
                        errors.append(
                            f"Ingestion receipt cache {cache_key!r} has an unresolved "
                            "lineage_ref without its missing_receipt uncertainty"
                        )
                else:
                    ok, error = validate_lineage_receipt_contract(
                        lineage_ref,
                        physical,
                    )
                    if not ok:
                        errors.append(
                            f"Ingestion receipt cache {cache_key!r} lineage_ref is invalid: "
                            f"{error}"
                        )
        return not errors, errors

    def compute_digests(self) -> Dict[str, str]:
        """Digest every first-class, non-circular kernel content registry."""
        object_entries = [
            {"registry_key": key, "value": _thaw_val(self.objects[key])}
            for key in sorted(self.objects)
        ]
        receipt_entries = [
            {"registry_key": key, "value": _thaw_val(self.receipts[key])}
            for key in sorted(self.receipts)
        ]
        uncertainty_entries = sorted(
            (_thaw_val(value) for value in self.uncertainties),
            key=lambda value: canonical_json_bytes(value),
        )
        artifact_entries = [
            {"artifact_id": key, "payload_sha256": self.ingested_artifacts[key]}
            for key in sorted(self.ingested_artifacts)
        ]
        digests: Dict[str, str] = {
            "object_registry_digest": compute_sha256(canonical_json_bytes(object_entries)),
            "receipt_registry_digest": compute_sha256(canonical_json_bytes(receipt_entries)),
            "uncertainty_state_digest": compute_sha256(canonical_json_bytes(uncertainty_entries)),
            "ingested_artifact_digest": compute_sha256(canonical_json_bytes(artifact_entries)),
        }
        if self.ceg is not None:
            digests["ceg_digest"] = self.ceg.graph_digest()
        if self.ledger is not None:
            digests["ledger_digest"] = self.ledger.ledger_digest()
        digests["kernel_content_digest"] = compute_sha256(
            canonical_json_bytes(dict(sorted(digests.items())))
        )
        return digests

    def _snapshot_payload(self) -> Dict[str, Any]:
        return {
            "protocol": "ingestion-kernel-state-1.0",
            "ceg": self.ceg.to_dict() if self.ceg is not None else None,
            "ledger": self.ledger.to_dict() if self.ledger is not None else None,
            "objects": {key: _thaw_val(self.objects[key]) for key in sorted(self.objects)},
            "receipts": {key: _thaw_val(self.receipts[key]) for key in sorted(self.receipts)},
            "uncertainties": [
                _thaw_val(value)
                for value in sorted(self.uncertainties, key=lambda item: item["item_id"])
            ],
            "ingested_artifacts": dict(sorted(self.ingested_artifacts.items())),
            "ingestion_receipts": {
                key: self.ingestion_receipts[key].to_dict()
                for key in sorted(self.ingestion_receipts)
            },
            "content_digests": self.compute_digests(),
        }

    def to_dict(self) -> Dict[str, Any]:
        payload = self._snapshot_payload()
        payload["snapshot_digest"] = compute_sha256(canonical_json_bytes(payload))
        _raise_schema_errors("IngestionKernelState", validate_kernel_state_dict(payload))
        return payload

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        ceg_cls: Type[Any],
        ledger_cls: Type[Any],
    ) -> "IngestionKernelState":
        if not isinstance(data, collections.abc.Mapping):
            raise TypeError("IngestionKernelState.from_dict expects a mapping")
        _raise_schema_errors("IngestionKernelState", validate_kernel_state_dict(data))
        raw = _thaw_val(data)
        declared = raw.pop("snapshot_digest")
        actual = compute_sha256(canonical_json_bytes(raw))
        if declared != actual:
            raise ValueError(
                f"Kernel snapshot tampering detected: declared {declared}, recomputed {actual}"
            )
        receipts = copy.deepcopy(raw["receipts"])
        ceg = ceg_cls.from_dict(raw["ceg"], receipt_registry=receipts) if raw["ceg"] else None
        ledger = (
            ledger_cls.from_dict(raw["ledger"], receipt_registry=receipts)
            if raw["ledger"]
            else None
        )
        state = cls(
            ceg=ceg,
            ledger=ledger,
            objects=raw["objects"],
            receipts=receipts,
            uncertainties=raw["uncertainties"],
            ingested_artifacts=raw["ingested_artifacts"],
            ingestion_receipts={
                key: IngestionReceipt.from_dict(value)
                for key, value in raw["ingestion_receipts"].items()
            },
        )
        if state.compute_digests() != raw["content_digests"]:
            raise ValueError("Kernel snapshot content digests do not match replayed state")
        valid, errors = state.validate_invariants()
        if not valid:
            raise ValueError(f"Kernel snapshot invariant failure: {'; '.join(errors)}")
        return state

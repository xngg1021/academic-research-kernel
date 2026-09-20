"""Shared Evidence Contract & Receipt Verification Primitives.

This module provides the canonical, cross-capability implementation of receipt
references, serialization, and contract verification across ResearchObject
Identity, Claim-Evidence Graph, and Decision Ledger.
"""

from __future__ import annotations

import collections.abc
from collections import deque
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import heapq
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Dict, Iterator, List, Mapping, Optional, Set, Tuple, Union

VALID_RECEIPT_KINDS = frozenset({"lineage", "academic_evidence"})
VALID_EVIDENCE_TYPES = frozenset({"metadata", "citation_count", "update_signal", "full_text", "computed"})
VALID_LINEAGE_ENTITY_TYPES = frozenset({
    "data_snapshot",
    "code_file",
    "environment_spec",
    "statistic_artifact",
    "table_cell",
    "figure_artifact",
    "generic_entity",
})
VALID_LINEAGE_ACTIVITY_TYPES = frozenset({
    "data_cleaning",
    "computation_run",
    "statistical_analysis",
    "table_extraction",
    "render_run",
    "generic_activity",
})
SHA256_REGEX = re.compile(r"^[0-9a-f]{64}$")
REMOTE_LOCATOR_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


@dataclass(frozen=True)
class LineageVerificationContext:
    """Invocation-scoped authority; never serialized into evidence or snapshots.

    Trusted hosts may authorize a root and a larger cumulative byte budget.
    Wire clients can supply bounded bytes, but cannot authorize host paths.
    """

    content_root: Optional[Union[str, Path]] = None
    content_by_entity_id: Optional[Mapping[str, bytes]] = None
    authorized_paths: Tuple[Path, ...] = ()
    max_content_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        if type(self.max_content_bytes) is not int or self.max_content_bytes < 0:
            raise ValueError("max_content_bytes must be a non-negative integer")
        if self.content_root is not None:
            object.__setattr__(self, "content_root", Path(self.content_root).resolve())
        object.__setattr__(self, "authorized_paths", tuple(sorted({Path(p).resolve() for p in self.authorized_paths})))
        if self.content_by_entity_id is not None:
            values = dict(self.content_by_entity_id)
            if any(not isinstance(k, str) or not isinstance(v, bytes) for k, v in values.items()):
                raise TypeError("content_by_entity_id must map string entity IDs to bytes")
            if sum(map(len, values.values())) > self.max_content_bytes:
                raise ValueError("Authorized lineage content exceeds the read-size budget")
            object.__setattr__(self, "content_by_entity_id", MappingProxyType(values))

    def __deepcopy__(self, memo: Dict[int, Any]) -> "LineageVerificationContext":
        return self

    def content_options(self) -> Dict[str, Any]:
        return {"content_root": self.content_root,
                "content_by_entity_id": self.content_by_entity_id,
                "max_content_bytes": self.max_content_bytes,
                "authorized_paths": self.authorized_paths}


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


def _replay_lineage_content_verification(
    entities: List[Mapping[str, Any]],
    *,
    check_on_disk_hashes: bool,
    content_root: Optional[Union[str, Path]] = None,
    content_by_entity_id: Optional[Mapping[str, bytes]] = None,
    max_content_bytes: int = 10 * 1024 * 1024,
    authorized_paths: Tuple[Path, ...] = (),
) -> Tuple[str, str, Optional[str]]:
    """Reproduce content checks through an explicit, size-bounded authority.

    Receipt locators are untrusted data.  They are never opened unless the
    caller explicitly supplies ``content_root``; even then, resolved paths must
    remain inside that root and the cumulative read budget is enforced.
    Callers may instead provide already-authorized bytes by entity ID.
    """
    if not check_on_disk_hashes:
        return "unchecked", "unchecked", None
    if type(max_content_bytes) is not int or max_content_bytes < 0:
        raise ValueError("max_content_bytes must be a non-negative integer")

    authorized_root: Optional[Path] = None
    if content_root is not None:
        authorized_root = Path(content_root).resolve(strict=True)
        if not authorized_root.is_dir():
            raise ValueError("content_root must resolve to an existing directory")
    supplied_content = content_by_entity_id or {}
    if not isinstance(supplied_content, collections.abc.Mapping):
        raise TypeError("content_by_entity_id must be a mapping of entity IDs to bytes")

    total_hashed = 0
    verified_hashed = 0
    unanchored_relatives = 0
    unauthorized_locals = 0
    consumed_bytes = 0
    for entity in entities:
        declared_sha = entity.get("sha256")
        locator = entity.get("locator")
        if not declared_sha or not locator:
            continue
        total_hashed += 1
        entity_id = entity.get("id")
        supplied = supplied_content.get(entity_id)
        if supplied is not None:
            if not isinstance(supplied, bytes):
                raise TypeError(
                    f"Authorized content for entity {entity_id!r} must be bytes"
                )
            consumed_bytes += len(supplied)
            if consumed_bytes > max_content_bytes:
                raise ValueError("Authorized lineage content exceeds the read-size budget")
            computed = hashlib.sha256(supplied).hexdigest().lower()
            if computed != str(declared_sha).lower():
                return (
                    "hash_mismatch",
                    "hash_mismatch",
                    f"Content hash mismatch on entity {entity_id!r}: "
                    f"expected {declared_sha}, got {computed}",
                )
            verified_hashed += 1
            continue

        locator_text = str(locator).strip()
        if (
            REMOTE_LOCATOR_REGEX.match(locator_text)
            or locator_text.startswith(("urn:", "doi:"))
        ):
            continue
        candidate_path = Path(locator_text.split("#", 1)[0].split("?", 1)[0])
        exact_path_authorized = candidate_path.is_absolute() and candidate_path.resolve() in authorized_paths
        if authorized_root is None and not exact_path_authorized:
            if Path(locator_text.split("#", 1)[0].split("?", 1)[0]).is_absolute():
                unauthorized_locals += 1
            else:
                unanchored_relatives += 1
            continue
        clean_path = locator_text.split("#", 1)[0].split("?", 1)[0]
        path = Path(clean_path)
        resolved = (
            path.resolve()
            if path.is_absolute()
            else (authorized_root / path).resolve()
        )
        if not exact_path_authorized:
            try:
                resolved.relative_to(authorized_root)
            except ValueError:
                unauthorized_locals += 1
                continue
        if not resolved.is_file():
            return (
                "missing_artifact",
                "missing_artifact",
                f"Entity {entity.get('id')!r} declared SHA256 and local locator "
                f"{locator!r}, but file does not exist on disk.",
            )
        size = resolved.stat().st_size
        if consumed_bytes + size > max_content_bytes:
            raise ValueError("Authorized lineage content exceeds the read-size budget")
        digest = hashlib.sha256()
        with resolved.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                consumed_bytes += len(chunk)
                if consumed_bytes > max_content_bytes:
                    raise ValueError(
                        "Authorized lineage content exceeds the read-size budget"
                    )
                digest.update(chunk)
        computed = digest.hexdigest().lower()
        if computed != str(declared_sha).lower():
            return (
                "hash_mismatch",
                "hash_mismatch",
                f"Content hash mismatch on entity {entity.get('id')!r}: "
                f"expected {declared_sha}, got {computed}",
            )
        verified_hashed += 1

    if total_hashed == 0:
        return "unchecked", "unchecked", None
    if verified_hashed == total_hashed:
        return "intact", "fully_verified", None
    if verified_hashed > 0:
        detail = None
        if unanchored_relatives > 0:
            detail = "Relative local locator requires explicit root_dir for on-disk verification"
        elif unauthorized_locals > 0:
            detail = "Local locator is outside the explicitly authorized content root"
        return "partial", "partially_verified", detail
    detail = None
    if unanchored_relatives > 0:
        detail = "Relative local locator requires explicit root_dir for on-disk verification"
    elif unauthorized_locals > 0:
        detail = (
            "Local locator is outside the explicitly authorized content root"
            if authorized_root is not None
            else "Local locator requires an explicitly authorized content root or provider"
        )
    return "unchecked", "unverified", detail


def _replay_lineage_receipt_structure(
    data: Mapping[str, Any],
) -> Tuple[str, str, List[str], List[Dict[str, Any]], Optional[str]]:
    """Independently replay a serialized lineage closure and its topology."""
    entities = data.get("entities")
    activities = data.get("activities")
    edges = data.get("edges")
    if not isinstance(entities, list) or not isinstance(activities, list) or not isinstance(edges, list):
        raise ValueError("entities, activities, and edges must be arrays")

    def unique_index(values: List[Any], label: str) -> Dict[str, Dict[str, Any]]:
        indexed: Dict[str, Dict[str, Any]] = {}
        for item in values:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError(f"Every {label} must be an object with a string id")
            item_id = item["id"]
            if item_id in indexed:
                raise ValueError(f"Duplicate {label} id {item_id!r}")
            indexed[item_id] = item
        return indexed

    entity_by_id = unique_index(entities, "entity")
    activity_by_id = unique_index(activities, "activity")

    entity_fields = {"id", "type", "sha256", "locator", "metadata"}
    for entity_id, entity in entity_by_id.items():
        unexpected = set(entity) - entity_fields
        if unexpected:
            raise ValueError(
                f"Entity {entity_id!r} has unexpected fields {sorted(unexpected)!r}"
            )
        if entity.get("type") not in VALID_LINEAGE_ENTITY_TYPES:
            raise ValueError(
                f"Entity {entity_id!r} has unsupported type {entity.get('type')!r}"
            )
        if "sha256" in entity and (
            not isinstance(entity["sha256"], str)
            or not SHA256_REGEX.fullmatch(entity["sha256"])
        ):
            raise ValueError(f"Entity {entity_id!r} has an invalid sha256")
        if "locator" in entity and not isinstance(entity["locator"], str):
            raise ValueError(f"Entity {entity_id!r} locator must be a string")
        if "metadata" in entity and not isinstance(entity["metadata"], dict):
            raise ValueError(f"Entity {entity_id!r} metadata must be an object")

    activity_fields = {
        "id",
        "type",
        "command",
        "script_id",
        "commit_sha",
        "parameters",
        "environment",
        "timestamp",
    }
    for activity_id, activity in activity_by_id.items():
        unexpected = set(activity) - activity_fields
        if unexpected:
            raise ValueError(
                f"Activity {activity_id!r} has unexpected fields {sorted(unexpected)!r}"
            )
        if activity.get("type") not in VALID_LINEAGE_ACTIVITY_TYPES:
            raise ValueError(
                f"Activity {activity_id!r} has unsupported type {activity.get('type')!r}"
            )
        for field_name in ("command", "script_id", "commit_sha", "timestamp"):
            if field_name in activity and not isinstance(activity[field_name], str):
                raise ValueError(
                    f"Activity {activity_id!r} {field_name} must be a string"
                )
        for field_name in ("parameters", "environment"):
            if field_name in activity and not isinstance(activity[field_name], dict):
                raise ValueError(
                    f"Activity {activity_id!r} {field_name} must be an object"
                )

    overlap = set(entity_by_id) & set(activity_by_id)
    if overlap:
        raise ValueError(f"Entity/activity namespace collision: {sorted(overlap)!r}")

    target_id = data.get("target_id")
    if not isinstance(target_id, str):
        raise ValueError("Lineage target_id must be a string")
    all_ids = set(entity_by_id) | set(activity_by_id)
    if target_id not in all_ids:
        if not entities and not activities and not edges:
            return "missing_input", "missing_input", [], [], (
                f"Target {target_id!r} not found in provenance graph"
            )
        raise ValueError(f"Target {target_id!r} is absent from the serialized lineage closure")

    sorted_edges = sorted(
        edges,
        key=lambda edge: (
            edge.get("type", "") if isinstance(edge, dict) else "",
            edge.get("source_id", "") if isinstance(edge, dict) else "",
            edge.get("target_id", "") if isinstance(edge, dict) else "",
            (edge.get("activity_id") or "") if isinstance(edge, dict) else "",
            canonical_json_bytes(edge.get("metadata", {})) if isinstance(edge, dict) else b"",
        ),
    )
    edge_identities: Set[bytes] = set()
    activity_inputs: Dict[str, Set[str]] = {
        activity_id: set() for activity_id in activity_by_id
    }
    activity_outputs: Dict[str, Set[str]] = {
        activity_id: set() for activity_id in activity_by_id
    }
    for edge in sorted_edges:
        if not isinstance(edge, dict):
            raise ValueError("Every lineage edge must be an object")
        unexpected = set(edge) - {
            "type", "source_id", "target_id", "activity_id", "metadata"
        }
        if unexpected:
            raise ValueError(
                f"Lineage edge has unexpected fields {sorted(unexpected)!r}"
            )
        if not isinstance(edge.get("source_id"), str) or not isinstance(
            edge.get("target_id"), str
        ):
            raise ValueError("Every lineage edge requires string source_id and target_id")
        if "activity_id" in edge and not isinstance(edge["activity_id"], str):
            raise ValueError("Lineage edge activity_id must be a string")
        if "metadata" in edge and not isinstance(edge["metadata"], dict):
            raise ValueError("Lineage edge metadata must be an object")
        edge_identity = canonical_json_bytes(edge)
        if edge_identity in edge_identities:
            raise ValueError("Duplicate lineage edge in serialized closure")
        edge_identities.add(edge_identity)
        edge_type = edge.get("type")
        if edge_type not in {"used", "generated", "derived_from"}:
            raise ValueError(f"Unsupported lineage edge type {edge_type!r}")
        if edge_type == "used":
            activity_inputs.setdefault(edge.get("source_id"), set()).add(
                edge.get("target_id")
            )
        elif edge_type == "generated":
            activity_outputs.setdefault(edge.get("source_id"), set()).add(
                edge.get("target_id")
            )

    structural_failure: Optional[Tuple[str, str, str]] = None

    def record_failure(verification: str, topology: str, detail: str) -> None:
        nonlocal structural_failure
        if structural_failure is None:
            structural_failure = (verification, topology, detail)

    generated_by: Dict[str, str] = {}
    for edge in sorted_edges:
        edge_type = edge["type"]
        source_id = edge.get("source_id")
        target = edge.get("target_id")
        if edge_type == "used":
            if source_id not in activity_by_id:
                record_failure(
                    "missing_input",
                    "missing_input",
                    f"Activity {source_id!r} referenced in 'used' edge does not exist",
                )
            if target not in entity_by_id:
                record_failure(
                    "missing_input",
                    "missing_input",
                    f"Entity {target!r} consumed by activity {source_id!r} does not exist",
                )
        elif edge_type == "generated":
            if source_id not in activity_by_id:
                record_failure(
                    "broken_chain",
                    "broken_chain",
                    f"Activity {source_id!r} referenced in 'generated' edge does not exist",
                )
            if target not in entity_by_id:
                record_failure(
                    "broken_chain",
                    "broken_chain",
                    f"Entity {target!r} generated by activity {source_id!r} does not exist",
                )
            previous = generated_by.get(target)
            if previous is not None and previous != source_id:
                record_failure(
                    "broken_chain",
                    "broken_chain",
                    f"Entity {target!r} has multiple generating activities",
                )
            generated_by[target] = source_id
        else:
            if source_id not in entity_by_id:
                record_failure(
                    "broken_chain",
                    "broken_chain",
                    f"Derived entity {source_id!r} does not exist",
                )
            if target not in entity_by_id:
                record_failure(
                    "broken_chain",
                    "broken_chain",
                    f"Source entity {target!r} in derivation does not exist",
                )
            if source_id == target:
                record_failure(
                    "cycle_detected",
                    "cycle_detected",
                    f"Self-derivation loop detected on entity {source_id!r}",
                )
            activity_id = edge.get("activity_id")
            if activity_id:
                if activity_id not in activity_by_id:
                    record_failure(
                        "broken_chain",
                        "broken_chain",
                        f"Derivation activity {activity_id!r} does not exist in activities",
                    )
                elif (
                    target not in activity_inputs.get(activity_id, set())
                    and source_id not in activity_outputs.get(activity_id, set())
                ):
                    record_failure(
                        "broken_chain",
                        "broken_chain",
                        f"Derivation activity {activity_id!r} is detached: it neither "
                        f"consumed source {target!r} nor generated derived {source_id!r}",
                    )

    for activity_id, activity in sorted(activity_by_id.items()):
        script_id = activity.get("script_id")
        if not script_id:
            continue
        if script_id not in entity_by_id:
            record_failure(
                "missing_input",
                "missing_input",
                f"Activity {activity_id!r} references missing script entity {script_id!r}",
            )
        elif entity_by_id[script_id].get("type") != "code_file":
            record_failure(
                "broken_chain",
                "broken_chain",
                f"Activity {activity_id!r} script {script_id!r} is not a 'code_file' entity",
            )

    # Recompute the exact target-scoped reverse closure before returning any
    # topology status.  Otherwise an unrelated cycle could bless a receipt for
    # an isolated target.  Pre-indexed activity memberships above also keep
    # this replay linear in the number of edges.
    reverse: Dict[str, List[Tuple[str, int]]] = {}
    for index, edge in enumerate(sorted_edges):
        if edge["type"] == "used":
            reverse.setdefault(edge["source_id"], []).append((edge["target_id"], index))
        elif edge["type"] == "generated":
            reverse.setdefault(edge["target_id"], []).append((edge["source_id"], index))
        else:
            reverse.setdefault(edge["source_id"], []).append((edge["target_id"], index))
            if edge.get("activity_id"):
                reverse.setdefault(edge["source_id"], []).append((edge["activity_id"], index))

    closure_nodes: Set[str] = {target_id}
    closure_edges: Set[int] = set()
    queue = deque([target_id])
    while queue:
        current = queue.popleft()
        for upstream, edge_index in reverse.get(current, []):
            closure_edges.add(edge_index)
            if upstream not in closure_nodes:
                closure_nodes.add(upstream)
                queue.append(upstream)
    for node_id in list(closure_nodes):
        activity = activity_by_id.get(node_id)
        if activity and activity.get("script_id") in entity_by_id:
            closure_nodes.add(activity["script_id"])
    if (
        closure_nodes.intersection(all_ids) != all_ids
        or closure_edges != set(range(len(sorted_edges)))
    ):
        raise ValueError("Serialized lineage graph is not the exact target-scoped causal closure")

    if structural_failure is not None:
        verification, topology, detail = structural_failure
        return verification, topology, [], [], detail

    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in all_ids}
    indegree: Dict[str, int] = {node_id: 0 for node_id in all_ids}
    for edge in sorted_edges:
        if edge["type"] == "used":
            upstream, downstream = edge["target_id"], edge["source_id"]
        elif edge["type"] == "generated":
            upstream, downstream = edge["source_id"], edge["target_id"]
        else:
            upstream, downstream = edge["target_id"], edge["source_id"]
        adjacency[upstream].append(downstream)
        indegree[downstream] += 1

    ready = [node_id for node_id, degree in indegree.items() if degree == 0]
    heapq.heapify(ready)
    visited_count = 0
    while ready:
        current = heapq.heappop(ready)
        visited_count += 1
        for downstream in sorted(adjacency[current]):
            indegree[downstream] -= 1
            if indegree[downstream] == 0:
                heapq.heappush(ready, downstream)
    if visited_count != len(all_ids):
        return (
            "cycle_detected",
            "cycle_detected",
            [],
            [],
            "Causal dependency cycle detected in graph",
        )

    derived_or_generated = {
        edge["target_id"]
        for edge in sorted_edges
        if edge["type"] == "generated"
    }
    derived_or_generated.update(
        edge["source_id"]
        for edge in sorted_edges
        if edge["type"] == "derived_from"
    )
    roots = sorted(
        entity_id
        for entity_id in entity_by_id
        if entity_id not in derived_or_generated and entity_id != target_id
    )
    if not roots and target_id in entity_by_id and not reverse.get(target_id):
        roots = [target_id]

    activity_dependencies: Dict[str, Set[str]] = {
        activity_id: set() for activity_id in activity_by_id
    }
    generator_map = {
        edge["target_id"]: edge["source_id"]
        for edge in sorted_edges
        if edge["type"] == "generated"
    }
    for edge in sorted_edges:
        if edge["type"] != "used":
            continue
        consumer = edge["source_id"]
        producer = generator_map.get(edge["target_id"])
        if producer and producer != consumer:
            activity_dependencies[consumer].add(producer)

    activity_dependents: Dict[str, Set[str]] = {
        activity_id: set() for activity_id in activity_by_id
    }
    remaining_dependencies = {
        activity_id: len(dependencies)
        for activity_id, dependencies in activity_dependencies.items()
    }
    for consumer, dependencies in activity_dependencies.items():
        for producer in dependencies:
            activity_dependents[producer].add(consumer)

    ordered_activities: List[str] = []
    ready_activities = [
        activity_id
        for activity_id, dependency_count in remaining_dependencies.items()
        if dependency_count == 0
    ]
    heapq.heapify(ready_activities)
    while ready_activities:
        current = heapq.heappop(ready_activities)
        ordered_activities.append(current)
        for activity_id in sorted(activity_dependents[current]):
            remaining_dependencies[activity_id] -= 1
            if remaining_dependencies[activity_id] == 0:
                heapq.heappush(ready_activities, activity_id)

    inputs: Dict[str, List[str]] = {activity_id: [] for activity_id in activity_by_id}
    outputs: Dict[str, List[str]] = {activity_id: [] for activity_id in activity_by_id}
    for edge in sorted_edges:
        if edge["type"] == "used":
            inputs[edge["source_id"]].append(edge["target_id"])
        elif edge["type"] == "generated":
            outputs[edge["source_id"]].append(edge["target_id"])
    steps = [
        {
            "step_number": index,
            "activity_id": activity_id,
            "inputs": sorted(inputs[activity_id]),
            "outputs": sorted(outputs[activity_id]),
        }
        for index, activity_id in enumerate(ordered_activities, start=1)
    ]
    return "unchecked", "valid_dag", roots, steps, None


@lru_cache(maxsize=None)
def _physical_receipt_validator(filename: str):
    from jsonschema import Draft202012Validator, FormatChecker
    path = Path(__file__).resolve().parents[2] / "schemas" / filename
    schema = json.loads(path.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def physical_receipt_schema_errors(value: Any, *, lineage: bool) -> List[str]:
    """Current wire contract with an explicit, closed historical v1 read form."""
    filenames = ["lineage-receipt.schema.json"] if lineage else [
        "evidence-receipt.schema.json", "legacy-academic-evidence.schema.json",
    ]
    results = []
    for filename in filenames:
        errors = sorted(_physical_receipt_validator(filename).iter_errors(_thaw_val(value)),
                        key=lambda error: (tuple(str(p) for p in error.absolute_path), error.message))
        if not errors:
            return []
        results.append([f"{filename}: {error.message}" for error in errors])
    return results[-1]


def validate_lineage_receipt_integrity(
    receipt_obj: Any,
    *,
    verification_context: Optional[LineageVerificationContext] = None,
    content_root: Optional[Union[str, Path]] = None,
    content_by_entity_id: Optional[Mapping[str, bytes]] = None,
    max_content_bytes: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """Recompute both identities of a serialized LineageReceipt.

    Historical v1 receipts did not serialize ``check_on_disk_hashes`` even
    though it participates in ``receipt_digest``.  Verification therefore
    tries both legitimate boolean modes and still rejects every other digest.
    """
    # Explicit invocation context wins. In-process producer context is a
    # compatibility convenience; portable callers must pass authority again.
    if verification_context is None and content_root is None and content_by_entity_id is None and max_content_bytes is None:
        verification_context = getattr(receipt_obj, "_verification_context", None)
    if verification_context is not None:
        if not isinstance(verification_context, LineageVerificationContext):
            return False, "verification_context must be a trusted LineageVerificationContext"
        if content_root is not None or content_by_entity_id is not None or max_content_bytes is not None:
            return False, "verification_context cannot be combined with legacy content options"
        content_root = verification_context.content_root
        content_by_entity_id = verification_context.content_by_entity_id
        max_content_bytes = verification_context.max_content_bytes
    elif content_root is None and content_by_entity_id is None:
        content_root = getattr(receipt_obj, "_content_root", None)
    if max_content_bytes is None:
        max_content_bytes = 10 * 1024 * 1024
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
    possible_by_mode = {
        mode: compute_sha256(
            canonical_json_bytes(dict(receipt_base, check_on_disk_hashes=mode))
        )
        for mode in (False, True)
    }
    declared_receipt = str(data.get("receipt_digest", "")).lower()
    matching_modes = [
        mode for mode, digest in possible_by_mode.items()
        if digest == declared_receipt
    ]
    if not matching_modes:
        return False, "Lineage verification receipt_digest does not match either valid verification mode"
    if data.get("receipt_id") != f"rec-{declared_receipt[:32]}":
        return False, "Lineage receipt_id is not derived from receipt_digest"

    try:
        (
            structural_verification,
            structural_topology,
            replayed_roots,
            replayed_steps,
            structural_error,
        ) = _replay_lineage_receipt_structure(data)
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"Lineage receipt cannot be canonically replayed: {exc}"
    if structural_topology != data.get("topology_status"):
        return False, (
            f"Lineage topology status mismatch: declared {data.get('topology_status')!r}, "
            f"replayed {structural_topology!r}"
        )
    if structural_topology != "valid_dag":
        if data.get("verification_status") != structural_verification:
            return False, (
                "Lineage verification status is inconsistent with replayed topology: "
                f"declared {data.get('verification_status')!r}, "
                f"replayed {structural_verification!r}"
            )
        if data.get("content_verification") != "unchecked":
            return False, "Invalid lineage topology must have unchecked content verification"
        if data.get("root_ancestors") or data.get("trace_steps"):
            return False, "Invalid lineage topology must not declare roots or trace steps"
        if (data.get("error_detail") or None) != structural_error:
            return False, (
                "Lineage structural error detail mismatch: "
                f"declared {(data.get('error_detail') or None)!r}, "
                f"replayed {structural_error!r}"
            )
    else:
        content_status = data.get("content_verification")
        if content_status not in {
            "fully_verified",
            "partially_verified",
            "unverified",
            "unchecked",
            "hash_mismatch",
            "missing_artifact",
        }:
            return False, f"Unsupported lineage content verification status {content_status!r}"
        try:
            independent_results = [
                _replay_lineage_content_verification(
                    data["entities"],
                    check_on_disk_hashes=mode,
                    content_root=content_root,
                    content_by_entity_id=content_by_entity_id,
                    max_content_bytes=max_content_bytes,
                    authorized_paths=(verification_context.authorized_paths if verification_context else ()),
                )
                for mode in matching_modes
            ]
        except (OSError, TypeError, ValueError) as exc:
            return False, (
                "Lineage content verification cannot be independently established: "
                f"local locator check failed: {exc}"
            )
        declared_content_result = (
            data.get("verification_status"),
            content_status,
            data.get("error_detail") or None,
        )
        if declared_content_result not in independent_results:
            replayed = independent_results[0]
            return False, (
                "Lineage content verification cannot be independently established: "
                f"declared {declared_content_result!r}, replayed {replayed!r}"
            )
        expected_roots = (
            [] if content_status in {"hash_mismatch", "missing_artifact"}
            else replayed_roots
        )
        expected_steps = (
            [] if content_status in {"hash_mismatch", "missing_artifact"}
            else replayed_steps
        )
        if data.get("root_ancestors") != expected_roots:
            return False, (
                f"Lineage root ancestors mismatch: declared {data.get('root_ancestors')!r}, "
                f"replayed {expected_roots!r}"
            )
        if data.get("trace_steps", []) != expected_steps:
            return False, "Lineage trace steps do not match the replayed causal graph"
    schema_errors = physical_receipt_schema_errors(data, lineage=True)
    if schema_errors:
        return False, "Lineage receipt schema validation failed: " + "; ".join(schema_errors)

    return True, None


def validate_lineage_receipt_contract(
    ref: ReceiptRef,
    receipt_obj: Any,
    *,
    verification_context: Optional[LineageVerificationContext] = None,
    content_root: Optional[Union[str, Path]] = None,
    content_by_entity_id: Optional[Mapping[str, bytes]] = None,
    max_content_bytes: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """Strictly assert lineage-receipt-1.0 protocol, exact receipt_id, and exact receipt_digest."""
    r_dict = receipt_obj.to_dict() if hasattr(receipt_obj, "to_dict") else receipt_obj
    if not isinstance(r_dict, (dict, collections.abc.Mapping)) or r_dict.get("protocol") != "lineage-receipt-1.0":
        return False, "Lineage receipt invalid protocol: expected 'lineage-receipt-1.0'"
    if r_dict.get("receipt_id") != ref.receipt_id:
        return False, f"Lineage receipt ID mismatch: expected {ref.receipt_id!r}, got {r_dict.get('receipt_id')!r}"
    if str(r_dict.get("receipt_digest", "")).lower() != str(ref.receipt_digest).lower():
        return False, f"Lineage receipt digest mismatch: expected {ref.receipt_digest!r}, got {r_dict.get('receipt_digest')!r}"
    return validate_lineage_receipt_integrity(
        receipt_obj,
        verification_context=verification_context,
        content_root=content_root,
        content_by_entity_id=content_by_entity_id,
        max_content_bytes=max_content_bytes,
    )


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

    schema_errors = physical_receipt_schema_errors(thawed, lineage=False)
    if schema_errors:
        return False, "AcademicEvidence receipt schema validation failed: " + "; ".join(schema_errors)
    for claim in thawed["claims"]:
        if "claim_digest" in claim and claim["claim_digest"] != canonical_evidence_claim_digest(claim):
            return False, "AcademicEvidence legacy claim_digest does not match canonical claim content"

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
    if not matched_claim:
        return False, f"AcademicEvidence claim digest mismatch: claim_digest {ref.claim_digest} not found in legitimate receipt claims"
    return True, None


def verify_receipt_reference(
    ref: ReceiptRef,
    receipt_obj: Any,
    *,
    verification_context: Optional[LineageVerificationContext] = None,
    content_root: Optional[Union[str, Path]] = None,
    content_by_entity_id: Optional[Mapping[str, bytes]] = None,
    max_content_bytes: Optional[int] = None,
) -> Tuple[bool, Optional[str]]:
    """Verify any ReceiptRef against a physical receipt instance based on kind."""
    if ref.kind == "lineage":
        return validate_lineage_receipt_contract(
            ref,
            receipt_obj,
            verification_context=verification_context,
            content_root=content_root,
            content_by_entity_id=content_by_entity_id,
            max_content_bytes=max_content_bytes,
        )
    if ref.kind == "academic_evidence":
        return validate_academic_receipt_contract(ref, receipt_obj)
    return False, f"Unsupported receipt kind: {ref.kind!r}"

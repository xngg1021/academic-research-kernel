"""Runtime admission contracts for artifact envelopes and adapter payloads.

The JSON files in ``schemas/`` are executable admission contracts, not merely
documentation.  All public ingestion paths use this module before adapter
planning so unknown fields, schema/version drift, and oversized/deep payloads
fail closed in the same way on Python and MCP surfaces.
"""

from __future__ import annotations

import collections.abc
import json
from functools import lru_cache
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from jsonschema import Draft202012Validator, FormatChecker

from shared_contracts.evidence import _thaw_val, canonical_json_bytes


ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"

MAX_PAYLOAD_BYTES = 10 * 1024 * 1024
MAX_STRUCTURE_DEPTH = 64
MAX_COLLECTION_ITEMS = 100_000


PAYLOAD_SCHEMA_FILES: Dict[str, str] = {
    "evidence-receipt-1.0": "evidence-receipt.schema.json",
    "academic-evidence-1.0": "legacy-academic-evidence.schema.json",
    "research-object-1.0": "research-object.schema.json",
    "lineage-receipt-1.0": "lineage-receipt.schema.json",
    "ceg-snapshot-1.0": "claim-evidence-graph.schema.json",
    "claim-evidence-graph-1.0": "claim-evidence-graph.schema.json",
    "decision-ledger-1.0": "decision-ledger-receipt.schema.json",
    "quantitative-audit-1.0": "quantitative-audit.schema.json",
    "reproduction-receipt-1.0": "reproduction-receipt.schema.json",
    "cross-review-finding-1.0": "cross-review-artifact.schema.json",
    "cross-review-2.0": "cross-review-artifact.schema.json",
    "screening-matrix-1.0": "systematic-review-artifact.schema.json",
    "meta-analysis-1.0": "systematic-review-artifact.schema.json",
    "canonical-work-1.0": "literature-analysis-artifact.schema.json",
    "corpus-matrix-1.0": "literature-analysis-artifact.schema.json",
    "literature-delta-1.0": "literature-delta.schema.json",
    "retraction-alert-1.0": "retraction-delta.schema.json",
    "retraction-delta-1.0": "retraction-delta.schema.json",
    "computation-receipt-1.0": "computation-artifact.schema.json",
    "manuscript-opaque-1.0": "opaque-manuscript.schema.json",
    "submission-package-1.0": "opaque-manuscript.schema.json",
}

# Producer versions are installed skill versions, not payload-schema versions.
# Most current skills are 1.x; cross-review-five intentionally exposes a 2.x
# producer contract.  Keep compatibility explicit so new majors fail closed
# without rejecting a legitimate current producer.
SUPPORTED_PRODUCER_MAJORS: Dict[str, frozenset[int]] = {
    "academic-source-verification": frozenset({1}),
    "research-object-identity": frozenset({1}),
    "claim-evidence-graph": frozenset({1}),
    "decision-ledger": frozenset({1}),
    "quantitative-paper-audit": frozenset({1}),
    "research-reproducibility": frozenset({1}),
    "cross-review-five": frozenset({2}),
    "systematic-review-meta-analysis": frozenset({1}),
    "literature-analysis": frozenset({1}),
    "literature-watch": frozenset({1}),
    "retraction-watch": frozenset({1}),
    "math-computation": frozenset({1}),
    "academic-writing": frozenset({1}),
}


def _json_pointer(parts: Iterable[Any]) -> str:
    encoded = []
    for part in parts:
        encoded.append(str(part).replace("~", "~0").replace("/", "~1"))
    return "/" + "/".join(encoded) if encoded else "/"


@lru_cache(maxsize=None)
def _load_schema(filename: str) -> Dict[str, Any]:
    path = SCHEMAS / filename
    if not path.is_file():
        raise ValueError(f"Runtime schema file is missing: {path.relative_to(ROOT)}")
    data = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(data)
    return data


def validate_schema(instance: Any, filename: str) -> List[str]:
    """Return stable, path-qualified Draft 2020-12 validation errors."""
    schema = _load_schema(filename)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(_thaw_val(instance)),
        key=lambda err: (tuple(str(p) for p in err.absolute_path), err.message),
    )
    return [f"{_json_pointer(err.absolute_path)}: {err.message}" for err in errors]


def validate_envelope_dict(data: Mapping[str, Any]) -> List[str]:
    return validate_schema(data, "research-artifact-envelope.schema.json")


def validate_receipt_dict(data: Mapping[str, Any]) -> List[str]:
    return validate_schema(data, "artifact-ingestion-receipt.schema.json")


def validate_kernel_state_dict(data: Mapping[str, Any]) -> List[str]:
    return validate_schema(data, "ingestion-kernel-state.schema.json")


def _measure_structure(value: Any, depth: int = 0) -> Tuple[int, int]:
    """Return ``(maximum_depth, collection_item_count)`` for a JSON value."""
    if depth > MAX_STRUCTURE_DEPTH:
        return depth, 0
    if isinstance(value, collections.abc.Mapping):
        maximum, count = depth, len(value)
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            child_depth, child_count = _measure_structure(item, depth + 1)
            maximum = max(maximum, child_depth)
            count += child_count
        return maximum, count
    if isinstance(value, (list, tuple)):
        maximum, count = depth, len(value)
        for item in value:
            child_depth, child_count = _measure_structure(item, depth + 1)
            maximum = max(maximum, child_depth)
            count += child_count
        return maximum, count
    if value is None or isinstance(value, (str, int, float, bool)):
        return depth, 0
    raise TypeError(f"Value of type {type(value).__name__!r} is outside the JSON domain")


def validate_payload_bounds(payload: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    thawed = _thaw_val(payload)
    try:
        payload_bytes = len(canonical_json_bytes(thawed))
        maximum_depth, collection_items = _measure_structure(thawed)
    except (TypeError, ValueError) as exc:
        return [f"Payload is not canonical JSON: {exc}"]
    if payload_bytes > MAX_PAYLOAD_BYTES:
        errors.append(
            f"Payload size {payload_bytes} bytes exceeds maximum {MAX_PAYLOAD_BYTES} bytes"
        )
    if maximum_depth > MAX_STRUCTURE_DEPTH:
        errors.append(
            f"Payload nesting depth {maximum_depth} exceeds maximum {MAX_STRUCTURE_DEPTH}"
        )
    if collection_items > MAX_COLLECTION_ITEMS:
        errors.append(
            f"Payload collection size {collection_items} exceeds maximum {MAX_COLLECTION_ITEMS}"
        )
    return errors


def validate_adapter_contract(envelope: Any, adapter: Any) -> List[str]:
    """Validate schema routing and producer-major compatibility for an adapter."""
    # The opaque fallback intentionally stores unknown artifacts without claiming
    # structured interoperability.
    if getattr(adapter, "adapter_id", "") == "adapter-opaque-fallback":
        return validate_payload_bounds(envelope.payload)

    errors: List[str] = []
    accepted_schemas = set(getattr(adapter, "accepted_schemas", set()))
    if envelope.payload_schema not in accepted_schemas:
        errors.append(
            f"Adapter {adapter.adapter_id} does not accept payload_schema "
            f"{envelope.payload_schema!r}; expected one of {sorted(accepted_schemas)}"
        )

    producer = envelope.producer.get("skill")
    accepted_producers = set(getattr(adapter, "accepted_producers", set()))
    if producer in accepted_producers:
        version = str(envelope.producer.get("version", ""))
        match = re.match(r"^(\d+)(?:\.|$)", version)
        if not match:
            errors.append(f"Producer version {version!r} is not a major-versioned contract")
        elif producer not in SUPPORTED_PRODUCER_MAJORS:
            errors.append(f"Producer {producer!r} has no declared compatible major version")
        elif int(match.group(1)) not in SUPPORTED_PRODUCER_MAJORS[producer]:
            errors.append(
                f"Producer {producer!r} major version {match.group(1)} is unsupported; "
                f"expected one of {sorted(SUPPORTED_PRODUCER_MAJORS[producer])}"
            )

    errors.extend(validate_payload_bounds(envelope.payload))
    filename = PAYLOAD_SCHEMA_FILES.get(envelope.payload_schema)
    if filename is None:
        errors.append(
            f"No executable runtime schema is registered for {envelope.payload_schema!r}"
        )
    else:
        errors.extend(validate_schema(envelope.payload, filename))
    return errors

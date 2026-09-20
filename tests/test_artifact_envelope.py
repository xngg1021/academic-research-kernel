"""Tests for ResearchArtifactEnvelope and ArtifactIngestionReceipt JSON Schemas."""

import json
import pytest
from pathlib import Path
import jsonschema

ROOT = Path(__file__).resolve().parent.parent

ENVELOPE_SCHEMA = json.loads((ROOT / "schemas" / "research-artifact-envelope.schema.json").read_text(encoding="utf-8"))
RECEIPT_SCHEMA = json.loads((ROOT / "schemas" / "artifact-ingestion-receipt.schema.json").read_text(encoding="utf-8"))


def test_valid_artifact_envelope():
    env = {
        "protocol": "artifact-envelope-1.0",
        "artifact_id": "art-" + "1" * 32,
        "artifact_kind": "evidence_receipt",
        "producer": {
            "skill": "academic-source-verification",
            "version": "1.0.0",
        },
        "payload_schema": "evidence-receipt-1.0",
        "payload_sha256": "a" * 64,
        "payload": {
            "query": "DOI:10.1000/182",
            "claims": [],
        },
        "subject_refs": ["work:doi:10.1000/182"],
        "locator": "https://doi.org/10.1000/182",
    }
    jsonschema.validate(instance=env, schema=ENVELOPE_SCHEMA)


def test_invalid_artifact_envelope_missing_required():
    env = {
        "protocol": "artifact-envelope-1.0",
        "artifact_id": "art-" + "1" * 32,
        # missing producer, payload_sha256, etc.
        "artifact_kind": "evidence_receipt",
        "payload": {},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=env, schema=ENVELOPE_SCHEMA)


def test_valid_ingestion_receipt():
    rec = {
        "protocol": "ingestion-receipt-1.0",
        "receipt_id": "ingest-" + "2" * 32,
        "source_artifact_id": "art-" + "1" * 32,
        "source_artifact_sha256": "b" * 64,
        "adapter_id": "adapter-academic-source-verification",
        "adapter_version": "1.0.0",
        "status": "accepted",
        "validation_state": {
            "valid": True,
            "errors": [],
        },
        "created_or_reused_objects": ["obj-1"],
        "ceg_nodes": ["c1", "ev1"],
        "ceg_edges": ["edge-1"],
        "ledger_bindings": [{
            "decision_id": "d1",
            "binding_kind": "evidence_receipt",
            "basis_id": "ev1",
            "record_digest": "1" * 64,
        }],
        "uncertainties": [],
        "ignored_fields": [],
        "output_digests": {
            "object_registry_digest": "a" * 64,
            "receipt_registry_digest": "b" * 64,
            "uncertainty_state_digest": "e" * 64,
            "ingested_artifact_digest": "f" * 64,
            "ceg_digest": "c" * 64,
            "ledger_digest": "d" * 64,
            "kernel_content_digest": "0" * 64,
        },
    }
    jsonschema.validate(instance=rec, schema=RECEIPT_SCHEMA)

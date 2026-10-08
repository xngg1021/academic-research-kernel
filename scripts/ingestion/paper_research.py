"""Typed admission of source-located paper reading, without automatic decisions."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .adapters import BaseArtifactAdapter, IngestionPlan
from .contracts import validate_schema
from .models import ArtifactEnvelope, IngestionKernelState

if __package__.startswith("academic_research_kernel"):
    from academic_research_kernel.shared_contracts.evidence import canonical_json_bytes, compute_sha256, _thaw_val
else:
    from shared_contracts.evidence import canonical_json_bytes, compute_sha256, _thaw_val


class PaperResearchAdapter(BaseArtifactAdapter):
    adapter_id = "adapter-paper-research"
    adapter_version = "1.0.0"
    accepted_producers = {"paper-research"}
    accepted_schemas = {"paper-extraction-1.0", "paper-comparison-1.0"}
    is_lossless = True
    tier = 2

    def probe(self, envelope: ArtifactEnvelope) -> bool:
        return envelope.producer.get("skill") in self.accepted_producers

    def validate(self, envelope: ArtifactEnvelope):
        filename = {
            "paper-extraction-1.0": "paper-extraction.schema.json",
            "paper-comparison-1.0": "paper-comparison.schema.json",
        }.get(envelope.payload_schema)
        if filename is None:
            return False, ["Unsupported paper research schema"]
        errors = validate_schema(envelope.payload, filename)
        if envelope.payload_schema == "paper-extraction-1.0":
            fields = envelope.payload.get("fields", [])
            ids = [field.get("id") for field in fields]
            if len(ids) != len(set(ids)):
                errors.append("Field identifiers must be unique")
            extracted = [f for f in fields if f.get("status") == "extracted"]
            if len(extracted) < 10:
                errors.append("At least ten located, populated fields are required")
            for index, field in enumerate(fields):
                if field.get("status") == "extracted":
                    value, kind = field.get("value"), field.get("type")
                    numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
                    if kind in {"number", "integer", "p_value"} and not numeric:
                        errors.append(f"fields[{index}] requires a numeric value")
                    if kind == "integer" and numeric and value != int(value):
                        errors.append(f"fields[{index}] requires an integer value")
                    if kind == "p_value" and numeric and not 0 <= value <= 1:
                        errors.append(f"fields[{index}] p value outside [0, 1]")
                    if kind == "text" and not isinstance(value, str):
                        errors.append(f"fields[{index}] requires a text value")
                    if kind == "boolean" and not isinstance(value, bool):
                        errors.append(f"fields[{index}] requires a boolean value")
            known = set(ids)
            for key, item in envelope.payload.get("summary", {}).items():
                if set(item.get("field_ids", [])) - known:
                    errors.append(f"summary.{key} refers to unknown fields")
        return not errors, errors

    def plan(self, envelope: ArtifactEnvelope, state: IngestionKernelState,
             bindings: Optional[Mapping[str, Any]] = None) -> IngestionPlan:
        valid, errors = self.validate(envelope)
        plan = IngestionPlan(envelope, self.adapter_id, self.adapter_version, valid, errors)
        if not valid:
            return plan
        payload = _thaw_val(envelope.payload)
        object_id = f"{envelope.artifact_id}:paper-research"
        plan.created_objects[object_id] = {
            "id": object_id, "kind": "paper_research", "payload_schema": envelope.payload_schema,
            "payload_sha256": envelope.payload_sha256, "payload": payload,
        }
        if envelope.payload_schema == "paper-extraction-1.0":
            for field in payload["fields"]:
                if field["status"] != "extracted":
                    continue
                digest = compute_sha256(canonical_json_bytes({
                    "artifact": envelope.artifact_id, "field": field,
                }))[:32]
                claim_id, evidence_id = f"clm-paper-{digest}", f"ev-paper-{digest}"
                locator = " | ".join(f"{s['document_id']}#{s['locator']}" for s in field["sources"])
                plan.ceg_claims.append({
                    "id": claim_id, "text": f"作者报告 {field['name']}: {field['literal']}",
                    "claim_type": "empirical_finding", "locator": locator,
                    "metadata": {"field_id": field["id"], "context": field["context"],
                                 "interpretation": "author_reported", "producer": payload["producer"]},
                })
                plan.ceg_evidences.append({
                    "id": evidence_id, "anchor_type": "direct_observation", "locator": locator,
                    "metadata": {"field": field, "project_fingerprint": payload["project_fingerprint"],
                                 "interpretation": "located_reading_candidate"},
                })
                plan.ceg_edges.append({
                    "claim_id": claim_id, "evidence_id": evidence_id, "support_status": "supported",
                    "rationale": "The located quotation supports the author-reported field; this edge does not establish scientific validity.",
                })
        return plan

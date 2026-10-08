# -*- coding: utf-8 -*-
"""Universal Model Context Protocol (MCP) server for the deterministic research-state kernel.

Exposes core research state verification, artifact ingestion, provenance tracing,
claim-evidence verification, decision audit, and statistical recomputation over
standard JSON-RPC 2.0 stdio transport without external framework lock-in.
Compatible with Claude Code, Cursor, Codex, Gemini CLI, and Hermes.
"""

from __future__ import annotations

import base64
import binascii
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator

if not __package__:
    ROOT = Path(__file__).resolve().parent.parent

    # Inject paths for core capabilities
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "skills" / "research-object-identity" / "scripts"))
    sys.path.insert(0, str(ROOT / "skills" / "claim-evidence-graph" / "scripts"))
    sys.path.insert(0, str(ROOT / "skills" / "decision-ledger" / "scripts"))
    sys.path.insert(0, str(ROOT / "skills" / "quantitative-paper-audit" / "scripts"))
    sys.path.insert(0, str(ROOT / "skills" / "academic-source-verification" / "scripts"))
    sys.path.insert(0, str(ROOT / "scripts" / "scfabric"))

if __package__ and __package__.startswith("academic_research_kernel"):
    from academic_research_kernel.shared_contracts.evidence import (
        ReceiptRef,
        LineageVerificationContext,
        physical_receipt_schema_errors,
        validate_lineage_receipt_contract,
        verify_receipt_reference,
    )
else:
    from shared_contracts.evidence import (
        ReceiptRef,
        LineageVerificationContext,
        physical_receipt_schema_errors,
        validate_lineage_receipt_contract,
        verify_receipt_reference,
    )
if __package__:
    from .ingestion import IngestionEngine, ArtifactEnvelope, IngestionKernelState
    from .ingestion.contracts import validate_adapter_contract, validate_schema
    from . import identity as id_mod, provenance as prov_mod, graph as ceg_mod, ledger as ledger_mod
    from . import recompute, hardware_probe
    from ._version import __version__
else:
    from ingestion import IngestionEngine, ArtifactEnvelope, IngestionKernelState
    from ingestion.contracts import validate_adapter_contract, validate_schema
    import identity as id_mod
    import provenance as prov_mod
    import graph as ceg_mod
    import ledger as ledger_mod
    import recompute
    import hardware_probe
    from _version import __version__


TOOLS = [
    # -------------------------------------------------------------------------
    # 1. Research Artifact Ingestion & Validation
    # -------------------------------------------------------------------------
    {
        "name": "research_artifact_validate",
        "description": "Validate a ResearchArtifactEnvelope against its schema and verify its cryptographic payload SHA-256 without side effects.",
        "inputSchema": {
            "type": "object",
            "required": ["envelope"],
            "properties": {
                "envelope": {
                    "type": "object",
                    "description": "The ResearchArtifactEnvelope dictionary to validate."
                },
                "receipts": {
                    "type": "object",
                    "description": "Optional physical receipt registry required to replay receipt-backed CEG or Ledger snapshots."
                }
            }
        }
    },
    {
        "name": "research_artifact_ingest",
        "description": "Deterministically ingest a scholarly artifact envelope into kernel state (ResearchObjects, CEG, and Ledger).",
        "inputSchema": {
            "type": "object",
            "required": ["envelope"],
            "properties": {
                "envelope": {
                    "type": "object",
                    "description": "The ResearchArtifactEnvelope to ingest."
                },
                "bindings": {
                    "type": "object",
                    "description": "Optional explicit bindings (e.g. {'decision_id': '...', 'claim_id': '...'})."
                },
                "state": {
                    "type": "object",
                    "description": "Optional initial kernel state snapshot (containing 'ceg', 'ledger', 'objects')."
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, simulates ingestion and returns plan without committing state."
                }
            }
        }
    },
    # -------------------------------------------------------------------------
    # 2. Receipt & Identity Verification
    # -------------------------------------------------------------------------
    {
        "name": "research_receipt_verify",
        "description": "Verify an AcademicEvidenceReceipt or LineageReceipt against a strongly typed ReceiptRef.",
        "inputSchema": {
            "type": "object",
            "required": ["receipt_ref", "receipt_payload"],
            "properties": {
                "receipt_ref": {
                    "type": "object",
                    "description": "The ReceiptRef reference dictionary."
                },
                "receipt_payload": {
                    "type": "object",
                    "description": "The full physical receipt payload dictionary to verify."
                },
                "content_payloads": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Optional base64 content bytes keyed by lineage entity ID; total decoded content is capped at 10 MiB."
                }
            }
        }
    },
    {
        "name": "research_object_resolve",
        "description": "Resolve and aggregate candidate bibliographic/identity records into discrete five-state equivalence judgments.",
        "inputSchema": {
            "type": "object",
            "required": ["records"],
            "properties": {
                "records": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of candidate metadata records sharing possible identifiers."
                }
            }
        }
    },
    {
        "name": "research_lineage_trace",
        "description": "Trace backward provenance ancestry for a specified entity within a LineageGraph snapshot.",
        "inputSchema": {
            "type": "object",
            "required": ["lineage_graph", "target_entity_id"],
            "properties": {
                "lineage_graph": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "entities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["id"],
                                "properties": {
                                    "id": {"type": "string", "minLength": 1},
                                    "type": {
                                        "type": "string",
                                        "enum": sorted(prov_mod.VALID_ENTITY_TYPES),
                                    },
                                    "sha256": {
                                        "type": "string",
                                        "pattern": "^[0-9a-f]{64}$",
                                    },
                                    "locator": {"type": "string"},
                                    "metadata": {"type": "object"},
                                },
                            },
                        },
                        "activities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["id", "timestamp"],
                                "properties": {
                                    "id": {"type": "string", "minLength": 1},
                                    "type": {
                                        "type": "string",
                                        "enum": sorted(prov_mod.VALID_ACTIVITY_TYPES),
                                    },
                                    "command": {"type": "string"},
                                    "script_id": {"type": "string"},
                                    "commit_sha": {"type": "string"},
                                    "parameters": {"type": "object"},
                                    "environment": {"type": "object"},
                                    "timestamp": {"type": "string", "minLength": 1},
                                },
                            },
                        },
                        "edges": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["type", "source_id", "target_id"],
                                "properties": {
                                    "type": {
                                        "type": "string",
                                        "enum": ["used", "generated", "derived_from"],
                                    },
                                    "source_id": {"type": "string", "minLength": 1},
                                    "target_id": {"type": "string", "minLength": 1},
                                    "activity_id": {"type": "string"},
                                    "metadata": {"type": "object"},
                                },
                            },
                        },
                    },
                    "description": "Exported LineageGraph dictionary."
                },
                "target_entity_id": {
                    "type": "string",
                    "minLength": 1,
                    "description": "The entity ID to trace upstream lineage from."
                }
            }
        }
    },
    # -------------------------------------------------------------------------
    # 3. Claim-Evidence Graph Primitives
    # -------------------------------------------------------------------------
    {
        "name": "claim_evidence_validate",
        "description": "Validate the structural integrity, cycles, and cryptographic receipt bindings of a ClaimEvidenceGraph snapshot.",
        "inputSchema": {
            "type": "object",
            "required": ["graph"],
            "properties": {
                "graph": {
                    "type": "object",
                    "description": "ClaimEvidenceGraph export dictionary."
                }
            }
        }
    },
    {
        "name": "claim_evidence_trace",
        "description": "Trace all supporting and refuting evidence anchors and attached receipts for a given claim.",
        "inputSchema": {
            "type": "object",
            "required": ["graph", "claim_id"],
            "properties": {
                "graph": {
                    "type": "object",
                    "description": "ClaimEvidenceGraph export dictionary."
                },
                "claim_id": {
                    "type": "string",
                    "description": "Target claim identifier to trace."
                }
            }
        }
    },
    # -------------------------------------------------------------------------
    # 4. Decision Ledger Primitives
    # -------------------------------------------------------------------------
    {
        "name": "decision_ledger_validate",
        "description": "Execute complete four-gate verification over a Decision Ledger export dictionary.",
        "inputSchema": {
            "type": "object",
            "required": ["ledger"],
            "properties": {
                "ledger": {
                    "type": "object",
                    "description": "DecisionLedger export dictionary."
                }
            }
        }
    },
    {
        "name": "decision_trace",
        "description": "Trace causal ancestry, basis dependencies, outcome corrections, and lifecycle state history for a decision.",
        "inputSchema": {
            "type": "object",
            "required": ["ledger", "decision_id"],
            "properties": {
                "ledger": {
                    "type": "object",
                    "description": "DecisionLedger export dictionary."
                },
                "decision_id": {
                    "type": "string",
                    "description": "The decision identifier to trace."
                }
            }
        }
    },
    # -------------------------------------------------------------------------
    # 5. Statistical & Execution Utilities
    # -------------------------------------------------------------------------
    {
        "name": "academic_recompute_statistics",
        "description": "Recompute a t-test p-value and/or two-group Cohen's d and Hedges' g. Optional reported p-value comparison uses decimal round-half-up intervals; input or partial execution failures are tool errors, statistical mismatches are successful results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "t_stat": {"type": "number", "description": "Reported t-statistic"},
                "df": {"type": "number", "description": "Degrees of freedom (integer or Welch fractional)"},
                "p_value": {"type": "number", "description": "Reported p-value"},
                "p_value_literal": {"type": "string", "description": "Optional exact reported decimal/scientific literal, preserving trailing zeros; must agree with p_value and any explicit decimals."},
                "p_value_decimals": {"type": "integer", "minimum": 0, "maximum": 10000, "description": "Optional decimal-place precision; must agree with a supplied literal."},
                "mean1": {"type": "number", "description": "Group 1 mean"},
                "sd1": {"type": "number", "description": "Group 1 SD"},
                "n1": {"type": "integer", "description": "Group 1 size"},
                "mean2": {"type": "number", "description": "Group 2 mean"},
                "sd2": {"type": "number", "description": "Group 2 SD"},
                "n2": {"type": "integer", "description": "Group 2 size"}
            }
        }
    },
    {
        "name": "academic_check_percentage",
        "description": "Check if a reported percentage and count can mathematically arise from a sample size.",
        "inputSchema": {
            "type": "object",
            "required": ["count", "percent"],
            "properties": {
                "count": {"type": "integer", "description": "Observed count (numerator)"},
                "percent": {"type": "number", "description": "Reported percentage (e.g. 12.5)"},
                "sample_size": {"type": "integer", "description": "Optional total sample size (denominator)"}
            }
        }
    },
    {
        "name": "academic_scfabric_hardware_probe",
        "description": "Probe local hardware accelerators (CUDA, ROCm, MPS, XPU) and execution environments.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]

# Snapshot verification accepts the physical receipt registry required to
# validate cryptographic references inside graphs and ledgers.
_CONTENT_TOOLS = {
    "research_artifact_validate", "research_artifact_ingest", "research_receipt_verify",
    "claim_evidence_validate", "claim_evidence_trace", "decision_ledger_validate", "decision_trace",
}
for _tool in TOOLS:
    if _tool["name"] in _CONTENT_TOOLS:
        _tool["inputSchema"]["properties"]["content_payloads"] = {
            "type": "object", "additionalProperties": {"type": "string"},
            "description": "Authorized base64 content by lineage entity ID; maximum total 10 MiB.",
        }
    if _tool["name"] == "research_artifact_validate":
        _tool["inputSchema"]["properties"].update({"state": {"type": "object"}, "bindings": {"type": "object"}})

for _tool in TOOLS:
    if _tool["name"] in {
        "claim_evidence_validate",
        "claim_evidence_trace",
        "decision_ledger_validate",
        "decision_trace",
    }:
        _tool["inputSchema"]["properties"]["receipts"] = {
            "type": "object",
            "description": "Physical receipt registry keyed by receipt ID or payload SHA-256.",
        }

# MCP itself rejects undeclared top-level arguments rather than merely
# advertising schemas that the runtime ignores.
for _tool in TOOLS:
    _tool["inputSchema"]["additionalProperties"] = False


# Adapter registry holder. Kernel state is explicit per call or initialized fresh.
_DEFAULT_ENGINE = IngestionEngine()


def _tool_argument_errors(name: str, arguments: Any) -> List[str]:
    tool = next((item for item in TOOLS if item["name"] == name), None)
    if tool is None:
        return [f"Unknown tool: {name}"]
    errors = sorted(
        Draft202012Validator(tool["inputSchema"]).iter_errors(arguments),
        key=lambda error: (tuple(str(part) for part in error.absolute_path), error.message),
    )
    return _finite_errors(arguments) + [
        f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in errors
    ]


def _finite_errors(value: Any, path: str = "") -> List[str]:
    """JSON numbers may overflow to infinity even without a NaN token."""
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{path or '/'}: number must be finite"]
    if isinstance(value, dict):
        return [error for key, item in value.items() for error in _finite_errors(item, f"{path}/{key}")]
    if isinstance(value, list):
        return [error for index, item in enumerate(value) for error in _finite_errors(item, f"{path}/{index}")]
    return []


def _wire_verification_context(arguments: dict, trusted: Optional[LineageVerificationContext]) -> Optional[LineageVerificationContext]:
    encoded_content = arguments.get("content_payloads")
    if encoded_content is None:
        return trusted
    if not isinstance(encoded_content, dict):
        raise ValueError("content_payloads must be a dictionary of base64 strings")
    budget = trusted.max_content_bytes if trusted is not None else 10 * 1024 * 1024
    supplied = dict(trusted.content_by_entity_id or {}) if trusted else {}
    total = 0
    for entity_id, encoded in encoded_content.items():
        if not isinstance(entity_id, str) or not isinstance(encoded, str):
            raise ValueError("content_payloads must map string entity IDs to base64 strings")
        if len(encoded) > 4 * ((budget + 2) // 3):
            raise ValueError("content_payloads exceeds the verification byte budget")
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"content_payloads[{entity_id!r}] is not valid base64") from exc
        total += len(decoded)
        if total > budget:
            raise ValueError("content_payloads exceeds the verification byte budget")
        if entity_id in supplied and supplied[entity_id] != decoded:
            raise ValueError("content_payloads conflicts with trusted content")
        supplied[entity_id] = decoded
    return LineageVerificationContext(
        content_root=trusted.content_root if trusted else None,
        authorized_paths=trusted.authorized_paths if trusted else (),
        content_by_entity_id=supplied, max_content_bytes=budget,
    )


def _validate_public_receipts(receipts: Any) -> dict:
    if not isinstance(receipts, dict):
        raise ValueError("receipts must be a dictionary")
    for key, payload in receipts.items():
        if not isinstance(key, str) or not key or not isinstance(payload, dict):
            raise ValueError("receipts must map nonempty string keys to physical receipt objects")
        if payload.get("protocol") != "lineage-receipt-1.0" and payload.get("schema_version") != "1.0":
            raise ValueError(f"Physical receipt {key!r} has invalid protocol")
        errors = physical_receipt_schema_errors(payload, lineage=payload.get("protocol") == "lineage-receipt-1.0")
        if errors:
            raise ValueError(f"Malformed receipt registry entry {key!r}: " + "; ".join(errors))
    return receipts


def handle_tool_call(name: str, arguments: dict, *, verification_context: Optional[LineageVerificationContext] = None) -> dict:
    try:
        if name in _CONTENT_TOOLS:
            verification_context = _wire_verification_context(arguments, verification_context)
        if "receipts" in arguments:
            _validate_public_receipts(arguments["receipts"])
        # 1. research_artifact_validate
        if name == "research_artifact_validate":
            env_data = arguments.get("envelope")
            if not isinstance(env_data, dict):
                return {"valid": False, "errors": ["'envelope' must be a dictionary"]}
            try:
                env = ArtifactEnvelope.from_dict(env_data)
            except Exception as exc:
                return {"valid": False, "errors": [f"Malformed envelope: {exc}"]}
            adapter = _DEFAULT_ENGINE.registry.resolve(env)
            errors = validate_adapter_contract(env, adapter)
            if not errors:
                try:
                    if arguments.get("state") is not None:
                        temp_state = IngestionKernelState.from_dict(
                            arguments["state"], ceg_cls=ceg_mod.ClaimEvidenceGraph,
                            ledger_cls=ledger_mod.DecisionLedger,
                            verification_context=verification_context,
                        )
                    else:
                        temp_state = IngestionKernelState(
                            ceg=ceg_mod.ClaimEvidenceGraph(), ledger=ledger_mod.DecisionLedger(),
                            verification_context=verification_context,
                        )
                    for key, value in arguments.get("receipts", {}).items():
                        temp_state.register_receipt(key, value)
                    # The same dry-run admission path checks constructor,
                    # plan, apply and cache invariants without publishing state.
                    receipt = _DEFAULT_ENGINE.ingest(
                        env, state=temp_state, bindings=arguments.get("bindings"), dry_run=True,
                    )
                    errors.extend(receipt.validation_state["errors"])
                except (TypeError, ValueError, KeyError, AttributeError) as exc:
                    errors.append(f"Artifact validation failed: {exc}")
            valid = not errors
            return {
                "valid": valid,
                "errors": errors,
                "matched_adapter": adapter.adapter_id,
                "artifact_id": env.artifact_id,
                "payload_sha256": env.payload_sha256,
            }

        # 2. research_artifact_ingest
        elif name == "research_artifact_ingest":
            env_data = arguments.get("envelope")
            bindings = arguments.get("bindings")
            state_data = arguments.get("state")
            dry_run = bool(arguments.get("dry_run", False))

            if not isinstance(env_data, dict):
                return {"success": False, "error": "'envelope' must be a dictionary"}

            env = ArtifactEnvelope.from_dict(env_data)

            if state_data is None:
                state = IngestionKernelState(
                    ceg=ceg_mod.ClaimEvidenceGraph(),
                    ledger=ledger_mod.DecisionLedger(),
                    verification_context=verification_context,
                )
            elif isinstance(state_data, dict):
                state = IngestionKernelState.from_dict(
                    state_data,
                    ceg_cls=ceg_mod.ClaimEvidenceGraph,
                    ledger_cls=ledger_mod.DecisionLedger,
                    verification_context=verification_context,
                )
            else:
                return {"success": False, "error": "'state' must be a complete kernel snapshot"}

            receipts, output_state = _DEFAULT_ENGINE.batch_ingest(
                [env],
                state=state,
                bindings_list=[bindings],
                dry_run=dry_run,
                atomic=True,
            )
            receipt = receipts[0]
            resp = {
                "success": receipt.status == "accepted",
                "receipt": receipt.to_dict(),
                "output_state": output_state.to_dict(),
            }
            return resp

        # 3. research_receipt_verify
        elif name == "research_receipt_verify":
            ref_dict = arguments.get("receipt_ref")
            receipt_payload = arguments.get("receipt_payload")
            if not isinstance(ref_dict, dict) or not isinstance(receipt_payload, dict):
                return {"valid": False, "error": "receipt_ref and receipt_payload must be dictionaries"}
            try:
                ref = ReceiptRef(**ref_dict)
            except Exception as exc:
                return {"valid": False, "error": f"Invalid ReceiptRef format: {exc}"}

            schema_errors = physical_receipt_schema_errors(receipt_payload, lineage=ref.kind == "lineage")
            if schema_errors:
                return {"valid": False, "error": "; ".join(schema_errors)}
            try:
                ok, err = verify_receipt_reference(
                    ref,
                    receipt_payload,
                    verification_context=verification_context,
                )
            except Exception as exc:
                return {"valid": False, "error": f"Receipt verification failed: {exc}"}
            if ok:
                return {"valid": True}
            return {"valid": False, "error": err or "Receipt verification failed"}

        # 4. research_object_resolve
        elif name == "research_object_resolve":
            records = arguments.get("records")
            if not isinstance(records, list):
                return {"error": "'records' must be a list of metadata records"}
            resolved = id_mod.resolve(records)
            return {"resolved": resolved}

        # 5. research_lineage_trace
        elif name == "research_lineage_trace":
            graph_data = arguments.get("lineage_graph")
            target_id = arguments.get("target_entity_id")
            if not isinstance(graph_data, dict) or not target_id:
                return {"error": "'lineage_graph' must be a dict and 'target_entity_id' non-empty"}
            try:
                lg = prov_mod.LineageGraph()
                for ent in graph_data.get("entities", []):
                    lg.add_entity(
                        ent["id"],
                        type=ent.get("type", "generic_entity"),
                        sha256=ent.get("sha256"),
                        locator=ent.get("locator"),
                        metadata=ent.get("metadata"),
                    )
                for act in graph_data.get("activities", []):
                    timestamp = act.get("timestamp")
                    if not isinstance(timestamp, str) or not timestamp.strip():
                        raise ValueError(
                            f"Lineage activity {act.get('id')!r} requires an explicit timestamp"
                        )
                    lg.add_activity(
                        act["id"],
                        type=act.get("type", "generic_activity"),
                        command=act.get("command"),
                        script_id=act.get("script_id"),
                        commit_sha=act.get("commit_sha"),
                        parameters=act.get("parameters"),
                        environment=act.get("environment"),
                        timestamp=timestamp,
                    )
                for edge in graph_data.get("edges", []):
                    edge_type = edge["type"]
                    metadata = edge.get("metadata")
                    if edge_type == "derived_from":
                        lg.record_derivation(
                            edge["source_id"],
                            edge["target_id"],
                            activity_id=edge.get("activity_id"),
                            metadata=metadata,
                        )
                    elif edge_type == "used":
                        lg.record_used(
                            edge["source_id"], edge["target_id"], metadata=metadata
                        )
                    elif edge_type == "generated":
                        lg.record_generated(
                            edge["source_id"], edge["target_id"], metadata=metadata
                        )
                    else:
                        raise ValueError(f"Unsupported lineage edge type: {edge_type!r}")
            except (KeyError, TypeError, ValueError) as exc:
                return {
                    "error": "Invalid lineage graph",
                    "details": [str(exc)],
                }
            receipt = prov_mod.trace_origin(lg, target_id, check_on_disk_hashes=False)
            return {"target_entity_id": target_id, "receipt": receipt.to_dict()}

        # 6. claim_evidence_validate
        elif name == "claim_evidence_validate":
            graph_data = arguments.get("graph")
            if not isinstance(graph_data, dict):
                return {"valid": False, "errors": ["'graph' must be a dictionary"]}
            try:
                schema_errors = validate_schema(graph_data, "claim-evidence-graph.schema.json")
                if schema_errors:
                    return {"valid": False, "errors": schema_errors}
                receipts = arguments.get("receipts") or {}
                cg = ceg_mod.ClaimEvidenceGraph.from_dict(
                    graph_data,
                    receipt_registry=receipts,
                    verification_context=verification_context,
                )
                valid, errors = cg.validate_graph()
                return {
                    "valid": valid,
                    "errors": errors,
                    "graph_digest": cg.graph_digest(),
                    "node_count": len(cg.claims) + len(cg.evidence_anchors),
                }
            except Exception as exc:
                return {"valid": False, "errors": [str(exc)]}

        # 7. claim_evidence_trace
        elif name == "claim_evidence_trace":
            graph_data = arguments.get("graph")
            claim_id = arguments.get("claim_id")
            if not isinstance(graph_data, dict) or not claim_id:
                return {"error": "'graph' must be a dict and 'claim_id' non-empty"}
            schema_errors = validate_schema(graph_data, "claim-evidence-graph.schema.json")
            if schema_errors:
                return {"error": "Invalid ClaimEvidenceGraph", "details": schema_errors}
            receipts = arguments.get("receipts") or {}
            try:
                cg = ceg_mod.ClaimEvidenceGraph.from_dict(
                    graph_data,
                    receipt_registry=receipts,
                    verification_context=verification_context,
                )
                trace_info = cg.trace_claim_provenance(claim_id)
                return {
                    "claim_id": claim_id,
                    "support": cg.find_support(claim_id),
                    "contradictions": cg.find_contradictions(claim_id),
                    "provenance_trace": trace_info,
                }
            except Exception as exc:
                return {"error": "Invalid ClaimEvidenceGraph", "details": [str(exc)]}

        # 8. decision_ledger_validate
        elif name == "decision_ledger_validate":
            ledger_data = arguments.get("ledger")
            if not isinstance(ledger_data, dict):
                return {"valid": False, "errors": ["'ledger' must be a dictionary"]}
            try:
                schema_errors = validate_schema(
                    ledger_data, "decision-ledger-receipt.schema.json"
                )
                if schema_errors:
                    return {"valid": False, "errors": schema_errors}
                receipts = arguments.get("receipts") or {}
                ledger_obj = ledger_mod.DecisionLedger.from_dict(
                    ledger_data, receipt_registry=receipts, verification_context=verification_context
                )
                return {
                    "valid": True,
                    "ledger_digest": ledger_obj.ledger_digest(),
                    "decision_count": len(ledger_data.get("decisions", [])),
                    "state_event_count": len(ledger_data.get("state_events", [])),
                }
            except Exception as exc:
                return {"valid": False, "errors": [str(exc)]}

        # 9. decision_trace
        elif name == "decision_trace":
            ledger_data = arguments.get("ledger")
            decision_id = arguments.get("decision_id")
            if not isinstance(ledger_data, dict) or not decision_id:
                return {"error": "'ledger' must be a dict and 'decision_id' non-empty"}
            try:
                schema_errors = validate_schema(
                    ledger_data, "decision-ledger-receipt.schema.json"
                )
                if schema_errors:
                    return {"error": "Invalid DecisionLedger", "details": schema_errors}
                receipts = arguments.get("receipts") or {}
                ledger_obj = ledger_mod.DecisionLedger.from_dict(
                    ledger_data, receipt_registry=receipts, verification_context=verification_context
                )
                node = ledger_obj.get_decision(decision_id)
                if node is None:
                    return {"error": f"Decision '{decision_id}' not found in ledger"}
                events = ledger_obj.state_history(decision_id)
                corrections = ledger_obj.get_corrections(decision_id)
                bases = ledger_obj.bases_of(decision_id)
                dependent_decisions = ledger_obj.find_decisions_for(decision_id)
                return {
                    "decision_id": decision_id,
                    "decision": node.to_dict(),
                    "state_history": events,
                    "corrections": [c.to_dict() for c in corrections],
                    "bases": bases,
                    "dependent_decisions": dependent_decisions,
                }
            except Exception as exc:
                return {"error": f"Failed to trace decision: {exc}"}

        # 10. academic_recompute_statistics
        elif name == "academic_recompute_statistics":
            if recompute is None:
                return {"error": "recompute module unavailable"}
            t = arguments.get("t_stat")
            df = arguments.get("df")
            p = arguments.get("p_value")
            res = {}
            failures = {}
            t_keys = ("t_stat", "df")
            requested_t = any(key in arguments for key in (*t_keys, "p_value", "p_value_literal", "p_value_decimals"))
            if requested_t and (t is None or df is None):
                failures["t_test"] = "t_stat and df are required together"
            if ("p_value_literal" in arguments or "p_value_decimals" in arguments) and p is None:
                failures["p_match"] = "p_value is required with reported precision"
            if t is not None and df is not None:
                try:
                    p_receipt = recompute.p_from_t(t, df, reported=p)
                    recomputed_val = p_receipt["recomputed"]
                    res["recomputed_p"] = recomputed_val
                    res["p_receipt"] = p_receipt
                    if p is not None:
                        res["p_match"] = recompute.check_p_match(
                            p, recomputed_val, decimals=arguments.get("p_value_decimals"),
                            reported_literal=arguments.get("p_value_literal"),
                        )
                except Exception as exc:
                    res["t_test_error"] = str(exc)
                    failures["t_test"] = str(exc)

            d_keys = ("mean1", "sd1", "n1", "mean2", "sd2", "n2")
            provided_d_keys = [k for k in d_keys if k in arguments and arguments[k] is not None]
            if provided_d_keys:
                missing_d = [k for k in d_keys if k not in arguments or arguments[k] is None]
                if missing_d:
                    res["cohens_d_error"] = f"Missing required parameters for Cohen's d: {', '.join(missing_d)}"
                    failures["cohens_d"] = res["cohens_d_error"]
                else:
                    try:
                        d_res = recompute.cohens_d(
                            arguments["mean1"], arguments["sd1"], arguments["n1"],
                            arguments["mean2"], arguments["sd2"], arguments["n2"]
                        )
                        stats_payload = d_res["recomputed"]
                        res["cohens_d"] = stats_payload["cohens_d"]
                        res["hedges_g"] = stats_payload["hedges_g"]
                        res["pooled_sd"] = stats_payload["pooled_sd"]
                        res["df"] = stats_payload["df"]
                    except Exception as exc:
                        res["cohens_d_error"] = str(exc)
                        failures["cohens_d"] = str(exc)
            if not requested_t and not provided_d_keys:
                failures["input"] = "Provide t_stat and df, or all six two-group effect-size parameters"
            if failures:
                res.update(error="Statistical computation failed", failures=failures,
                           status="partial_failure" if "recomputed_p" in res or "cohens_d" in res else "failed")
            return res

        # 11. academic_check_percentage
        elif name == "academic_check_percentage":
            if recompute is None:
                return {"error": "recompute module unavailable"}
            count = arguments["count"]
            pct = arguments["percent"]
            n = arguments.get("sample_size")
            return recompute.check_percentage(count, pct, n)

        # 12. academic_scfabric_hardware_probe
        elif name == "academic_scfabric_hardware_probe":
            return hardware_probe.probe()

        return {"error": f"Unknown tool: {name}"}

    except (TypeError, ValueError, KeyError, AttributeError) as exc:
        if name in {"research_artifact_validate", "claim_evidence_validate", "decision_ledger_validate"}:
            return {"valid": False, "errors": [str(exc)]}
        if name == "research_receipt_verify":
            return {"valid": False, "error": str(exc)}
        return {"error": "Invalid tool input", "details": [str(exc)]}
    except Exception as exc:
        return {"error": f"Internal execution failure in tool '{name}': {str(exc)}"}


def _rpc_error(msg_id: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def process_message(msg: Any) -> dict | None:
    # MCP uses JSON-RPC objects, string/integer IDs and named parameters.
    # Validate the envelope before deciding whether it is a notification.
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _rpc_error(None, -32600, "Invalid Request")
    if "id" in msg and (isinstance(msg["id"], bool) or not isinstance(msg["id"], (str, int))):
        return _rpc_error(None, -32600, "Invalid request ID")
    if "params" in msg and not isinstance(msg["params"], (dict, list)):
        return _rpc_error(None, -32600, "Invalid Request params")
    if "id" not in msg:
        # Includes cancelled and unknown notifications. This synchronous server
        # does not claim preemptive cancellation of an in-flight computation.
        return None
    method, msg_id = msg["method"], msg["id"]
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return _rpc_error(msg_id, -32602, "MCP params must be an object")

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "initialize":
        client_version = params.get("protocolVersion", "2026-07-28")
        if not isinstance(client_version, str):
            return _rpc_error(msg_id, -32602, "protocolVersion must be a string")
        negotiated_version = client_version if client_version in ("2026-07-28", "2024-11-05") else "2026-07-28"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": negotiated_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "academic-research-kernel",
                    "version": __version__
                }
            }
        }
    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS}
        }
    elif method == "tools/call":
        name = params.get("name")
        if not isinstance(name, str) or not any(tool["name"] == name for tool in TOOLS):
            return _rpc_error(msg_id, -32602, "Unknown or missing tool name")
        arguments = params.get("arguments", {})
        argument_errors = _tool_argument_errors(name, arguments)
        result_data = (
            {"error": "Invalid tool arguments", "details": argument_errors}
            if argument_errors
            else handle_tool_call(name, arguments)
        )
        if _finite_errors(result_data):
            result_data = {"error": "Execution produced a non-finite result"}
        is_error = bool(
            "error" in result_data
            or result_data.get("success") is False
        )
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result_data, ensure_ascii=False, indent=2, allow_nan=False)
                    }
                ],
                "isError": is_error,
            }
        }
    return _rpc_error(msg_id, -32601, f"Method not found: {method}")


def main():
    if sys.platform == "win32":
        for s in (sys.stdin, sys.stdout):
            if s and hasattr(s, "reconfigure"):
                s.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(f"Invalid JSON constant: {token}")))
        except (ValueError, RecursionError) as exc:
            resp = _rpc_error(None, -32700, f"Parse error: {exc}")
        else:
            try:
                resp = process_message(req)
            except Exception as exc:
                print(f"Request execution failed: {exc}", file=sys.stderr)
                resp = _rpc_error(req.get("id") if isinstance(req, dict) else None, -32603, "Internal error")
        if resp is not None:
            # ASCII escapes preserve JSON string identity, including escaped
            # surrogate code units, without crashing the UTF-8 transport writer.
            sys.stdout.write(json.dumps(resp, ensure_ascii=True, allow_nan=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

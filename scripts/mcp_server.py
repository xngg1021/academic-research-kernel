# -*- coding: utf-8 -*-
"""Universal Model Context Protocol (MCP) server for the deterministic research-state kernel.

Exposes core research state verification, artifact ingestion, provenance tracing,
claim-evidence verification, decision audit, and statistical recomputation over
standard JSON-RPC 2.0 stdio transport without external framework lock-in.
Compatible with Claude Code, Cursor, Codex, Gemini CLI, and Hermes.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent

# Inject paths for core capabilities
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "research-object-identity" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "claim-evidence-graph" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "decision-ledger" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "quantitative-paper-audit" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "academic-source-verification" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "scfabric"))

from shared_contracts.evidence import ReceiptRef, verify_receipt_reference
from ingestion import IngestionEngine, ArtifactEnvelope, IngestionKernelState
from ingestion.contracts import validate_adapter_contract, validate_schema
import identity as id_mod
import provenance as prov_mod
import graph as ceg_mod
import ledger as ledger_mod

try:
    import recompute
except Exception:
    recompute = None


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
                    "properties": {
                        "activities": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "required": ["id", "timestamp"],
                                "properties": {
                                    "id": {"type": "string", "minLength": 1},
                                    "timestamp": {"type": "string", "minLength": 1}
                                }
                            }
                        }
                    },
                    "description": "Exported LineageGraph dictionary."
                },
                "target_entity_id": {
                    "type": "string",
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
        "description": "Recompute statistical claims (effect sizes, p-values, t-tests, CIs, OR/RR) to detect rounding errors or impossible figures.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "t_stat": {"type": "number", "description": "Reported t-statistic"},
                "df": {"type": "number", "description": "Degrees of freedom (integer or Welch fractional)"},
                "p_value": {"type": "number", "description": "Reported p-value"},
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
    return [
        f"/{'/'.join(str(part) for part in error.absolute_path)}: {error.message}"
        for error in errors
    ]


def handle_tool_call(name: str, arguments: dict) -> dict:
    try:
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
                receipts = arguments.get("receipts") or {}
                if not isinstance(receipts, dict):
                    return {"valid": False, "errors": ["'receipts' must be a dictionary"]}
                temp_state = IngestionKernelState(
                    ceg=ceg_mod.ClaimEvidenceGraph(),
                    ledger=ledger_mod.DecisionLedger(),
                    receipts=receipts,
                )
                plan = adapter.plan(env, temp_state)
                errors.extend(plan.errors)
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
                )
            elif isinstance(state_data, dict):
                state = IngestionKernelState.from_dict(
                    state_data,
                    ceg_cls=ceg_mod.ClaimEvidenceGraph,
                    ledger_cls=ledger_mod.DecisionLedger,
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
                ref = ReceiptRef(
                    kind=ref_dict["kind"],
                    schema_version=ref_dict["schema_version"],
                    receipt_id=ref_dict.get("receipt_id"),
                    receipt_digest=ref_dict.get("receipt_digest"),
                    claim_digest=ref_dict.get("claim_digest"),
                    payload_sha256=ref_dict.get("payload_sha256"),
                    locator=ref_dict.get("locator"),
                )
            except Exception as exc:
                return {"valid": False, "error": f"Invalid ReceiptRef format: {exc}"}

            ok, err = verify_receipt_reference(ref, receipt_payload)
            if ok:
                schema_file = (
                    "lineage-receipt.schema.json"
                    if ref.kind == "lineage"
                    else "evidence-receipt.schema.json"
                )
                schema_errors = validate_schema(receipt_payload, schema_file)
                if schema_errors:
                    return {"valid": False, "error": "; ".join(schema_errors)}
            return {"valid": ok, "error": err}

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
                    lg.record_used(edge["source_id"], edge["target_id"], metadata=metadata)
                elif edge_type == "generated":
                    lg.record_generated(edge["source_id"], edge["target_id"], metadata=metadata)
                else:
                    raise ValueError(f"Unsupported lineage edge type: {edge_type!r}")
            receipt = prov_mod.trace_origin(lg, target_id, check_on_disk_hashes=False)
            return {"target_entity_id": target_id, "receipt": receipt.to_dict()}

        # 6. claim_evidence_validate
        elif name == "claim_evidence_validate":
            graph_data = arguments.get("graph")
            if not isinstance(graph_data, dict):
                return {"valid": False, "errors": ["'graph' must be a dictionary"]}
            schema_errors = validate_schema(graph_data, "claim-evidence-graph.schema.json")
            if schema_errors:
                return {"valid": False, "errors": schema_errors}
            receipts = arguments.get("receipts") or {}
            cg = ceg_mod.ClaimEvidenceGraph.from_dict(graph_data, receipt_registry=receipts)
            valid, errors = cg.validate_graph()
            return {
                "valid": valid,
                "errors": errors,
                "graph_digest": cg.graph_digest(),
                "node_count": len(cg.claims) + len(cg.evidence_anchors),
            }

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
            cg = ceg_mod.ClaimEvidenceGraph.from_dict(graph_data, receipt_registry=receipts)
            trace_info = cg.trace_claim_provenance(claim_id)
            return {"claim_id": claim_id, "provenance_trace": trace_info}

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
                    ledger_data, receipt_registry=receipts
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
                    ledger_data, receipt_registry=receipts
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
            if t is not None and df is not None:
                try:
                    p_receipt = recompute.p_from_t(float(t), float(df), reported=p)
                    recomputed_val = p_receipt["recomputed"]
                    res["recomputed_p"] = recomputed_val
                    res["p_receipt"] = p_receipt
                    if p is not None:
                        res["p_match"] = recompute.check_p_match(float(p), recomputed_val)
                except Exception as exc:
                    res["t_test_error"] = str(exc)

            d_keys = ("mean1", "sd1", "n1", "mean2", "sd2", "n2")
            provided_d_keys = [k for k in d_keys if k in arguments and arguments[k] is not None]
            if provided_d_keys:
                missing_d = [k for k in d_keys if k not in arguments or arguments[k] is None]
                if missing_d:
                    res["cohens_d_error"] = f"Missing required parameters for Cohen's d: {', '.join(missing_d)}"
                else:
                    try:
                        d_res = recompute.cohens_d(
                            float(arguments["mean1"]), float(arguments["sd1"]), int(arguments["n1"]),
                            float(arguments["mean2"]), float(arguments["sd2"]), int(arguments["n2"])
                        )
                        stats_payload = d_res["recomputed"]
                        res["cohens_d"] = stats_payload["cohens_d"]
                        res["hedges_g"] = stats_payload["hedges_g"]
                        res["pooled_sd"] = stats_payload["pooled_sd"]
                        res["df"] = stats_payload["df"]
                    except Exception as exc:
                        res["cohens_d_error"] = str(exc)
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
            import hardware_probe
            return hardware_probe.probe()

        return {"error": f"Unknown tool: {name}"}

    except Exception as exc:
        return {"error": f"Internal execution failure in tool '{name}': {str(exc)}"}


def process_message(msg: dict) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        client_version = (msg.get("params") or {}).get("protocolVersion", "2026-07-28")
        negotiated_version = client_version if client_version in ("2026-07-28", "2024-11-05") else "2026-07-28"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": negotiated_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "academic-research-kernel",
                    "version": "2.0.0"
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
        params = msg.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        argument_errors = _tool_argument_errors(name, arguments)
        result_data = (
            {"error": "Invalid tool arguments", "details": argument_errors}
            if argument_errors
            else handle_tool_call(name, arguments)
        )
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
                        "text": json.dumps(result_data, ensure_ascii=False, indent=2)
                    }
                ],
                "isError": is_error,
            }
        }
    elif method == "notifications/initialized":
        return None

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }


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
            req = json.loads(line)
            resp = process_message(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"}
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

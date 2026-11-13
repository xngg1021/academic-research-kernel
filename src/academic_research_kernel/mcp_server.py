"""Hardened JSON-RPC 2.0 stdio MCP server for academic-research-kernel (Occam edition).

Provides:
- Bounded binary stdio frame reader (10 MiB frame cap, 64 MiB drain cap, UTF-8 & LSP Content-Length support)
- Strict JSON-RPC 2.0 envelope & notification handling (id-less notifications never mutate state)
- Strict Draft 2020-12 tool argument validation + finite-number & non-boolean numeric enforcement
- Lazy domain-module loading (zero SciPy/NumPy import cost on cold server/CLI startup)
- Server-owned persistent SQLite session state + workspace-confined explicit db_path + read-only trace
- Privacy-redacted double-blind scan responses (never exporting raw author identifiers into LLM logs)
"""
from __future__ import annotations

import collections.abc
from dataclasses import asdict
import importlib
import json
import math
import os
from pathlib import Path
import sys
import threading
from typing import Any, Callable, Mapping, Optional

from ._stdlib import canonical_json, normalize_identifier, safe_path, sha256_hex, thaw, validate_schema
from ._version import __version__
from .state_db import ALLOWED_ARTIFACT_KINDS, ResearchStateDB

MAX_MCP_FRAME_BYTES = 10 * 1024 * 1024
MAX_MCP_DRAIN_BYTES = 64 * 1024 * 1024
SUPPORTED_PROTOCOLS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28")
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

_LAZY_ATTRS = {
    "recompute": "recompute",
    "id_mod": "identity",
    "identity": "identity",
    "meta_core": "meta_core",
    "verify_work": "verify_work",
    "openreview_audit": "openreview_audit",
    "double_blind_sanitizer": "double_blind_sanitizer",
    "pre_submission_linter": "pre_submission_linter",
    "watch": "watch",
}


def __getattr__(name: str) -> Any:
    target = _LAZY_ATTRS.get(name)
    if target is not None:
        mod = importlib.import_module(f".{target}", __package__ or "academic_research_kernel")
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _mod(name: str) -> Any:
    return importlib.import_module(f".{name}", __package__ or "academic_research_kernel")


_SESSION_LOCK = threading.RLock()
_SESSION_DB: Optional[ResearchStateDB] = None


def get_session_db() -> ResearchStateDB:
    global _SESSION_DB
    with _SESSION_LOCK:
        if _SESSION_DB is None or _SESSION_DB._closed:
            _SESSION_DB = ResearchStateDB(":memory:")
        return _SESSION_DB


def reset_session_db() -> None:
    global _SESSION_DB
    with _SESSION_LOCK:
        if _SESSION_DB is not None:
            _SESSION_DB.close()
            _SESSION_DB = None


def authorized_workspace_root() -> Path:
    env_root = (os.environ.get("ARK_WORKSPACE_ROOT") or "").strip()
    base = Path(env_root) if env_root else Path.cwd()
    return safe_path(base)


def _with_db(args: Mapping[str, Any], fn: Callable[[ResearchStateDB], Any], *, readonly: bool = False) -> Any:
    raw_db = args.get("db_path")
    if raw_db is None or str(raw_db).strip() in ("", ":memory:"):
        return thaw(fn(get_session_db()))
    root = authorized_workspace_root()
    with ResearchStateDB(str(raw_db), readonly=readonly, root=root) as db:
        return thaw(fn(db))


TOOLS: list[dict[str, Any]] = [
    {
        "name": "research_state_ingest",
        "description": "Atomically ingest research artifacts & lineage edges into SQLite STRICT state.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["items"],
            "properties": {
                "db_path": {"type": "string"},
                "items": {"type": "array", "items": {"type": "object"}},
                "atomic": {"type": "boolean"},
            },
        },
    },
    {
        "name": "research_artifact_ingest",
        "description": "Ingest a single research artifact or envelope into SQLite STRICT state.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["artifact_id", "kind", "payload"],
            "properties": {
                "db_path": {"type": "string"},
                "artifact_id": {"type": "string", "minLength": 1},
                "kind": {"type": "string", "minLength": 1},
                "payload": {"type": "object"},
                "parents": {"type": "array", "items": {"type": "string"}},
                "relation": {"type": "string"},
            },
        },
    },
    {
        "name": "research_artifact_validate",
        "description": "Validate a research artifact against canonical JSON schemas and kind invariants.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["kind", "payload"],
            "properties": {
                "artifact_id": {"type": "string"},
                "kind": {"type": "string"},
                "payload": {"type": "object"},
                "schema_name": {"type": "string"},
            },
        },
    },
    {
        "name": "research_receipt_verify",
        "description": "Verify canonical SHA-256 digest of an artifact payload against an expected receipt digest.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["payload", "expected_sha256"],
            "properties": {
                "payload": {"type": "object"},
                "expected_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
            },
        },
    },
    {
        "name": "research_lineage_trace",
        "description": "Trace transitive ancestor artifacts via SQLite recursive CTE or an inline lineage_graph.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "db_path": {"type": "string"},
                "artifact_id": {"type": "string", "minLength": 1},
                "target_entity_id": {"type": "string", "minLength": 1},
                "lineage_graph": {"type": "object"},
            },
        },
    },
    {
        "name": "claim_evidence_add",
        "description": "Register an immutable scholarly claim with supporting/contradicting artifact anchors.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["claim_id", "claim_text"],
            "properties": {
                "db_path": {"type": "string"},
                "claim_id": {"type": "string", "minLength": 1},
                "claim_text": {"type": "string", "minLength": 1},
                "status": {"type": "string"},
                "evidence": {"type": "array", "items": {"type": "array"}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "metadata": {"type": "object"},
            },
        },
    },
    {
        "name": "claim_evidence_validate",
        "description": "Validate a ClaimEvidenceGraph JSON document against canonical schema and anchor rules.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ceg"],
            "properties": {"ceg": {"type": "object"}},
        },
    },
    {
        "name": "claim_evidence_trace",
        "description": "Export or trace claim support/contestation status from SQLite state.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"db_path": {"type": "string"}, "claim_id": {"type": "string"}},
        },
    },
    {
        "name": "decision_record",
        "description": "Append an immutable research decision or negative result (enforces E405/E406 basis rule).",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decision_id", "title"],
            "properties": {
                "db_path": {"type": "string"},
                "decision_id": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1},
                "entry_kind": {"type": "string"},
                "action": {"type": "string"},
                "verdict": {"type": "string"},
                "basis_decision_id": {"type": "string"},
                "artifact_id": {"type": "string"},
                "initial_state": {"type": "string"},
                "metadata": {"type": "object"},
            },
        },
    },
    {
        "name": "decision_transition",
        "description": "Append an acyclic prune/reopen state event to a recorded decision.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decision_id", "new_state", "reason"],
            "properties": {
                "db_path": {"type": "string"},
                "decision_id": {"type": "string", "minLength": 1},
                "new_state": {"type": "string"},
                "reason": {"type": "string"},
                "superseded_by_id": {"type": "string"},
                "verdict_override": {"type": "string"},
            },
        },
    },
    {
        "name": "decision_ledger_validate",
        "description": "Validate a decision-ledger receipt JSON object against canonical schema.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["ledger"],
            "properties": {"ledger": {"type": "object"}},
        },
    },
    {
        "name": "decision_trace",
        "description": "Read immutable decision record and chronological event history from SQLite state.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decision_id"],
            "properties": {"db_path": {"type": "string"}, "decision_id": {"type": "string", "minLength": 1}},
        },
    },
    {
        "name": "research_object_resolve",
        "description": "Resolve scholarly work metadata records using the 5-state deterministic identity resolver.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "records": {"type": "array", "items": {"type": "object"}},
                "record": {"type": "object"},
            },
        },
    },
    {
        "name": "academic_recompute_statistics",
        "description": "Recompute t/F/chi2/z p-values, Cohen's d, OR/RR, CI consistency, SD bounds, df, or power.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "kind": {"type": "string"},
                "params": {"type": "object"},
                "t_stat": {"type": "number"},
                "df": {"type": "number"},
                "p_value": {"type": "number"},
                "p_value_literal": {"type": "string"},
                "f_stat": {"type": "number"},
                "df1": {"type": "number"},
                "df2": {"type": "number"},
                "chi2_stat": {"type": "number"},
                "chi2_df": {"type": "number"},
                "beta": {"type": "number"},
                "se": {"type": "number"},
                "z_value": {"type": "number"},
                "ci_estimate": {"type": "number"},
                "ci_lower": {"type": "number"},
                "ci_upper": {"type": "number"},
                "ci_level": {"type": "number"},
                "ci_log_scale": {"type": "boolean"},
                "ci_method": {"type": "string"},
                "cell_a": {"type": "integer"},
                "cell_b": {"type": "integer"},
                "cell_c": {"type": "integer"},
                "cell_d": {"type": "integer"},
                "mean1": {"type": "number"},
                "sd1": {"type": "number"},
                "n1": {"type": "integer"},
                "mean2": {"type": "number"},
                "sd2": {"type": "number"},
                "n2": {"type": "integer"},
                "check_sd": {"type": "number"},
                "scale_min": {"type": "number"},
                "scale_max": {"type": "number"},
                "sample_n": {"type": "integer"},
                "sample_df": {"type": "number"},
                "reported_n": {"type": "integer"},
                "df_kind": {"type": "string"},
                "n_params": {"type": "integer"},
                "effect_size_d": {"type": "number"},
                "power_n1": {"type": "integer"},
                "power_n2": {"type": "integer"},
                "alpha": {"type": "number"},
            },
        },
    },
    {
        "name": "academic_check_percentage",
        "description": "GRIM-style integer numerator/denominator consistency check for reported percentages.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["count", "percent"],
            "properties": {
                "count": {"type": "integer"},
                "percent": {"type": ["number", "string"]},
                "sample_size": {"type": "integer"},
                "n": {"type": "integer"},
                "denominator": {"type": "integer"},
                "decimals": {"type": "integer"},
            },
        },
    },
    {
        "name": "academic_table_forensics",
        "description": "Audit partition conservation, constant-offset ablation deltas, and storage/bandwidth bounds.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "partition": {"type": "object"},
                "ablation_matrix": {"type": ["object", "array"]},
                "ablation_baseline_col": {"type": "integer"},
                "ablation_min_rows": {"type": "integer"},
                "ablation_tol": {"type": "number"},
                "storage_bandwidth": {"type": "object"},
            },
        },
    },
    {
        "name": "academic_meta_analyze",
        "description": "Run fixed-effect and DerSimonian-Laird random-effects meta-analysis with LOO and Egger/trim-and-fill.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["studies"],
            "properties": {
                "studies": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["yi", "vi"],
                        "properties": {"yi": {"type": "number"}, "vi": {"type": "number"}, "study_id": {"type": "string"}},
                    },
                }
            },
        },
    },
    {
        "name": "academic_verify_source",
        "description": "Normalize DOI/arXiv/PMID/OpenAlex ID or compare OpenAlex and Crossref work records.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["identifier"],
            "properties": {
                "identifier": {"type": "string"},
                "live": {"type": "boolean"},
                "offline": {"type": "boolean"},
                "normalize_only": {"type": "boolean"},
                "openalex": {"type": "object"},
                "openalex_record": {"type": "object"},
                "crossref": {"type": "object"},
                "crossref_record": {"type": "object"},
            },
        },
    },
    {
        "name": "academic_openreview_audit",
        "description": "Audit OpenReview forum notes, mirror records, or venue-level rating distributions.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "forum_id": {"type": "string"},
                "notes": {"type": ["array", "object"]},
                "venue_records": {"type": "array", "items": {"type": "object"}},
                "topic_regex": {"type": "string"},
            },
        },
    },
    {
        "name": "academic_double_blind_sanitize",
        "description": "Scan manuscript file or directory for double-blind anonymity leaks (redacted public output).",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "target": {"type": "string"},
                "target_path": {"type": "string"},
                "forbidden_tokens": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
    {
        "name": "academic_pre_submission_lint",
        "description": "Check TeX bundle for missing includes/refs/bibs, layout tampering, page limits, and blind leaks.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "tex": {"type": "string"},
                "tex_path": {"type": "string"},
                "venue": {"type": "string"},
                "phase": {"type": "string"},
                "contribution_type": {"type": "string"},
                "double_blind": {"type": "boolean"},
                "pdf_path": {"type": "string"},
                "ceg_path": {"type": "string"},
                "require_ceg_binding": {"type": "boolean"},
                "check_academic_style": {"type": "boolean"},
            },
        },
    },
    {
        "name": "academic_retraction_watch",
        "description": "Check DOI retraction/correction deltas backed by SQLite WAL state with CAS ordering.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["dois"],
            "properties": {
                "dois": {"type": "array", "items": {"type": "string"}},
                "db_path": {"type": "string"},
                "live": {"type": "boolean"},
            },
        },
    },
]

_TOOL_MAP: dict[str, dict[str, Any]] = {t["name"]: t for t in TOOLS}


def _check_finite(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, float):
        if not math.isfinite(value):
            return [f"{path}: non-finite number {value!r} is not allowed"]
        return []
    if isinstance(value, collections.abc.Mapping):
        errs: list[str] = []
        for k, v in value.items():
            errs.extend(_check_finite(v, f"{path}.{k}"))
        return errs
    if isinstance(value, (list, tuple)):
        errs = []
        for idx, item in enumerate(value):
            errs.extend(_check_finite(item, f"{path}[{idx}]"))
        return errs
    return []


TOOL_ALIASES: Mapping[str, str] = {
    "academic_recompute_stat": "academic_recompute_statistics",
    "verify_statistical_consistency": "academic_recompute_statistics",
    "run_meta_analysis": "academic_meta_analyze",
    "academic_sanitize_double_blind": "academic_double_blind_sanitize",
    "audit_anonymity": "academic_double_blind_sanitize",
    "lint_manuscript": "academic_pre_submission_lint",
    "academic_resolve_work_identity": "research_object_resolve",
    "resolve_work_identity": "research_object_resolve",
    "research_claim_register": "claim_evidence_add",
}


def _validate_tool_arguments(name: str, arguments: Any) -> list[str]:
    if not isinstance(arguments, dict):
        return ["Tool arguments must be a JSON object"]
    errs = _check_finite(arguments)
    if errs:
        return errs
    canon = TOOL_ALIASES.get(name, name)
    spec = _TOOL_MAP.get(canon)
    if spec is None:
        return [f"Unknown tool: {name}"]
    from jsonschema import Draft202012Validator

    validator = Draft202012Validator(spec["inputSchema"])
    for err in validator.iter_errors(arguments):
        loc = ".".join(str(p) for p in err.path) or "<arguments>"
        errs.append(f"{loc}: {err.message}")
    return errs


def _redact_blind_scan_report(rep: Mapping[str, Any]) -> dict[str, Any]:
    raw_findings = rep.get("findings") or []
    public_findings: list[dict[str, Any]] = []
    if isinstance(raw_findings, list):
        for idx, item in enumerate(raw_findings, 1):
            if not isinstance(item, dict):
                continue
            pub: dict[str, Any] = {
                "finding_id": idx,
                "kind": str(item.get("kind") or "leak"),
                "matched": "[REDACTED]",
            }
            line_val = item.get("line")
            if type(line_val) is int and line_val >= 0:
                pub["line"] = line_val
            public_findings.append(pub)
    unsupported = rep.get("unsupported_files") or []
    skipped = rep.get("skipped_symlinks") or []
    return {
        "status": str(rep.get("status") or "incomplete"),
        "files_scanned": int(rep.get("files_scanned", 0)),
        "unsupported_file_count": len(unsupported) if isinstance(unsupported, list) else 0,
        "skipped_symlink_count": len(skipped) if isinstance(skipped, list) else 0,
        "leak_count": len(public_findings),
        "findings": public_findings,
    }


def _trace_inline_lineage_graph(graph: Mapping[str, Any], target_id: str) -> dict[str, Any]:
    edges = graph.get("derivations") or graph.get("edges") or []
    parents_by_child: dict[str, set[str]] = {}
    if isinstance(edges, list):
        for e in edges:
            if isinstance(e, dict):
                c = str(e.get("child_id") or e.get("derived_id") or e.get("entity_id") or "")
                p = str(e.get("parent_id") or e.get("source_id") or e.get("used_id") or "")
                if c and p:
                    parents_by_child.setdefault(c, set()).add(p)
    visited: set[str] = set()
    stack = list(parents_by_child.get(target_id, ()))
    while stack:
        cur = stack.pop()
        if cur == target_id:
            raise ValueError(f"Cycle detected in inline lineage_graph at {target_id!r}")
        if cur in visited:
            continue
        visited.add(cur)
        stack.extend(parents_by_child.get(cur, ()))
    return {"artifact_id": target_id, "ancestors": sorted(visited), "verification_status": "intact"}


def handle_tool_call(name: str, args: Mapping[str, Any] | None = None) -> dict[str, Any]:
    name = TOOL_ALIASES.get(name, name)
    a = dict(args or {})

    if name == "research_state_ingest":
        return _with_db(
            a,
            lambda db: {
                "receipts": db.batch_ingest(a["items"], atomic=a.get("atomic", True)),
                "state_digest": db.snapshot_digest(),
            },
        )

    if name == "research_artifact_ingest":
        item = {
            "artifact_id": a["artifact_id"],
            "kind": a["kind"],
            "payload": a["payload"],
            "parents": a.get("parents") or (),
            "relation": a.get("relation", "derived_from"),
        }
        return _with_db(
            a,
            lambda db: {
                "receipt": db.batch_ingest([item], atomic=True)[0],
                "state_digest": db.snapshot_digest(),
            },
        )

    if name == "research_artifact_validate":
        kind = str(a["kind"])
        if kind not in ALLOWED_ARTIFACT_KINDS:
            return {"valid": False, "errors": [f"Unknown artifact kind: {kind!r}"]}
        schema_name = a.get("schema_name")
        if schema_name:
            errs = validate_schema(a["payload"], str(schema_name))
            return {"valid": len(errs) == 0, "errors": errs}
        try:
            ResearchStateDB._validate_artifact_semantics(a.get("artifact_id") or "probe", kind, a["payload"])
            return {"valid": True, "errors": []}
        except Exception as exc:
            return {"valid": False, "errors": [str(exc)]}

    if name == "research_receipt_verify":
        actual = sha256_hex(canonical_json(a["payload"]))
        expected = str(a["expected_sha256"]).strip().lower()
        return {"valid": actual == expected, "computed_sha256": actual, "expected_sha256": expected}

    if name == "research_lineage_trace":
        if isinstance(a.get("lineage_graph"), Mapping) and a.get("target_entity_id"):
            return _trace_inline_lineage_graph(a["lineage_graph"], str(a["target_entity_id"]))
        aid = a.get("artifact_id") or a.get("target_entity_id")
        if not aid:
            raise ValueError("research_lineage_trace requires artifact_id (or lineage_graph + target_entity_id)")
        return _with_db(
            a,
            lambda db: {"artifact_id": str(aid), "ancestors": db.trace_lineage(str(aid))},
            readonly=bool(a.get("db_path") and str(a.get("db_path")) != ":memory:"),
        )

    if name == "claim_evidence_add":
        ev = [tuple(x) for x in a.get("evidence", ())]
        return _with_db(
            a,
            lambda db: db.add_claim(
                a["claim_id"],
                a["claim_text"],
                a.get("status"),
                ev,
                a.get("depends_on", ()),
                metadata=a.get("metadata"),
            ),
        )

    if name == "claim_evidence_validate":
        errs = validate_schema(a["ceg"], "claim-evidence-graph.schema.json")
        return {"valid": len(errs) == 0, "errors": errs}

    if name == "claim_evidence_trace":
        is_ro = bool(a.get("db_path") and str(a.get("db_path")) != ":memory:")

        def _trace_ceg(db: ResearchStateDB) -> dict[str, Any]:
            ceg = db.export_ceg_dict()
            target_cid = a.get("claim_id")
            if target_cid:
                matches = [c for c in ceg["claims"] if c["id"] == target_cid]
                edges = [e for e in ceg["support_edges"] if e["claim_id"] == target_cid]
                return {"claim": matches[0] if matches else None, "support_edges": edges}
            return ceg

        return _with_db(a, _trace_ceg, readonly=is_ro)

    if name == "decision_record":
        return _with_db(
            a,
            lambda db: db.record_decision(
                a["decision_id"],
                a["title"],
                entry_kind=a.get("entry_kind", "decision"),
                action=a.get("action", "explore"),
                verdict=a.get("verdict", "inconclusive"),
                basis_decision_id=a.get("basis_decision_id"),
                artifact_id=a.get("artifact_id"),
                initial_state=a.get("initial_state", "active"),
                metadata=a.get("metadata"),
            ),
        )

    if name == "decision_transition":
        return _with_db(
            a,
            lambda db: db.transition_decision(
                a["decision_id"],
                a["new_state"],
                a["reason"],
                a.get("superseded_by_id"),
                a.get("verdict_override"),
            ),
        )

    if name == "decision_ledger_validate":
        errs = validate_schema(a["ledger"], "decision-ledger-receipt.schema.json")
        return {"valid": len(errs) == 0, "errors": errs}

    if name == "decision_trace":
        is_ro = bool(a.get("db_path") and str(a.get("db_path")) != ":memory:")

        def _trace_dec(db: ResearchStateDB) -> dict[str, Any]:
            with db._read_snapshot() as conn:
                dec = conn.execute("SELECT * FROM decisions WHERE decision_id = ?", (a["decision_id"],)).fetchone()
                evs = conn.execute(
                    "SELECT * FROM decision_events WHERE decision_id = ? ORDER BY seq ASC", (a["decision_id"],)
                ).fetchall()
            if dec is None:
                raise ValueError(f"Unknown decision_id: {a['decision_id']!r}")
            return {"decision": dict(dec), "events": [dict(e) for e in evs]}

        return _with_db(a, _trace_dec, readonly=is_ro)

    if name == "research_object_resolve":
        ident = _mod("identity")
        if "records" in a and a["records"] is not None:
            recs = a["records"]
            if not isinstance(recs, list) or not recs:
                raise ValueError("records must be a non-empty list of work observation dicts")
            return {"resolved": thaw(ident.resolve(recs))}
        if "record" in a and isinstance(a["record"], Mapping):
            return {"resolved": thaw(ident.resolve([dict(a["record"])]))}
        raise ValueError("research_object_resolve requires 'records' (list) or 'record' (object)")

    if name == "academic_check_percentage":
        rec_mod = _mod("recompute")
        denom = a.get("sample_size", a.get("n", a.get("denominator")))
        if isinstance(a["count"], bool) or isinstance(denom, bool):
            raise TypeError("count and sample_size must be integers, not booleans")
        return rec_mod.check_percentage(a["count"], a["percent"], denominator=denom, decimals=a.get("decimals"))

    if name == "academic_recompute_statistics":
        rec_mod = _mod("recompute")
        if "params" in a and "kind" in a:
            p = dict(a["params"] or {})
            dispatch = {
                "t": rec_mod.p_from_t,
                "f": rec_mod.p_from_f,
                "chi2": rec_mod.p_from_chi2,
                "z": rec_mod.z_from_beta_se,
                "cohens_d": rec_mod.cohens_d,
                "ci": rec_mod.check_ci_consistency,
                "power": rec_mod.achieved_power_ttest,
            }
            if a["kind"] not in dispatch:
                raise ValueError(f"Unsupported statistics kind: {a['kind']!r}")
            return dispatch[a["kind"]](**p)

        out_stat: dict[str, Any] = {}
        partial_errors: dict[str, str] = {}

        def _run_part(label: str, fn: Callable[[], None]) -> None:
            try:
                fn()
            except Exception as exc:
                partial_errors[label] = f"{type(exc).__name__}: {exc}"

        if "t_stat" in a or "df" in a:
            def _do_t() -> None:
                r = rec_mod.p_from_t(a["t_stat"], a["df"], reported=a.get("p_value"))
                out_stat.update(recomputed_p=r["recomputed"], p_receipt=r)
                if "p_value" in a or "p_value_literal" in a:
                    rep_val = a["p_value"] if "p_value" in a else a["p_value_literal"]
                    try:
                        pm = rec_mod.check_p_match(
                            rep_val,
                            r["recomputed"],
                            reported_literal=a.get("p_value_literal"),
                        )
                    except ValueError as exc:
                        pm = {"consistent": False, "error": str(exc)}
                    out_stat["p_match"] = pm
                    out_stat["consistent"] = bool(pm.get("consistent"))
            _run_part("t_test", _do_t)

        if "f_stat" in a:
            _run_part(
                "f_test",
                lambda: out_stat.update(
                    **{
                        "f_receipt": (r := rec_mod.p_from_f(a["f_stat"], a["df1"], a["df2"], reported=a.get("p_value"))),
                        "recomputed_f_p": r["recomputed"],
                    }
                ),
            )

        if "chi2_stat" in a:
            _run_part(
                "chi2_test",
                lambda: out_stat.update(
                    **{
                        "chi2_receipt": (
                            r := rec_mod.p_from_chi2(a["chi2_stat"], a.get("chi2_df", a.get("df")), reported=a.get("p_value"))
                        ),
                        "recomputed_chi2_p": r["recomputed"],
                    }
                ),
            )

        if "beta" in a or "se" in a:
            def _do_z() -> None:
                r = rec_mod.z_from_beta_se(a["beta"], a["se"], reported=a.get("z_value"))
                out_stat.update(recomputed_z=r["recomputed"]["z"], recomputed_z_p=r["recomputed"]["p"], z_receipt=r)
            _run_part("z_test", _do_z)

        if "ci_estimate" in a:
            _run_part(
                "ci_consistency",
                lambda: out_stat.update(
                    ci_consistency=rec_mod.check_ci_consistency(
                        a["ci_estimate"],
                        a["ci_lower"],
                        a["ci_upper"],
                        level=a.get("ci_level", 0.95),
                        log_scale=a.get("ci_log_scale", False),
                        ci_method=a.get("ci_method"),
                    )
                ),
            )

        if "cell_a" in a:
            _run_part(
                "or_rr",
                lambda: out_stat.update(
                    or_rr=rec_mod.or_rr_from_2x2(
                        a["cell_a"], a["cell_b"], a["cell_c"], a["cell_d"], level=a.get("ci_level", 0.95)
                    )
                ),
            )

        if any(k in a for k in ("mean1", "sd1", "n1", "mean2", "sd2", "n2")):
            def _do_d() -> None:
                r = rec_mod.cohens_d(a["mean1"], a["sd1"], a["n1"], a["mean2"], a["sd2"], a["n2"])
                out_stat.update(r["recomputed"] if isinstance(r.get("recomputed"), dict) else r)
            _run_part("effect_size", _do_d)

        if "check_sd" in a:
            _run_part(
                "sd_possible",
                lambda: out_stat.update(
                    sd_possible=rec_mod.check_sd_possible(a["check_sd"], a["scale_min"], a["scale_max"], n=a.get("sample_n"))
                ),
            )

        if "sample_df" in a:
            _run_part(
                "sample_size_from_df",
                lambda: out_stat.update(
                    sample_size_from_df=rec_mod.check_sample_size_from_df(
                        a["sample_df"], a["reported_n"], kind=a.get("df_kind", "ttest_2sample"), n_params=a.get("n_params")
                    )
                ),
            )

        if "effect_size_d" in a:
            _run_part(
                "achieved_power",
                lambda: out_stat.update(
                    achieved_power=rec_mod.achieved_power_ttest(
                        a["effect_size_d"], a["power_n1"], n2=a.get("power_n2"), alpha=a.get("alpha", 0.05)
                    )
                ),
            )

        if not out_stat and not partial_errors:
            raise ValueError("No statistical parameters provided to academic_recompute_statistics")
        if partial_errors:
            if not out_stat:
                raise ValueError("; ".join(f"{k}: {v}" for k, v in partial_errors.items()))
            out_stat["partial_failure"] = partial_errors
        return out_stat

    if name == "academic_table_forensics":
        rec_mod = _mod("recompute")
        out: dict[str, Any] = {}
        if a.get("partition") is not None:
            pt = a["partition"]
            out["partition_conservation"] = rec_mod.check_partition_conservation(
                pt["total"],
                pt["parts"],
                reported_shares=pt.get("reported_shares"),
                tol=pt.get("tol", 0),
                share_tol_pct=pt.get("share_tol_pct", 0.5),
                share_unit=pt.get("share_unit", "auto"),
            )
        if a.get("ablation_matrix") is not None:
            ab = a["ablation_matrix"]
            mat = ab["matrix"] if isinstance(ab, dict) else ab
            out["ablation_delta_regularity"] = rec_mod.check_ablation_delta_regularity(
                mat,
                baseline_col=a.get("ablation_baseline_col", ab.get("baseline_col", 0) if isinstance(ab, dict) else 0),
                min_rows=a.get("ablation_min_rows", ab.get("min_rows", 3) if isinstance(ab, dict) else 3),
                tol=a.get("ablation_tol", ab.get("tol", 1e-9) if isinstance(ab, dict) else 1e-9),
            )
        if a.get("storage_bandwidth") is not None:
            sb = a["storage_bandwidth"]
            out["storage_bandwidth_bounds"] = rec_mod.check_storage_bandwidth_bounds(**sb)
        if not out:
            raise ValueError("Provide at least one of: partition, ablation_matrix, storage_bandwidth")
        out["consistent"] = all(v.get("consistent") is True for v in out.values() if isinstance(v, dict))
        return out

    if name == "academic_meta_analyze":
        mc = _mod("meta_core")
        studies = a["studies"]
        if not studies:
            raise ValueError("studies must be a non-empty list")
        yi: list[float] = []
        vi: list[float] = []
        for idx, s in enumerate(studies):
            ry, rv = s["yi"], s["vi"]
            if isinstance(ry, bool) or isinstance(rv, bool):
                raise TypeError(f"studies[{idx}] yi/vi must be numbers, not booleans")
            yv, vv = float(ry), float(rv)
            if not (math.isfinite(yv) and math.isfinite(vv)) or vv <= 0:
                raise ValueError(f"studies[{idx}] requires finite yi and positive finite vi")
            yi.append(yv)
            vi.append(vv)
        loo = [asdict(r) for r in mc.leave_one_out(yi, vi)] if len(yi) >= 2 else []
        bias = None
        if len(yi) >= 3:
            try:
                icp, tv, pv = mc.egger_test(yi, vi)
                egger_out = {
                    "status": "ok",
                    "intercept": icp,
                    "t": tv if math.isfinite(tv) else None,
                    "p": pv if math.isfinite(pv) else None,
                }
            except (ValueError, ZeroDivisionError) as exc:
                egger_out = {"status": "not_estimable", "reason": str(exc)}
            try:
                tf_out = mc.trim_and_fill(yi, vi)
            except (ValueError, ZeroDivisionError) as exc:
                tf_out = {"status": "not_estimable", "reason": str(exc)}
            bias = {"egger": egger_out, "trim_and_fill": tf_out}
        return {
            "study_count": len(yi),
            "fixed_effect": asdict(mc.pool_fixed(yi, vi)),
            "random_effects_dl": asdict(mc.pool_random(yi, vi)),
            "leave_one_out": loo,
            "publication_bias": bias,
        }

    if name == "academic_verify_source":
        vw = _mod("verify_work")
        norm = normalize_identifier(a["identifier"])
        if a.get("normalize_only") or norm["type"] != "doi":
            return norm
        doi = norm["value"]
        oa_in = a.get("openalex_record") if a.get("openalex_record") is not None else a.get("openalex")
        cr_in = a.get("crossref_record") if a.get("crossref_record") is not None else a.get("crossref")
        offline = bool(a.get("offline")) or (a.get("live") is False and oa_in is None and cr_in is None)
        sources_out: dict[str, Any] = {}
        parsed = []
        for s_name, pre_rec, live_fn, parse_fn in (
            ("openalex", oa_in, vw.fetch_openalex, vw.parse_openalex_work),
            ("crossref", cr_in, vw.fetch_crossref, vw.parse_crossref_work),
        ):
            if pre_rec is not None:
                w = parse_fn(pre_rec)
                sources_out[s_name] = {"status": "ok", "mode": "offline-record", "work": w}
                parsed.append(w)
            elif offline or not a.get("live", False):
                sources_out[s_name] = {"status": "skipped", "reason": "offline mode; no record provided"}
            else:
                try:
                    w = parse_fn(live_fn(doi))
                    sources_out[s_name] = {"status": "ok", "mode": "live", "work": w}
                    parsed.append(w)
                except Exception as exc:
                    sources_out[s_name] = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
        cmp = vw.compare_works(parsed, target_doi=doi) if parsed else None
        return {"normalized": norm, "target_doi": doi, "sources": sources_out, "comparison": cmp}

    if name == "academic_openreview_audit":
        ora = _mod("openreview_audit")
        if a.get("venue_records") is not None:
            return ora.summarize_venue_mirror(a["venue_records"], topic_regex=a.get("topic_regex"))
        if a.get("notes") is not None:
            notes_in = a["notes"]
            fid = a.get("forum_id")
            if isinstance(notes_in, list) and notes_in and isinstance(notes_in[0], dict):
                if not fid:
                    fid = notes_in[0].get("forum") or notes_in[0].get("id") or notes_in[0].get("openreview_forum")
                if "content" not in notes_in[0] and (
                    "rating" in notes_in[0] or "openreview_forum" in notes_in[0] or "status" in notes_in[0]
                ):
                    return ora.parse_openreview_notes(notes_in, forum_id=fid)
            payload = notes_in if isinstance(notes_in, dict) else {"notes": notes_in}
            return ora.parse_openreview_notes(payload, forum_id=fid)
        if a.get("forum_id"):
            return ora.audit_forum(a["forum_id"])
        raise ValueError("Provide one of: venue_records, notes, or forum_id")

    if name == "academic_double_blind_sanitize":
        target = a.get("target_path") or a.get("target")
        if not target:
            return {"error": "Invalid tool input", "details": ["Provide target or target_path"]}
        try:
            dbs = _mod("double_blind_sanitizer")
            forb = [str(t) for t in (a.get("forbidden_tokens") or []) if str(t)]
            rep = dbs.scan_target(Path(str(target)), forbidden_tokens=forb)
            return _redact_blind_scan_report(rep)
        except Exception:
            return {
                "error": "Anonymity scan failed",
                "details": ["Source path and error details were withheld to prevent identifier leakage"],
            }

    if name == "academic_pre_submission_lint":
        tex = a.get("tex_path") or a.get("tex")
        if not tex:
            raise ValueError("Provide tex or tex_path")
        psl = _mod("pre_submission_linter")
        return thaw(
            psl.lint_manuscript(
                tex,
                venue=a.get("venue", "iclr"),
                double_blind=a.get("double_blind"),
                phase=a.get("phase", "submission"),
                contribution_type=a.get("contribution_type", "general_empirical"),
                pdf_path=a.get("pdf_path"),
                ceg_path=a.get("ceg_path"),
                require_ceg_binding=bool(a.get("require_ceg_binding", False)),
                check_academic_style=bool(a.get("check_academic_style", False)),
            )
        )

    if name == "academic_retraction_watch":
        wmod = _mod("watch")
        raw_db = a.get("db_path")
        if raw_db is None or str(raw_db).strip() in ("", ":memory:"):
            rep = wmod.check_retraction_report(a["dois"], live=bool(a.get("live")), db=get_session_db())
        else:
            rep = wmod.check_retraction_report(
                a["dois"],
                db_path=str(raw_db),
                live=bool(a.get("live")),
                root=authorized_workspace_root(),
            )
        return rep

    raise ValueError(f"Unknown MCP tool: {name!r}")


def _rpc_error(msg_id: Any, code: int, message: str, data: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": msg_id, "error": err}


def process_message(msg: Any) -> dict[str, Any] | None:
    """Validate JSON-RPC 2.0 envelope and dispatch synchronously without executing id-less call notifications."""
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
        return _rpc_error(None, -32600, "Invalid Request")
    if "id" in msg and (isinstance(msg["id"], bool) or not isinstance(msg["id"], (str, int))):
        return _rpc_error(None, -32600, "Invalid request ID")
    if "params" in msg and not isinstance(msg["params"], (dict, list)):
        return _rpc_error(None, -32600, "Invalid Request params")
    if "id" not in msg:
        # JSON-RPC notification (e.g. notifications/initialized, notifications/cancelled): never mutate state or reply
        return None

    method = msg["method"]
    msg_id = msg["id"]
    params = msg.get("params", {})
    if not isinstance(params, dict):
        return _rpc_error(msg_id, -32602, "MCP params must be an object")

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "initialize":
        client_ver = params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION)
        if not isinstance(client_ver, str):
            return _rpc_error(msg_id, -32602, "protocolVersion must be a string")
        negotiated = client_ver if client_ver in SUPPORTED_PROTOCOLS else DEFAULT_PROTOCOL_VERSION
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "academic-research-kernel", "version": __version__},
            },
        }
    if method == "server/discover":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "supportedVersions": list(SUPPORTED_PROTOCOLS),
                "resultType": "complete",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "academic-research-kernel", "version": __version__},
                "tools": TOOLS,
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "resources/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resources": []}}
    if method == "resources/templates/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"resourceTemplates": []}}
    if method == "prompts/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"prompts": []}}
    if method == "tools/call":
        tname = params.get("name")
        canon_name = TOOL_ALIASES.get(tname, tname) if isinstance(tname, str) else None
        if not isinstance(canon_name, str) or canon_name not in _TOOL_MAP:
            return _rpc_error(msg_id, -32602, f"Unknown or missing tool name: {tname!r}")
        targs = params.get("arguments", {})
        arg_errs = _validate_tool_arguments(tname, targs)
        if arg_errs:
            payload: dict[str, Any] = {"error": "Invalid tool arguments", "details": arg_errs}
            is_err = True
        else:
            try:
                payload = handle_tool_call(tname, targs)
                is_err = bool("error" in payload or payload.get("valid") is False and "errors" in payload and False)
                if "error" in payload:
                    is_err = True
            except Exception as exc:
                payload = {"error": str(exc)}
                is_err = True
        if _check_finite(payload):
            payload = {"error": "Execution produced a non-finite result"}
            is_err = True
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, allow_nan=False)}],
                "isError": is_err,
            },
        }
    return _rpc_error(msg_id, -32601, f"Method not found: {method}")


# Keep alias for existing internal/test callers
handle_rpc = process_message


import io


def _iter_bounded_stdio_frames(stream: Any):
    """Yield (payload_str, err_kind, use_lsp_header) with strict 10 MiB frame and 64 MiB drain caps."""
    buf = getattr(stream, "buffer", None)
    if buf is None and isinstance(stream, (io.RawIOBase, io.BufferedIOBase, io.BytesIO)):
        buf = stream
    if buf is not None:
        while True:
            line = buf.readline(MAX_MCP_FRAME_BYTES + 1)
            if not line:
                break
            if len(line) > MAX_MCP_FRAME_BYTES or (len(line) == MAX_MCP_FRAME_BYTES and not line.endswith(b"\n")):
                drained = 0
                while not line.endswith(b"\n"):
                    more = buf.readline(65536)
                    if not more:
                        break
                    drained += len(more)
                    line = more
                    if drained > MAX_MCP_DRAIN_BYTES:
                        yield None, "oversized", False
                        return
                yield None, "oversized", False
                continue

            if line.lower().startswith(b"content-length:"):
                try:
                    length = int(line.split(b":", 1)[1].strip())
                except ValueError:
                    yield None, "invalid_header", True
                    continue
                while True:
                    hdr = buf.readline(4096)
                    if not hdr or hdr in (b"\r\n", b"\n"):
                        break
                if length < 0 or length > MAX_MCP_FRAME_BYTES:
                    if 0 < length <= MAX_MCP_DRAIN_BYTES:
                        _ = buf.read(length)
                    yield None, "oversized", True
                    if length > MAX_MCP_DRAIN_BYTES:
                        return
                    continue
                body = buf.read(length)
                if len(body) < length:
                    yield None, "truncated", True
                    return
                try:
                    yield body.decode("utf-8", errors="strict"), None, True
                except UnicodeDecodeError:
                    yield None, "invalid_utf8", True
                continue

            try:
                yield line.decode("utf-8", errors="strict"), None, False
            except UnicodeDecodeError:
                yield None, "invalid_utf8", False
    else:
        for raw in stream:
            enc_len = len(raw.encode("utf-8", errors="replace"))
            if enc_len > MAX_MCP_FRAME_BYTES:
                yield None, "oversized", False
            else:
                yield raw, None, False


def _write_frame_to(out_stream: Any, resp: Mapping[str, Any], *, lsp_framing: bool = False) -> None:
    # ensure_ascii=True safely escapes lone surrogates in echoed request IDs without crashing stdout
    encoded_str = json.dumps(resp, ensure_ascii=True, allow_nan=False)
    framed = f"Content-Length: {len(encoded_str.encode('ascii'))}\r\n\r\n{encoded_str}" if lsp_framing else (encoded_str + "\n")
    if isinstance(out_stream, (io.RawIOBase, io.BufferedIOBase, io.BytesIO)):
        out_stream.write(framed.encode("utf-8"))
    else:
        out_stream.write(framed)
    out_stream.flush()


def _write_frame(resp: Mapping[str, Any], *, lsp_framing: bool = False) -> None:
    _write_frame_to(sys.stdout, resp, lsp_framing=lsp_framing)


def _reject_json_constant(token: str) -> Any:
    raise ValueError(f"Invalid non-finite JSON constant: {token}")


handle_rpc = process_message


def serve_stream(in_stream: Any, out_stream: Any) -> int:
    for frame_text, err_kind, is_lsp in _iter_bounded_stdio_frames(in_stream):
        if err_kind == "oversized":
            _write_frame_to(
                out_stream,
                _rpc_error(None, -32600, f"Request frame exceeds maximum transport budget ({MAX_MCP_FRAME_BYTES} bytes)"),
                lsp_framing=is_lsp,
            )
            continue
        if err_kind in ("invalid_utf8", "invalid_header", "truncated"):
            _write_frame_to(out_stream, _rpc_error(None, -32700, f"Parse error: {err_kind}"), lsp_framing=is_lsp)
            continue
        line = (frame_text or "").strip()
        if not line:
            continue
        try:
            req = json.loads(line, parse_constant=_reject_json_constant)
            if _check_finite(req):
                raise ValueError("Numeric literal overflowed to non-finite float")
        except (ValueError, RecursionError) as exc:
            resp: Optional[dict[str, Any]] = _rpc_error(None, -32700, f"Parse error: {exc}")
        else:
            try:
                resp = process_message(req)
            except Exception:
                req_id = req.get("id") if isinstance(req, dict) and isinstance(req.get("id"), (str, int)) and not isinstance(req.get("id"), bool) else None
                resp = _rpc_error(req_id, -32603, "Internal error")
        if resp is not None:
            _write_frame_to(out_stream, resp, lsp_framing=is_lsp)
    return 0


def main() -> int:
    if sys.platform == "win32":
        for s in (sys.stdin, sys.stdout):
            if s and hasattr(s, "reconfigure"):
                try:
                    s.reconfigure(encoding="utf-8")
                except Exception:
                    pass
    return serve_stream(sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())

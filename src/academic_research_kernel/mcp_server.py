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

import collections
import collections.abc
from dataclasses import asdict
import datetime as dt
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
from .state_db import ALLOWED_ARTIFACT_KINDS, ResearchStateDB, compute_kernel_execution_id

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


def _register_kernel_execution(
    tool_name: str,
    args: Mapping[str, Any],
    result: dict[str, Any],
    *,
    verification_scope: str,
    consistent: Optional[bool],
    executed_at: Optional[str] = None,
) -> dict[str, Any]:
    clean_inputs = {k: thaw(v) for k, v in args.items() if k != "db_path"}
    clean_outputs = thaw(result)
    in_json = canonical_json(clean_inputs)
    out_json = canonical_json(clean_outputs)
    in_sha = sha256_hex(in_json)
    out_sha = sha256_hex(out_json)
    exec_at = executed_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    exec_id = compute_kernel_execution_id(
        tool_name,
        __version__,
        verification_scope,
        consistent,
        exec_at,
        in_sha,
        out_sha,
    )
    raw_db = args.get("db_path")
    if raw_db is not None and str(raw_db).strip() not in ("", ":memory:"):
        _with_db(
            args,
            lambda db: db.record_kernel_execution(
                exec_id,
                tool_name,
                __version__,
                verification_scope,
                consistent,
                exec_at,
                clean_inputs,
                clean_outputs,
            ),
        )
    else:
        get_session_db().record_kernel_execution(
            exec_id,
            tool_name,
            __version__,
            verification_scope,
            consistent,
            exec_at,
            clean_inputs,
            clean_outputs,
        )
    out = dict(result)
    out["execution_id"] = exec_id
    out["verification_scope"] = verification_scope
    return out


def _lookup_kernel_execution(args: Mapping[str, Any], execution_id: str) -> dict[str, Any]:
    eid = str(execution_id or "").strip()
    if not eid:
        raise ValueError("execution_id must be a non-empty string")
    raw_db = args.get("db_path")
    if raw_db is not None and str(raw_db).strip() not in ("", ":memory:"):
        ws = authorized_workspace_root()
        target_p = safe_path(str(raw_db), root=ws)
        if not target_p.is_file():
            raise ValueError(f"Unknown or unauthenticated kernel execution_id {eid!r}: target db_path does not exist")
        found_db = _with_db(args, lambda db: db.get_kernel_execution(eid), readonly=True)
        if found_db is not None:
            return found_db
        raise ValueError(f"Unknown or expired kernel execution_id in target db_path: {eid!r}")
    found_mem = get_session_db().get_kernel_execution(eid)
    if found_mem is not None:
        return found_mem
    raise ValueError(f"Unknown or expired kernel execution_id: {eid!r}")


def _canonical_payload_from_execution(eff_kind: str, exec_rec: Mapping[str, Any]) -> dict[str, Any]:
    from .state_db import canonical_payload_from_execution

    return canonical_payload_from_execution(eff_kind, exec_rec)


def _resolve_executed_artifact_payload(
    kind: Optional[str],
    exec_rec: Mapping[str, Any],
    caller_payload: Any = None,
    *,
    _has_caller_payload: bool = True,
) -> tuple[str, dict[str, Any]]:
    from .state_db import OMIT_PAYLOAD, resolve_executed_artifact_payload

    return resolve_executed_artifact_payload(
        kind, exec_rec, caller_payload if _has_caller_payload else OMIT_PAYLOAD
    )


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


def _optional_auth_artifacts(
    args: Mapping[str, Any],
    *,
    allow_missing_file: bool = False,
) -> Optional[dict[str, tuple[str, str, Any]]]:
    raw_db = args.get("db_path")
    if raw_db is None or str(raw_db).strip() == "":
        return None
    if str(raw_db).strip() == ":memory:":
        return get_session_db().extract_authoritative_artifacts()
    if allow_missing_file:
        root = authorized_workspace_root()
        resolved = safe_path(str(raw_db), root=root)
        if not resolved.is_file():
            return None
    return _with_db(args, lambda db: db.extract_authoritative_artifacts(), readonly=True)


_ALLOWED_INLINE_STATE_KEYS: frozenset[str] = frozenset({
    "ceg",
    "ledger",
    "objects",
    "artifacts",
    "receipts",
    "uncertainties",
    "schema_version",
    "state_digest",
})
_ALLOWED_BINDING_KEYS: frozenset[str] = frozenset({
    "claim_id",
    "artifact_id",
})
_UNSUPPORTED_BINDING_HINTS: dict[str, str] = {
    "decision_id": "use 'decision_record' or 'decision_transition' (CLI 'ledger --action record-decision') to bind decision outcomes",
    "evidence_id": "use 'claim_evidence_add' to attach explicit evidence anchors",
    "work_id": "use 'research_object_resolve' or 'research_state_ingest' to register canonical works",
}


def _resolve_bound_claim_stance(kind: str, payload: Any, bound_claim_id: Optional[str]) -> Optional[str]:
    if bound_claim_id is None:
        return None
    if isinstance(payload, Mapping):
        if kind == "quantitative_audit":
            raw_items = payload.get("assertions") if "assertions" in payload else [payload]
            if not isinstance(raw_items, list) or not raw_items:
                raise ValueError("quantitative_audit assertions must be a non-empty array")
            verdicts: list[str] = []
            for idx, x in enumerate(raw_items):
                if not isinstance(x, Mapping):
                    raise ValueError(f"quantitative_audit assertion[{idx}] must be a JSON object")
                cid_raw = x.get("claim_id")
                if cid_raw is not None:
                    if not isinstance(cid_raw, str) or not cid_raw.strip() or cid_raw != cid_raw.strip():
                        raise ValueError(
                            f"quantitative_audit assertion[{idx}].claim_id must be a non-empty, unpadded string or null"
                        )
                    if cid_raw != bound_claim_id:
                        raise ValueError(
                            f"Bound claim_id mismatch: bindings.claim_id={bound_claim_id!r} cannot bind "
                            f"assertion[{idx}] targeting claim_id={cid_raw!r} (omit bindings.claim_id for multi-claim storage)"
                        )
                disc = x.get("discrepancy_detected") if type(x.get("discrepancy_detected")) is bool else None
                cons = x.get("consistent") if type(x.get("consistent")) is bool else None
                if disc is not None and cons is not None and disc == cons:
                    raise ValueError(
                        f"quantitative_audit assertion[{idx}] has contradictory discrepancy_detected={disc} and consistent={cons}"
                    )
                if disc is True or cons is False:
                    verdicts.append("contradicts")
                elif disc is False or cons is True:
                    verdicts.append("supports")
                else:
                    verdicts.append("qualifies")
            if "contradicts" in verdicts:
                return "contradicts"
            if verdicts and all(v == "supports" for v in verdicts):
                return "supports"
            return "qualifies"
        if kind == "evidence_receipt":
            claims = payload.get("claims")
            if isinstance(claims, list) and claims:
                for idx, x in enumerate(claims):
                    if isinstance(x, Mapping):
                        ec_id = x.get("claim_id") if x.get("claim_id") is not None else x.get("id")
                        if ec_id is not None and str(ec_id) != bound_claim_id:
                            raise ValueError(
                                f"Bound claim_id mismatch: bindings.claim_id={bound_claim_id!r} cannot bind "
                                f"evidence_receipt claims[{idx}] targeting {ec_id!r}"
                            )
                statuses = {str(x.get("support_status")) for x in claims if isinstance(x, Mapping)}
                if "contradicted" in statuses:
                    return "contradicts"
                if statuses == {"supported"}:
                    return "supports"
    return "qualifies"


def _validate_receipt_registry_map(reg: Any, *, label: str = "receipts", dec_content: Optional[Mapping[str, bytes]] = None) -> None:
    from .state_db import validate_academic_evidence_payload, validate_lineage_receipt_semantics

    if not isinstance(reg, Mapping):
        raise ValueError(f"{label} must be a JSON object")
    for rk, rv in reg.items():
        if not isinstance(rk, str) or not rk.strip() or rk != rk.strip() or not isinstance(rv, Mapping) or not rv:
            raise ValueError(f"{label}[{rk!r}] must map a non-empty key to a non-empty receipt object")
        if rv.get("protocol") == "lineage-receipt-1.0":
            l_errs = validate_lineage_receipt_semantics(rv, decoded_content=dec_content, strict_unknown_entities=False)
            if l_errs:
                raise ValueError(f"Invalid lineage receipt in {label}[{rk!r}]: {l_errs[0]}")
        elif rv.get("schema_version") == "1.0" or "claims" in rv:
            ae_errs = validate_academic_evidence_payload(rv)
            if ae_errs:
                raise ValueError(f"Invalid academic_evidence receipt in {label}[{rk!r}]: {ae_errs[0]}")


def _validate_mcp_state_and_bindings(
    args: Mapping[str, Any],
    *,
    allow_inline_state: bool,
) -> tuple[Optional[str], Optional[str]]:
    from .state_db import decode_content_payloads_map

    dec_cp = decode_content_payloads_map(args["content_payloads"]) if args.get("content_payloads") is not None else None
    if args.get("receipts") is not None:
        _validate_receipt_registry_map(args["receipts"], label="receipts", dec_content=dec_cp)

    state = args.get("state")
    if state is not None:
        if not allow_inline_state:
            raise ValueError(
                "Inline 'state' snapshot mutation is not supported in v3.0 SQLite mode; "
                "use 'db_path' (or dry_run=True / research_artifact_validate)"
            )
        if not isinstance(state, Mapping):
            raise ValueError("'state' must be a JSON object")
        extra_sk = set(state.keys()) - _ALLOWED_INLINE_STATE_KEYS
        if extra_sk:
            raise ValueError(f"Unsupported 'state' fields: {sorted(extra_sk)!r}")
        if state.get("receipts") is not None:
            _validate_receipt_registry_map(state["receipts"], label="state.receipts", dec_content=dec_cp)
        eff_receipts = args.get("receipts") if args.get("receipts") is not None else state.get("receipts")
        if state.get("ceg") is not None:
            from .venue_template_manager import validate_ceg_semantics

            ceg_plain = thaw(state["ceg"])
            c_errs = list(validate_schema(ceg_plain, "claim-evidence-graph.schema.json"))
            if c_errs:
                raise ValueError(f"Invalid state.ceg schema: {c_errs[0]}")
            c_sem = validate_ceg_semantics(
                ceg_plain,
                receipts=thaw(eff_receipts) if eff_receipts is not None else None,
                content_payloads=args.get("content_payloads"),
            )
            if c_sem.get("semantic_errors"):
                sem_e = c_sem["semantic_errors"][0]
                raise ValueError(f"Invalid state.ceg semantics: {sem_e}")
        if state.get("ledger") is not None:
            from .state_db import validate_decision_ledger_semantics

            led_plain = thaw(state["ledger"])
            l_errs = list(validate_schema(led_plain, "decision-ledger.schema.json"))
            if not l_errs:
                l_errs = validate_decision_ledger_semantics(
                    led_plain,
                    receipts=eff_receipts,
                    content_payloads=args.get("content_payloads"),
                )
            if l_errs:
                raise ValueError(f"Invalid state.ledger: {l_errs[0]}")
        if state.get("uncertainties") is not None:
            uncs = state["uncertainties"]
            if not isinstance(uncs, list):
                raise ValueError("state.uncertainties must be a JSON array")
            for idx_u, u_item in enumerate(uncs):
                if (
                    not isinstance(u_item, Mapping)
                    or not all(isinstance(u_item.get(fk), str) and u_item[fk].strip() for fk in ("item_id", "subject_id", "kind", "reason"))
                    or type(u_item.get("needs_human")) is not bool
                ):
                    raise ValueError(f"Invalid state.uncertainties[{idx_u}] entry")
        if state.get("objects") is not None:
            objs = state["objects"]
            if not isinstance(objs, Mapping):
                raise ValueError("state.objects must be a JSON object")
            for ok_id, ov in objs.items():
                if (
                    not isinstance(ok_id, str)
                    or not ok_id.strip()
                    or not isinstance(ov, Mapping)
                    or ov.get("work_id") != ok_id
                    or not isinstance(ov.get("title"), str)
                    or not ov["title"].strip()
                ):
                    raise ValueError(f"Invalid state.objects[{ok_id!r}] canonical work entry")
        if state.get("artifacts") is not None:
            arts = state["artifacts"]
            if not isinstance(arts, Mapping):
                raise ValueError("state.artifacts must be a JSON object")
            for ak_id, av in arts.items():
                if not isinstance(ak_id, str) or not ak_id.strip() or not isinstance(av, Mapping):
                    raise ValueError(f"Invalid state.artifacts[{ak_id!r}] entry")
                a_kind = av.get("kind")
                a_pay = av.get("payload")
                if not isinstance(a_kind, str) or a_kind not in ALLOWED_ARTIFACT_KINDS or not isinstance(a_pay, Mapping):
                    raise ValueError(f"state.artifacts[{ak_id!r}] requires valid 'kind' and 'payload' object")
                ResearchStateDB._validate_artifact_semantics(
                    ak_id,
                    a_kind,
                    a_pay,
                    receipts=eff_receipts,
                    content_payloads=args.get("content_payloads"),
                )

    bindings = args.get("bindings")
    if bindings is None:
        return None, None
    if not isinstance(bindings, Mapping):
        raise ValueError("'bindings' must be a JSON object")
    extra_bk = set(bindings.keys()) - _ALLOWED_BINDING_KEYS
    if extra_bk:
        hints = [f"{k!r}: {_UNSUPPORTED_BINDING_HINTS[k]}" for k in sorted(extra_bk) if k in _UNSUPPORTED_BINDING_HINTS]
        suffix = f" ({'; '.join(hints)})" if hints else ""
        raise ValueError(
            f"Unsupported 'bindings' fields: {sorted(extra_bk)!r}; only ['artifact_id', 'claim_id'] are applied by artifact ingestion{suffix}"
        )
    norm_b: dict[str, str] = {}
    for bk, bv in bindings.items():
        if not isinstance(bv, str) or not bv.strip() or bv != bv.strip():
            raise ValueError(f"bindings[{bk!r}] must be a non-empty, unpadded string")
        norm_b[str(bk)] = bv
    if not norm_b:
        return None, None

    claim_ids: set[str] = set()
    artifact_ids: set[str] = set()
    if state is not None:
        ceg_obj = state.get("ceg")
        if isinstance(ceg_obj, Mapping):
            claim_ids = {str(c["id"]) for c in (ceg_obj.get("claims") or ()) if isinstance(c, Mapping) and c.get("id")}
        if isinstance(state.get("artifacts"), Mapping):
            artifact_ids = {str(k) for k in state["artifacts"].keys()}
    else:
        def _collect_from_db(db: ResearchStateDB) -> None:
            nonlocal claim_ids, artifact_ids
            ceg_d = db.export_ceg_dict()
            claim_ids = {str(c["id"]) for c in (ceg_d.get("claims") or ())}
            auth_map = db.extract_authoritative_artifacts()
            artifact_ids = set(auth_map.keys())

        raw_db = args.get("db_path")
        if raw_db is None or str(raw_db).strip() in ("", ":memory:"):
            _collect_from_db(get_session_db())
        else:
            root = authorized_workspace_root()
            resolved = safe_path(str(raw_db), root=root)
            if resolved.is_file():
                with ResearchStateDB(str(raw_db), readonly=True, root=root) as db_ro:
                    _collect_from_db(db_ro)

    lookup = {
        "claim_id": claim_ids,
        "artifact_id": artifact_ids,
    }
    for bk, bv in norm_b.items():
        if bv not in lookup[bk]:
            raise ValueError(f"Dangling binding: {bk} {bv!r} not found in target state")
    return norm_b.get("claim_id"), norm_b.get("artifact_id")


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
        "description": "Ingest a single research artifact or v2.4 envelope into SQLite STRICT state.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "db_path": {"type": "string"},
                "artifact_id": {"type": "string", "minLength": 1},
                "kind": {"type": "string", "minLength": 1},
                "payload": {"type": "object"},
                "parents": {"type": "array", "items": {"type": "string"}},
                "relation": {"type": "string"},
                "envelope": {"type": "object"},
                "dry_run": {"type": "boolean"},
                "state": {"type": "object"},
                "bindings": {"type": "object"},
                "receipts": {"type": "object"},
                "content_payloads": {"type": "object"},
                "execution_id": {"type": "string", "minLength": 1},
                "require_kernel_execution": {"type": "boolean"},
            },
        },
    },
    {
        "name": "research_artifact_validate",
        "description": "Validate a research artifact or v2.4 envelope against canonical JSON schemas and kind invariants.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "db_path": {"type": "string"},
                "artifact_id": {"type": "string"},
                "kind": {"type": "string"},
                "payload": {"type": "object"},
                "schema_name": {"type": "string"},
                "envelope": {"type": "object"},
                "state": {"type": "object"},
                "bindings": {"type": "object"},
                "receipts": {"type": "object"},
                "content_payloads": {"type": "object"},
                "execution_id": {"type": "string", "minLength": 1},
                "require_kernel_execution": {"type": "boolean"},
            },
        },
    },
    {
        "name": "research_receipt_verify",
        "description": "Verify canonical SHA-256 digest and claim/lineage integrity of an artifact payload or ReceiptRef.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "payload": {"type": "object"},
                "expected_sha256": {"type": "string", "minLength": 64, "maxLength": 64},
                "receipt_ref": {"type": "object"},
                "receipt_payload": {"type": "object"},
                "content_payloads": {"type": "object"},
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
                "target_id": {"type": "string", "minLength": 1},
                "lineage_graph": {"type": "object"},
                "lineage": {"type": "object"},
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
                "evidence": {"type": "array", "items": {"anyOf": [{"type": "array"}, {"type": "object"}]}},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "relations": {"type": "array", "items": {"type": "object"}},
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
            "properties": {
                "db_path": {"type": "string"},
                "ceg": {"type": "object"},
                "graph": {"type": "object"},
                "receipts": {"type": "object"},
                "content_payloads": {"type": "object"},
            },
        },
    },
    {
        "name": "claim_evidence_trace",
        "description": "Export or trace claim support/contestation status from SQLite state or an inline graph.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "db_path": {"type": "string"},
                "claim_id": {"type": "string"},
                "graph": {"type": "object"},
                "ceg": {"type": "object"},
                "receipts": {"type": "object"},
                "content_payloads": {"type": "object"},
            },
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
            "properties": {
                "db_path": {"type": "string"},
                "ledger": {"type": "object"},
                "receipts": {"type": "object"},
                "content_payloads": {"type": "object"},
            },
        },
    },
    {
        "name": "decision_trace",
        "description": "Read immutable decision record and chronological event history from SQLite state or an inline ledger.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decision_id"],
            "properties": {
                "db_path": {"type": "string"},
                "decision_id": {"type": "string", "minLength": 1},
                "ledger": {"type": "object"},
                "receipts": {"type": "object"},
                "content_payloads": {"type": "object"},
            },
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
                "db_path": {"type": "string"},
                "kind": {"type": "string"},
                "params": {"type": "object"},
                "t_stat": {"type": "number"},
                "df": {"type": "number"},
                "p_value": {"type": "number"},
                "p_value_literal": {"type": "string"},
                "p_value_decimals": {"type": "integer"},
                "p_operator": {"type": "string", "enum": ["=", "==", "<", "<=", ">", ">="]},
                "stat_literal": {"type": "string"},
                "stat_decimals": {"type": "integer"},
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
                "target_power": {"type": "number"},
                "sample_ratio": {"type": "number"},
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
                "db_path": {"type": "string"},
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
                "db_path": {"type": "string"},
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
                        "properties": {
                            "yi": {"type": "number"},
                            "vi": {"type": "number"},
                            "study_id": {"type": "string"},
                            "subgroup": {"type": "string"},
                            "moderator": {"type": "number"},
                        },
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
                "db_path": {"type": "string"},
                "identifier": {"type": "string"},
                "live": {"type": "boolean"},
                "offline": {"type": "boolean"},
                "normalize_only": {"type": "boolean"},
                "openalex": {"type": "object"},
                "openalex_record": {"type": "object"},
                "crossref": {"type": "object"},
                "crossref_record": {"type": "object"},
                "cited_title": {"type": "string"},
                "cited_authors": {"type": "array", "items": {"type": "string"}},
                "cited_authors_et_al": {"type": "boolean"},
                "cited_year": {"type": "integer"},
                "cited_venue": {"type": "string"},
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
    {
        "name": "academic_scfabric_hardware_probe",
        "description": "Probe local CPU/GPU accelerators, numerical library versions, and optional ComputeReceipt benchmark.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "emit_receipt": {"type": "boolean"},
                "measure_candidates": {"type": "boolean"},
                "operation": {"type": "string"},
                "scale": {"type": "string", "enum": ["small", "medium", "large"]},
                "dtype": {"type": "string", "enum": ["float32", "float64"]},
            },
        },
    },
    {
        "name": "academic_cross_review",
        "description": "Run deterministic multi-model sparse deliberation clustering, anonymous challenge planning, and minority-protected synthesis.",
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["findings_by_model"],
            "properties": {
                "findings_by_model": {"type": "object"},
                "mode": {"type": "string", "enum": ["economy", "standard", "audit"]},
                "challenge_replies": {
                    "type": "object",
                    "description": "Map of challenge_id -> {'text': str, 'bundle_sha256': 64-hex, 'run_id'?: str, 'task_sha256'?: str}",
                    "additionalProperties": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["bundle_sha256"],
                        "properties": {
                            "text": {"type": "string"},
                            "reply": {"type": "string"},
                            "bundle_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                            "run_id": {"type": "string"},
                            "task_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                        },
                    },
                },
                "base_dir": {"type": "string"},
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
    "academic_compute_probe": "academic_scfabric_hardware_probe",
    "cross_review_deliberate": "academic_cross_review",
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
    def _redact_list(items: Any, default_kind: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if isinstance(items, list):
            for idx, item in enumerate(items, 1):
                if not isinstance(item, dict):
                    continue
                pub: dict[str, Any] = {
                    "finding_id": idx,
                    "kind": str(item.get("kind") or default_kind),
                    "severity": str(item.get("severity") or ("warning" if default_kind == "warning" else "error")),
                    "matched": "[REDACTED]",
                }
                line_val = item.get("line")
                if type(line_val) is int and line_val >= 0:
                    pub["line"] = line_val
                out.append(pub)
        return out

    public_findings = _redact_list(rep.get("findings"), "leak")
    public_warnings = _redact_list(rep.get("warnings"), "warning")
    unsupported = rep.get("unsupported_files") or []
    skipped = rep.get("skipped_symlinks") or []
    return {
        "status": str(rep.get("status") or "incomplete"),
        "files_scanned": int(rep.get("files_scanned", 0)),
        "unsupported_file_count": len(unsupported) if isinstance(unsupported, list) else 0,
        "skipped_symlink_count": len(skipped) if isinstance(skipped, list) else 0,
        "leak_count": len(public_findings),
        "warning_count": len(public_warnings),
        "findings": public_findings,
        "warnings": public_warnings,
    }


def _trace_inline_lineage_graph(graph: Mapping[str, Any], target_id: str) -> dict[str, Any]:
    tid = str(target_id or "").strip()
    if not tid:
        raise ValueError("target_entity_id must be a non-empty string")
    raw_entities = graph.get("entities")
    raw_activities = graph.get("activities")
    declared_entities: set[str] | None = None
    declared_activities: set[str] = set()
    has_verified_hashes = False

    if isinstance(raw_entities, Mapping):
        declared_entities = {str(k).strip() for k in raw_entities.keys() if str(k).strip()}
    elif isinstance(raw_entities, list):
        declared_entities = set()
        for ent in raw_entities:
            if isinstance(ent, Mapping):
                eid = str(ent.get("id") or ent.get("entity_id") or ent.get("artifact_id") or "").strip()
                if eid:
                    declared_entities.add(eid)
    if isinstance(raw_activities, Mapping):
        declared_activities = {str(k).strip() for k in raw_activities.keys() if str(k).strip()}
    elif isinstance(raw_activities, list):
        for act in raw_activities:
            if isinstance(act, Mapping):
                aid = str(act.get("id") or act.get("activity_id") or "").strip()
                if aid:
                    declared_activities.add(aid)

    edges = graph.get("derivations") if graph.get("derivations") is not None else graph.get("edges")
    if edges is None:
        edges = []
    if not isinstance(edges, list):
        raise ValueError("lineage_graph edges/derivations must be a list")

    parents_by_child: dict[str, set[str]] = {}
    edge_nodes: set[str] = set()
    broken_refs: list[str] = []
    known_declared = (declared_entities | declared_activities) if declared_entities is not None else None

    for idx, e in enumerate(edges):
        if not isinstance(e, Mapping):
            raise ValueError(f"lineage_graph edge[{idx}] must be an object")
        etype = str(e.get("type") or e.get("relation") or "").strip().lower()
        if "child_id" in e or "parent_id" in e:
            c = str(e.get("child_id") or "").strip()
            p = str(e.get("parent_id") or "").strip()
        elif "source_id" in e and "target_id" in e:
            src = str(e.get("source_id") or "").strip()
            tgt = str(e.get("target_id") or "").strip()
            if etype in ("generated", "produces", "produced"):
                # activity -> generated entity: target depends on source
                c, p = tgt, src
            elif etype in ("derived_from", "used", "extracted_from", "recomputed_from", "verified_by", ""):
                # W3C PROV: derived/activity (source_id) -> upstream entity (target_id)
                c, p = src, tgt
            else:
                raise ValueError(f"Unsupported inline lineage edge type: {etype!r}")
        elif "derived_id" in e or "entity_id" in e:
            c = str(e.get("derived_id") or e.get("entity_id") or "").strip()
            p = str(e.get("source_id") or e.get("used_id") or "").strip()
        else:
            raise ValueError(f"Unrecognized inline lineage edge format at index {idx}")

        if not c or not p:
            broken_refs.append(f"edge[{idx}] has empty endpoint")
            continue
        edge_nodes.add(c)
        edge_nodes.add(p)
        if known_declared is not None and (c not in known_declared or p not in known_declared):
            broken_refs.append(f"edge[{idx}] references undeclared node ({c!r} -> {p!r})")
        parents_by_child.setdefault(c, set()).add(p)
        act_id = str(e.get("activity_id") or "").strip()
        if act_id:
            edge_nodes.add(act_id)
            if known_declared is not None and act_id not in known_declared:
                broken_refs.append(f"edge[{idx}] references undeclared activity {act_id!r}")

    universe = known_declared if known_declared is not None else edge_nodes
    if tid not in universe:
        return {
            "artifact_id": tid,
            "target_id": tid,
            "ancestors": [],
            "root_ancestors": [],
            "chain_length": 0,
            "verification_status": "missing_input",
            "topology_status": "missing_input",
            "content_verification": "unchecked",
            "error_detail": f"Target {tid!r} not found in provenance graph",
        }

    # Explicit iterative DFS stack (avoids Python RecursionError on 1,000+ node chains)
    visited: set[str] = set()
    state: dict[str, int] = {tid: 1}  # 1 = active on stack, 2 = finished
    dfs_stack: list[tuple[str, list[str], int]] = [(tid, sorted(parents_by_child.get(tid, ())), 0)]
    has_cycle = False
    while dfs_stack:
        cur_n, ups, idx_u = dfs_stack[-1]
        if idx_u >= len(ups):
            state[cur_n] = 2
            dfs_stack.pop()
            continue
        dfs_stack[-1] = (cur_n, ups, idx_u + 1)
        up = ups[idx_u]
        up_state = state.get(up, 0)
        if up_state == 1:
            has_cycle = True
            break
        visited.add(up)
        if up_state == 0:
            state[up] = 1
            dfs_stack.append((up, sorted(parents_by_child.get(up, ())), 0))

    if has_cycle:
        return {
            "artifact_id": tid,
            "target_id": tid,
            "ancestors": sorted(visited),
            "root_ancestors": [],
            "chain_length": 0,
            "verification_status": "cycle_detected",
            "topology_status": "cycle_detected",
            "content_verification": "unchecked",
            "error_detail": f"Cycle detected in lineage closure of {tid!r}",
        }

    if broken_refs:
        return {
            "artifact_id": tid,
            "target_id": tid,
            "ancestors": sorted(visited),
            "root_ancestors": [],
            "chain_length": 0,
            "verification_status": "broken_chain",
            "topology_status": "broken_chain",
            "content_verification": "unchecked",
            "error_detail": "; ".join(broken_refs),
        }

    # Root ancestors = upstream entities with no further transitive upstream entity (traversing through activities)
    entity_filter = declared_entities if declared_entities is not None else (universe - declared_activities)

    def _has_upstream_entity(ent_node: str) -> bool:
        seen_a: set[str] = set()
        q_a = list(parents_by_child.get(ent_node, ()))
        while q_a:
            cand_u = q_a.pop()
            if cand_u in seen_a:
                continue
            seen_a.add(cand_u)
            if cand_u in entity_filter and cand_u != ent_node:
                return True
            q_a.extend(parents_by_child.get(cand_u, ()))
        return False

    roots = sorted(n for n in visited if n in entity_filter and not _has_upstream_entity(n))
    if not roots and tid in entity_filter and not _has_upstream_entity(tid):
        roots = [tid]

    v_status = "intact" if has_verified_hashes else "unchecked"
    return {
        "artifact_id": tid,
        "target_id": tid,
        "ancestors": sorted(visited),
        "root_ancestors": roots,
        "chain_length": len(visited) + 1,
        "verification_status": v_status,
        "topology_status": "valid_dag",
        "content_verification": v_status,
    }


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
        is_dry = bool(a.get("dry_run", False))
        req_exec = bool(a.get("require_kernel_execution", False))
        exec_id_raw = a.get("execution_id")
        if req_exec and not exec_id_raw:
            raise ValueError(
                "research_artifact_ingest with require_kernel_execution=True requires a valid kernel 'execution_id'"
            )
        exec_rec: Optional[dict[str, Any]] = None
        if exec_id_raw is not None:
            exec_rec = _lookup_kernel_execution(a, str(exec_id_raw))

        bound_cid, bound_aid = _validate_mcp_state_and_bindings(a, allow_inline_state=is_dry)
        if "envelope" in a and a["envelope"] is not None:
            if any(k in a and a[k] is not None for k in ("payload", "artifact_id", "kind")):
                raise ValueError("Cannot mix 'envelope' with top-level 'payload', 'artifact_id', or 'kind'")
            env = a["envelope"]
            if not isinstance(env, Mapping):
                raise ValueError("envelope must be a JSON object")
            env_errs = validate_schema(env, "research-artifact-envelope.schema.json")
            if env_errs:
                raise ValueError(f"Invalid artifact envelope: {'; '.join(env_errs[:5])}")
            env_id = str(env["artifact_id"])
            env_kind = str(env["artifact_kind"])
            env_sha = str(env["payload_sha256"]).lower()
            env_pay = env["payload"]
            if exec_rec is not None:
                _, _ = _resolve_executed_artifact_payload(env_kind, exec_rec, env_pay)
            comp_sha = sha256_hex(canonical_json(env_pay))
            if comp_sha != env_sha or env_id != f"art-{comp_sha[:32]}":
                raise ValueError("Artifact envelope payload_sha256 or artifact_id mismatch")
            auth_dry = _optional_auth_artifacts(a, allow_missing_file=True)
            ResearchStateDB._validate_artifact_semantics(
                env_id,
                env_kind,
                env_pay,
                env_sha,
                authoritative_artifacts=auth_dry,
                receipts=a.get("receipts"),
                content_payloads=a.get("content_payloads"),
            )
            bound_stance_env = _resolve_bound_claim_stance(env_kind, env_pay, bound_cid)
            if is_dry:
                return {
                    "valid": True,
                    "dry_run": True,
                    "status": "validated_dry_run",
                    "artifact_id": env_id,
                    "artifact_kind": env_kind,
                    "payload_sha256": comp_sha,
                }
            parents_env = list(a.get("parents") or ())
            if bound_aid and bound_aid not in parents_env and bound_aid != env_id:
                parents_env.append(bound_aid)
            item = {
                "artifact_id": env_id,
                "kind": env_kind,
                "payload": env_pay,
                "payload_sha256": env_sha,
                "parents": parents_env,
                "relation": a.get("relation", "derived_from"),
                "receipts": a.get("receipts"),
                "content_payloads": a.get("content_payloads"),
            }

            def _ingest_env(db: ResearchStateDB) -> dict[str, Any]:
                with db.transaction() as conn:
                    rec0 = db.batch_ingest([item], atomic=True)[0]
                    if exec_rec is not None:
                        db.record_kernel_execution(
                            str(exec_rec["execution_id"]),
                            str(exec_rec["tool_name"]),
                            str(exec_rec["kernel_version"]),
                            str(exec_rec["verification_scope"]),
                            exec_rec["consistent"],
                            str(exec_rec["executed_at"]),
                            exec_rec["inputs"],
                            exec_rec["outputs"],
                        )
                        db.bind_artifact_execution(
                            env_id,
                            str(exec_rec["execution_id"]),
                            str(exec_rec["verification_scope"]),
                            provenance_tier="kernel_executed",
                            ingest_bound_claim_id=bound_cid,
                        )
                    if bound_cid and bound_stance_env is not None:
                        row_c = conn.execute("SELECT claim_text FROM claims WHERE claim_id = ?", (bound_cid,)).fetchone()
                        if row_c is None:
                            raise ValueError(f"Dangling binding: claim_id {bound_cid!r} not found in target state")
                        db.add_claim(bound_cid, str(row_c[0]), None, [(env_id, bound_stance_env, "")])
                    return {"valid": True, "receipt": rec0, "state_digest": db.snapshot_digest()}

            return _with_db(a, _ingest_env)

        eff_art_id = a.get("artifact_id")
        eff_kind_raw = a.get("kind")
        has_caller_pay = "payload" in a
        eff_payload = a.get("payload")
        if exec_rec is not None:
            eff_kind_raw, eff_payload = _resolve_executed_artifact_payload(
                str(eff_kind_raw) if eff_kind_raw is not None else None,
                exec_rec,
                eff_payload,
                _has_caller_payload=has_caller_pay,
            )
            if eff_art_id is None:
                eff_art_id = f"results-{str(exec_rec['execution_id']).removeprefix('kexec-')}"
        if not all(x is not None for x in (eff_art_id, eff_kind_raw, eff_payload)):
            raise ValueError("research_artifact_ingest requires ('artifact_id', 'kind', 'payload'), 'execution_id', or 'envelope'")
        auth_dry_s = _optional_auth_artifacts(a, allow_missing_file=True)
        aid_d, k_d, _, sha_d = ResearchStateDB._validate_artifact_semantics(
            eff_art_id,
            eff_kind_raw,
            eff_payload,
            authoritative_artifacts=auth_dry_s,
            receipts=a.get("receipts"),
            content_payloads=a.get("content_payloads"),
        )
        bound_stance_raw = _resolve_bound_claim_stance(k_d, eff_payload, bound_cid)
        if is_dry:
            return {
                "valid": True,
                "dry_run": True,
                "status": "validated_dry_run",
                "artifact_id": aid_d,
                "artifact_kind": k_d,
                "payload_sha256": sha_d,
            }
        parents_raw = list(a.get("parents") or ())
        if bound_aid and bound_aid not in parents_raw and bound_aid != str(eff_art_id):
            parents_raw.append(bound_aid)
        item = {
            "artifact_id": eff_art_id,
            "kind": eff_kind_raw,
            "payload": eff_payload,
            "parents": parents_raw,
            "relation": a.get("relation", "derived_from"),
            "receipts": a.get("receipts"),
            "content_payloads": a.get("content_payloads"),
        }

        def _ingest_raw(db: ResearchStateDB) -> dict[str, Any]:
            with db.transaction() as conn:
                rec0 = db.batch_ingest([item], atomic=True)[0]
                if exec_rec is not None:
                    db.record_kernel_execution(
                        str(exec_rec["execution_id"]),
                        str(exec_rec["tool_name"]),
                        str(exec_rec["kernel_version"]),
                        str(exec_rec["verification_scope"]),
                        exec_rec["consistent"],
                        str(exec_rec["executed_at"]),
                        exec_rec["inputs"],
                        exec_rec["outputs"],
                    )
                    db.bind_artifact_execution(
                        str(eff_art_id),
                        str(exec_rec["execution_id"]),
                        str(exec_rec["verification_scope"]),
                        provenance_tier="kernel_executed",
                        ingest_bound_claim_id=bound_cid,
                    )
                if bound_cid and bound_stance_raw is not None:
                    row_c = conn.execute("SELECT claim_text FROM claims WHERE claim_id = ?", (bound_cid,)).fetchone()
                    if row_c is None:
                        raise ValueError(f"Dangling binding: claim_id {bound_cid!r} not found in target state")
                    db.add_claim(
                        bound_cid,
                        str(row_c[0]),
                        None,
                        [(str(eff_art_id), bound_stance_raw, "")],
                    )
                return {"receipt": rec0, "state_digest": db.snapshot_digest()}

        return _with_db(a, _ingest_raw)

    if name == "research_artifact_validate":
        req_exec_v = bool(a.get("require_kernel_execution", False))
        exec_id_v = a.get("execution_id")
        if req_exec_v and not exec_id_v:
            return {"valid": False, "errors": ["research_artifact_validate with require_kernel_execution=True requires 'execution_id'"]}
        exec_rec_v: Optional[dict[str, Any]] = None
        if exec_id_v is not None:
            try:
                exec_rec_v = _lookup_kernel_execution(a, str(exec_id_v))
            except Exception as exc:
                return {"valid": False, "errors": [str(exc)]}
        if "envelope" in a and a["envelope"] is not None:
            if any(k in a and a[k] is not None for k in ("payload", "artifact_id", "kind")):
                raise ValueError("Cannot mix 'envelope' with top-level 'payload', 'artifact_id', or 'kind'")
            env = a["envelope"]
            if not isinstance(env, Mapping):
                return {"valid": False, "errors": ["envelope must be a JSON object"]}
            env_errs = list(validate_schema(env, "research-artifact-envelope.schema.json"))
            if env_errs:
                return {"valid": False, "errors": env_errs}
            env_id = str(env["artifact_id"])
            env_kind = str(env["artifact_kind"])
            env_sha = str(env["payload_sha256"]).lower()
            env_pay = env["payload"]
            if exec_rec_v is not None:
                try:
                    _resolve_executed_artifact_payload(env_kind, exec_rec_v, env_pay)
                except Exception as exc:
                    return {"valid": False, "errors": [str(exc)]}
            comp_sha = sha256_hex(canonical_json(env_pay))
            if comp_sha != env_sha:
                return {"valid": False, "errors": [f"Envelope payload_sha256 mismatch: expected {env_sha}, computed {comp_sha}"]}
            if env_id != f"art-{comp_sha[:32]}":
                return {"valid": False, "errors": [f"Envelope artifact_id {env_id!r} != expected 'art-{comp_sha[:32]}'"]}
            try:
                bound_cid_ve, _ = _validate_mcp_state_and_bindings(a, allow_inline_state=True)
                auth_val_env = _optional_auth_artifacts(a)
                ResearchStateDB._validate_artifact_semantics(
                    env_id,
                    env_kind,
                    env_pay,
                    env_sha,
                    authoritative_artifacts=auth_val_env,
                    receipts=a.get("receipts"),
                    content_payloads=a.get("content_payloads"),
                )
                _resolve_bound_claim_stance(env_kind, env_pay, bound_cid_ve)
                return {"valid": True, "errors": [], "artifact_id": env_id, "artifact_kind": env_kind, "payload_sha256": comp_sha}
            except Exception as exc:
                return {"valid": False, "errors": [str(exc)]}
        if "kind" not in a or "payload" not in a:
            return {"valid": False, "errors": ["research_artifact_validate requires ('kind', 'payload') or 'envelope'"]}
        kind = str(a["kind"])
        if kind not in ALLOWED_ARTIFACT_KINDS:
            return {"valid": False, "errors": [f"Unknown artifact kind: {kind!r}"]}
        schema_name = a.get("schema_name")
        if schema_name:
            errs = list(validate_schema(a["payload"], str(schema_name)))
            if errs:
                return {"valid": False, "errors": errs}
        try:
            if exec_rec_v is not None:
                _resolve_executed_artifact_payload(kind, exec_rec_v, a["payload"])
            bound_cid_vr, _ = _validate_mcp_state_and_bindings(a, allow_inline_state=True)
            auth_val = _optional_auth_artifacts(a)
            ResearchStateDB._validate_artifact_semantics(
                a.get("artifact_id") or "probe",
                kind,
                a["payload"],
                authoritative_artifacts=auth_val,
                receipts=a.get("receipts"),
                content_payloads=a.get("content_payloads"),
            )
            _resolve_bound_claim_stance(kind, a["payload"], bound_cid_vr)
            return {"valid": True, "errors": []}
        except Exception as exc:
            return {"valid": False, "errors": [str(exc)]}

    if name == "research_receipt_verify":
        from .state_db import (
            canonical_evidence_claim_digest,
            decode_content_payloads_map,
            validate_academic_evidence_payload,
            validate_lineage_receipt_semantics,
            validate_receipt_ref_dict,
        )

        dec_cp = decode_content_payloads_map(a["content_payloads"]) if a.get("content_payloads") is not None else None
        if "receipt_ref" in a and a["receipt_ref"] is not None:
            rref = a["receipt_ref"]
            target_payload = (
                a.get("receipt_payload")
                if isinstance(a.get("receipt_payload"), Mapping)
                else a.get("payload")
            )
            if not isinstance(rref, Mapping) or not isinstance(target_payload, Mapping):
                raise ValueError(
                    "research_receipt_verify with receipt_ref requires JSON objects for receipt_ref and receipt_payload (or payload)"
                )
            ref_errs = validate_receipt_ref_dict(rref)
            if ref_errs:
                return {"valid": False, "errors": ref_errs}
            rk = rref.get("kind")
            if rk == "academic_evidence":
                cdig = str(rref["claim_digest"]).lower()
                expected = str(rref["payload_sha256"]).lower()
                actual = sha256_hex(canonical_json(target_payload))
                errs_ae = validate_academic_evidence_payload(target_payload)
                if actual != expected:
                    errs_ae.append(f"AcademicEvidence payload_sha256 mismatch: expected {expected}, computed {actual}")
                if not errs_ae:
                    matched_c = any(
                        isinstance(ci, Mapping) and canonical_evidence_claim_digest(ci) == cdig
                        for ci in (target_payload.get("claims") or ())
                    )
                    if not matched_c:
                        errs_ae.append(f"claim_digest {cdig} not found in receipt claims")
                return {
                    "valid": len(errs_ae) == 0,
                    "errors": errs_ae,
                    "computed_sha256": actual,
                    "expected_sha256": expected,
                    "claim_digest": cdig,
                }
            rid = str(rref["receipt_id"])
            expected = str(rref["receipt_digest"]).lower()
            if target_payload.get("protocol") != "lineage-receipt-1.0":
                return {
                    "valid": False,
                    "errors": ["Lineage ReceiptRef requires a lineage-receipt-1.0 payload"],
                    "expected_sha256": expected,
                    "receipt_id": rid,
                }
            l_errs = validate_lineage_receipt_semantics(target_payload, decoded_content=dec_cp)
            actual_rdig = str(target_payload.get("receipt_digest") or "").lower()
            if target_payload.get("receipt_id") != rid:
                l_errs.append(f"Lineage receipt_id mismatch: expected {rid!r}, got {target_payload.get('receipt_id')!r}")
            if actual_rdig != expected:
                l_errs.append(f"Lineage receipt_digest mismatch: expected {expected}, got {actual_rdig}")
            return {
                "valid": len(l_errs) == 0,
                "errors": l_errs,
                "computed_sha256": actual_rdig,
                "expected_sha256": expected,
                "receipt_id": rid,
            }
        if not isinstance(a.get("payload"), Mapping) or not isinstance(a.get("expected_sha256"), str):
            raise ValueError("research_receipt_verify requires 'payload' and 'expected_sha256' (or 'receipt_ref' + 'receipt_payload')")
        actual = sha256_hex(canonical_json(a["payload"]))
        expected = str(a["expected_sha256"]).strip().lower()
        return {"valid": actual == expected, "computed_sha256": actual, "expected_sha256": expected}

    if name == "research_lineage_trace":
        inline_lg = a.get("lineage_graph") if isinstance(a.get("lineage_graph"), Mapping) else a.get("lineage")
        inline_tid = a.get("target_entity_id") or a.get("target_id") or a.get("artifact_id")
        if isinstance(inline_lg, Mapping) and inline_tid:
            return _trace_inline_lineage_graph(inline_lg, str(inline_tid))
        aid = a.get("artifact_id") or a.get("target_entity_id") or a.get("target_id")
        if not aid:
            raise ValueError("research_lineage_trace requires artifact_id (or lineage_graph + target_entity_id)")
        return _with_db(
            a,
            lambda db: db.trace_lineage_verified(str(aid)),
            readonly=bool(a.get("db_path") and str(a.get("db_path")) != ":memory:"),
        )

    if name == "claim_evidence_add":
        ev = [
            (x["artifact_id"], x.get("stance", "supports"), x.get("locator", ""))
            if isinstance(x, Mapping)
            else tuple(x)
            for x in a.get("evidence", ())
        ]
        rels = list(a.get("relations") or ())

        def _add_ceg(db: ResearchStateDB) -> Mapping[str, Any]:
            with db.transaction():
                res_c = db.add_claim(
                    a["claim_id"],
                    a["claim_text"],
                    a.get("status"),
                    ev,
                    a.get("depends_on", ()),
                    metadata=a.get("metadata"),
                )
                for rel_item in rels:
                    if isinstance(rel_item, Mapping):
                        db.add_claim_relation(
                            a["claim_id"],
                            str(rel_item["target_claim_id"]),
                            str(rel_item.get("relation") or rel_item.get("relation_type") or "depends_on"),
                        )
                if rels:
                    ceg_now = db.export_ceg_dict()
                    matched = next((c for c in ceg_now.get("claims", ()) if c.get("id") == a["claim_id"]), None)
                    if matched and "metadata" in matched and "status" in matched["metadata"]:
                        res_out = dict(thaw(res_c))
                        res_out["status"] = matched["metadata"]["status"]
                        return res_out
                return res_c

        return _with_db(a, _add_ceg)

    if name == "claim_evidence_validate":
        ceg_doc = a.get("ceg") if a.get("ceg") is not None else a.get("graph")
        if ceg_doc is None and a.get("db_path") is not None and str(a.get("db_path")).strip():
            is_ro_ceg = str(a.get("db_path")).strip() != ":memory:"
            ceg_doc = _with_db(a, lambda db: db.export_ceg_dict(), readonly=is_ro_ceg)
        if not isinstance(ceg_doc, Mapping):
            return {"valid": False, "errors": ["claim_evidence_validate requires a 'ceg' (or 'graph') object or 'db_path'"]}
        errs = list(validate_schema(ceg_doc, "claim-evidence-graph.schema.json"))
        try:
            from .venue_template_manager import validate_ceg_semantics

            auth_ceg = _optional_auth_artifacts(a)
            sem = validate_ceg_semantics(
                dict(ceg_doc),
                receipts=dict(a["receipts"]) if isinstance(a.get("receipts"), Mapping) else a.get("receipts"),
                content_payloads=dict(a["content_payloads"]) if isinstance(a.get("content_payloads"), Mapping) else a.get("content_payloads"),
                authoritative_artifacts=auth_ceg,
            )
            errs.extend(sem["semantic_errors"])
        except Exception as exc:
            errs.append(str(exc))
        return {"valid": len(errs) == 0, "errors": errs}

    if name == "claim_evidence_trace":
        inline_ceg = a.get("graph") if a.get("graph") is not None else a.get("ceg")
        if inline_ceg is not None:
            if not isinstance(inline_ceg, Mapping):
                raise ValueError("graph / ceg must be a JSON object")
            from .venue_template_manager import validate_ceg_semantics

            errs_c = list(validate_schema(inline_ceg, "claim-evidence-graph.schema.json"))
            sem_c = validate_ceg_semantics(
                dict(inline_ceg),
                receipts=dict(a["receipts"]) if isinstance(a.get("receipts"), Mapping) else a.get("receipts"),
                content_payloads=dict(a["content_payloads"]) if isinstance(a.get("content_payloads"), Mapping) else a.get("content_payloads"),
            )
            errs_c.extend(sem_c["semantic_errors"])
            if errs_c:
                raise ValueError(f"Invalid ClaimEvidenceGraph: {'; '.join(errs_c[:5])}")
            target_cid = a.get("claim_id")
            if target_cid:
                claims_l = inline_ceg.get("claims") or []
                s_edges = inline_ceg.get("support_edges") or []
                matched_cl = next((c for c in claims_l if isinstance(c, Mapping) and c.get("id") == target_cid), None)
                if matched_cl is None:
                    raise ValueError(f"Unknown claim_id in graph: {target_cid!r}")
                matched_anc = next((anc for anc in sem_c["anchors"] if anc["claim_id"] == target_cid), None)
                edges_cl = [e for e in s_edges if isinstance(e, Mapping) and e.get("claim_id") == target_cid]
                return {
                    "claim": matched_cl,
                    "anchor": matched_anc,
                    "support_edges": edges_cl,
                    "status": matched_anc["anchor_status"] if matched_anc else "unknown",
                }
            return dict(inline_ceg)

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
        from .state_db import validate_decision_ledger_semantics

        if "ledger" in a and a["ledger"] is not None:
            raw_rec = a.get("receipts")
            raw_cp = a.get("content_payloads")
            try:
                auth_dl = _optional_auth_artifacts(a)
                errs = validate_decision_ledger_semantics(
                    a["ledger"],
                    receipts=raw_rec,
                    content_payloads=raw_cp,
                    authoritative_artifacts=auth_dl,
                )
            except Exception as exc:
                errs = [str(exc)]
            is_valid = len(errs) == 0
            v_man = a["ledger"].get("verification_manifest") if isinstance(a["ledger"], Mapping) and isinstance(a["ledger"].get("verification_manifest"), Mapping) else {}
            if not is_valid:
                scope = "validation_failed"
            elif (raw_rec is not None or auth_dl is not None) and bool(v_man):
                scope = "payload_verified"
            else:
                scope = "structure_and_self_consistency_only"
            return {
                "valid": is_valid,
                "errors": errs,
                "verification_scope": scope,
            }
        is_ro = bool(a.get("db_path") and str(a.get("db_path")) != ":memory:")
        return _with_db(a, lambda db: db.validate_decisions(), readonly=is_ro)

    if name == "decision_trace":
        if "ledger" in a and a["ledger"] is not None:
            from .state_db import validate_decision_ledger_semantics

            ledger_doc = a["ledger"]
            if not isinstance(ledger_doc, Mapping):
                raise ValueError("ledger must be a JSON object")
            errs_l = validate_decision_ledger_semantics(
                ledger_doc,
                receipts=a.get("receipts"),
                content_payloads=a.get("content_payloads"),
            )
            if errs_l:
                raise ValueError(f"Invalid DecisionLedger: {'; '.join(errs_l[:5])}")
            did_t = str(a["decision_id"])
            matched_d = next(
                (d for d in (ledger_doc.get("decisions") or []) if isinstance(d, Mapping) and str(d.get("id")) == did_t),
                None,
            )
            if matched_d is None:
                raise ValueError(f"Unknown decision_id in ledger: {did_t!r}")
            evs_d = [e for e in (ledger_doc.get("state_events") or []) if isinstance(e, Mapping) and str(e.get("decision_id")) == did_t]
            corrs_d = [c for c in (ledger_doc.get("corrections") or []) if isinstance(c, Mapping) and str(c.get("decision_id")) == did_t]
            bases_d = [b for b in (ledger_doc.get("bases") or []) if isinstance(b, Mapping) and str(b.get("decision_id")) == did_t]
            unc_d = [u for u in (ledger_doc.get("uncertainties") or []) if isinstance(u, Mapping) and str(u.get("subject_id")) == did_t]
            return {
                "decision": matched_d,
                "events": evs_d,
                "corrections": corrs_d,
                "bases": bases_d,
                "uncertainties": unc_d,
            }

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
        pct_res = rec_mod.check_percentage(a["count"], a["percent"], denominator=denom, decimals=a.get("decimals"))
        pct_cons = pct_res.get("consistent") if isinstance(pct_res.get("consistent"), bool) else None
        return _register_kernel_execution(
            "academic_check_percentage",
            a,
            pct_res,
            verification_scope="statistical_numerical_consistency",
            consistent=pct_cons,
        )

    if name == "academic_recompute_statistics":
        rec_mod = _mod("recompute")
        if "params" in a:
            if "kind" not in a or a["kind"] is None:
                raise ValueError("Dispatch mode with 'params' requires 'kind'")
            extra_stat_keys = set(a) - {"params", "kind", "db_path"}
            if extra_stat_keys:
                raise ValueError(f"Cannot mix kind+params dispatch with flat statistical fields: {sorted(extra_stat_keys)}")
            p = dict(a["params"] or {})
            dispatch = {
                "t": rec_mod.p_from_t,
                "f": rec_mod.p_from_f,
                "chi2": rec_mod.p_from_chi2,
                "z": rec_mod.z_from_beta_se,
                "cohens_d": rec_mod.cohens_d,
                "ci": rec_mod.check_ci_consistency,
                "power": rec_mod.achieved_power_ttest,
                "required_sample_size": rec_mod.required_n_ttest,
                "required-sample-size": rec_mod.required_n_ttest,
                "required_n": rec_mod.required_n_ttest,
                "stat_p_consistency": rec_mod.check_stat_p_consistency,
            }
            if a["kind"] not in dispatch:
                raise ValueError(f"Unsupported statistics kind: {a['kind']!r}")
            res_k = dispatch[a["kind"]](**p)
            cons_k = res_k.get("consistent") if isinstance(res_k.get("consistent"), bool) else None
            return _register_kernel_execution(
                "academic_recompute_statistics",
                a,
                res_k,
                verification_scope="statistical_numerical_consistency",
                consistent=cons_k,
            )

        if "df" in a and "t_stat" not in a and "chi2_stat" not in a:
            raise ValueError("'df' requires 't_stat' or 'chi2_stat'")

        out_stat: dict[str, Any] = {}
        partial_errors: dict[str, str] = {}
        verdict_flags: list[Optional[bool]] = []

        def _agg_tri_bool(vals: Any) -> Optional[bool]:
            items = list(vals)
            if False in items:
                return False
            if None in items:
                return None
            return True
        has_reported_p = ("p_value" in a and a["p_value"] is not None) or (
            "p_value_literal" in a and a["p_value_literal"] is not None
        )
        p_op_raw = a.get("p_operator")
        p_op = "=" if p_op_raw in (None, "==") else str(p_op_raw).strip()

        def _attach_stat_consistency(kind_tag: str, stat_val: Any, df1_val: Any, df2_val: Any = None, *, recomputed_p: float) -> None:
            import re as _re
            from decimal import Decimal, InvalidOperation

            raw_lit = a.get("p_value_literal")
            eff_op = p_op
            clean_lit: Optional[str] = None
            if isinstance(raw_lit, str) and raw_lit.strip():
                s_lit = _re.sub(r"^\s*[pP]\s*", "", raw_lit.strip())
                m_op = _re.match(r"^(<=|>=|==|<|>|=)\s*(.+)$", s_lit)
                if m_op:
                    parsed_op_raw, num_part = m_op.group(1), m_op.group(2).strip()
                    parsed_op = "=" if parsed_op_raw == "==" else parsed_op_raw
                    if p_op_raw is not None and p_op != parsed_op:
                        raise ValueError(
                            f"Conflicting p_operator={p_op_raw!r} and operator in p_value_literal={raw_lit!r}"
                        )
                    eff_op = parsed_op
                    clean_lit = ("0" + num_part) if num_part.startswith(".") else num_part
                else:
                    clean_lit = ("0" + s_lit) if s_lit.startswith(".") else s_lit

            has_num_p = "p_value" in a and a["p_value"] is not None
            if has_num_p:
                if isinstance(a["p_value"], bool):
                    raise TypeError("p_value must be a number, not bool")
                num_p = float(a["p_value"])
                if not math.isfinite(num_p) or not (0.0 <= num_p <= 1.0):
                    raise ValueError("报告 p 值须在 [0,1]")
            if clean_lit is not None:
                try:
                    lit_dec = Decimal(clean_lit)
                except InvalidOperation as exc:
                    raise ValueError(f"Invalid p_value_literal: {raw_lit!r}") from exc
                if not lit_dec.is_finite() or not (Decimal(0) <= lit_dec <= Decimal(1)):
                    raise ValueError("报告 p_value_literal 须在 [0,1]")
                if has_num_p and Decimal(str(a["p_value"])) != lit_dec:
                    spc_num = rec_mod.check_stat_p_consistency(
                        kind_tag,
                        stat_val,
                        df1_val,
                        df2_val,
                        reported_p=a["p_value"],
                        p_decimals=a.get("p_value_decimals"),
                        stat_literal=a.get("stat_literal"),
                        stat_decimals=a.get("stat_decimals"),
                        op=p_op,
                    )
                    spc_lit = rec_mod.check_stat_p_consistency(
                        kind_tag,
                        stat_val,
                        df1_val,
                        df2_val,
                        reported_p=clean_lit,
                        reported_p_literal=clean_lit,
                        stat_literal=a.get("stat_literal"),
                        stat_decimals=a.get("stat_decimals"),
                        op=eff_op,
                    )
                    both_ok = bool(spc_num["consistent"] is True and spc_lit["consistent"] is True)
                    conflict_entry = {
                        "consistent": False,
                        "dual_p_input_conflict": True,
                        "numeric_check": spc_num,
                        "literal_check": spc_lit,
                        "note": "Numeric p_value and p_value_literal disagree",
                        "both_individually_consistent": both_ok,
                    }
                    by_t_conf = out_stat.setdefault("stat_p_consistency_by_test", {})
                    by_t_conf[kind_tag] = conflict_entry
                    out_stat["stat_p_consistency"] = (
                        conflict_entry
                        if len(by_t_conf) == 1
                        else {"consistent": False, "by_test": dict(by_t_conf)}
                    )
                    pm_conf = out_stat.setdefault("p_match_by_test", {})
                    pm_conf[kind_tag] = {
                        "consistent": False,
                        "error": "p_value conflicts with p_value_literal",
                    }
                    out_stat["p_match"] = (
                        pm_conf[kind_tag]
                        if len(pm_conf) == 1
                        else {"consistent": False, "by_test": dict(pm_conf)}
                    )
                    verdict_flags.append(False)
                    return

            rep_val = a["p_value"] if has_num_p else clean_lit
            spc = rec_mod.check_stat_p_consistency(
                kind_tag,
                stat_val,
                df1_val,
                df2_val,
                reported_p=rep_val,
                reported_p_literal=clean_lit,
                p_decimals=a.get("p_value_decimals"),
                stat_literal=a.get("stat_literal"),
                stat_decimals=a.get("stat_decimals"),
                op=eff_op,
            )
            by_test = out_stat.setdefault("stat_p_consistency_by_test", {})
            by_test[kind_tag] = spc
            if len(by_test) == 1:
                out_stat["stat_p_consistency"] = spc
            else:
                out_stat["stat_p_consistency"] = {
                    "consistent": _agg_tri_bool(v.get("consistent") for v in by_test.values()),
                    "by_test": dict(by_test),
                }
            if eff_op == "=":
                pm_res = rec_mod.check_p_match(
                    rep_val,
                    recomputed_p,
                    decimals=a.get("p_value_decimals"),
                    reported_literal=clean_lit,
                )
                if recomputed_p < 1e-300:
                    pm_res = dict(pm_res)
                    pm_res["consistent"] = spc.get("point_consistent")
                    pm_res["confidence"] = spc.get("confidence", "low")
                pm_by = out_stat.setdefault("p_match_by_test", {})
                pm_by[kind_tag] = pm_res
                if len(pm_by) == 1:
                    out_stat["p_match"] = pm_res
                else:
                    out_stat["p_match"] = {
                        "consistent": _agg_tri_bool(v.get("consistent") for v in pm_by.values()),
                        "by_test": dict(pm_by),
                    }
            verdict_flags.append(spc.get("consistent"))

        def _run_part(label: str, fn: Callable[[], None]) -> None:
            try:
                fn()
            except (ValueError, TypeError):
                raise
            except Exception as exc:
                partial_errors[label] = f"{type(exc).__name__}: {exc}"

        if "t_stat" in a:
            def _do_t() -> None:
                if "df" not in a:
                    raise ValueError("'t_stat' requires 'df'")
                r = rec_mod.p_from_t(a["t_stat"], a["df"], reported=a.get("p_value"))
                out_stat.update(recomputed_p=r["recomputed"], p_receipt=r)
                if has_reported_p:
                    _attach_stat_consistency("t", a["t_stat"], a["df"], recomputed_p=r["recomputed"])
            _run_part("t_test", _do_t)

        if "f_stat" in a:
            def _do_f() -> None:
                if "df1" not in a or "df2" not in a:
                    raise ValueError("'f_stat' requires 'df1' and 'df2'")
                r = rec_mod.p_from_f(a["f_stat"], a["df1"], a["df2"], reported=a.get("p_value"))
                out_stat.update(f_receipt=r, recomputed_f_p=r["recomputed"])
                if has_reported_p:
                    _attach_stat_consistency("f", a["f_stat"], a["df1"], a["df2"], recomputed_p=r["recomputed"])
            _run_part("f_test", _do_f)

        if "chi2_stat" in a:
            def _do_chi2() -> None:
                chi_df = a.get("chi2_df", a.get("df"))
                if chi_df is None:
                    raise ValueError("'chi2_stat' requires 'chi2_df' or 'df'")
                r = rec_mod.p_from_chi2(a["chi2_stat"], chi_df, reported=a.get("p_value"))
                out_stat.update(chi2_receipt=r, recomputed_chi2_p=r["recomputed"])
                if has_reported_p:
                    _attach_stat_consistency("chi2", a["chi2_stat"], chi_df, recomputed_p=r["recomputed"])
            _run_part("chi2_test", _do_chi2)

        if "beta" in a or "se" in a:
            def _do_z() -> None:
                r = rec_mod.z_from_beta_se(a["beta"], a["se"], reported=a.get("z_value"))
                out_stat.update(recomputed_z=r["recomputed"]["z"], recomputed_z_p=r["recomputed"]["p"], z_receipt=r)
                if has_reported_p:
                    _attach_stat_consistency("z", r["recomputed"]["z"], None, recomputed_p=r["recomputed"]["p"])
            _run_part("z_test", _do_z)

        if "ci_estimate" in a:
            def _do_ci() -> None:
                ci_r = rec_mod.check_ci_consistency(
                    a["ci_estimate"],
                    a["ci_lower"],
                    a["ci_upper"],
                    level=a.get("ci_level", 0.95),
                    log_scale=a.get("ci_log_scale", False),
                    ci_method=a.get("ci_method"),
                )
                out_stat["ci_consistency"] = ci_r
                if "consistent" in ci_r:
                    verdict_flags.append(ci_r.get("consistent"))
            _run_part("ci_consistency", _do_ci)

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
            def _do_sd() -> None:
                sd_r = rec_mod.check_sd_possible(a["check_sd"], a["scale_min"], a["scale_max"], n=a.get("sample_n"))
                out_stat["sd_possible"] = sd_r
                if "consistent" in sd_r:
                    verdict_flags.append(sd_r.get("consistent"))
            _run_part("sd_possible", _do_sd)

        if "sample_df" in a:
            def _do_sdf() -> None:
                sdf_r = rec_mod.check_sample_size_from_df(
                    a["sample_df"], a["reported_n"], kind=a.get("df_kind", "ttest_2sample"), n_params=a.get("n_params")
                )
                out_stat["sample_size_from_df"] = sdf_r
                if "consistent" in sdf_r:
                    verdict_flags.append(sdf_r.get("consistent"))
            _run_part("sample_size_from_df", _do_sdf)

        if "effect_size_d" in a:
            if "power_n1" in a:
                _run_part(
                    "achieved_power",
                    lambda: out_stat.update(
                        achieved_power=rec_mod.achieved_power_ttest(
                            a["effect_size_d"], a["power_n1"], n2=a.get("power_n2"), alpha=a.get("alpha", 0.05)
                        )
                    ),
                )
            if "target_power" in a or "power_n1" not in a:
                def _do_req_n() -> None:
                    rn = rec_mod.required_n_ttest(
                        a["effect_size_d"],
                        power=a.get("target_power", 0.8),
                        alpha=a.get("alpha", 0.05),
                        ratio=a.get("sample_ratio", 1.0),
                    )
                    out_stat["required_sample_size"] = rn
                    out_stat["required_n"] = rn

                _run_part("required_sample_size", _do_req_n)

        if not out_stat and not partial_errors:
            raise ValueError("No statistical parameters provided to academic_recompute_statistics")
        if partial_errors:
            if not out_stat:
                raise ValueError("; ".join(f"{k}: {v}" for k, v in partial_errors.items()))
            out_stat["partial_failure"] = partial_errors
        eff_cons: Optional[bool] = None
        if partial_errors:
            eff_cons = False if (False in verdict_flags) else None
            if eff_cons is False:
                out_stat["consistent"] = False
        elif verdict_flags:
            eff_cons = _agg_tri_bool(verdict_flags)
            out_stat["consistent"] = eff_cons
        return _register_kernel_execution(
            "academic_recompute_statistics",
            a,
            out_stat,
            verification_scope="statistical_numerical_consistency",
            consistent=eff_cons,
        )

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
        tf_vals = [v.get("consistent") for v in out.values() if isinstance(v, dict) and "consistent" in v]
        tf_cons: Optional[bool] = False if (False in tf_vals) else (None if (None in tf_vals) else True)
        out["consistent"] = tf_cons
        return _register_kernel_execution(
            "academic_table_forensics",
            a,
            out,
            verification_scope="table_arithmetic_conservation",
            consistent=tf_cons,
        )

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
        out_meta: dict[str, Any] = {
            "study_count": len(yi),
            "fixed_effect": asdict(mc.pool_fixed(yi, vi)),
            "random_effects_dl": asdict(mc.pool_random(yi, vi)),
            "leave_one_out": loo,
            "publication_bias": bias,
        }
        if all(isinstance(s.get("subgroup"), str) and s["subgroup"].strip() for s in studies):
            groups = [s["subgroup"].strip() for s in studies]
            if len(set(groups)) >= 2:
                out_meta["subgroup_analysis"] = mc.subgroup_analysis(yi, vi, groups)
        if len(yi) >= 3 and all(isinstance(s.get("moderator"), (int, float)) and not isinstance(s.get("moderator"), bool) for s in studies):
            mods = [float(s["moderator"]) for s in studies]
            if len(set(mods)) >= 2:
                out_meta["meta_regression"] = mc.meta_regression(yi, vi, mods)
        return out_meta

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
        obs_ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        for s_name, pre_rec, live_fn, parse_fn in (
            ("openalex", oa_in, vw.fetch_openalex, vw.parse_openalex_work),
            ("crossref", cr_in, vw.fetch_crossref, vw.parse_crossref_work),
        ):
            q_ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            if pre_rec is not None:
                w = parse_fn(pre_rec)
                sources_out[s_name] = {"status": "ok", "mode": "offline-record", "queried_at": q_ts, "work": w}
                parsed.append(w)
            elif offline or not a.get("live", False):
                sources_out[s_name] = {"status": "skipped", "queried_at": q_ts, "reason": "offline mode; no record provided"}
            else:
                try:
                    w = parse_fn(live_fn(doi))
                    sources_out[s_name] = {"status": "ok", "mode": "live", "queried_at": q_ts, "work": w}
                    parsed.append(w)
                except Exception as exc:
                    sources_out[s_name] = {"status": "failed", "queried_at": q_ts, "error": f"{type(exc).__name__}: {exc}"}
        cmp = vw.compare_works(parsed, target_doi=doi) if parsed else None
        bound_srcs = list(cmp.get("positively_bound_sources") or []) if isinstance(cmp, dict) else []
        mismatches = list(cmp.get("identity_binding_mismatch") or []) if isinstance(cmp, dict) else []
        id_resolved = bool(len(bound_srcs) > 0 and len(mismatches) == 0)
        is_retracted = bool(cmp.get("is_retracted")) if isinstance(cmp, dict) else False
        has_cited = any(
            a.get(k) is not None for k in ("cited_title", "cited_authors", "cited_year", "cited_venue")
        )
        cit_chk = vw.compare_cited_metadata(a, parsed, target_doi=doi) if (has_cited and parsed) else None
        cit_match = cit_chk["citation_metadata_match"] if isinstance(cit_chk, dict) else None
        modes_used = {
            str(s_obj.get("mode"))
            for s_obj in sources_out.values()
            if isinstance(s_obj, Mapping) and s_obj.get("status") == "ok" and s_obj.get("mode")
        }
        if modes_used == {"live"}:
            mode_suffix = "live"
        elif modes_used == {"offline-record"}:
            mode_suffix = "caller_record"
        elif len(modes_used) > 1:
            mode_suffix = "mixed_sources"
        else:
            mode_suffix = "unobserved"
        v_scope = (
            f"bibliographic_citation_faithfulness_{mode_suffix}"
            if has_cited
            else f"bibliographic_registry_identity_{mode_suffix}"
        )
        if not parsed:
            cons_bib: Optional[bool] = None
        elif mismatches or not id_resolved or is_retracted:
            cons_bib = False
        elif has_cited:
            cons_bib = cit_match
        else:
            cons_bib = True
        vs_out = {
            "normalized": norm,
            "target_doi": doi,
            "identifier_resolved": id_resolved,
            "is_retracted": is_retracted,
            "citation_metadata_match": cit_match,
            "citation_check": cit_chk,
            "consistent": cons_bib,
            "sources": sources_out,
            "comparison": cmp,
        }
        return _register_kernel_execution(
            "academic_verify_source",
            a,
            vs_out,
            verification_scope=v_scope,
            consistent=cons_bib,
            executed_at=obs_ts,
        )

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
            raise ValueError("Provide target or target_path")
        ws_root = authorized_workspace_root()
        try:
            target_p = safe_path(str(target), root=ws_root, must_exist=True)
        except Exception as exc:
            raise ValueError("Target path is outside authorized workspace root or inaccessible") from exc
        try:
            dbs = _mod("double_blind_sanitizer")
            forb = [str(t) for t in (a.get("forbidden_tokens") or []) if str(t)]
            rep = dbs.scan_target(target_p, forbidden_tokens=forb, root=ws_root)
            return _redact_blind_scan_report(rep)
        except Exception as exc:
            raise RuntimeError("Anonymity scan failed; source path and error details were withheld to prevent identifier leakage") from exc

    if name == "academic_pre_submission_lint":
        tex = a.get("tex_path") or a.get("tex")
        if not tex:
            raise ValueError("Provide tex or tex_path")
        ws_root = authorized_workspace_root()
        tex_p = safe_path(str(tex), root=ws_root, must_exist=True)
        pdf_p = safe_path(str(a["pdf_path"]), root=ws_root, must_exist=True) if a.get("pdf_path") else None
        ceg_p = safe_path(str(a["ceg_path"]), root=ws_root, must_exist=True) if a.get("ceg_path") else None
        psl = _mod("pre_submission_linter")
        return thaw(
            psl.lint_manuscript(
                tex_p,
                venue=a.get("venue", "iclr"),
                double_blind=a.get("double_blind"),
                phase=a.get("phase", "submission"),
                contribution_type=a.get("contribution_type", "general_empirical"),
                pdf_path=pdf_p,
                ceg_path=ceg_p,
                require_ceg_binding=bool(a.get("require_ceg_binding", False)),
                check_academic_style=bool(a.get("check_academic_style", False)),
                workspace_root=ws_root,
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

    if name == "academic_scfabric_hardware_probe":
        cp = _mod("compute_probe")
        if a.get("emit_receipt"):
            return cp.build_compute_receipt(
                operation=str(a.get("operation") or "matmul_f64"),
                scale=str(a.get("scale") or "small"),
                dtype=str(a["dtype"]) if a.get("dtype") is not None else None,
                measure_candidates=bool(a.get("measure_candidates", False)),
            )
        return cp.probe()

    if name == "academic_cross_review":
        cr = _mod("cross_review")
        bdir_raw = a.get("base_dir")
        bdir = safe_path(bdir_raw, root=authorized_workspace_root(), must_exist=True) if bdir_raw else authorized_workspace_root()
        return cr.deliberate_inline(
            a["findings_by_model"],
            mode=str(a.get("mode") or "standard"),
            challenge_replies=a.get("challenge_replies"),
            base_dir=bdir,
        )

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

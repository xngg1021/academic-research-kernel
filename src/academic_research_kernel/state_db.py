"""Unified SQLite-backed research state kernel (Occam edition, hardened).

Delegates relational, foreign-key, append-only, savepoint, and recursive-DAG
invariants to CPython's built-in C ``sqlite3`` engine (with ``PRAGMA
recursive_triggers = ON``, ``STRICT`` tables, cycle triggers, and monotonic CAS
watcher state), paired with strict semantic/schema admission at the API boundary.
"""
from __future__ import annotations

import collections.abc
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
from typing import Any, Iterable, Iterator, Mapping, Optional

from ._stdlib import (
    ARK_SQLITE_APP_ID,
    ARK_SQLITE_USER_VERSION,
    _SQLITE_INIT_LOCK,
    canonical_json,
    configure_sqlite_connection,
    freeze,
    nfc_compact,
    normalize_doi,
    run_with_sqlite_retry,
    safe_path,
    sha256_hex,
    thaw,
    validate_schema,
    verify_or_claim_sqlite_identity,
)

ALLOWED_ARTIFACT_KINDS: frozenset[str] = frozenset({
    "data_snapshot",
    "source",
    "computed_evidence",
    "table_cell",
    "statistic_artifact",
    "research_object",
    "research_documents",
    "lineage_receipt",
    "paper_extraction",
    "paper_comparison",
    "reproduction_receipt",
    "literature_delta",
    "retraction_delta",
    "systematic_review",
    "evidence_receipt",
    "compute_receipt",
    "computation_artifact",
    "quantitative_audit",
    "opaque_manuscript",
    "literature_analysis",
    "claim_evidence_graph",
    "decision_ledger",
    "cross_review_artifact",
    "review_run_receipt",
    "review_panel_spec",
    "review_finding",
    "review_result",
    "artifact_ingestion_receipt",
    "research_artifact_envelope",
    "ingestion_kernel_state",
    "legacy_academic_evidence",
})

KIND_SCHEMA_MAP: Mapping[str, str] = {
    "research_object": "research-object.schema.json",
    "research_documents": "research-documents.schema.json",
    "paper_extraction": "paper-extraction.schema.json",
    "paper_comparison": "paper-comparison.schema.json",
    "lineage_receipt": "lineage-receipt.schema.json",
    "reproduction_receipt": "reproduction-receipt.schema.json",
    "literature_delta": "literature-delta.schema.json",
    "retraction_delta": "retraction-delta.schema.json",
    "systematic_review": "systematic-review-artifact.schema.json",
    "evidence_receipt": "evidence-receipt.schema.json",
    "compute_receipt": "compute-receipt.schema.json",
    "computation_artifact": "computation-artifact.schema.json",
    "quantitative_audit": "quantitative-audit.schema.json",
    "opaque_manuscript": "opaque-manuscript.schema.json",
    "literature_analysis": "literature-analysis-artifact.schema.json",
    "claim_evidence_graph": "claim-evidence-graph.schema.json",
    "decision_ledger": "decision-ledger-receipt.schema.json",
    "cross_review_artifact": "cross-review-artifact.schema.json",
    "review_run_receipt": "review-run-receipt.schema.json",
    "review_panel_spec": "review-panel-spec.schema.json",
    "review_finding": "review-finding.schema.json",
    "review_result": "review-result.schema.json",
    "artifact_ingestion_receipt": "artifact-ingestion-receipt.schema.json",
    "research_artifact_envelope": "research-artifact-envelope.schema.json",
    "ingestion_kernel_state": "ingestion-kernel-state.schema.json",
    "legacy_academic_evidence": "legacy-academic-evidence.schema.json",
}

ALLOWED_LINEAGE_RELATIONS: frozenset[str] = frozenset({
    "derived_from",
    "extracted_from",
    "recomputed_from",
    "verified_by",
})

ALLOWED_CLAIM_STATUSES: frozenset[str] = frozenset({"supported", "contested", "unresolved", "refuted"})
ALLOWED_EVIDENCE_STANCES: frozenset[str] = frozenset({"supports", "contradicts", "qualifies"})
ALLOWED_CLAIM_RELATIONS: frozenset[str] = frozenset({"depends_on", "refines", "contradicts", "corroborates", "cites"})
ALLOWED_DECISION_VERDICTS: frozenset[str] = frozenset({"positive", "negative", "inconclusive", "unverifiable"})


def canonical_evidence_claim_digest(claim_item: Mapping[str, Any]) -> str:
    """Compute canonical SHA-256 digest of a claim item inside an AcademicEvidenceReceipt."""
    payload = {
        "claim": claim_item.get("claim", ""),
        "evidence_type": claim_item.get("evidence_type", ""),
        "locator": claim_item.get("locator", ""),
        "source": claim_item.get("source", ""),
        "support_status": claim_item.get("support_status", ""),
    }
    return sha256_hex(canonical_json(payload))


_HEX64_LOWER_RE = re.compile(r"^[0-9a-f]{64}\Z")


def validate_receipt_ref_dict(rref: Any) -> list[str]:
    """Validate a ReceiptRef dictionary against the canonical oneOf contract."""
    if not isinstance(rref, Mapping):
        return ["ReceiptRef must be a JSON object"]
    rk = rref.get("kind")
    if rk == "lineage":
        extra = set(rref.keys()) - {"kind", "schema_version", "receipt_id", "receipt_digest", "locator"}
        if extra:
            return [f"Lineage ReceiptRef contains unsupported fields: {sorted(extra)!r}"]
        if rref.get("schema_version") != "lineage-receipt-1.0":
            return [f"Lineage ReceiptRef requires schema_version='lineage-receipt-1.0', got {rref.get('schema_version')!r}"]
        rid = rref.get("receipt_id")
        rdig = rref.get("receipt_digest")
        if not isinstance(rid, str) or not rid.strip() or rid != rid.strip():
            return ["Lineage ReceiptRef requires non-empty receipt_id"]
        if not isinstance(rdig, str) or not _HEX64_LOWER_RE.fullmatch(rdig):
            return ["Lineage ReceiptRef requires lowercase 64-hex receipt_digest"]
        if "locator" in rref and not isinstance(rref["locator"], str):
            return ["Lineage ReceiptRef locator must be a string"]
        return []
    if rk == "academic_evidence":
        extra = set(rref.keys()) - {"kind", "schema_version", "claim_digest", "payload_sha256", "locator"}
        if extra:
            return [f"AcademicEvidence ReceiptRef contains unsupported fields: {sorted(extra)!r}"]
        if rref.get("schema_version") != "1.0":
            return [f"AcademicEvidence ReceiptRef requires schema_version='1.0', got {rref.get('schema_version')!r}"]
        cdig = rref.get("claim_digest")
        psha = rref.get("payload_sha256")
        if not isinstance(cdig, str) or not _HEX64_LOWER_RE.fullmatch(cdig):
            return ["AcademicEvidence ReceiptRef requires lowercase 64-hex claim_digest"]
        if not isinstance(psha, str) or not _HEX64_LOWER_RE.fullmatch(psha):
            return ["AcademicEvidence ReceiptRef requires lowercase 64-hex payload_sha256"]
        if "locator" in rref and not isinstance(rref["locator"], str):
            return ["AcademicEvidence ReceiptRef locator must be a string"]
        return []
    return [f"Unsupported ReceiptRef kind: {rk!r}"]


def validate_academic_evidence_payload(payload: Any) -> list[str]:
    """Validate an AcademicEvidence physical receipt against legacy-academic-evidence.schema.json and inner claim digests."""
    if not isinstance(payload, Mapping):
        return ["AcademicEvidence payload must be a JSON object"]
    plain = thaw(payload)
    errs = list(validate_schema(plain, "legacy-academic-evidence.schema.json"))
    if errs:
        return errs
    for idx, ci in enumerate(plain.get("claims") or ()):
        if isinstance(ci, Mapping) and "claim_digest" in ci:
            comp_cd = canonical_evidence_claim_digest(ci)
            if str(ci["claim_digest"]).lower() != comp_cd:
                errs.append(f"AcademicEvidence claims[{idx}] inner claim_digest mismatch")
    return errs


def decode_content_payloads_map(
    content_payloads: Any,
    *,
    max_bytes: int = 10 * 1024 * 1024,
) -> dict[str, bytes]:
    """Decode and validate legacy MCP base64 entity content_payloads map."""
    import base64
    import binascii

    if content_payloads is None:
        return {}
    if not isinstance(content_payloads, Mapping):
        raise ValueError("content_payloads must be a dictionary mapping entity IDs to base64 strings")
    out: dict[str, bytes] = {}
    total = 0
    max_enc_len = 4 * ((max_bytes + 2) // 3)
    for eid, enc in content_payloads.items():
        if not isinstance(eid, str) or not eid or not isinstance(enc, str):
            raise ValueError("content_payloads must map non-empty string entity IDs to base64 strings")
        if len(enc) > max_enc_len:
            raise ValueError("content_payloads exceeds verification byte budget")
        try:
            raw_b = base64.b64decode(enc, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"content_payloads[{eid!r}] is not valid base64") from exc
        total += len(raw_b)
        if total > max_bytes:
            raise ValueError("content_payloads exceeds verification byte budget")
        out[eid] = raw_b
    return out


def validate_lineage_receipt_semantics(
    doc: Mapping[str, Any],
    *,
    decoded_content: Optional[Mapping[str, bytes]] = None,
    strict_unknown_entities: bool = True,
) -> list[str]:
    """Verify structural DAG closure, status invariants, dual digests, and optional entity bytes on lineage-receipt-1.0."""
    errs = list(validate_schema(doc, "lineage-receipt.schema.json"))
    if errs or not isinstance(doc, Mapping):
        return errs or ["Lineage receipt must be a JSON object"]

    data = thaw(doc)
    target_id = str(data.get("target_id") or "")
    entities = list(data.get("entities") or [])
    activities = list(data.get("activities") or [])
    edges = list(data.get("edges") or [])
    trace_steps = list(data.get("trace_steps") or [])
    roots_decl = list(data.get("root_ancestors") or [])
    v_status = str(data.get("verification_status") or "")
    t_status = str(data.get("topology_status") or "")
    c_status = str(data.get("content_verification") or "")
    err_detail = str(data.get("error_detail") or "")

    ent_by_id: dict[str, dict[str, Any]] = {}
    for idx, ent in enumerate(entities):
        raw_eid = ent.get("id")
        if not isinstance(raw_eid, str) or not raw_eid.strip() or raw_eid != raw_eid.strip() or raw_eid in ent_by_id:
            errs.append(f"Duplicate, empty, or whitespace-padded entity id at entities[{idx}]: {raw_eid!r}")
        else:
            ent_by_id[raw_eid] = ent

    act_by_id: dict[str, dict[str, Any]] = {}
    for idx, act in enumerate(activities):
        raw_aid = act.get("id")
        if not isinstance(raw_aid, str) or not raw_aid.strip() or raw_aid != raw_aid.strip() or raw_aid in act_by_id or raw_aid in ent_by_id:
            errs.append(f"Duplicate, empty, whitespace-padded, or entity-colliding activity id at activities[{idx}]: {raw_aid!r}")
        else:
            act_by_id[raw_aid] = act

    if errs:
        return errs

    edge_key = lambda edge: (
        edge.get("type", ""),
        edge.get("source_id", ""),
        edge.get("target_id", ""),
        edge.get("activity_id") or "",
        canonical_json(edge.get("metadata", {})),
    )
    lineage_payload = {
        "protocol": "lineage-receipt-1.0",
        "target_id": target_id,
        "root_ancestors": sorted(roots_decl),
        "entities": sorted(entities, key=lambda item: item["id"]),
        "activities": sorted(activities, key=lambda item: item["id"]),
        "edges": sorted(edges, key=edge_key),
        "trace_steps": trace_steps,
    }
    recomputed_lineage = sha256_hex(canonical_json(lineage_payload))
    declared_lineage = str(data.get("lineage_digest") or "").lower()
    missing_input_form = (
        declared_lineage == "0" * 64
        and v_status == "missing_input"
        and t_status == "missing_input"
        and c_status == "unchecked"
        and not roots_decl
        and not entities
        and not activities
        and not edges
        and not trace_steps
    )
    exp_lineage = declared_lineage if missing_input_form else recomputed_lineage
    if declared_lineage != exp_lineage:
        errs.append(f"Lineage digest mismatch: declared {declared_lineage!r}, recomputed {exp_lineage!r}")
    if data.get("content_digest") is not None and str(data["content_digest"]).lower() != exp_lineage:
        errs.append("Lineage content_digest alias disagrees with lineage_digest")

    receipt_base = {
        "lineage_digest": exp_lineage,
        "target_id": target_id,
        "verification_status": v_status,
        "topology_status": t_status,
        "content_verification": c_status,
        "error_detail": err_detail,
    }
    possible_by_mode = {
        mode: sha256_hex(canonical_json(dict(receipt_base, check_on_disk_hashes=mode)))
        for mode in (False, True)
    }
    declared_receipt = str(data.get("receipt_digest") or "").lower()
    matching_modes = [m for m, dig in possible_by_mode.items() if dig == declared_receipt]
    if not matching_modes:
        errs.append("Lineage receipt_digest does not match canonical verification metadata digest")
    if data.get("receipt_id") != f"rec-{declared_receipt[:32]}":
        errs.append(f"Lineage receipt_id {data.get('receipt_id')!r} != expected 'rec-{declared_receipt[:32]}'")

    # Structural & topological validation
    if t_status != "missing_input" and target_id not in ent_by_id:
        errs.append(f"Lineage target_id {target_id!r} missing from entities while topology_status={t_status!r}")
        return errs

    if t_status == "missing_input":
        if v_status != "missing_input" or c_status != "unchecked" or roots_decl or trace_steps:
            errs.append("missing_input topology requires verification_status='missing_input', content_verification='unchecked', and empty roots/steps")
        return errs

    parents_by_child: dict[str, set[str]] = {}
    used_by_act: dict[str, set[str]] = {}
    gen_by_act: dict[str, set[str]] = {}
    endpoint_broken = False
    self_loop = False
    for idx, e in enumerate(edges):
        et = str(e.get("type") or "")
        src = str(e.get("source_id") or "")
        tgt = str(e.get("target_id") or "")
        act_ref = e.get("activity_id")
        if et == "used":
            if src not in act_by_id or tgt not in ent_by_id:
                endpoint_broken = True
            else:
                parents_by_child.setdefault(src, set()).add(tgt)
                used_by_act.setdefault(src, set()).add(tgt)
        elif et == "generated":
            if src not in act_by_id or tgt not in ent_by_id:
                endpoint_broken = True
            else:
                parents_by_child.setdefault(tgt, set()).add(src)
                gen_by_act.setdefault(src, set()).add(tgt)
        elif et == "derived_from":
            if src not in ent_by_id or tgt not in ent_by_id:
                endpoint_broken = True
            elif src == tgt:
                self_loop = True
            else:
                parents_by_child.setdefault(src, set()).add(tgt)
            if act_ref:
                if str(act_ref) not in act_by_id:
                    endpoint_broken = True
                else:
                    parents_by_child.setdefault(src, set()).add(str(act_ref))

    for aid, act in act_by_id.items():
        sid = act.get("script_id")
        if sid:
            if str(sid) not in ent_by_id or ent_by_id[str(sid)].get("type") != "code_file":
                endpoint_broken = True
            else:
                parents_by_child.setdefault(aid, set()).add(str(sid))

    # Global cycle detection across ALL nodes in the receipt (including disconnected components)
    global_state: dict[str, int] = {}
    has_global_cycle = self_loop
    for start_n in sorted(set(ent_by_id) | set(act_by_id)):
        if has_global_cycle:
            break
        if global_state.get(start_n, 0) != 0:
            continue
        global_state[start_n] = 1
        g_stack: list[tuple[str, list[str], int]] = [(start_n, sorted(parents_by_child.get(start_n, ())), 0)]
        while g_stack and not has_global_cycle:
            cur_g, ups_g, idx_g = g_stack[-1]
            if idx_g >= len(ups_g):
                global_state[cur_g] = 2
                g_stack.pop()
                continue
            g_stack[-1] = (cur_g, ups_g, idx_g + 1)
            up_g = ups_g[idx_g]
            st_g = global_state.get(up_g, 0)
            if st_g == 1:
                has_global_cycle = True
                break
            if st_g == 0:
                global_state[up_g] = 1
                g_stack.append((up_g, sorted(parents_by_child.get(up_g, ())), 0))

    # DFS reachability & cycle check from target_id
    state_dfs: dict[str, int] = {target_id: 1}
    visited: set[str] = {target_id}
    stack_dfs: list[tuple[str, list[str], int]] = [(target_id, sorted(parents_by_child.get(target_id, ())), 0)]
    has_cycle = self_loop
    while stack_dfs and not has_cycle:
        cur_n, ups, idx_u = stack_dfs[-1]
        if idx_u >= len(ups):
            state_dfs[cur_n] = 2
            stack_dfs.pop()
            continue
        stack_dfs[-1] = (cur_n, ups, idx_u + 1)
        up = ups[idx_u]
        st_u = state_dfs.get(up, 0)
        if st_u == 1:
            has_cycle = True
            break
        visited.add(up)
        if st_u == 0:
            state_dfs[up] = 1
            stack_dfs.append((up, sorted(parents_by_child.get(up, ())), 0))

    if t_status != "valid_dag":
        if t_status == "cycle_detected" and not (has_cycle or has_global_cycle):
            errs.append("Lineage declares topology_status='cycle_detected' on an acyclic graph")
        elif t_status == "broken_chain" and not endpoint_broken:
            errs.append("Lineage declares topology_status='broken_chain' without broken references")
        if v_status != t_status:
            errs.append(f"Invalid lineage topology {t_status!r} requires verification_status={t_status!r}, got {v_status!r}")
        if c_status != "unchecked":
            errs.append(f"Invalid lineage topology {t_status!r} requires content_verification='unchecked', got {c_status!r}")
        if roots_decl or trace_steps:
            errs.append(f"Invalid lineage topology {t_status!r} must have empty root_ancestors and trace_steps")
    else:
        if endpoint_broken:
            errs.append("Lineage declares topology_status='valid_dag' despite broken entity/activity references")
        if has_cycle or has_global_cycle:
            errs.append("Lineage declares topology_status='valid_dag' despite cycle in lineage graph")
        all_declared_nodes = set(ent_by_id) | set(act_by_id)
        if all_declared_nodes - visited:
            errs.append(f"Lineage declares disconnected nodes outside target closure: {sorted(all_declared_nodes - visited)!r}")
        seen_ts_acts: set[str] = set()
        for idx_ts, ts in enumerate(trace_steps, 1):
            if not isinstance(ts, Mapping):
                errs.append(f"trace_steps[{idx_ts - 1}] must be an object")
                continue
            sn = ts.get("step_number")
            ts_aid = str(ts.get("activity_id") or "")
            inps = list(ts.get("inputs") or [])
            outs = list(ts.get("outputs") or [])
            if type(sn) is not int or sn != idx_ts:
                errs.append(f"trace_steps[{idx_ts - 1}] step_number {sn!r} != expected {idx_ts}")
            if ts_aid not in act_by_id or ts_aid in seen_ts_acts:
                errs.append(f"trace_steps[{idx_ts - 1}] references unknown or duplicate activity_id {ts_aid!r}")
                continue
            seen_ts_acts.add(ts_aid)
            if any(x not in ent_by_id for x in inps) or any(x not in ent_by_id for x in outs):
                errs.append(f"trace_steps[{idx_ts - 1}] inputs/outputs reference unknown entity")
            if sorted(inps) != sorted(used_by_act.get(ts_aid, ())):
                errs.append(f"trace_steps[{idx_ts - 1}] inputs mismatch used edges for {ts_aid!r}")
            if sorted(outs) != sorted(gen_by_act.get(ts_aid, ())):
                errs.append(f"trace_steps[{idx_ts - 1}] outputs mismatch generated edges for {ts_aid!r}")
        if act_by_id and seen_ts_acts != set(act_by_id):
            errs.append("Lineage valid_dag trace_steps must cover every declared activity")
        if c_status == "hash_mismatch" and v_status != "hash_mismatch":
            errs.append(f"content_verification='hash_mismatch' requires verification_status='hash_mismatch', got {v_status!r}")
        if c_status == "missing_artifact" and v_status != "missing_artifact":
            errs.append(f"content_verification='missing_artifact' requires verification_status='missing_artifact', got {v_status!r}")
        if v_status == "intact" and c_status != "fully_verified":
            errs.append(f"Lineage declares verification_status='intact' with incompatible content_verification={c_status!r}")
        if c_status == "fully_verified" and v_status != "intact":
            errs.append(f"Lineage declares content_verification='fully_verified' with incompatible verification_status={v_status!r}")
        if not errs:
            def _has_up_ent(en: str) -> bool:
                seen_q: set[str] = set()
                q = list(parents_by_child.get(en, ()))
                while q:
                    u = q.pop()
                    if u in seen_q:
                        continue
                    seen_q.add(u)
                    if u in ent_by_id and u != en:
                        return True
                    q.extend(parents_by_child.get(u, ()))
                return False

            closure_ents = sorted(n for n in visited if n in ent_by_id)
            exp_roots = [] if c_status in ("hash_mismatch", "missing_artifact") else sorted(n for n in closure_ents if not _has_up_ent(n))
            if roots_decl != exp_roots:
                errs.append(f"Lineage root_ancestors mismatch: declared {roots_decl!r}, expected {exp_roots!r}")
            ents_with_sha = [n for n in closure_ents if ent_by_id[n].get("sha256")]
            if c_status == "fully_verified" and (not closure_ents or len(ents_with_sha) != len(closure_ents)):
                errs.append("Lineage declares content_verification='fully_verified' without sha256 on all closure entities")

    if decoded_content is not None:
        for eid_c, raw_b in decoded_content.items():
            if eid_c not in ent_by_id:
                if strict_unknown_entities:
                    errs.append(f"content_payloads references unknown entity_id {eid_c!r}")
                continue
            exp_ent_sha = str(ent_by_id[eid_c].get("sha256") or "").lower()
            act_ent_sha = sha256_hex(raw_b)
            if exp_ent_sha and act_ent_sha != exp_ent_sha and c_status != "hash_mismatch":
                errs.append(f"Entity {eid_c!r} content_payloads SHA-256 mismatch: expected {exp_ent_sha}, computed {act_ent_sha}")

    return errs

PRUNE_REASONS: frozenset[str] = frozenset({
    "resource_exhausted",
    "superseded",
    "contradicted",
    "out_of_scope",
    "duplicate",
    "external_constraint",
    "investigator_error",
    "other",
})
REOPEN_REASONS: frozenset[str] = frozenset({
    "new_evidence",
    "scope_change",
    "investigator_reconsideration",
    "error_correction",
    "other",
})

_VALID_TRANSITIONS: Mapping[Optional[str], frozenset[str]] = {
    None: frozenset({"active", "pruned"}),
    "active": frozenset({"pruned"}),
    "pruned": frozenset({"reopened"}),
    "reopened": frozenset({"pruned"}),
}

SCHEMA_SQL = f"""
PRAGMA application_id = {ARK_SQLITE_APP_ID};
PRAGMA user_version = {ARK_SQLITE_USER_VERSION};

CREATE TABLE IF NOT EXISTS works (
    work_id TEXT PRIMARY KEY CHECK (length(trim(work_id)) > 0),
    doi TEXT,
    arxiv_id TEXT,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    year INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{{}}'
) STRICT;

CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY CHECK (length(trim(artifact_id)) > 0),
    kind TEXT NOT NULL CHECK (length(trim(kind)) > 0),
    payload_json TEXT NOT NULL CHECK (length(payload_json) >= 2),
    payload_sha256 TEXT NOT NULL CHECK (length(payload_sha256) = 64 AND payload_sha256 NOT GLOB '*[^0-9a-f]*')
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_upd
BEFORE UPDATE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_artifacts_immutable_del
BEFORE DELETE ON artifacts
BEGIN
    SELECT RAISE(ABORT, 'artifacts table is append-only');
END;

CREATE TABLE IF NOT EXISTS lineage_edges (
    child_id TEXT NOT NULL,
    parent_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('derived_from', 'extracted_from', 'recomputed_from', 'verified_by')),
    CHECK (child_id != parent_id),
    PRIMARY KEY (child_id, parent_id, relation),
    FOREIGN KEY (child_id) REFERENCES artifacts(artifact_id),
    FOREIGN KEY (parent_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE INDEX IF NOT EXISTS idx_lineage_child ON lineage_edges(child_id);
CREATE INDEX IF NOT EXISTS idx_lineage_parent ON lineage_edges(parent_id);

CREATE TRIGGER IF NOT EXISTS trg_lineage_no_cycle
BEFORE INSERT ON lineage_edges
BEGIN
    SELECT CASE WHEN EXISTS (
        WITH RECURSIVE reach(node) AS (
            SELECT NEW.parent_id
            UNION
            SELECT e.parent_id FROM lineage_edges e JOIN reach r ON e.child_id = r.node
        )
        SELECT 1 FROM reach WHERE node = NEW.child_id
    ) THEN RAISE(ABORT, 'Cycle detected in lineage_edges') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_lineage_immutable_upd
BEFORE UPDATE ON lineage_edges
BEGIN
    SELECT RAISE(ABORT, 'lineage_edges table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_lineage_immutable_del
BEFORE DELETE ON lineage_edges
BEGIN
    SELECT RAISE(ABORT, 'lineage_edges table is append-only');
END;

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY CHECK (length(trim(claim_id)) > 0),
    claim_text TEXT NOT NULL CHECK (length(trim(claim_text)) > 0),
    claim_digest TEXT NOT NULL CHECK (length(claim_digest) = 64 AND claim_digest NOT GLOB '*[^0-9a-f]*'),
    status TEXT NOT NULL DEFAULT 'unresolved' CHECK (status IN ('supported', 'contested', 'unresolved', 'refuted')),
    metadata_json TEXT NOT NULL DEFAULT '{{}}'
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_claims_text_immutable_upd
BEFORE UPDATE ON claims
WHEN OLD.claim_id != NEW.claim_id OR OLD.claim_text != NEW.claim_text OR OLD.claim_digest != NEW.claim_digest
BEGIN
    SELECT RAISE(ABORT, 'claim identity, text, and digest are immutable');
END;

CREATE TRIGGER IF NOT EXISTS trg_claims_immutable_del
BEFORE DELETE ON claims
BEGIN
    SELECT RAISE(ABORT, 'claims table is append-only');
END;

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    stance TEXT NOT NULL DEFAULT 'supports' CHECK (stance IN ('supports', 'contradicts', 'qualifies')),
    locator TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (claim_id, artifact_id, locator),
    FOREIGN KEY (claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_claim_evidence_immutable_upd
BEFORE UPDATE ON claim_evidence
BEGIN
    SELECT RAISE(ABORT, 'claim_evidence table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_evidence_immutable_del
BEFORE DELETE ON claim_evidence
BEGIN
    SELECT RAISE(ABORT, 'claim_evidence table is append-only');
END;

CREATE TABLE IF NOT EXISTS claim_edges (
    src_claim_id TEXT NOT NULL,
    dst_claim_id TEXT NOT NULL,
    relation TEXT NOT NULL CHECK (relation IN ('depends_on', 'refines', 'contradicts', 'corroborates', 'cites')),
    CHECK (src_claim_id != dst_claim_id),
    PRIMARY KEY (src_claim_id, dst_claim_id, relation),
    FOREIGN KEY (src_claim_id) REFERENCES claims(claim_id),
    FOREIGN KEY (dst_claim_id) REFERENCES claims(claim_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_claim_edges_no_cycle
BEFORE INSERT ON claim_edges
WHEN NEW.relation IN ('depends_on', 'refines')
BEGIN
    SELECT CASE WHEN EXISTS (
        WITH RECURSIVE reach(node) AS (
            SELECT NEW.dst_claim_id
            UNION
            SELECT e.dst_claim_id FROM claim_edges e
            JOIN reach r ON e.src_claim_id = r.node
            WHERE e.relation IN ('depends_on', 'refines')
        )
        SELECT 1 FROM reach WHERE node = NEW.src_claim_id
    ) THEN RAISE(ABORT, 'Cycle detected in claim_edges') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_edges_immutable_upd
BEFORE UPDATE ON claim_edges
BEGIN
    SELECT RAISE(ABORT, 'claim_edges table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_claim_edges_immutable_del
BEFORE DELETE ON claim_edges
BEGIN
    SELECT RAISE(ABORT, 'claim_edges table is append-only');
END;

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY CHECK (length(trim(decision_id)) > 0),
    entry_kind TEXT NOT NULL CHECK (entry_kind IN ('decision', 'negative_result')),
    action TEXT NOT NULL CHECK (action IN ('explore', 'commit', 'abandon', 'revise', 'negative_result')),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0 AND length(title) <= 512),
    verdict TEXT NOT NULL DEFAULT 'inconclusive' CHECK (verdict IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    basis_decision_id TEXT,
    artifact_id TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{{}}',
    CHECK (
        (entry_kind = 'negative_result' AND action = 'negative_result' AND basis_decision_id IS NOT NULL AND basis_decision_id != decision_id)
        OR (entry_kind = 'decision' AND action != 'negative_result')
    ),
    FOREIGN KEY (basis_decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_decisions_basis_check
BEFORE INSERT ON decisions
WHEN NEW.entry_kind = 'negative_result'
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM decisions WHERE decision_id = NEW.basis_decision_id AND entry_kind = 'decision'
    ) THEN RAISE(ABORT, 'negative_result basis must reference an existing non-negative decision') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_decisions_immutable_upd
BEFORE UPDATE ON decisions
BEGIN
    SELECT RAISE(ABORT, 'decisions table is append-only; record changes via decision_events');
END;

CREATE TRIGGER IF NOT EXISTS trg_decisions_immutable_del
BEFORE DELETE ON decisions
BEGIN
    SELECT RAISE(ABORT, 'decisions table is append-only');
END;

CREATE TABLE IF NOT EXISTS decision_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    new_state TEXT NOT NULL CHECK (new_state IN ('active', 'pruned', 'reopened')),
    reason TEXT NOT NULL CHECK (
        reason IN (
            'genesis', 'resource_exhausted', 'superseded', 'contradicted',
            'out_of_scope', 'duplicate', 'external_constraint', 'investigator_error',
            'new_evidence', 'scope_change', 'investigator_reconsideration', 'error_correction', 'other'
        )
    ),
    superseded_by_id TEXT,
    verdict_override TEXT CHECK (verdict_override IS NULL OR verdict_override IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (superseded_by_id) REFERENCES decisions(decision_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_decision_events_immutable_upd
BEFORE UPDATE ON decision_events
BEGIN
    SELECT RAISE(ABORT, 'decision_events log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_decision_events_immutable_del
BEFORE DELETE ON decision_events
BEGIN
    SELECT RAISE(ABORT, 'decision_events log is append-only');
END;

CREATE TABLE IF NOT EXISTS decision_corrections (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('positive', 'negative', 'inconclusive', 'unverifiable')),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) > 0 AND length(rationale) <= 4096),
    artifact_id TEXT,
    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id),
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_decision_corrections_immutable_upd
BEFORE UPDATE ON decision_corrections
BEGIN
    SELECT RAISE(ABORT, 'decision_corrections log is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_decision_corrections_immutable_del
BEFORE DELETE ON decision_corrections
BEGIN
    SELECT RAISE(ABORT, 'decision_corrections log is append-only');
END;

CREATE TABLE IF NOT EXISTS doi_watch_state (
    watcher TEXT NOT NULL CHECK (length(trim(watcher)) > 0),
    item_key TEXT NOT NULL CHECK (length(trim(item_key)) > 0),
    current_status TEXT NOT NULL DEFAULT 'unknown' CHECK (current_status IN ('retracted', 'not_retracted', 'unknown')),
    confirmed_retracted INTEGER CHECK (confirmed_retracted IS NULL OR confirmed_retracted IN (0, 1)),
    signals_json TEXT NOT NULL DEFAULT '[]',
    reserved_seq INTEGER NOT NULL DEFAULT 0 CHECK (reserved_seq >= 0),
    applied_seq INTEGER NOT NULL DEFAULT 0 CHECK (applied_seq >= 0),
    confirmed_seq INTEGER NOT NULL DEFAULT 0 CHECK (confirmed_seq >= 0),
    observation_version INTEGER NOT NULL DEFAULT 0 CHECK (observation_version >= 0),
    truncated INTEGER NOT NULL DEFAULT 0 CHECK (truncated IN (0, 1)),
    last_error TEXT,
    unacked_delta_json TEXT,
    PRIMARY KEY (watcher, item_key)
) STRICT;

CREATE TABLE IF NOT EXISTS doi_watch_commits (
    watcher TEXT NOT NULL CHECK (length(trim(watcher)) > 0),
    item_key TEXT NOT NULL CHECK (length(trim(item_key)) > 0),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    commit_digest TEXT NOT NULL CHECK (length(commit_digest) = 64 AND commit_digest NOT GLOB '*[^0-9a-f]*'),
    snapshot_json TEXT NOT NULL CHECK (length(snapshot_json) >= 2),
    PRIMARY KEY (watcher, item_key, seq)
) STRICT;

CREATE TABLE IF NOT EXISTS kernel_executions (
    execution_id TEXT PRIMARY KEY CHECK (length(trim(execution_id)) > 0),
    tool_name TEXT NOT NULL CHECK (length(trim(tool_name)) > 0),
    kernel_version TEXT NOT NULL CHECK (length(trim(kernel_version)) > 0),
    verification_scope TEXT NOT NULL CHECK (length(trim(verification_scope)) > 0),
    consistent INTEGER CHECK (consistent IN (0, 1)),
    executed_at TEXT NOT NULL CHECK (length(trim(executed_at)) > 0),
    inputs_json TEXT NOT NULL CHECK (length(inputs_json) >= 2),
    inputs_sha256 TEXT NOT NULL CHECK (length(inputs_sha256) = 64 AND inputs_sha256 NOT GLOB '*[^0-9a-f]*'),
    outputs_json TEXT NOT NULL CHECK (length(outputs_json) >= 2),
    outputs_sha256 TEXT NOT NULL CHECK (length(outputs_sha256) = 64 AND outputs_sha256 NOT GLOB '*[^0-9a-f]*'),
    auth_hmac TEXT NOT NULL CHECK (length(auth_hmac) = 64 AND auth_hmac NOT GLOB '*[^0-9a-f]*')
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_kernel_executions_immutable_upd
BEFORE UPDATE ON kernel_executions
BEGIN
    SELECT RAISE(ABORT, 'kernel_executions table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_kernel_executions_immutable_del
BEFORE DELETE ON kernel_executions
BEGIN
    SELECT RAISE(ABORT, 'kernel_executions table is append-only');
END;

CREATE TABLE IF NOT EXISTS artifact_execution_bindings (
    artifact_id TEXT PRIMARY KEY REFERENCES artifacts(artifact_id),
    execution_id TEXT NOT NULL REFERENCES kernel_executions(execution_id),
    verification_scope TEXT NOT NULL CHECK (length(trim(verification_scope)) > 0),
    provenance_tier TEXT NOT NULL CHECK (provenance_tier IN ('kernel_executed', 'external_unverified')),
    ingest_bound_claim_id TEXT,
    binding_hmac TEXT NOT NULL CHECK (length(binding_hmac) = 64 AND binding_hmac NOT GLOB '*[^0-9a-f]*')
) STRICT;

CREATE TRIGGER IF NOT EXISTS trg_artifact_exec_bindings_immutable_upd
BEFORE UPDATE ON artifact_execution_bindings
BEGIN
    SELECT RAISE(ABORT, 'artifact_execution_bindings table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS trg_artifact_exec_bindings_immutable_del
BEFORE DELETE ON artifact_execution_bindings
BEGIN
    SELECT RAISE(ABORT, 'artifact_execution_bindings table is append-only');
END;
"""


_PROCESS_EXEC_SECRET: bytes = secrets.token_bytes(32)


def _get_kernel_exec_secret(*, require_persistent: bool = False) -> bytes:
    """Return HMAC key for kernel execution receipts.

    File-backed SQLite stores require an explicit 64-hex-char ``ARK_EXECUTION_KEY_HEX`` so
    authenticated receipts survive across process restarts; the random process key is
    restricted strictly to ephemeral ``:memory:`` sessions.
    """
    env_hex = (os.environ.get("ARK_EXECUTION_KEY_HEX") or "").strip()
    if env_hex:
        if len(env_hex) != 64 or not re.fullmatch(r"[0-9a-fA-F]{64}", env_hex):
            raise ValueError("ARK_EXECUTION_KEY_HEX must be exactly 64 hex characters (32 bytes)")
        return bytes.fromhex(env_hex)
    if require_persistent:
        raise ValueError(
            "Persistent file-backed kernel execution receipts require ARK_EXECUTION_KEY_HEX "
            "(64 hex characters); ephemeral keys are only permitted for :memory: sessions"
        )
    return _PROCESS_EXEC_SECRET


def compute_kernel_execution_id(
    tool_name: str,
    kernel_version: str,
    verification_scope: str,
    consistent: Optional[bool],
    executed_at: str,
    inputs_sha256: str,
    outputs_sha256: str,
) -> str:
    return f"kexec-{sha256_hex(canonical_json([tool_name, kernel_version, verification_scope, consistent, executed_at, inputs_sha256, outputs_sha256]))[:24]}"


def _compute_kernel_exec_hmac(
    store_scope: str,
    execution_id: str,
    tool_name: str,
    kernel_version: str,
    verification_scope: str,
    consistent: Optional[bool],
    executed_at: str,
    inputs_sha256: str,
    outputs_sha256: str,
) -> str:
    msg = canonical_json(
        [store_scope, execution_id, tool_name, kernel_version, verification_scope, consistent, executed_at, inputs_sha256, outputs_sha256]
    ).encode("utf-8")
    secret = _get_kernel_exec_secret(require_persistent=not store_scope.startswith("memory:"))
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _compute_binding_hmac(
    store_scope: str,
    artifact_id: str,
    artifact_kind: str,
    payload_sha256: str,
    execution_id: str,
    verification_scope: str,
    provenance_tier: str,
    ingest_bound_claim_id: Optional[str],
) -> str:
    msg = canonical_json(
        [store_scope, artifact_id, artifact_kind, payload_sha256, execution_id, verification_scope, provenance_tier, ingest_bound_claim_id]
    ).encode("utf-8")
    secret = _get_kernel_exec_secret(require_persistent=not store_scope.startswith("memory:"))
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def _verify_execution_row_dict(row: Mapping[str, Any], *, store_scope: str) -> dict[str, Any]:
    eid = str(row["execution_id"])
    tname = str(row["tool_name"])
    kver = str(row["kernel_version"])
    vscope = str(row["verification_scope"])
    cons_raw = row["consistent"]
    cons: Optional[bool] = None if cons_raw is None else bool(cons_raw)
    exec_at = str(row["executed_at"])
    in_raw = str(row["inputs_json"])
    out_raw = str(row["outputs_json"])
    in_sha_stored = str(row["inputs_sha256"])
    out_sha_stored = str(row["outputs_sha256"])
    mac_stored = str(row["auth_hmac"])

    in_obj = json.loads(in_raw)
    out_obj = json.loads(out_raw)
    if sha256_hex(canonical_json(in_obj)) != in_sha_stored:
        raise ValueError(f"Tampered inputs_json digest on kernel execution {eid!r}")
    if sha256_hex(canonical_json(out_obj)) != out_sha_stored:
        raise ValueError(f"Tampered outputs_json digest on kernel execution {eid!r}")
    expected_id = compute_kernel_execution_id(tname, kver, vscope, cons, exec_at, in_sha_stored, out_sha_stored)
    if eid != expected_id:
        raise ValueError(f"Tampered execution_id tuple on kernel execution {eid!r}")
    expected_mac = _compute_kernel_exec_hmac(
        store_scope, eid, tname, kver, vscope, cons, exec_at, in_sha_stored, out_sha_stored
    )
    if not hmac.compare_digest(mac_stored, expected_mac):
        raise ValueError(f"Unauthenticated kernel execution {eid!r}: HMAC verification failed")
    return {
        "execution_id": eid,
        "tool_name": tname,
        "kernel_version": kver,
        "verification_scope": vscope,
        "consistent": cons,
        "executed_at": exec_at,
        "inputs": in_obj,
        "inputs_sha256": in_sha_stored,
        "outputs": out_obj,
        "outputs_sha256": out_sha_stored,
    }


_QUANT_EXECUTION_TOOLS = frozenset(
    {"academic_recompute_statistics", "academic_check_percentage", "academic_table_forensics"}
)
_BIB_EXECUTION_TOOLS = frozenset({"academic_verify_source", "academic_retraction_watch"})


def canonical_payload_from_execution(eff_kind: str, exec_rec: Mapping[str, Any]) -> dict[str, Any]:
    tname = str(exec_rec["tool_name"])
    k_cons = exec_rec.get("consistent")
    inputs = dict(exec_rec.get("inputs") or {})
    outputs = dict(exec_rec.get("outputs") or {})
    exec_at = str(exec_rec.get("executed_at") or "2026-01-01T00:00:00Z")

    if eff_kind == "quantitative_audit":
        assertion: dict[str, Any] = {
            "statistic": tname,
            "consistent": k_cons,
            "inputs": inputs,
            "recomputed": {
                k: v
                for k, v in outputs.items()
                if k not in ("execution_id", "verification_scope")
            },
            "formula": f"kernel_execution:{tname}",
            "reported": {
                k: inputs[k]
                for k in ("p_value", "p_value_literal", "percent", "ci_estimate", "check_sd", "reported_n")
                if k in inputs
            },
            "library": f"academic-research-kernel/{exec_rec['kernel_version']}",
            "note": f"Derived from kernel execution {exec_rec['execution_id']} ({exec_rec['verification_scope']})",
        }
        if isinstance(k_cons, bool):
            assertion["discrepancy_detected"] = not k_cons
        return {"assertions": [assertion]}

    k_stance = "supports" if k_cons is True else ("contradicts" if k_cons is False else "qualifies")
    status_map = {"supports": "supported", "contradicts": "contradicted", "qualifies": "unverifiable"}
    norm_info = outputs.get("normalized") if isinstance(outputs.get("normalized"), Mapping) else {}
    id_type = str(norm_info.get("type") or "doi")
    id_val = outputs.get("target_doi") or norm_info.get("value") or inputs.get("identifier")
    identifiers_map: dict[str, Any] = {"doi": None, "arxiv_id": None, "openalex_id": None, "pmid": None}
    if id_type in identifiers_map and isinstance(id_val, str):
        identifiers_map[id_type] = id_val

    sources_list: list[dict[str, Any]] = []
    raw_sources = outputs.get("sources")
    if isinstance(raw_sources, Mapping) and raw_sources:
        for s_name, s_obj in raw_sources.items():
            if isinstance(s_obj, Mapping):
                st_s = str(s_obj.get("status") or "failed")
                if st_s not in ("ok", "failed", "skipped"):
                    st_s = "failed"
                src_entry: dict[str, Any] = {
                    "source": str(s_name),
                    "queried_at": str(s_obj.get("queried_at") or exec_at),
                    "status": st_s,
                    "raw_identifier": str(id_val) if isinstance(id_val, str) else None,
                }
                if s_obj.get("mode"):
                    src_entry["coverage"] = str(s_obj["mode"])
                sources_list.append(src_entry)
    if not sources_list:
        sources_list.append(
            {
                "source": tname,
                "queried_at": exec_at,
                "status": "ok" if k_cons is not None else "skipped",
                "raw_identifier": str(id_val) if isinstance(id_val, str) else None,
            }
        )

    return {
        "schema_version": "1.0",
        "query": str(inputs.get("identifier") or canonical_json(inputs.get("dois") or tname)),
        "identifiers": identifiers_map,
        "sources": sources_list,
        "claims": [
            {
                "claim": f"{exec_rec['verification_scope']}:{id_val or tname}",
                "evidence_type": "metadata",
                "source": str(exec_rec["verification_scope"]),
                "support_status": status_map[k_stance],
            }
        ],
        "generated_at": exec_at,
    }


OMIT_PAYLOAD = object()


def resolve_executed_artifact_payload(
    kind: Optional[str],
    exec_rec: Mapping[str, Any],
    caller_payload: Any = OMIT_PAYLOAD,
) -> tuple[str, dict[str, Any]]:
    tname = str(exec_rec["tool_name"])
    eff_kind = str(kind or ("quantitative_audit" if tname in _QUANT_EXECUTION_TOOLS else "evidence_receipt"))
    if eff_kind == "quantitative_audit" and tname not in _QUANT_EXECUTION_TOOLS:
        raise ValueError(f"Kernel execution {exec_rec['execution_id']!r} from tool {tname!r} cannot back quantitative_audit")
    if eff_kind == "evidence_receipt" and tname not in _BIB_EXECUTION_TOOLS:
        raise ValueError(f"Kernel execution {exec_rec['execution_id']!r} from tool {tname!r} cannot back evidence_receipt")
    if eff_kind not in ("quantitative_audit", "evidence_receipt"):
        raise ValueError(f"Kernel execution binding unsupported for artifact kind {eff_kind!r}")

    canonical_pay = canonical_payload_from_execution(eff_kind, exec_rec)
    if caller_payload is not OMIT_PAYLOAD:
        if not isinstance(caller_payload, Mapping):
            raise ValueError("payload must be a JSON object")
        if canonical_json(caller_payload) != canonical_json(canonical_pay):
            raise ValueError(
                f"Execution receipt tamper/mismatch: supplied payload does not match canonical kernel execution payload ({exec_rec['execution_id']})"
            )
    return eff_kind, canonical_pay


def canonical_literature_watch_key(raw: Any) -> str:
    """Canonical deduplication identity shared by live literature-watch and legacy v2.4.x JSON import."""
    if isinstance(raw, Mapping):
        doi = normalize_doi(str(raw.get("doi") or ""))
        if doi:
            return doi
        oid = str(raw.get("id") or "").strip().lower()
        if oid:
            return oid
        return re.sub(r"\s+", " ", str(raw.get("title") or "").strip().lower())
    s = str(raw or "").strip()
    if not s:
        return ""
    low = s.lower()
    if low.startswith("doi:"):
        return normalize_doi(s[4:])
    if low.startswith("id:"):
        return s[3:].strip().lower()
    if low.startswith("title:"):
        return re.sub(r"\s+", " ", s[6:].strip().lower())
    nd = normalize_doi(s)
    if nd:
        return nd
    return re.sub(r"\s+", " ", low)


def _require_str_id(value: Any, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str, got {type(value).__name__}: {value!r}")
    if "\r" in value or "\n" in value or "\x00" in value:
        raise ValueError(f"{field_name} must not contain control/newline characters: {value!r}")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"{field_name} must be a non-empty string")
    return cleaned


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, collections.abc.Mapping):
        raise TypeError(f"{field_name} must be a JSON object/mapping, got {type(value).__name__}")
    return value


class ResearchStateDB:
    """Single-file ACID research ledger, claim-evidence graph, provenance DAG, and watcher store."""

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        *,
        readonly: bool = False,
        root: Optional[str | Path] = None,
    ) -> None:
        self.readonly = bool(readonly)
        self.root = Path(root) if root is not None else None
        raw_path = str(db_path)
        if raw_path == ":memory:":
            if self.readonly:
                raise ValueError("Cannot open transient ':memory:' database in read-only mode")
            self.db_path = ":memory:"
            self._resolved_path: Optional[Path] = None
        else:
            self._resolved_path = safe_path(raw_path, root=self.root)
            self.db_path = str(self._resolved_path)

        self._lock = threading.RLock()
        self._tls = threading.local()
        self._conns: list[sqlite3.Connection] = []
        self._closed = False
        self._mem_conn: Optional[sqlite3.Connection] = None

        if self.db_path == ":memory:":
            conn = sqlite3.connect(":memory:", timeout=10.0, isolation_level=None)
            configure_sqlite_connection(conn, readonly=False)
            conn.executescript(SCHEMA_SQL)
            self._mem_conn = conn
        elif self.readonly:
            # Verify database exists and carries ARK3 identity immediately without mutating anything
            conn = self._get_conn()
            assert conn is not None
        else:
            assert self._resolved_path is not None
            self._resolved_path.parent.mkdir(parents=True, exist_ok=True)
            self._resolved_path = safe_path(self._resolved_path, root=self.root)
            self.db_path = str(self._resolved_path)

            def _cold_init() -> None:
                with _SQLITE_INIT_LOCK:
                    conn = self._get_conn()
                    verify_or_claim_sqlite_identity(conn, readonly=False)
                    cur_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                    if cur_mode != "wal":
                        conn.execute("PRAGMA journal_mode = WAL")
                    conn.execute("PRAGMA synchronous = NORMAL")
                    prior_user_ver = int(conn.execute("PRAGMA user_version").fetchone()[0])
                    conn.execute("BEGIN IMMEDIATE")
                    try:
                        stmt_buf = ""
                        for raw_line in SCHEMA_SQL.splitlines(keepends=True):
                            if not stmt_buf.strip() and (not raw_line.strip() or raw_line.lstrip().startswith("--")):
                                continue
                            stmt_buf += raw_line
                            if sqlite3.complete_statement(stmt_buf):
                                conn.execute(stmt_buf)
                                stmt_buf = ""
                        if stmt_buf.strip():
                            conn.execute(stmt_buf)
                        cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(doi_watch_state)").fetchall()}
                        if "confirmed_seq" not in cols:
                            conn.execute("ALTER TABLE doi_watch_state ADD COLUMN confirmed_seq INTEGER NOT NULL DEFAULT 0")
                            conn.execute(
                                "UPDATE doi_watch_state SET confirmed_seq = applied_seq WHERE confirmed_retracted IS NOT NULL AND confirmed_seq = 0"
                            )
                        ce_sql_row = conn.execute(
                            "SELECT sql FROM sqlite_master WHERE type='table' AND name='claim_edges'"
                        ).fetchone()
                        ce_trg_row = conn.execute(
                            "SELECT sql FROM sqlite_master WHERE type='trigger' AND name='trg_claim_edges_no_cycle'"
                        ).fetchone()
                        ce_sql = str(ce_sql_row[0] or "") if ce_sql_row else ""
                        ce_trg_sql = str(ce_trg_row[0] or "") if ce_trg_row else ""
                        if (0 < prior_user_ver < ARK_SQLITE_USER_VERSION) or ("corroborates" not in ce_sql) or ("WHEN NEW.relation" not in ce_trg_sql):
                            conn.execute("DROP TRIGGER IF EXISTS trg_claim_edges_no_cycle")
                            conn.execute("DROP TRIGGER IF EXISTS trg_claim_edges_immutable_upd")
                            conn.execute("DROP TRIGGER IF EXISTS trg_claim_edges_immutable_del")
                            conn.execute(
                                """
                                CREATE TABLE claim_edges_v4 (
                                    src_claim_id TEXT NOT NULL,
                                    dst_claim_id TEXT NOT NULL,
                                    relation TEXT NOT NULL CHECK (relation IN ('depends_on', 'refines', 'contradicts', 'corroborates', 'cites')),
                                    CHECK (src_claim_id != dst_claim_id),
                                    PRIMARY KEY (src_claim_id, dst_claim_id, relation),
                                    FOREIGN KEY (src_claim_id) REFERENCES claims(claim_id),
                                    FOREIGN KEY (dst_claim_id) REFERENCES claims(claim_id)
                                ) STRICT
                                """
                            )
                            conn.execute(
                                "INSERT INTO claim_edges_v4 (src_claim_id, dst_claim_id, relation) SELECT src_claim_id, dst_claim_id, relation FROM claim_edges"
                            )
                            conn.execute("DROP TABLE claim_edges")
                            conn.execute("ALTER TABLE claim_edges_v4 RENAME TO claim_edges")
                            conn.execute(
                                """
                                CREATE TRIGGER trg_claim_edges_no_cycle
                                BEFORE INSERT ON claim_edges
                                WHEN NEW.relation IN ('depends_on', 'refines')
                                BEGIN
                                    SELECT CASE WHEN EXISTS (
                                        WITH RECURSIVE reach(node) AS (
                                            SELECT NEW.dst_claim_id
                                            UNION
                                            SELECT e.dst_claim_id FROM claim_edges e
                                            JOIN reach r ON e.src_claim_id = r.node
                                            WHERE e.relation IN ('depends_on', 'refines')
                                        )
                                        SELECT 1 FROM reach WHERE node = NEW.src_claim_id
                                    ) THEN RAISE(ABORT, 'Cycle detected in claim_edges') END;
                                END
                                """
                            )
                            conn.execute(
                                """
                                CREATE TRIGGER trg_claim_edges_immutable_upd
                                BEFORE UPDATE ON claim_edges
                                BEGIN
                                    SELECT RAISE(ABORT, 'claim_edges table is append-only');
                                END
                                """
                            )
                            conn.execute(
                                """
                                CREATE TRIGGER trg_claim_edges_immutable_del
                                BEFORE DELETE ON claim_edges
                                BEGIN
                                    SELECT RAISE(ABORT, 'claim_edges table is append-only');
                                END
                                """
                            )
                            # Backfill legacy v3 decision_events.verdict_override rows for decisions without explicit corrections
                            legacy_overrides = conn.execute(
                                """
                                SELECT decision_id, new_state, reason, verdict_override
                                FROM decision_events
                                WHERE verdict_override IS NOT NULL
                                  AND decision_id NOT IN (SELECT DISTINCT decision_id FROM decision_corrections)
                                ORDER BY seq ASC
                                """
                            ).fetchall()
                            for ov_row in legacy_overrides:
                                conn.execute(
                                    """
                                    INSERT INTO decision_corrections (decision_id, verdict, rationale, artifact_id)
                                    VALUES (?, ?, ?, NULL)
                                    """,
                                    (
                                        str(ov_row["decision_id"]),
                                        str(ov_row["verdict_override"]),
                                        f"Lifecycle transition ({ov_row['new_state']}:{ov_row['reason']}) verdict override",
                                    ),
                                )
                            conn.execute(f"PRAGMA user_version = {ARK_SQLITE_USER_VERSION}")
                        conn.execute("COMMIT")
                    except BaseException:
                        if conn.in_transaction:
                            conn.execute("ROLLBACK")
                        raise

            run_with_sqlite_retry(_cold_init)

    def __enter__(self) -> "ResearchStateDB":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _get_conn(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("ResearchStateDB is closed")
        if self._mem_conn is not None:
            configure_sqlite_connection(self._mem_conn, readonly=False)
            return self._mem_conn
        conn = getattr(self._tls, "conn", None)
        if conn is not None:
            configure_sqlite_connection(conn, readonly=self.readonly)
            return conn
        assert self._resolved_path is not None
        checked = safe_path(self._resolved_path, root=self.root)
        if self.readonly:
            if not checked.is_file():
                raise FileNotFoundError(f"Research state database not found: {checked}")
            conn = sqlite3.connect(checked.as_uri() + "?mode=ro", uri=True, timeout=10.0, isolation_level=None)
            try:
                configure_sqlite_connection(conn, readonly=True)
                verify_or_claim_sqlite_identity(conn, readonly=True)
            except BaseException:
                conn.close()
                raise
        else:
            conn = sqlite3.connect(str(checked), timeout=10.0, isolation_level=None)
            try:
                configure_sqlite_connection(conn, readonly=False)
                conn.execute("PRAGMA synchronous = NORMAL")
            except BaseException:
                conn.close()
                raise
        with self._lock:
            self._conns.append(conn)
        self._tls.conn = conn
        return conn

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._mem_conn is not None:
                self._mem_conn.close()
                self._mem_conn = None
            for c in self._conns:
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()
            if hasattr(self._tls, "conn"):
                delattr(self._tls, "conn")

    def _tx_depth(self) -> int:
        return int(getattr(self._tls, "tx_depth", 0))

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Explicit reentrant write unit-of-work; nested calls use SQLite SAVEPOINTs."""
        if self.readonly:
            raise PermissionError("Cannot start a write transaction on a read-only ResearchStateDB")
        conn = self._get_conn()
        depth = self._tx_depth()
        if depth == 0:
            run_with_sqlite_retry(lambda: conn.execute("BEGIN IMMEDIATE"))
            self._tls.tx_depth = 1
            try:
                yield conn
                conn.execute("COMMIT")
            except BaseException:
                if conn.in_transaction:
                    conn.execute("ROLLBACK")
                raise
            finally:
                self._tls.tx_depth = 0
        else:
            sp = f"uow_sp_{depth}"
            conn.execute(f"SAVEPOINT {sp}")
            self._tls.tx_depth = depth + 1
            try:
                yield conn
                conn.execute(f"RELEASE SAVEPOINT {sp}")
            except BaseException:
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                conn.execute(f"RELEASE SAVEPOINT {sp}")
                raise
            finally:
                self._tls.tx_depth = depth

    @contextmanager
    def _read_snapshot(self) -> Iterator[sqlite3.Connection]:
        """Consistent MVCC read transaction preventing torn reads across multi-table SELECTs."""
        conn = self._get_conn()
        if conn.in_transaction or self._tx_depth() > 0:
            yield conn
            return
        conn.execute("BEGIN DEFERRED")
        try:
            yield conn
        finally:
            if conn.in_transaction:
                conn.execute("COMMIT")

    @staticmethod
    def _assert_acyclic(conn: sqlite3.Connection, table: str, src_col: str, dst_col: str, start: str, target: str) -> None:
        if start == target:
            raise ValueError(f"Self-loop rejected in {table}: {start!r}")
        row = conn.execute(
            f"""
            WITH RECURSIVE reach(node) AS (
                SELECT ?
                UNION
                SELECT e.{dst_col} FROM {table} e JOIN reach r ON e.{src_col} = r.node
            )
            SELECT 1 FROM reach WHERE node = ? LIMIT 1
            """,
            (target, start),
        ).fetchone()
        if row is not None:
            raise ValueError(f"Cycle detected in {table}: adding {start!r} -> {target!r} creates a loop")

    @staticmethod
    def _validate_artifact_semantics(
        artifact_id: Any,
        kind: Any,
        payload: Any,
        expected_sha256: Optional[str] = None,
        *,
        authoritative_artifacts: Optional[Mapping[str, tuple[str, str, Any]]] = None,
        receipts: Any = None,
        content_payloads: Any = None,
    ) -> tuple[str, str, str, str]:
        aid = _require_str_id(artifact_id, "artifact_id")
        k = _require_str_id(kind, "kind")
        if k not in ALLOWED_ARTIFACT_KINDS:
            raise ValueError(f"Unknown artifact kind {k!r}; allowed={sorted(ALLOWED_ARTIFACT_KINDS)}")
        pmap = _require_mapping(payload, "payload")
        plain_payload = thaw(pmap)
        dec_cp = decode_content_payloads_map(content_payloads) if content_payloads is not None else None
        schema_file = KIND_SCHEMA_MAP.get(k)
        if schema_file is not None:
            errs = list(validate_schema(plain_payload, schema_file))
            if not errs and k == "claim_evidence_graph":
                from .venue_template_manager import validate_ceg_semantics

                errs.extend(
                    validate_ceg_semantics(
                        dict(plain_payload),
                        receipts=receipts,
                        content_payloads=content_payloads,
                        authoritative_artifacts=authoritative_artifacts,
                    )["semantic_errors"]
                )
            elif not errs and k == "decision_ledger":
                errs.extend(
                    validate_decision_ledger_semantics(
                        plain_payload,
                        receipts=receipts,
                        content_payloads=content_payloads,
                        authoritative_artifacts=authoritative_artifacts,
                    )
                )
            elif not errs and k == "lineage_receipt":
                errs.extend(validate_lineage_receipt_semantics(plain_payload, decoded_content=dec_cp))
            if errs:
                raise ValueError(f"Schema validation failed for {k} ({aid}): {'; '.join(errs[:5])}")
        elif k in ("computed_evidence", "table_cell", "statistic_artifact"):
            has_concrete_val = bool(plain_payload) and any(v is not None for v in plain_payload.values())
            if not has_concrete_val:
                raise ValueError(f"Artifact kind {k!r} ({aid}) requires at least one non-null concrete field value")
        cjson = canonical_json(plain_payload)
        digest = sha256_hex(cjson)
        if expected_sha256 is not None:
            exp = _require_str_id(expected_sha256, "payload_sha256").lower()
            if exp != digest:
                raise ValueError(f"Payload SHA-256 mismatch on {aid!r}: expected {exp}, computed {digest}")
        return aid, k, cjson, digest

    def _admit_artifact_in_tx(
        self,
        conn: sqlite3.Connection,
        artifact_id: Any,
        kind: Any,
        payload: Any,
        *,
        expected_sha256: Optional[str] = None,
        parents: Iterable[Any] = (),
        relation: Any = "derived_from",
        receipts: Any = None,
        content_payloads: Any = None,
    ) -> Mapping[str, Any]:
        auth_map: Optional[dict[str, tuple[str, str, Any]]] = None
        if str(kind).strip() in ("claim_evidence_graph", "decision_ledger"):
            auth_map = {
                str(r["artifact_id"]): (
                    str(r["kind"]),
                    str(r["payload_sha256"]),
                    json.loads(str(r["payload_json"])),
                )
                for r in conn.execute("SELECT artifact_id, kind, payload_sha256, payload_json FROM artifacts").fetchall()
            }
        aid, k, cjson, digest = self._validate_artifact_semantics(
            artifact_id,
            kind,
            payload,
            expected_sha256,
            authoritative_artifacts=auth_map,
            receipts=receipts,
            content_payloads=content_payloads,
        )
        rel = _require_str_id(relation, "relation")
        if rel not in ALLOWED_LINEAGE_RELATIONS:
            raise ValueError(f"Invalid lineage relation {rel!r}; allowed={sorted(ALLOWED_LINEAGE_RELATIONS)}")
        parent_ids = [_require_str_id(pid, "parent_id") for pid in parents]

        existing = conn.execute(
            "SELECT payload_sha256, kind FROM artifacts WHERE artifact_id = ?", (aid,)
        ).fetchone()
        replayed = existing is not None
        if existing is not None:
            if existing["payload_sha256"] != digest or existing["kind"] != k:
                raise ValueError(
                    f"Artifact collision for {aid!r}: stored kind={existing['kind']!r}/sha={existing['payload_sha256'][:12]} "
                    f"vs incoming kind={k!r}/sha={digest[:12]}"
                )
        else:
            conn.execute(
                "INSERT INTO artifacts (artifact_id, kind, payload_json, payload_sha256) VALUES (?, ?, ?, ?)",
                (aid, k, cjson, digest),
            )

        for pid in parent_ids:
            self._assert_acyclic(conn, "lineage_edges", "child_id", "parent_id", aid, pid)
            conn.execute(
                """
                INSERT INTO lineage_edges (child_id, parent_id, relation)
                VALUES (?, ?, ?)
                ON CONFLICT(child_id, parent_id, relation) DO NOTHING
                """,
                (aid, pid, rel),
            )
        return freeze({
            "artifact_id": aid,
            "kind": k,
            "status": "accepted",
            "replayed": replayed,
            "payload_sha256": digest,
        })

    def register_work(
        self,
        work_id: str,
        title: str,
        *,
        doi: Optional[str] = None,
        arxiv_id: Optional[str] = None,
        year: Optional[int] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        wid = _require_str_id(work_id, "work_id")
        clean_title = nfc_compact(_require_str_id(title, "title"))
        norm_doi = normalize_doi(doi) if doi else None
        norm_arxiv = str(arxiv_id).strip().lower() if arxiv_id else None
        if year is not None and (type(year) is not int):
            raise TypeError("year must be int or None")
        meta_json = canonical_json(metadata or {})

        with self.transaction() as conn:
            existing = conn.execute("SELECT title, doi, arxiv_id FROM works WHERE work_id = ?", (wid,)).fetchone()
            if existing is not None:
                if existing["title"] != clean_title or existing["doi"] != norm_doi or existing["arxiv_id"] != norm_arxiv:
                    raise ValueError(f"Conflicting work registration for {wid!r}")
            else:
                conn.execute(
                    "INSERT INTO works (work_id, doi, arxiv_id, title, year, metadata_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (wid, norm_doi, norm_arxiv, clean_title, year, meta_json),
                )
        return freeze({"work_id": wid, "title": clean_title, "doi": norm_doi, "arxiv_id": norm_arxiv})

    def extract_authoritative_artifacts(self) -> dict[str, tuple[str, str, Any]]:
        with self._read_snapshot() as conn:
            return {
                str(r["artifact_id"]): (
                    str(r["kind"]),
                    str(r["payload_sha256"]),
                    json.loads(str(r["payload_json"])),
                )
                for r in conn.execute("SELECT artifact_id, kind, payload_sha256, payload_json FROM artifacts").fetchall()
            }

    def register_artifact(
        self,
        artifact_id: str,
        kind: str,
        payload: Mapping[str, Any],
        *,
        receipts: Any = None,
        content_payloads: Any = None,
    ) -> Mapping[str, Any]:
        with self.transaction() as conn:
            return self._admit_artifact_in_tx(
                conn,
                artifact_id,
                kind,
                payload,
                receipts=receipts,
                content_payloads=content_payloads,
            )

    def batch_ingest(self, items: Iterable[Mapping[str, Any]], atomic: bool = True) -> tuple[Mapping[str, Any], ...]:
        if type(atomic) is not bool:
            raise TypeError(f"atomic must be bool, got {type(atomic).__name__}")
        batch = list(items)
        out: list[Mapping[str, Any]] = []
        with self.transaction() as conn:
            for idx, item in enumerate(batch):
                if not isinstance(item, collections.abc.Mapping):
                    if atomic:
                        raise TypeError(f"items[{idx}] must be an object/mapping")
                    out.append(freeze({"artifact_id": "", "status": "rejected", "error": "item must be an object/mapping"}))
                    continue
                sp = f"batch_sp_{idx}"
                conn.execute(f"SAVEPOINT {sp}")
                try:
                    rec = self._admit_artifact_in_tx(
                        conn,
                        item.get("artifact_id"),
                        item.get("kind"),
                        item.get("payload"),
                        expected_sha256=item.get("payload_sha256"),
                        parents=item.get("parents") or (),
                        relation=item.get("relation", "derived_from"),
                        receipts=item.get("receipts"),
                        content_payloads=item.get("content_payloads"),
                    )
                    conn.execute(f"RELEASE SAVEPOINT {sp}")
                    out.append(rec)
                except Exception as exc:
                    conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                    conn.execute(f"RELEASE SAVEPOINT {sp}")
                    if atomic:
                        raise
                    raw_id = item.get("artifact_id")
                    safe_id = raw_id if type(raw_id) is str else ""
                    out.append(freeze({"artifact_id": safe_id, "status": "rejected", "error": str(exc)}))
        return tuple(out)

    def trace_lineage(self, artifact_id: str, *, max_vm_steps: int = 500_000) -> tuple[str, ...]:
        aid = _require_str_id(artifact_id, "artifact_id")
        with self._read_snapshot() as conn:
            steps = 0

            def _budget() -> int:
                nonlocal steps
                steps += 1
                return 1 if steps > max_vm_steps else 0

            conn.set_progress_handler(_budget, 1000)
            try:
                rows = conn.execute(
                    """
                    WITH RECURSIVE anc(id) AS (
                        SELECT parent_id FROM lineage_edges WHERE child_id = ?
                        UNION
                        SELECT e.parent_id FROM lineage_edges e JOIN anc a ON e.child_id = a.id
                    )
                    SELECT id FROM anc ORDER BY id
                    """,
                    (aid,),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise RuntimeError(f"Lineage trace exceeded VM step budget for {aid!r}") from exc
                raise
            finally:
                conn.set_progress_handler(None, 0)
            return tuple(str(r["id"]) for r in rows)

    def trace_lineage_verified(self, artifact_id: str, *, max_vm_steps: int = 500_000) -> dict[str, Any]:
        """Trace ancestor DAG and verify stored payload SHA-256 integrity inside a single MVCC read snapshot."""
        aid = _require_str_id(artifact_id, "artifact_id")
        with self._read_snapshot() as conn:
            steps = 0

            def _budget() -> int:
                nonlocal steps
                steps += 1
                return 1 if steps > max_vm_steps else 0

            conn.set_progress_handler(_budget, 1000)
            try:
                anc_rows = conn.execute(
                    """
                    WITH RECURSIVE anc(id) AS (
                        SELECT parent_id FROM lineage_edges WHERE child_id = ?
                        UNION
                        SELECT e.parent_id FROM lineage_edges e JOIN anc a ON e.child_id = a.id
                    )
                    SELECT id FROM anc ORDER BY id
                    """,
                    (aid,),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise RuntimeError(f"Lineage trace exceeded VM step budget for {aid!r}") from exc
                raise
            finally:
                conn.set_progress_handler(None, 0)

            ancestors = tuple(str(r["id"]) for r in anc_rows)
            all_nodes = (aid, *ancestors)
            art_rows = {
                str(r["artifact_id"]): (str(r["payload_json"]), str(r["payload_sha256"]))
                for r in conn.execute(
                    f"SELECT artifact_id, payload_json, payload_sha256 FROM artifacts WHERE artifact_id IN ({','.join('?' for _ in all_nodes)})",
                    all_nodes,
                ).fetchall()
            }
            if aid not in art_rows:
                return {
                    "artifact_id": aid,
                    "ancestors": list(ancestors),
                    "root_ancestors": [],
                    "chain_length": 0,
                    "verification_status": "missing_input",
                }
            edge_rows = conn.execute(
                f"SELECT child_id, parent_id FROM lineage_edges WHERE child_id IN ({','.join('?' for _ in all_nodes)})",
                all_nodes,
            ).fetchall()

        all_nodes_set = set(all_nodes)
        parents_map: dict[str, list[str]] = {n: [] for n in all_nodes}
        unclosed_edge = False
        for er in edge_rows:
            c_id, p_id = str(er["child_id"]), str(er["parent_id"])
            if p_id not in all_nodes_set:
                unclosed_edge = True
            if c_id in parents_map:
                parents_map[c_id].append(p_id)

        missing_any = unclosed_edge or any(n not in art_rows for n in all_nodes)
        corrupted_any = False
        for n in all_nodes:
            if n in art_rows:
                p_json, p_sha = art_rows[n]
                if sha256_hex(p_json) != p_sha.lower():
                    corrupted_any = True
                    break

        if corrupted_any:
            v_status = "corrupted"
        elif missing_any:
            v_status = "missing_input"
        else:
            v_status = "intact"

        roots = sorted(n for n in ancestors if not parents_map.get(n))
        memo_depth: dict[str, int] = {}

        def _depth(node: str, visiting: set[str]) -> int:
            if node in memo_depth:
                return memo_depth[node]
            ps = parents_map.get(node) or []
            if not ps:
                memo_depth[node] = 0
                return 0
            best = 0
            for p in ps:
                if p not in visiting:
                    best = max(best, 1 + _depth(p, visiting | {p}))
            memo_depth[node] = best
            return best

        chain_len = _depth(aid, {aid})
        return {
            "artifact_id": aid,
            "ancestors": list(ancestors),
            "root_ancestors": roots,
            "chain_length": chain_len,
            "verification_status": v_status,
        }

    def add_claim(
        self,
        claim_id: str,
        claim_text: str,
        status: Optional[str] = None,
        evidence: Iterable[tuple[str, str, str]] = (),
        depends_on: Iterable[str] = (),
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        cid = _require_str_id(claim_id, "claim_id")
        if type(claim_text) is not str or not nfc_compact(claim_text):
            raise ValueError("claim_text must be a non-empty string")
        norm = nfc_compact(claim_text)
        digest = sha256_hex(norm)
        ev_list: list[tuple[str, str, str]] = []
        for idx, tup in enumerate(evidence):
            if not isinstance(tup, (list, tuple)) or len(tup) != 3:
                raise ValueError(f"evidence[{idx}] must be a 3-tuple (artifact_id, stance, locator)")
            ev_aid = _require_str_id(tup[0], f"evidence[{idx}].artifact_id")
            ev_stance = _require_str_id(tup[1], f"evidence[{idx}].stance")
            if ev_stance not in ALLOWED_EVIDENCE_STANCES:
                raise ValueError(f"Invalid evidence stance {ev_stance!r}")
            if type(tup[2]) is not str:
                raise TypeError(f"evidence[{idx}].locator must be str")
            ev_list.append((ev_aid, ev_stance, tup[2]))

        dep_list = [_require_str_id(d, "depends_on") for d in depends_on]
        meta_json = canonical_json(metadata or {})

        if status is None:
            has_contra = any(st == "contradicts" for _, st, _ in ev_list)
            has_supp = any(st == "supports" for _, st, _ in ev_list)
            if has_contra and has_supp:
                resolved_status = "contested"
            elif has_contra:
                resolved_status = "refuted"
            elif has_supp:
                resolved_status = "supported"
            else:
                resolved_status = "unresolved"
        else:
            resolved_status = _require_str_id(status, "status")
            if resolved_status not in ALLOWED_CLAIM_STATUSES:
                raise ValueError(f"Invalid claim status {resolved_status!r}")
            if resolved_status == "supported" and not any(st == "supports" for _, st, _ in ev_list):
                # Check if existing claim already has supporting evidence in DB before allowing supported
                pass

        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT claim_text, claim_digest, status FROM claims WHERE claim_id = ?", (cid,)
            ).fetchone()
            if existing is not None:
                if existing["claim_digest"] != digest:
                    raise ValueError(
                        f"Immutable claim collision for {cid!r}: cannot overwrite existing claim text {existing['claim_text']!r}"
                    )
                if status is not None and existing["status"] != resolved_status:
                    raise ValueError(
                        f"Conflicting status registration for {cid!r}: stored={existing['status']!r} vs incoming={resolved_status!r}"
                    )
            else:
                if resolved_status == "supported" and not any(st == "supports" for _, st, _ in ev_list):
                    resolved_status = "unresolved"
                conn.execute(
                    "INSERT INTO claims (claim_id, claim_text, claim_digest, status, metadata_json) VALUES (?, ?, ?, ?, ?)",
                    (cid, norm, digest, resolved_status, meta_json),
                )

            for ev_aid, ev_stance, ev_loc in ev_list:
                prev_ev = conn.execute(
                    "SELECT stance FROM claim_evidence WHERE claim_id = ? AND artifact_id = ? AND locator = ?",
                    (cid, ev_aid, ev_loc),
                ).fetchone()
                if prev_ev is not None:
                    if prev_ev["stance"] != ev_stance:
                        raise ValueError(
                            f"Conflicting evidence stance on ({cid!r}, {ev_aid!r}, {ev_loc!r}): "
                            f"stored={prev_ev['stance']!r} vs incoming={ev_stance!r}"
                        )
                else:
                    conn.execute(
                        "INSERT INTO claim_evidence (claim_id, artifact_id, stance, locator) VALUES (?, ?, ?, ?)",
                        (cid, ev_aid, ev_stance, ev_loc),
                    )

            # Reconcile derived status if contradicting/supporting evidence was newly attached without conflicting explicit override
            stances_rows = conn.execute("SELECT stance FROM claim_evidence WHERE claim_id = ?", (cid,)).fetchall()
            stances = {str(r["stance"]) for r in stances_rows}
            cur_row = conn.execute("SELECT status FROM claims WHERE claim_id = ?", (cid,)).fetchone()
            final_status = str(cur_row["status"])
            if "contradicts" in stances:
                new_st = "contested" if "supports" in stances else "refuted"
                if final_status != new_st:
                    conn.execute("UPDATE claims SET status = ? WHERE claim_id = ?", (new_st, cid))
                    final_status = new_st
            elif "supports" in stances and final_status == "unresolved" and status is None:
                conn.execute("UPDATE claims SET status = 'supported' WHERE claim_id = ?", (cid,))
                final_status = "supported"

            for dst in dep_list:
                if cid == dst:
                    raise ValueError(f"Cycle detected in claim_edges: adding {cid!r} -> {dst!r} creates a loop")
                cyc_row = conn.execute(
                    """
                    WITH RECURSIVE reach(node) AS (
                        SELECT ?
                        UNION
                        SELECT e.dst_claim_id FROM claim_edges e
                        JOIN reach r ON e.src_claim_id = r.node
                        WHERE e.relation IN ('depends_on', 'refines')
                    )
                    SELECT 1 FROM reach WHERE node = ? LIMIT 1
                    """,
                    (dst, cid),
                ).fetchone()
                if cyc_row is not None:
                    raise ValueError(f"Cycle detected in claim_edges: adding {cid!r} -> {dst!r} creates a loop")
                conn.execute(
                    """
                    INSERT INTO claim_edges (src_claim_id, dst_claim_id, relation)
                    VALUES (?, ?, 'depends_on')
                    ON CONFLICT(src_claim_id, dst_claim_id, relation) DO NOTHING
                    """,
                    (cid, dst),
                )
        return freeze({"claim_id": cid, "claim_digest": digest, "status": final_status})

    def attach_claim_evidence(self, claim_id: str, artifact_id: str, stance: str, locator: str = "") -> Mapping[str, Any]:
        """Attach verified evidence to an existing claim and reconcile support/contestation status."""
        cid = _require_str_id(claim_id, "claim_id")
        with self.transaction() as conn:
            row = conn.execute("SELECT claim_text FROM claims WHERE claim_id = ?", (cid,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown target claim_id {cid!r}")
            return self.add_claim(cid, str(row["claim_text"]), status=None, evidence=[(artifact_id, stance, locator)])

    def add_claim_relation(self, src_claim_id: str, dst_claim_id: str, relation: str = "depends_on") -> Mapping[str, Any]:
        """Link two existing claims via depends_on, refines, contradicts, corroborates, or cites."""
        src = _require_str_id(src_claim_id, "src_claim_id")
        dst = _require_str_id(dst_claim_id, "dst_claim_id")
        rel = _require_str_id(relation, "relation")
        if rel not in ("depends_on", "refines", "contradicts", "corroborates", "cites"):
            raise ValueError(f"Invalid claim relation {rel!r}")
        if src == dst:
            raise ValueError("Claim cannot link to itself")
        with self.transaction() as conn:
            for cid in (src, dst):
                if conn.execute("SELECT 1 FROM claims WHERE claim_id = ?", (cid,)).fetchone() is None:
                    raise ValueError(f"Unknown claim_id {cid!r}")
            if rel in ("depends_on", "refines"):
                row = conn.execute(
                    """
                    WITH RECURSIVE reach(node) AS (
                        SELECT ?
                        UNION
                        SELECT e.dst_claim_id FROM claim_edges e
                        JOIN reach r ON e.src_claim_id = r.node
                        WHERE e.relation IN ('depends_on', 'refines')
                    )
                    SELECT 1 FROM reach WHERE node = ? LIMIT 1
                    """,
                    (dst, src),
                ).fetchone()
                if row is not None:
                    raise ValueError(f"Cycle detected in claim_edges: adding {src!r} -> {dst!r} ({rel}) creates a loop")
            conn.execute(
                """
                INSERT INTO claim_edges (src_claim_id, dst_claim_id, relation)
                VALUES (?, ?, ?)
                ON CONFLICT(src_claim_id, dst_claim_id, relation) DO NOTHING
                """,
                (src, dst, rel),
            )
            if rel == "contradicts":
                conn.execute(
                    "UPDATE claims SET status = 'contested' WHERE claim_id IN (?, ?) AND status = 'supported'",
                    (src, dst),
                )
        return freeze({"source_claim_id": src, "target_claim_id": dst, "relation_type": rel})

    def record_decision(
        self,
        decision_id: str,
        title: str,
        entry_kind: str = "decision",
        action: str = "explore",
        verdict: str = "inconclusive",
        basis_decision_id: Optional[str] = None,
        artifact_id: Optional[str] = None,
        initial_state: str = "active",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        did = _require_str_id(decision_id, "decision_id")
        if type(title) is not str or not nfc_compact(title):
            raise ValueError("title must be a non-empty string")
        clean_title = nfc_compact(title)
        ek = _require_str_id(entry_kind, "entry_kind")
        act = _require_str_id(action, "action")
        verd = _require_str_id(verdict, "verdict")
        init_st = _require_str_id(initial_state, "initial_state")

        if init_st not in _VALID_TRANSITIONS[None]:
            raise ValueError(f"Invalid genesis initial_state {init_st!r}; allowed={sorted(_VALID_TRANSITIONS[None])}")

        if ek == "negative_result" or act == "negative_result":
            if ek == "decision" and act == "negative_result" and entry_kind != "negative_result":
                # Normalize only when caller omitted entry_kind? No: reject explicit mismatch, require basis either way!
                ek = "negative_result"
            act = "negative_result"
            ek = "negative_result"

        basis_id = _require_str_id(basis_decision_id, "basis_decision_id") if basis_decision_id is not None else None
        art_id = _require_str_id(artifact_id, "artifact_id") if artifact_id is not None else None
        meta_json = canonical_json(metadata or {})

        with self.transaction() as conn:
            if ek == "negative_result":
                if not basis_id:
                    raise ValueError("negative_result requires basis_decision_id referencing a prior non-negative decision")
                if basis_id == did:
                    raise ValueError("negative_result cannot reference itself as basis")
                basis = conn.execute(
                    "SELECT entry_kind FROM decisions WHERE decision_id = ?", (basis_id,)
                ).fetchone()
                if basis is None or basis["entry_kind"] == "negative_result":
                    raise ValueError("negative_result basis must be an existing non-negative decision")
            conn.execute(
                """
                INSERT INTO decisions
                (decision_id, entry_kind, action, title, verdict, basis_decision_id, artifact_id, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (did, ek, act, clean_title, verd, basis_id, art_id, meta_json),
            )
            conn.execute(
                "INSERT INTO decision_events (decision_id, new_state, reason) VALUES (?, ?, 'genesis')",
                (did, init_st),
            )
        return freeze({"decision_id": did, "entry_kind": ek, "action": act, "state": init_st, "verdict": verd})

    def transition_decision(
        self,
        decision_id: str,
        new_state: str,
        reason: str,
        superseded_by_id: Optional[str] = None,
        verdict_override: Optional[str] = None,
    ) -> Mapping[str, Any]:
        did = _require_str_id(decision_id, "decision_id")
        nst = _require_str_id(new_state, "new_state")
        rsn = _require_str_id(reason, "reason")
        sup_id = _require_str_id(superseded_by_id, "superseded_by_id") if superseded_by_id is not None else None
        v_over = _require_str_id(verdict_override, "verdict_override") if verdict_override is not None else None
        if v_over is not None and v_over not in ("positive", "negative", "inconclusive", "unverifiable"):
            raise ValueError(f"Invalid verdict_override {v_over!r}")

        if rsn == "genesis":
            raise ValueError("Reason 'genesis' is reserved exclusively for initial decision creation")
        if nst == "pruned" and rsn not in PRUNE_REASONS:
            raise ValueError(f"Invalid prune reason {rsn!r}; allowed={sorted(PRUNE_REASONS)}")
        if nst == "reopened" and rsn not in REOPEN_REASONS:
            raise ValueError(f"Invalid reopen reason {rsn!r}; allowed={sorted(REOPEN_REASONS)}")

        with self.transaction() as conn:
            last = conn.execute(
                "SELECT new_state FROM decision_events WHERE decision_id = ? ORDER BY seq DESC LIMIT 1",
                (did,),
            ).fetchone()
            if last is None:
                raise ValueError(f"Unknown decision_id {did!r}")
            cur_state = str(last["new_state"])
            if nst not in _VALID_TRANSITIONS.get(cur_state, frozenset()):
                raise ValueError(f"Illegal state transition {cur_state!r} -> {nst!r}")
            if rsn == "superseded" and sup_id is None:
                raise ValueError("Reason 'superseded' requires superseded_by_id")
            if sup_id is not None:
                if sup_id == did:
                    raise ValueError("Decision cannot supersede itself")
                row = conn.execute(
                    """
                    WITH RECURSIVE sup(node) AS (
                        SELECT ?
                        UNION
                        SELECT e.superseded_by_id FROM decision_events e
                        JOIN sup r ON e.decision_id = r.node
                        WHERE e.superseded_by_id IS NOT NULL
                    )
                    SELECT 1 FROM sup WHERE node = ? LIMIT 1
                    """,
                    (sup_id, did),
                ).fetchone()
                if row is not None:
                    raise ValueError("Cycle detected in abandonment/supersession chain")
            conn.execute(
                """
                INSERT INTO decision_events (decision_id, new_state, reason, superseded_by_id, verdict_override)
                VALUES (?, ?, ?, ?, ?)
                """,
                (did, nst, rsn, sup_id, v_over),
            )
            if v_over is not None:
                conn.execute(
                    "INSERT INTO decision_corrections (decision_id, verdict, rationale, artifact_id) VALUES (?, ?, ?, ?)",
                    (did, v_over, f"Lifecycle transition ({nst}:{rsn}) verdict override", None),
                )
        return freeze({"decision_id": did, "state": nst, "reason": rsn})

    def reserve_watch_seq(self, watcher: str, item_key: str) -> int:
        """Reserve a monotonic observation sequence BEFORE network I/O to enforce chronological CAS."""
        w = _require_str_id(watcher, "watcher")
        k = normalize_doi(item_key) if w == "retraction" else _require_str_id(item_key, "item_key")
        if not k:
            raise ValueError("Watch item_key must be non-empty")
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO doi_watch_state (watcher, item_key, reserved_seq)
                VALUES (?, ?, 1)
                ON CONFLICT(watcher, item_key) DO UPDATE SET reserved_seq = doi_watch_state.reserved_seq + 1
                """,
                (w, k),
            )
            row = conn.execute(
                "SELECT reserved_seq FROM doi_watch_state WHERE watcher = ? AND item_key = ?",
                (w, k),
            ).fetchone()
            return int(row["reserved_seq"])

    def commit_watch_observation(
        self,
        watcher: str,
        item_key: str,
        *,
        seq: int,
        status: str,
        signals: Iterable[str] = (),
        signals_complete: bool = True,
        truncated: bool = False,
        error: Optional[str] = None,
    ) -> Mapping[str, Any]:
        """CAS-merge a 3-state observation ('retracted' | 'not_retracted' | 'unknown') without erasing confirmed state."""
        w = _require_str_id(watcher, "watcher")
        k = normalize_doi(item_key) if w == "retraction" else _require_str_id(item_key, "item_key")
        if not k:
            raise ValueError("Watch item_key must be non-empty")
        if isinstance(seq, bool) or not isinstance(seq, int) or seq < 1:
            raise ValueError(f"Watch observation seq must be a positive integer, got {seq!r}")
        if status not in ("retracted", "not_retracted", "unknown"):
            raise ValueError(f"Invalid watch observation status: {status!r}")
        sig_list = sorted({str(s) for s in signals if str(s).strip()})
        sig_json = canonical_json(sig_list)
        trunc_int = 1 if truncated else 0
        commit_digest = sha256_hex(
            canonical_json(
                {
                    "status": status,
                    "signals": sig_list,
                    "signals_complete": bool(signals_complete),
                    "truncated": bool(truncated),
                }
            )
        )

        with self.transaction() as conn:
            prior_commit = conn.execute(
                "SELECT commit_digest, snapshot_json FROM doi_watch_commits WHERE watcher = ? AND item_key = ? AND seq = ?",
                (w, k, seq),
            ).fetchone()
            if prior_commit is not None:
                if str(prior_commit["commit_digest"]) != commit_digest:
                    raise ValueError(
                        f"Conflicting watch observation replay for ({w!r}, {k!r}, seq={seq})"
                    )
                idem = json.loads(str(prior_commit["snapshot_json"]))
                idem["changed"] = False
                return freeze(idem)

            prev = conn.execute(
                """
                SELECT current_status, confirmed_retracted, signals_json, reserved_seq, applied_seq,
                       confirmed_seq, observation_version, truncated, last_error, unacked_delta_json
                FROM doi_watch_state WHERE watcher = ? AND item_key = ?
                """,
                (w, k),
            ).fetchone()

            prev_applied = int(prev["applied_seq"]) if prev is not None else 0
            prev_conf_seq = int(prev["confirmed_seq"]) if prev is not None else 0
            prev_conf = prev["confirmed_retracted"] if prev is not None else None
            prev_sigs_list = json.loads(str(prev["signals_json"])) if prev is not None else []
            prev_sigs = canonical_json(prev_sigs_list)
            prev_ver = int(prev["observation_version"]) if prev is not None else 0
            prev_unacked = prev["unacked_delta_json"] if prev is not None else None
            prev_status = str(prev["current_status"]) if prev is not None else "unknown"

            is_stale = (status == "unknown" and seq < prev_applied) or (
                status != "unknown" and seq < prev_conf_seq
            )
            if prev is not None and is_stale:
                stale_obj = {
                    "doi": k,
                    "changed": False,
                    "stale_ignored": True,
                    "status": prev_status,
                    "is_retracted": bool(prev_conf) if prev_conf is not None else None,
                    "version": prev_ver,
                    "signals": prev_sigs_list,
                    "truncated": bool(trunc_int),
                }
                conn.execute(
                    "INSERT INTO doi_watch_commits (watcher, item_key, seq, commit_digest, snapshot_json) VALUES (?, ?, ?, ?, ?)",
                    (w, k, seq, commit_digest, canonical_json(stale_obj)),
                )
                return freeze(stale_obj)

            new_applied = max(prev_applied, seq)
            eff_trunc = int(prev["truncated"]) if (prev is not None and seq < prev_applied) else trunc_int
            eff_error = prev["last_error"] if (prev is not None and seq < prev_applied) else error
            if status == "unknown":
                # Offline or unavailable observation: NEVER overwrite confirmed_retracted or prior signals
                new_conf = prev_conf
                new_conf_seq = prev_conf_seq
                merged_sigs = sorted(set(prev_sigs_list) | set(sig_list)) if sig_list else prev_sigs_list
                new_sigs = canonical_json(merged_sigs)
                new_current_status = "unknown"
                changed = new_sigs != prev_sigs
                new_ver = prev_ver + 1 if changed else prev_ver
            else:
                obs_flag = 1 if status == "retracted" else 0
                # If a newer unknown observation already arrived (seq < prev_applied), keep current_status='unknown'
                # while recording the newly confirmed historical truth at confirmed_seq = seq and preserving newer diagnostics.
                new_current_status = prev_status if seq < prev_applied else status
                new_conf = obs_flag
                new_conf_seq = max(prev_conf_seq, seq)
                if seq < prev_applied or not signals_complete:
                    merged_sigs = sorted(set(prev_sigs_list) | set(sig_list))
                else:
                    merged_sigs = sig_list
                new_sigs = canonical_json(merged_sigs)
                changed = (prev_conf is None) or (int(prev_conf) != obs_flag) or (prev_sigs != new_sigs)
                new_ver = prev_ver + 1 if (changed or prev_ver == 0) else prev_ver

            delta_obj = {
                "doi": k,
                "changed": changed,
                "stale_ignored": False,
                "status": new_current_status,
                "is_retracted": bool(new_conf) if new_conf is not None else None,
                "version": new_ver,
                "signals": json.loads(new_sigs),
                "truncated": bool(eff_trunc),
                "error": eff_error,
            }
            new_unacked = canonical_json(delta_obj) if changed else prev_unacked
            new_reserved = max(seq, int(prev["reserved_seq"]) if prev is not None else seq)

            conn.execute(
                """
                INSERT INTO doi_watch_state (
                    watcher, item_key, current_status, confirmed_retracted, signals_json,
                    reserved_seq, applied_seq, confirmed_seq, observation_version, truncated, last_error, unacked_delta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(watcher, item_key) DO UPDATE SET
                    current_status = excluded.current_status,
                    confirmed_retracted = excluded.confirmed_retracted,
                    signals_json = excluded.signals_json,
                    reserved_seq = excluded.reserved_seq,
                    applied_seq = excluded.applied_seq,
                    confirmed_seq = excluded.confirmed_seq,
                    observation_version = excluded.observation_version,
                    truncated = excluded.truncated,
                    last_error = excluded.last_error,
                    unacked_delta_json = excluded.unacked_delta_json
                """,
                (
                    w, k, new_current_status, new_conf, new_sigs,
                    new_reserved, new_applied, new_conf_seq, new_ver, eff_trunc, eff_error, new_unacked,
                ),
            )
            conn.execute(
                "INSERT INTO doi_watch_commits (watcher, item_key, seq, commit_digest, snapshot_json) VALUES (?, ?, ?, ?, ?)",
                (w, k, seq, commit_digest, canonical_json(delta_obj)),
            )
            return freeze(delta_obj)

    def drain_unacked_watch_deltas(self, watcher: str, keys: Optional[Iterable[str]] = None) -> list[dict[str, Any]]:
        """Atomically fetch and acknowledge pending watch deltas so partial batch timeouts never drop alerts."""
        w = _require_str_id(watcher, "watcher")
        key_filter = [normalize_doi(k) if w == "retraction" else str(k).strip() for k in keys] if keys is not None else None
        with self.transaction() as conn:
            rows = conn.execute(
                "SELECT item_key, unacked_delta_json FROM doi_watch_state WHERE watcher = ? AND unacked_delta_json IS NOT NULL ORDER BY item_key",
                (w,),
            ).fetchall()
            deltas: list[dict[str, Any]] = []
            for r in rows:
                ik = str(r["item_key"])
                if key_filter is not None and ik not in key_filter:
                    continue
                deltas.append(json.loads(str(r["unacked_delta_json"])))
                conn.execute(
                    "UPDATE doi_watch_state SET unacked_delta_json = NULL WHERE watcher = ? AND item_key = ?",
                    (w, ik),
                )
            return deltas

    def update_doi_watch(self, watcher: str, doi: str, is_retracted: Optional[bool], signals: Iterable[str] = ()) -> Mapping[str, Any]:
        """Convenience single-step wrapper over reserve_watch_seq + commit_watch_observation."""
        seq = self.reserve_watch_seq(watcher, doi)
        status = "unknown" if is_retracted is None else ("retracted" if is_retracted else "not_retracted")
        res = self.commit_watch_observation(watcher, doi, seq=seq, status=status, signals=signals)
        if res["changed"]:
            self.drain_unacked_watch_deltas(watcher, [doi])
        return res

    def import_legacy_watch_json(self, watcher: str, legacy_payload: Any) -> dict[str, Any]:
        """One-time migration helper importing v2.4.x JSON watch state into SQLite STRICT tables."""
        w = _require_str_id(watcher, "watcher")
        imported = 0
        unchanged = 0
        with self.transaction() as conn:
            if w == "retraction":
                if not isinstance(legacy_payload, Mapping):
                    raise ValueError("Legacy retraction watch JSON must be a JSON object mapping DOI -> snapshot")
                items = (
                    legacy_payload.get("dois")
                    if isinstance(legacy_payload.get("dois"), Mapping)
                    else (legacy_payload.get("items") if isinstance(legacy_payload.get("items"), Mapping) else legacy_payload)
                )
                for raw_doi, entry in items.items():
                    if raw_doi in ("schema_version", "updated_at", "watcher"):
                        continue
                    if not isinstance(entry, Mapping):
                        raise ValueError(f"Legacy retraction entry for {raw_doi!r} must be a JSON object")
                    norm_doi = normalize_doi(str(raw_doi))
                    if not norm_doi:
                        raise ValueError(f"Invalid DOI key in legacy retraction watch JSON: {raw_doi!r}")
                    is_ret = entry.get("is_retracted")
                    if is_ret is not None and not isinstance(is_ret, bool):
                        raise ValueError(f"Legacy is_retracted for {raw_doi!r} must be boolean or null")
                    has_cur = "current_observation" in entry
                    cur_obs = entry.get("current_observation")
                    if has_cur and cur_obs is not None and not isinstance(cur_obs, bool):
                        raise ValueError(f"Legacy current_observation for {raw_doi!r} must be boolean or null")
                    if has_cur and cur_obs is not None and is_ret is not None and bool(cur_obs) != bool(is_ret):
                        raise ValueError(f"Contradictory legacy retraction snapshot for {raw_doi!r}")
                    ver_status = str(entry.get("verification_status") or "").strip().lower()
                    sigs = sorted({str(s).strip() for s in (entry.get("signals") or []) if str(s).strip()})
                    trunc = bool(entry.get("truncated", False))

                    is_retained_unknown = is_ret is not None and ((has_cur and cur_obs is None) or ver_status == "retained_prior")
                    if is_retained_unknown:
                        target_status = "unknown"
                        target_conf: Optional[int] = 1 if bool(is_ret) else 0
                    elif is_ret is None and (not has_cur or cur_obs is None):
                        target_status = "unknown"
                        target_conf = None
                    else:
                        eff_bool = bool(cur_obs) if (has_cur and cur_obs is not None) else bool(is_ret)
                        target_status = "retracted" if eff_bool else "not_retracted"
                        target_conf = 1 if eff_bool else 0

                    prev = conn.execute(
                        "SELECT current_status, confirmed_retracted, signals_json, truncated, unacked_delta_json "
                        "FROM doi_watch_state WHERE watcher = 'retraction' AND item_key = ?",
                        (norm_doi,),
                    ).fetchone()
                    if (
                        prev is not None
                        and str(prev["current_status"]) == target_status
                        and prev["confirmed_retracted"] == target_conf
                        and str(prev["signals_json"]) == canonical_json(sigs)
                        and int(prev["truncated"]) == int(trunc)
                        and prev["unacked_delta_json"] is None
                    ):
                        unchanged += 1
                        continue

                    if is_retained_unknown:
                        seq1 = self.reserve_watch_seq("retraction", norm_doi)
                        base_st = "retracted" if bool(is_ret) else "not_retracted"
                        self.commit_watch_observation("retraction", norm_doi, seq=seq1, status=base_st, signals=sigs, truncated=trunc)
                        seq2 = self.reserve_watch_seq("retraction", norm_doi)
                        self.commit_watch_observation("retraction", norm_doi, seq=seq2, status="unknown", signals=sigs, truncated=trunc)
                    else:
                        seq1 = self.reserve_watch_seq("retraction", norm_doi)
                        self.commit_watch_observation("retraction", norm_doi, seq=seq1, status=target_status, signals=sigs, truncated=trunc)
                    self.drain_unacked_watch_deltas("retraction", [norm_doi])
                    imported += 1
            else:
                if isinstance(legacy_payload, (list, tuple)):
                    seen_list: Any = legacy_payload
                elif isinstance(legacy_payload, Mapping):
                    if "seen_ids" not in legacy_payload and "seen" not in legacy_payload:
                        raise ValueError("Legacy literature watch JSON object must contain 'seen_ids' or 'seen'")
                    seen_list = legacy_payload["seen_ids"] if "seen_ids" in legacy_payload else legacy_payload["seen"]
                    if isinstance(seen_list, Mapping):
                        seen_list = list(seen_list.keys())
                else:
                    raise ValueError("Legacy literature watch JSON must be a top-level array or an object with 'seen_ids'/'seen'")
                if not isinstance(seen_list, (list, tuple)):
                    raise ValueError("Legacy literature seen list must be an array")
                for raw_id in seen_list:
                    if not isinstance(raw_id, str):
                        raise ValueError("Legacy literature seen entries must be strings")
                    sid = canonical_literature_watch_key(raw_id)
                    if not sid:
                        continue
                    prev_lit = conn.execute(
                        "SELECT unacked_delta_json FROM doi_watch_state WHERE watcher = ? AND item_key = ?",
                        (w, sid),
                    ).fetchone()
                    if prev_lit is not None and prev_lit["unacked_delta_json"] is None:
                        unchanged += 1
                        continue
                    seq = self.reserve_watch_seq(w, sid)
                    self.commit_watch_observation(w, sid, seq=seq, status="not_retracted", signals=["legacy_import"])
                    self.drain_unacked_watch_deltas(w, [sid])
                    imported += 1
        return {"watcher": w, "imported_count": imported, "unchanged_count": unchanged}

    def export_ceg_dict(self) -> dict[str, Any]:
        """Export complete authoritative Claim-Evidence Graph in canonical claim-evidence-graph-1.0 format."""
        with self._read_snapshot() as conn:
            c_rows = conn.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
            ev_rows = conn.execute("SELECT * FROM claim_evidence ORDER BY claim_id, artifact_id, locator").fetchall()
            ce_rows = conn.execute("SELECT * FROM claim_edges ORDER BY src_claim_id, dst_claim_id, relation").fetchall()
            art_kind_rows = conn.execute("SELECT artifact_id, kind, payload_json, payload_sha256 FROM artifacts").fetchall()
            has_exec_tbl = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kernel_executions'"
                ).fetchone()
                is not None
            )
            has_exec_bindings = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifact_execution_bindings'"
                ).fetchone()
                is not None
            )
            ke_rows = (
                conn.execute(
                    """
                    SELECT * FROM kernel_executions
                    WHERE execution_id IN (SELECT execution_id FROM artifact_execution_bindings)
                    """
                ).fetchall()
                if (has_exec_tbl and has_exec_bindings)
                else []
            )
            bind_rows = (
                conn.execute("SELECT * FROM artifact_execution_bindings").fetchall()
                if has_exec_bindings
                else []
            )

        store_scope = self._store_scope_id()
        art_kinds = {str(r["artifact_id"]): str(r["kind"]) for r in art_kind_rows}
        bound_art_ids = {str(r["artifact_id"]) for r in bind_rows}
        art_live_shas: dict[str, Optional[str]] = {}
        for r in art_kind_rows:
            aid_r = str(r["artifact_id"])
            if aid_r not in bound_art_ids:
                continue
            stored_sha = str(r["payload_sha256"])
            try:
                recomp_sha = sha256_hex(canonical_json(json.loads(str(r["payload_json"]))))
                art_live_shas[aid_r] = recomp_sha if recomp_sha == stored_sha else None
            except Exception:
                art_live_shas[aid_r] = None

        verified_ke: dict[str, dict[str, Any]] = {}
        for kr in ke_rows:
            try:
                vk = _verify_execution_row_dict(kr, store_scope=store_scope)
                verified_ke[vk["execution_id"]] = vk
            except Exception:
                continue

        exec_bindings: dict[str, dict[str, Any]] = {}
        tampered_binding_artifacts: set[str] = set()
        for r in bind_rows:
            aid_b = str(r["artifact_id"])
            eid_b = str(r["execution_id"])
            vsc_b = str(r["verification_scope"])
            pt_b = str(r["provenance_tier"])
            ibc_b = str(r["ingest_bound_claim_id"]) if r["ingest_bound_claim_id"] is not None else None
            bmac = str(r["binding_hmac"])
            live_sha = art_live_shas.get(aid_b)
            ak_b = art_kinds.get(aid_b, "")
            if live_sha is not None and eid_b in verified_ke:
                try:
                    expected_bmac = _compute_binding_hmac(
                        store_scope, aid_b, ak_b, live_sha, eid_b, vsc_b, pt_b, ibc_b
                    )
                except ValueError:
                    expected_bmac = ""
                if (
                    pt_b == "kernel_executed"
                    and expected_bmac
                    and hmac.compare_digest(bmac, expected_bmac)
                    and verified_ke[eid_b]["verification_scope"] == vsc_b
                ):
                    try:
                        _, expected_pay = resolve_executed_artifact_payload(ak_b, verified_ke[eid_b])
                        expected_pay_sha = sha256_hex(canonical_json(expected_pay))
                    except Exception:
                        expected_pay_sha = None
                    if expected_pay_sha is not None and live_sha == expected_pay_sha:
                        cons_v = verified_ke[eid_b]["consistent"]
                        ib_stance = "supports" if cons_v is True else ("contradicts" if cons_v is False else "qualifies")
                        exec_bindings[aid_b] = {
                            "execution_id": eid_b,
                            "verification_scope": vsc_b,
                            "artifact_provenance_tier": pt_b,
                            "ingest_bound_claim_id": ibc_b,
                            "ingest_bound_stance": ib_stance,
                        }
                        continue
            tampered_binding_artifacts.add(aid_b)

        claims = []
        for r in c_rows:
            raw_meta = json.loads(str(r["metadata_json"]))
            meta_out = dict(raw_meta) if isinstance(raw_meta, dict) else {"value": raw_meta}
            meta_out["status"] = str(r["status"])
            txt = str(r["claim_text"])
            claims.append({
                "id": str(r["claim_id"]),
                "text": txt,
                "normalized_text": nfc_compact(txt),
                "claim_type": str(meta_out.get("claim_type") or "generic_claim")
                if meta_out.get("claim_type") in (
                    "empirical_finding", "theoretical_claim", "benchmark_result", "methodological_assertion", "generic_claim"
                )
                else "generic_claim",
                "claim_digest": str(r["claim_digest"]),
                "metadata": meta_out,
            })

        evidence_by_id: dict[str, dict[str, Any]] = {}
        support_edges = []
        stance_to_support = {"supports": "supported", "contradicts": "contradicted", "qualifies": "unverifiable"}
        for r in ev_rows:
            art_s = str(r["artifact_id"])
            loc_s = str(r["locator"])
            cid_edge = str(r["claim_id"])
            eb = exec_bindings.get(art_s)
            if eb is not None:
                bound_at_ingest = bool(
                    eb["ingest_bound_claim_id"] is not None
                    and cid_edge == eb["ingest_bound_claim_id"]
                    and loc_s == ""
                    and str(r["stance"]) == eb["ingest_bound_stance"]
                )
                art_tier = eb["artifact_provenance_tier"]
                v_scope = eb["verification_scope"]
                edge_meta: dict[str, Any] = {
                    "artifact_provenance_tier": art_tier,
                    "edge_provenance_tier": "caller_asserted_binding",
                    "bound_at_ingest": bound_at_ingest,
                    "verification_scope": v_scope,
                    "execution_id": eb["execution_id"],
                }
            else:
                ak = art_kinds.get(art_s, "")
                v_scope = (
                    "statistical_numerical_consistency_unverified"
                    if ak == "quantitative_audit"
                    else (
                        "bibliographic_or_evidence_receipt_unverified"
                        if ak == "evidence_receipt"
                        else "external_assertion_unscoped"
                    )
                )
                art_tier = "external_unverified"
                edge_meta = {
                    "artifact_provenance_tier": art_tier,
                    "edge_provenance_tier": "caller_asserted_binding",
                    "bound_at_ingest": False,
                    "verification_scope": v_scope,
                }
                if art_s in tampered_binding_artifacts:
                    edge_meta["unauthenticated_execution_binding"] = True
            ev_prefix = "ev-quant-" if art_s.startswith("results-") else "ev-"
            ev_id = ev_prefix + sha256_hex(canonical_json([art_s, loc_s]))[:20]
            if ev_id not in evidence_by_id:
                anc_meta: dict[str, Any] = {
                    "artifact_id": art_s,
                    "artifact_provenance_tier": art_tier,
                    "verification_scope": v_scope,
                }
                if eb is not None:
                    anc_meta["execution_id"] = eb["execution_id"]
                evidence_by_id[ev_id] = {
                    "id": ev_id,
                    "anchor_type": "evidence_receipt",
                    "locator": loc_s,
                    "metadata": anc_meta,
                }
            support_edges.append({
                "evidence_id": ev_id,
                "claim_id": cid_edge,
                "support_status": stance_to_support[str(r["stance"])],
                "metadata": dict(edge_meta),
            })
        evidence_anchors = list(evidence_by_id.values())

        rel_map = {
            "depends_on": "depends_on",
            "supports": "corroborates",
            "corroborates": "corroborates",
            "cites": "cites",
            "refines": "refines",
            "contradicts": "contradicts",
        }
        claim_relations = [
            {
                "source_claim_id": str(r["src_claim_id"]),
                "target_claim_id": str(r["dst_claim_id"]),
                "relation_type": rel_map.get(str(r["relation"]), "depends_on"),
            }
            for r in ce_rows
        ]
        contra_claims = {
            cr["source_claim_id"] for cr in claim_relations if cr["relation_type"] == "contradicts"
        } | {
            cr["target_claim_id"] for cr in claim_relations if cr["relation_type"] == "contradicts"
        }
        uncertainties: list[dict[str, Any]] = []
        for r in c_rows:
            cid_s = str(r["claim_id"])
            st_s = str(r["status"])
            if st_s == "contested" or cid_s in contra_claims:
                uhash = sha256_hex(canonical_json(["unresolved_contradiction", cid_s]))[:16]
                uncertainties.append({
                    "item_id": f"unc-{uhash}",
                    "subject_id": cid_s,
                    "kind": "unresolved_contradiction",
                    "reason": "Claim has conflicting evidence or unresolved contradiction edges",
                    "needs_human": True,
                })
            elif st_s == "unresolved":
                uhash = sha256_hex(canonical_json(["unverifiable_claim", cid_s]))[:16]
                uncertainties.append({
                    "item_id": f"unc-{uhash}",
                    "subject_id": cid_s,
                    "kind": "unverifiable_claim",
                    "reason": "Claim has no supporting or contradicting empirical evidence attached",
                    "needs_human": True,
                })

        body_for_digest = {
            "protocol": "claim-evidence-graph-1.0",
            "claims": claims,
            "evidence_anchors": evidence_anchors,
            "support_edges": support_edges,
            "claim_relations": claim_relations,
            "uncertainties": uncertainties,
        }
        g_digest = sha256_hex(canonical_json(body_for_digest))
        return {
            "protocol": "claim-evidence-graph-1.0",
            "graph_id": f"ceg-{g_digest[:16]}",
            "graph_digest": g_digest,
            "claims": claims,
            "evidence_anchors": evidence_anchors,
            "support_edges": support_edges,
            "claim_relations": claim_relations,
            "uncertainties": uncertainties,
        }

    def correct_decision_outcome(
        self,
        decision_id: str,
        verdict: str,
        rationale: str,
        artifact_id: Optional[str] = None,
    ) -> Mapping[str, Any]:
        """Append an independent outcome correction without mutating lifecycle state."""
        did = _require_str_id(decision_id, "decision_id")
        verd = _require_str_id(verdict, "verdict")
        if verd not in ("positive", "negative", "inconclusive", "unverifiable"):
            raise ValueError(f"Invalid verdict {verd!r}")
        if type(rationale) is not str or not nfc_compact(rationale):
            raise ValueError("rationale must be a non-empty string")
        clean_rat = nfc_compact(rationale)
        art_id = _require_str_id(artifact_id, "artifact_id") if artifact_id is not None else None
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM decisions WHERE decision_id = ?", (did,)).fetchone() is None:
                raise ValueError(f"Unknown decision_id {did!r}")
            cur = conn.execute(
                "INSERT INTO decision_corrections (decision_id, verdict, rationale, artifact_id) VALUES (?, ?, ?, ?)",
                (did, verd, clean_rat, art_id),
            )
            seq = int(cur.lastrowid or 1)
        return freeze({"decision_id": did, "verdict": verd, "rationale": clean_rat, "sequence": seq})

    def export_decision_ledger_dict(self) -> dict[str, Any]:
        """Export schema-compliant decision-ledger-1.0 receipt from SQLite STRICT tables."""
        with self._read_snapshot() as conn:
            d_rows = conn.execute("SELECT * FROM decisions ORDER BY decision_id ASC").fetchall()
            e_rows = conn.execute("SELECT * FROM decision_events ORDER BY seq ASC").fetchall()
            c_rows = conn.execute("SELECT * FROM decision_corrections ORDER BY seq ASC").fetchall()
            art_shas: dict[str, str] = {}
            for r in conn.execute("SELECT artifact_id, kind, payload_sha256, payload_json FROM artifacts").fetchall():
                aid_r = str(r["artifact_id"])
                if str(r["kind"]) == "lineage_receipt":
                    try:
                        l_pay = json.loads(str(r["payload_json"]))
                        art_shas[aid_r] = str(l_pay.get("receipt_digest") or r["payload_sha256"]).lower()
                    except Exception:
                        art_shas[aid_r] = str(r["payload_sha256"]).lower()
                else:
                    art_shas[aid_r] = str(r["payload_sha256"]).lower()

        decisions_out: list[dict[str, Any]] = []
        bases_out: list[dict[str, Any]] = []
        uncertainties_out: list[dict[str, Any]] = []
        v_manifest: dict[str, str] = {}

        # Replay effective verdict per decision across explicit outcome corrections and any unmigrated legacy overrides
        eff_verdict_by_dec: dict[str, str] = {str(r["decision_id"]): str(r["verdict"]) for r in d_rows}
        decs_with_explicit_corr: set[str] = {str(cr["decision_id"]) for cr in c_rows}
        for er in e_rows:
            did_e = str(er["decision_id"])
            if er["verdict_override"] is not None and did_e not in decs_with_explicit_corr:
                eff_verdict_by_dec[did_e] = str(er["verdict_override"])
        for cr in c_rows:
            eff_verdict_by_dec[str(cr["decision_id"])] = str(cr["verdict"])

        for r in d_rows:
            did = str(r["decision_id"])
            ek = str(r["entry_kind"])
            act = str(r["action"])
            title = str(r["title"])
            ntitle = nfc_compact(title)
            art_id = str(r["artifact_id"]) if r["artifact_id"] is not None else None
            basis_id = str(r["basis_decision_id"]) if r["basis_decision_id"] is not None else None
            raw_meta = json.loads(str(r["metadata_json"]))
            meta_d = dict(raw_meta) if isinstance(raw_meta, dict) else {"value": raw_meta}
            init_v = str(r["verdict"])
            eff_v = eff_verdict_by_dec.get(did, init_v)
            meta_d["initial_verdict"] = init_v
            meta_d["verdict"] = eff_v
            if art_id:
                meta_d["artifact_id"] = art_id
                if art_id in art_shas:
                    v_manifest[art_id] = art_shas[art_id]

            d_digest = sha256_hex(canonical_json({"id": did, "entry_kind": ek, "action": act, "title": ntitle}))
            d_obj: dict[str, Any] = {
                "id": did,
                "title": title,
                "normalized_title": ntitle,
                "decision_type": "negative_result" if ek == "negative_result" else act,
                "entry_kind": ek,
                "decision_action": None if ek == "negative_result" else act,
                "decision_digest": d_digest,
                "metadata": meta_d,
            }
            decisions_out.append(d_obj)

            if basis_id:
                b_edge: dict[str, Any] = {
                    "decision_id": did,
                    "basis_kind": "decision",
                    "basis_id": basis_id,
                }
                if art_id and art_id in art_shas:
                    b_edge["receipt_ref"] = {
                        "kind": "lineage",
                        "schema_version": "lineage-receipt-1.0",
                        "receipt_id": art_id,
                        "receipt_digest": art_shas[art_id],
                    }
                bases_out.append(b_edge)

            if ek == "negative_result" and not art_id:
                uh = sha256_hex(canonical_json(["unsupported_negative_result", did]))[:16]
                uncertainties_out.append({
                    "item_id": f"unc-{uh}",
                    "subject_id": did,
                    "kind": "unsupported_negative_result",
                    "reason": "Negative result recorded without empirical artifact_id receipt",
                    "needs_human": True,
                })
            elif ek == "decision" and act in ("commit", "abandon", "revise") and not basis_id and not art_id:
                uh = sha256_hex(canonical_json(["decision_without_basis", did]))[:16]
                uncertainties_out.append({
                    "item_id": f"unc-{uh}",
                    "subject_id": did,
                    "kind": "decision_without_basis",
                    "reason": f"Decision action {act!r} recorded without basis_decision_id or artifact_id",
                    "needs_human": True,
                })

        prev_state_by_dec: dict[str, str] = {}
        events_out: list[dict[str, Any]] = []
        override_corrs: list[tuple[str, str, str, Optional[str]]] = []
        for er in e_rows:
            seq = int(er["seq"])
            did = str(er["decision_id"])
            to_st = str(er["new_state"])
            rsn = str(er["reason"])
            sup_id = str(er["superseded_by_id"]) if er["superseded_by_id"] is not None else None
            v_over = str(er["verdict_override"]) if er["verdict_override"] is not None else None
            from_st = prev_state_by_dec.get(did)
            prev_state_by_dec[did] = to_st

            ev_hash = sha256_hex(canonical_json([seq, did, from_st, to_st, rsn, sup_id, v_over]))[:32]
            ev_obj: dict[str, Any] = {
                "event_id": f"evt-{ev_hash}",
                "decision_id": did,
                "to_state": to_st,
                "sequence": seq,
            }
            if from_st is not None:
                ev_obj["from_state"] = from_st
            if to_st in ("pruned", "reopened") and rsn != "genesis":
                ev_obj["reason"] = rsn
            elif to_st == "pruned" and rsn == "genesis":
                ev_obj["reason"] = "other"
            if sup_id is not None and to_st == "pruned":
                ev_obj["alternative_ref"] = sup_id
            if v_over is not None:
                ev_obj["metadata"] = {"verdict_override": v_over}
                if did not in decs_with_explicit_corr:
                    override_corrs.append((did, v_over, f"Lifecycle transition ({to_st}:{rsn}) verdict override", None))
            events_out.append(ev_obj)

        corrections_out: list[dict[str, Any]] = []
        corr_seq_counter = 0
        for did, verd, rat, c_art in override_corrs:
            corr_seq_counter += 1
            o_dig = sha256_hex(canonical_json([did, verd, rat, c_art]))
            c_hash = sha256_hex(canonical_json(["override", corr_seq_counter, did, o_dig]))[:32]
            corrections_out.append({
                "correction_id": f"corr-{c_hash}",
                "decision_id": did,
                "verdict": verd,
                "rationale": rat,
                "outcome_digest": o_dig,
                "sequence": corr_seq_counter,
            })
        for cr in c_rows:
            corr_seq_counter += 1
            did = str(cr["decision_id"])
            verd = str(cr["verdict"])
            rat = str(cr["rationale"])
            c_art = str(cr["artifact_id"]) if cr["artifact_id"] is not None else None
            if c_art and c_art in art_shas:
                v_manifest[c_art] = art_shas[c_art]
            o_dig = sha256_hex(canonical_json([did, verd, rat, c_art]))
            c_hash = sha256_hex(canonical_json(["explicit", int(cr["seq"]), corr_seq_counter, did, o_dig]))[:32]
            c_obj: dict[str, Any] = {
                "correction_id": f"corr-{c_hash}",
                "decision_id": did,
                "verdict": verd,
                "rationale": rat,
                "outcome_digest": o_dig,
                "sequence": corr_seq_counter,
            }
            if c_art and c_art in art_shas:
                c_obj["receipt_ref"] = {
                    "kind": "lineage",
                    "schema_version": "lineage-receipt-1.0",
                    "receipt_id": c_art,
                    "receipt_digest": art_shas[c_art],
                }
            corrections_out.append(c_obj)

        v_digest = sha256_hex(canonical_json(v_manifest))
        body = {
            "protocol": "decision-ledger-1.0",
            "verification_digest": v_digest,
            "verification_manifest": v_manifest,
            "decisions": decisions_out,
            "bases": bases_out,
            "forks": [],
            "state_events": events_out,
            "corrections": corrections_out,
            "uncertainties": uncertainties_out,
        }
        l_digest = sha256_hex(canonical_json(body))
        return {
            "protocol": "decision-ledger-1.0",
            "ledger_id": f"dl-{l_digest[:16]}",
            "ledger_digest": l_digest,
            **body,
        }

    def validate_decisions(self) -> dict[str, Any]:
        """Validate raw SQLite decision tables, event transitions, referential integrity, and exported schema."""
        errors: list[str] = []
        with self._read_snapshot() as conn:
            d_rows = conn.execute("SELECT * FROM decisions ORDER BY decision_id ASC").fetchall()
            e_rows = conn.execute("SELECT * FROM decision_events ORDER BY seq ASC").fetchall()
            c_rows = conn.execute("SELECT * FROM decision_corrections ORDER BY seq ASC").fetchall()

        dec_by_id = {str(r["decision_id"]): dict(r) for r in d_rows}
        for did, d in dec_by_id.items():
            if not re.fullmatch(r"^[a-z0-9][a-z0-9._-]{0,63}$", did):
                errors.append(f"Invalid decision_id format {did!r} (must match ^[a-z0-9][a-z0-9._-]{{0,63}}$)")
            b_id = d.get("basis_decision_id")
            if d["entry_kind"] == "negative_result":
                if not b_id or str(b_id) not in dec_by_id:
                    errors.append(f"negative_result {did!r} missing valid basis_decision_id")
                elif dec_by_id[str(b_id)]["entry_kind"] != "decision":
                    errors.append(f"negative_result {did!r} basis {b_id!r} must be entry_kind='decision'")
            elif b_id is not None and str(b_id) not in dec_by_id:
                errors.append(f"decision {did!r} references unknown basis_decision_id {b_id!r}")

        seen_seqs: set[int] = set()
        last_seq = 0
        state_by_dec: dict[str, str] = {}
        sup_adj: dict[str, set[str]] = {}
        for er in e_rows:
            seq = int(er["seq"])
            if seq <= last_seq or seq in seen_seqs:
                errors.append(f"Non-monotonic or duplicate event sequence {seq}")
            seen_seqs.add(seq)
            last_seq = max(last_seq, seq)
            did = str(er["decision_id"])
            if did not in dec_by_id:
                errors.append(f"Event seq={seq} references unknown decision_id {did!r}")
                continue
            nst = str(er["new_state"])
            rsn = str(er["reason"])
            sup_id = str(er["superseded_by_id"]) if er["superseded_by_id"] is not None else None
            prev_st = state_by_dec.get(did)
            if prev_st is None:
                if rsn != "genesis":
                    errors.append(f"Initial event for {did!r} must have reason='genesis', got {rsn!r}")
                if nst not in _VALID_TRANSITIONS[None]:
                    errors.append(f"Invalid genesis state {nst!r} for {did!r}")
            else:
                if rsn == "genesis":
                    errors.append(f"Non-initial event seq={seq} for {did!r} cannot use reason='genesis'")
                if nst not in _VALID_TRANSITIONS.get(prev_st, frozenset()):
                    errors.append(f"Illegal state transition {prev_st!r} -> {nst!r} on {did!r} at seq={seq}")
                if nst == "pruned" and rsn not in PRUNE_REASONS:
                    errors.append(f"Invalid prune reason {rsn!r} on {did!r} at seq={seq}")
                if nst == "reopened" and rsn not in REOPEN_REASONS:
                    errors.append(f"Invalid reopen reason {rsn!r} on {did!r} at seq={seq}")
            if rsn == "superseded":
                if not sup_id or sup_id not in dec_by_id or sup_id == did:
                    errors.append(f"Invalid superseded_by_id {sup_id!r} on {did!r} at seq={seq}")
                else:
                    sup_adj.setdefault(did, set()).add(sup_id)
            state_by_dec[did] = nst

        for did in dec_by_id:
            if did not in state_by_dec:
                errors.append(f"Decision {did!r} has no genesis event in decision_events")

        for cr in c_rows:
            if str(cr["decision_id"]) not in dec_by_id:
                errors.append(f"Correction seq={cr['seq']} references unknown decision_id {cr['decision_id']!r}")

        if not errors:
            exported = self.export_decision_ledger_dict()
            errors.extend(validate_decision_ledger_semantics(exported))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "decision_count": len(d_rows),
            "event_count": len(e_rows),
            "correction_count": len(c_rows),
        }

    def _store_scope_id(self) -> str:
        if self.db_path == ":memory:":
            return f"memory:{id(self)}"
        assert self._resolved_path is not None
        return f"file:{os.path.normcase(str(self._resolved_path))}"

    def record_kernel_execution(
        self,
        execution_id: str,
        tool_name: str,
        kernel_version: str,
        verification_scope: str,
        consistent: Optional[bool],
        executed_at: str,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
    ) -> dict[str, Any]:
        eid = _require_str_id(execution_id, "execution_id")
        tname = _require_str_id(tool_name, "tool_name")
        kver = _require_str_id(kernel_version, "kernel_version")
        vscope = _require_str_id(verification_scope, "verification_scope")
        exec_at = _require_str_id(executed_at, "executed_at")
        cons_int: Optional[int] = None
        if consistent is not None:
            if type(consistent) is not bool:
                raise TypeError("consistent must be bool or None")
            cons_int = 1 if consistent else 0
        in_json = canonical_json(inputs)
        in_sha = sha256_hex(in_json)
        out_json = canonical_json(outputs)
        out_sha = sha256_hex(out_json)
        expected_id = compute_kernel_execution_id(tname, kver, vscope, consistent, exec_at, in_sha, out_sha)
        if eid != expected_id:
            raise ValueError(f"Invalid execution_id {eid!r}; expected {expected_id!r}")
        store_scope = self._store_scope_id()
        mac = _compute_kernel_exec_hmac(
            store_scope, eid, tname, kver, vscope, consistent, exec_at, in_sha, out_sha
        )
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT * FROM kernel_executions WHERE execution_id = ?",
                (eid,),
            ).fetchone()
            if existing is not None:
                verified_existing = _verify_execution_row_dict(existing, store_scope=store_scope)
                if (
                    verified_existing["tool_name"] != tname
                    or verified_existing["kernel_version"] != kver
                    or verified_existing["verification_scope"] != vscope
                    or verified_existing["consistent"] != consistent
                    or verified_existing["executed_at"] != exec_at
                    or verified_existing["inputs_sha256"] != in_sha
                    or verified_existing["outputs_sha256"] != out_sha
                ):
                    raise ValueError(f"Execution receipt collision/tamper on execution_id {eid!r}")
            else:
                conn.execute(
                    """
                    INSERT INTO kernel_executions
                    (execution_id, tool_name, kernel_version, verification_scope, consistent, executed_at, inputs_json, inputs_sha256, outputs_json, outputs_sha256, auth_hmac)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (eid, tname, kver, vscope, cons_int, exec_at, in_json, in_sha, out_json, out_sha, mac),
                )
        return {
            "execution_id": eid,
            "tool_name": tname,
            "kernel_version": kver,
            "verification_scope": vscope,
            "consistent": consistent,
            "executed_at": exec_at,
            "inputs_sha256": in_sha,
            "outputs_sha256": out_sha,
        }

    def get_kernel_execution(self, execution_id: str) -> Optional[dict[str, Any]]:
        eid = _require_str_id(execution_id, "execution_id")
        with self._read_snapshot() as conn:
            has_tbl = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='kernel_executions'"
                ).fetchone()
                is not None
            )
            if not has_tbl:
                return None
            row = conn.execute("SELECT * FROM kernel_executions WHERE execution_id = ?", (eid,)).fetchone()
        if row is None:
            return None
        return _verify_execution_row_dict(row, store_scope=self._store_scope_id())

    def bind_artifact_execution(
        self,
        artifact_id: str,
        execution_id: str,
        verification_scope: str,
        provenance_tier: str = "kernel_executed",
        ingest_bound_claim_id: Optional[str] = None,
    ) -> None:
        aid = _require_str_id(artifact_id, "artifact_id")
        eid = _require_str_id(execution_id, "execution_id")
        vscope = _require_str_id(verification_scope, "verification_scope")
        ptier = _require_str_id(provenance_tier, "provenance_tier")
        ibc = _require_str_id(ingest_bound_claim_id, "ingest_bound_claim_id") if ingest_bound_claim_id is not None else None
        if ptier != "kernel_executed":
            raise ValueError(f"Execution binding provenance_tier must be 'kernel_executed', got {ptier!r}")
        store_scope = self._store_scope_id()
        with self.transaction() as conn:
            art_row = conn.execute(
                "SELECT kind, payload_json, payload_sha256 FROM artifacts WHERE artifact_id = ?", (aid,)
            ).fetchone()
            if art_row is None:
                raise ValueError(f"Cannot bind execution to non-existent artifact_id {aid!r}")
            ak_b = str(art_row["kind"])
            psha = str(art_row["payload_sha256"])
            live_obj = json.loads(str(art_row["payload_json"]))
            if not isinstance(live_obj, Mapping):
                raise ValueError(f"Artifact {aid!r} payload_json must be a JSON object")
            live_sha = sha256_hex(canonical_json(live_obj))
            if live_sha != psha:
                raise ValueError(f"Artifact {aid!r} payload_json does not match stored payload_sha256")
            ke_row = conn.execute("SELECT * FROM kernel_executions WHERE execution_id = ?", (eid,)).fetchone()
            if ke_row is None:
                raise ValueError(f"Cannot bind unknown execution_id {eid!r}")
            verified_ke = _verify_execution_row_dict(ke_row, store_scope=store_scope)
            if verified_ke["verification_scope"] != vscope:
                raise ValueError(f"Verification scope mismatch on execution binding {eid!r}")
            resolve_executed_artifact_payload(ak_b, verified_ke, live_obj)
            bmac = _compute_binding_hmac(store_scope, aid, ak_b, live_sha, eid, vscope, ptier, ibc)
            existing = conn.execute(
                "SELECT execution_id, verification_scope, provenance_tier, ingest_bound_claim_id, binding_hmac FROM artifact_execution_bindings WHERE artifact_id = ?",
                (aid,),
            ).fetchone()
            if existing is not None:
                if (
                    str(existing["execution_id"]) != eid
                    or str(existing["verification_scope"]) != vscope
                    or str(existing["provenance_tier"]) != ptier
                    or existing["ingest_bound_claim_id"] != ibc
                    or not hmac.compare_digest(str(existing["binding_hmac"]), bmac)
                ):
                    raise ValueError(f"Conflicting execution binding on artifact_id {aid!r}")
                return
            conn.execute(
                """
                INSERT INTO artifact_execution_bindings
                (artifact_id, execution_id, verification_scope, provenance_tier, ingest_bound_claim_id, binding_hmac)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (aid, eid, vscope, ptier, ibc, bmac),
            )

    def snapshot_digest(self) -> str:
        """Deterministic order-invariant SHA-256 digest of all authoritative tables under one read snapshot."""
        tables = (
            "works",
            "artifacts",
            "lineage_edges",
            "claims",
            "claim_evidence",
            "claim_edges",
            "decisions",
            "decision_events",
            "decision_corrections",
            "doi_watch_state",
            "doi_watch_commits",
        )
        with self._read_snapshot() as conn:
            dump: dict[str, Any] = {"schema_version": ARK_SQLITE_USER_VERSION}
            for tbl in tables:
                rows = conn.execute(f"SELECT * FROM {tbl}").fetchall()
                dump[tbl] = sorted((dict(r) for r in rows), key=canonical_json)
            has_bind = (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='artifact_execution_bindings'"
                ).fetchone()
                is not None
            )
            if has_bind:
                b_rows = conn.execute(
                    """
                    SELECT artifact_id, execution_id, verification_scope, provenance_tier, ingest_bound_claim_id
                    FROM artifact_execution_bindings
                    ORDER BY artifact_id
                    """
                ).fetchall()
                if b_rows:
                    dump["artifact_execution_bindings"] = [dict(r) for r in b_rows]
                    ke_rows = conn.execute(
                        """
                        SELECT execution_id, tool_name, kernel_version, verification_scope, consistent, executed_at, inputs_sha256, outputs_sha256
                        FROM kernel_executions
                        WHERE execution_id IN (SELECT execution_id FROM artifact_execution_bindings)
                        ORDER BY execution_id
                        """
                    ).fetchall()
                    dump["bound_kernel_executions"] = [dict(r) for r in ke_rows]
            return sha256_hex(canonical_json(dump))


def validate_decision_ledger_semantics(
    doc: Mapping[str, Any],
    *,
    receipts: Optional[Mapping[str, Any]] = None,
    content_payloads: Optional[Mapping[str, Any]] = None,
    authoritative_artifacts: Optional[Mapping[str, tuple[str, str, Any]]] = None,
) -> list[str]:
    """Validate schema AND referential/lifecycle/enum/receipt invariants on a decision-ledger-1.0 JSON document."""
    errs = list(validate_schema(doc, "decision-ledger-receipt.schema.json"))
    if not isinstance(doc, Mapping):
        return errs or ["Ledger must be a JSON object"]

    decs = doc.get("decisions")
    bases = doc.get("bases")
    forks = doc.get("forks")
    events = doc.get("state_events")
    corrs = doc.get("corrections")
    uncerts = doc.get("uncertainties")
    v_manifest = doc.get("verification_manifest") if isinstance(doc.get("verification_manifest"), Mapping) else {}
    dec_content: Optional[dict[str, bytes]] = None
    if content_payloads is not None:
        try:
            dec_content = decode_content_payloads_map(content_payloads)
        except ValueError as exc:
            errs.append(str(exc))

    ext_receipts: dict[str, Mapping[str, Any]] = {}
    if receipts is not None:
        if not isinstance(receipts, Mapping):
            errs.append("receipts must be a JSON object mapping receipt keys to receipt payloads")
        else:
            for rk, rv in receipts.items():
                if not isinstance(rk, str) or not rk or not isinstance(rv, Mapping):
                    errs.append(f"receipts[{rk!r}] must map a non-empty string key to a JSON object")
                else:
                    ext_receipts[rk] = rv

    missing_receipt_subjects = {
        str(u.get("subject_id") or "")
        for u in (uncerts if isinstance(uncerts, list) else ())
        if isinstance(u, Mapping) and u.get("kind") == "missing_receipt"
    }

    def _lineage_status_usable(l_doc: Mapping[str, Any]) -> bool:
        return (
            l_doc.get("topology_status") == "valid_dag"
            and l_doc.get("verification_status") not in ("hash_mismatch", "missing_artifact", "missing_input", "broken_chain", "cycle_detected")
            and l_doc.get("content_verification") not in ("hash_mismatch", "missing_artifact")
        )

    known_content_keys: set[str] = set()

    def _record_lineage_entities(l_doc: Mapping[str, Any]) -> None:
        for ent_i in (l_doc.get("entities") or ()):
            if isinstance(ent_i, Mapping) and isinstance(ent_i.get("id"), str) and ent_i["id"] == ent_i["id"].strip() and ent_i["id"]:
                known_content_keys.add(ent_i["id"])

    # When validating inside a ResearchStateDB transaction, every verification_manifest entry must match DB truth
    if authoritative_artifacts is not None:
        for m_key, m_sha in v_manifest.items():
            mk_s = str(m_key)
            ms_s = str(m_sha).lower()
            if mk_s in authoritative_artifacts:
                db_kind, db_sha, db_pay = authoritative_artifacts[mk_s]
                if db_kind == "lineage_receipt" and isinstance(db_pay, Mapping):
                    _record_lineage_entities(db_pay)
                else:
                    known_content_keys.add(mk_s)
                exp_db_dig = (
                    str(db_pay.get("receipt_digest") or "").lower()
                    if (db_kind == "lineage_receipt" and isinstance(db_pay, Mapping))
                    else db_sha.lower()
                )
                if exp_db_dig != ms_s:
                    errs.append(
                        f"verification_manifest[{mk_s!r}] digest {ms_s[:12]} disagrees with stored DB artifact digest {exp_db_dig[:12]}"
                    )
                elif db_kind == "lineage_receipt" and isinstance(db_pay, Mapping):
                    l_errs_db_m = validate_lineage_receipt_semantics(
                        db_pay, decoded_content=dec_content, strict_unknown_entities=False
                    )
                    if l_errs_db_m or not _lineage_status_usable(db_pay):
                        errs.append(
                            f"verification_manifest[{mk_s!r}] references failed or content-mismatched lineage_receipt ({db_pay.get('verification_status')!r})"
                        )
                elif dec_content is not None and mk_s in dec_content and sha256_hex(dec_content[mk_s]) != ms_s:
                    errs.append(f"verification_manifest[{mk_s!r}] content_payloads SHA-256 mismatch")
            else:
                # Could also be an academic_evidence claim_digest backed by a stored evidence_receipt
                matched_ae = False
                for _, (db_kind, db_sha, db_payload) in authoritative_artifacts.items():
                    if db_sha.lower() == ms_s and not validate_academic_evidence_payload(db_payload):
                        if any(isinstance(ci, Mapping) and canonical_evidence_claim_digest(ci) == mk_s for ci in db_payload["claims"]):
                            matched_ae = True
                            break
                if not matched_ae:
                    errs.append(f"verification_manifest[{mk_s!r}] references unregistered artifact or unverified claim_digest in DB")

    elif receipts is not None:
        for m_key, m_sha in v_manifest.items():
            mk_s = str(m_key)
            ms_s = str(m_sha).lower()
            if mk_s in ext_receipts:
                phys_m = ext_receipts[mk_s]
                if phys_m.get("protocol") == "lineage-receipt-1.0":
                    _record_lineage_entities(phys_m)
                    l_errs_m = validate_lineage_receipt_semantics(
                        phys_m, decoded_content=dec_content, strict_unknown_entities=False
                    )
                    if l_errs_m or str(phys_m.get("receipt_digest") or "").lower() != ms_s or not _lineage_status_usable(phys_m):
                        errs.append(f"verification_manifest[{mk_s!r}] lineage receipt failed verification")
                elif phys_m.get("schema_version") == "1.0" and isinstance(phys_m.get("claims"), list):
                    if (
                        validate_academic_evidence_payload(phys_m)
                        or sha256_hex(canonical_json(phys_m)) != ms_s
                        or not any(isinstance(ci, Mapping) and canonical_evidence_claim_digest(ci) == mk_s for ci in phys_m["claims"])
                    ):
                        errs.append(f"verification_manifest[{mk_s!r}] academic_evidence failed verification")
                elif sha256_hex(canonical_json(phys_m)) != ms_s:
                    errs.append(f"verification_manifest[{mk_s!r}] artifact SHA-256 mismatch")
                else:
                    known_content_keys.add(mk_s)
                    if dec_content is not None and mk_s in dec_content and sha256_hex(dec_content[mk_s]) != ms_s:
                        errs.append(f"verification_manifest[{mk_s!r}] content_payloads SHA-256 mismatch")
            else:
                matched_m_ae = False
                for _, phys_cand in ext_receipts.items():
                    if sha256_hex(canonical_json(phys_cand)) == ms_s and not validate_academic_evidence_payload(phys_cand):
                        if any(isinstance(ci, Mapping) and canonical_evidence_claim_digest(ci) == mk_s for ci in phys_cand["claims"]):
                            matched_m_ae = True
                            break
                if not matched_m_ae:
                    errs.append(f"verification_manifest[{mk_s!r}] missing from supplied receipts")

    def _check_receipt_ref(rref: Any, ctx: str, subject_id: str = "") -> bool:
        ref_errs = validate_receipt_ref_dict(rref)
        if ref_errs:
            errs.append(f"{ctx} invalid receipt_ref: {ref_errs[0]}")
            return False
        if rref.get("kind") == "lineage":
            rid = str(rref.get("receipt_id") or "")
            rdig = str(rref.get("receipt_digest") or "").lower()
            if rid not in v_manifest:
                if subject_id not in missing_receipt_subjects:
                    errs.append(f"{ctx} lineage receipt_id {rid!r} missing from verification_manifest")
                return False
            if str(v_manifest.get(rid)).lower() != rdig:
                errs.append(f"{ctx} lineage receipt_digest mismatch for {rid!r}")
                return False
            if authoritative_artifacts is not None:
                if rid not in authoritative_artifacts:
                    errs.append(f"{ctx} lineage receipt_id {rid!r} does not exist in authoritative state DB")
                    return False
                db_kind, db_sha, db_pay = authoritative_artifacts[rid]
                if db_kind == "lineage_receipt" and isinstance(db_pay, Mapping):
                    _record_lineage_entities(db_pay)
                else:
                    known_content_keys.add(rid)
                exp_db_dig = (
                    str(db_pay.get("receipt_digest") or "").lower()
                    if (db_kind == "lineage_receipt" and isinstance(db_pay, Mapping))
                    else db_sha.lower()
                )
                if exp_db_dig != rdig:
                    errs.append(f"{ctx} lineage receipt_digest {rdig[:12]} != DB artifact digest {exp_db_dig[:12]} for {rid!r}")
                    return False
                if db_kind == "lineage_receipt" and isinstance(db_pay, Mapping):
                    l_errs_db_r = validate_lineage_receipt_semantics(
                        db_pay, decoded_content=dec_content, strict_unknown_entities=False
                    )
                    if l_errs_db_r or not _lineage_status_usable(db_pay):
                        errs.append(
                            f"{ctx} lineage_receipt {rid!r} failed verification or status={db_pay.get('verification_status')!r}"
                        )
                        return False
                elif dec_content is not None and rid in dec_content and sha256_hex(dec_content[rid]) != rdig:
                    errs.append(f"{ctx} content_payloads[{rid!r}] SHA-256 mismatch vs DB artifact")
                    return False
            elif receipts is not None or dec_content is not None:
                if rid in ext_receipts:
                    phys = ext_receipts[rid]
                    if phys.get("protocol") == "lineage-receipt-1.0":
                        _record_lineage_entities(phys)
                        l_errs = validate_lineage_receipt_semantics(
                            phys, decoded_content=dec_content, strict_unknown_entities=False
                        )
                        if l_errs or str(phys.get("receipt_digest") or "").lower() != rdig or not _lineage_status_usable(phys):
                            errs.append(f"{ctx} physical lineage receipt failed verification for {rid!r}")
                            return False
                    elif sha256_hex(canonical_json(phys)) != rdig:
                        errs.append(f"{ctx} physical artifact payload SHA-256 mismatch for {rid!r}")
                        return False
                    else:
                        known_content_keys.add(rid)
                        if dec_content is not None and rid in dec_content and sha256_hex(dec_content[rid]) != rdig:
                            errs.append(f"{ctx} content_payloads[{rid!r}] SHA-256 mismatch")
                            return False
                elif receipts is not None and subject_id not in missing_receipt_subjects:
                    errs.append(f"{ctx} lineage receipt_id {rid!r} missing from supplied receipts")
                    return False
            return True
        if rref.get("kind") == "academic_evidence":
            cdig = str(rref.get("claim_digest") or "").lower()
            psha = str(rref.get("payload_sha256") or "").lower()
            if not cdig or not psha:
                errs.append(f"{ctx} academic_evidence receipt_ref missing claim_digest or payload_sha256")
                return False
            if cdig not in v_manifest or str(v_manifest.get(cdig)).lower() != psha:
                if subject_id not in missing_receipt_subjects:
                    errs.append(f"{ctx} academic_evidence claim_digest {cdig!r} not verified in verification_manifest")
                return False
            if authoritative_artifacts is not None:
                matched_db = False
                for _, (_, db_sha, db_payload) in authoritative_artifacts.items():
                    if db_sha.lower() == psha and not validate_academic_evidence_payload(db_payload):
                        if any(isinstance(ci, Mapping) and canonical_evidence_claim_digest(ci) == cdig for ci in db_payload["claims"]):
                            matched_db = True
                            break
                if not matched_db:
                    errs.append(f"{ctx} academic_evidence ({cdig[:12]}, {psha[:12]}) not backed by any registered receipt in DB")
                    return False
            elif receipts is not None:
                cand_obj = ext_receipts.get(cdig) or ext_receipts.get(psha)
                if cand_obj is None:
                    for v_cand in ext_receipts.values():
                        if sha256_hex(canonical_json(v_cand)) == psha:
                            cand_obj = v_cand
                            break
                if cand_obj is None:
                    if subject_id not in missing_receipt_subjects:
                        errs.append(f"{ctx} academic_evidence ({cdig[:12]}, {psha[:12]}) missing from supplied receipts")
                    return False
                if (
                    validate_academic_evidence_payload(cand_obj)
                    or sha256_hex(canonical_json(cand_obj)) != psha
                    or not any(isinstance(ci, Mapping) and canonical_evidence_claim_digest(ci) == cdig for ci in (cand_obj.get("claims") or []))
                ):
                    errs.append(f"{ctx} physical academic_evidence payload failed verification for {cdig[:12]}")
                    return False
            return True
        errs.append(f"{ctx} unsupported receipt_ref kind {rref.get('kind')!r}")
        return False

    dec_by_id: dict[str, Mapping[str, Any]] = {}
    replayed_verdict_by_id: dict[str, str] = {}
    exported_verdict_by_id: dict[str, str] = {}
    if isinstance(decs, list):
        for idx, d in enumerate(decs):
            if not isinstance(d, Mapping):
                continue
            did = str(d.get("id") or "")
            if did in dec_by_id:
                errs.append(f"Duplicate decision id {did!r} at decisions[{idx}]")
            elif did:
                dec_by_id[did] = d
                title_raw = str(d.get("title") or "")
                exp_ntitle = nfc_compact(title_raw)
                if d.get("normalized_title") != exp_ntitle:
                    errs.append(f"decisions[{idx}] normalized_title mismatch on {did!r}")
                ek_d = str(d.get("entry_kind") or "")
                act_d = str(d.get("decision_action") if ek_d != "negative_result" else (d.get("decision_type") or "negative_result"))
                exp_ddig_v3 = sha256_hex(canonical_json({"id": did, "entry_kind": ek_d, "action": act_d, "title": exp_ntitle}))
                exp_ddig_v2 = sha256_hex(
                    canonical_json(
                        {
                            "version": 1,
                            "text": exp_ntitle,
                            "context_work_id": d.get("context_work_id"),
                            "locator": d.get("locator"),
                            "decision_type": "negative_result" if ek_d == "negative_result" else act_d,
                        }
                    )
                )
                if d.get("decision_digest") not in (exp_ddig_v3, exp_ddig_v2):
                    errs.append(f"decisions[{idx}] decision_digest mismatch on {did!r}")
                meta_d0 = d.get("metadata") if isinstance(d.get("metadata"), Mapping) else {}
                raw_init_v = meta_d0.get("initial_verdict")
                raw_exp_v = meta_d0.get("verdict")
                if raw_init_v is not None and (not isinstance(raw_init_v, str) or raw_init_v not in ALLOWED_DECISION_VERDICTS):
                    errs.append(f"decisions[{idx}] illegal metadata.initial_verdict={raw_init_v!r} on {did!r}")
                if raw_exp_v is not None and (not isinstance(raw_exp_v, str) or raw_exp_v not in ALLOWED_DECISION_VERDICTS):
                    errs.append(f"decisions[{idx}] illegal metadata.verdict={raw_exp_v!r} on {did!r}")
                init_v = str(raw_init_v if raw_init_v is not None else (raw_exp_v if raw_exp_v is not None else "inconclusive"))
                exp_v = str(raw_exp_v if raw_exp_v is not None else init_v)
                replayed_verdict_by_id[did] = init_v
                exported_verdict_by_id[did] = exp_v

    neg_with_basis: set[str] = set()
    neg_with_receipt: set[str] = set()
    if isinstance(bases, list):
        for idx, b in enumerate(bases):
            if not isinstance(b, Mapping):
                continue
            did = str(b.get("decision_id") or "")
            bid = str(b.get("basis_id") or "")
            if did not in dec_by_id:
                errs.append(f"bases[{idx}] references unknown decision_id {did!r}")
            if bid not in dec_by_id:
                errs.append(f"bases[{idx}] references unknown basis_id {bid!r}")
            if did and did == bid:
                errs.append(f"bases[{idx}] self-basis on {did!r}")
            has_rref = b.get("receipt_ref") is not None and _check_receipt_ref(b.get("receipt_ref"), f"bases[{idx}]")
            if did in dec_by_id and bid in dec_by_id:
                if dec_by_id[did].get("entry_kind") == "negative_result":
                    if dec_by_id[bid].get("entry_kind") != "decision":
                        errs.append(f"negative_result {did!r} basis {bid!r} must be entry_kind='decision'")
                    else:
                        neg_with_basis.add(did)
                        if has_rref:
                            neg_with_receipt.add(did)

    unsupported_neg_uncerts: set[str] = set()
    if isinstance(uncerts, list):
        for idx, u in enumerate(uncerts):
            if isinstance(u, Mapping) and u.get("kind") == "unsupported_negative_result":
                unsupported_neg_uncerts.add(str(u.get("subject_id") or ""))

    for did, d in dec_by_id.items():
        if d.get("entry_kind") == "negative_result":
            if did not in neg_with_basis:
                errs.append(f"negative_result {did!r} has no valid basisEdge to a prior decision")
            meta_d = d.get("metadata") if isinstance(d.get("metadata"), Mapping) else {}
            art_ref = str(meta_d.get("artifact_id") or "")
            has_manifest_art = bool(art_ref and art_ref in v_manifest)
            if did not in neg_with_receipt and not has_manifest_art and did not in unsupported_neg_uncerts:
                errs.append(f"negative_result {did!r} lacks empirical receipt_ref and is missing unsupported_negative_result uncertainty")

    if isinstance(forks, list):
        for idx, fk in enumerate(forks):
            if not isinstance(fk, Mapping):
                continue
            did = str(fk.get("decision_id") or "")
            aid = str(fk.get("alternative_id") or "")
            if did not in dec_by_id:
                errs.append(f"forks[{idx}] references unknown decision_id {did!r}")
            if aid not in dec_by_id:
                errs.append(f"forks[{idx}] references unknown alternative_id {aid!r}")
            if did and did == aid:
                errs.append(f"forks[{idx}] self-fork on {did!r}")
            if fk.get("receipt_ref") is not None:
                _check_receipt_ref(fk.get("receipt_ref"), f"forks[{idx}]")

    cur_state: dict[str, str] = {}
    if isinstance(events, list):
        seen_seq: set[int] = set()
        prev_seq = 0
        sup_adj: dict[str, set[str]] = {}
        for idx, ev in enumerate(events):
            if not isinstance(ev, Mapping):
                continue
            seq = ev.get("sequence")
            if isinstance(seq, int) and not isinstance(seq, bool):
                if seq in seen_seq or seq <= prev_seq:
                    errs.append(f"state_events[{idx}] has non-monotonic or duplicate sequence {seq}")
                seen_seq.add(seq)
                prev_seq = max(prev_seq, seq)
            did = str(ev.get("decision_id") or "")
            if did not in dec_by_id:
                errs.append(f"state_events[{idx}] references unknown decision_id {did!r}")
                continue
            if ev.get("receipt_ref") is not None:
                _check_receipt_ref(ev.get("receipt_ref"), f"state_events[{idx}]")
            from_st = ev.get("from_state")
            to_st = str(ev.get("to_state") or "")
            prior = cur_state.get(did)
            if prior is None:
                if from_st is not None:
                    errs.append(f"Initial event for {did!r} must omit from_state, got {from_st!r}")
                if to_st not in _VALID_TRANSITIONS[None]:
                    errs.append(f"Illegal initial state {to_st!r} for {did!r}")
            else:
                if from_st != prior:
                    errs.append(f"Event state mismatch on {did!r}: expected from_state={prior!r}, got {from_st!r}")
                if to_st not in _VALID_TRANSITIONS.get(prior, frozenset()):
                    errs.append(f"Illegal transition {prior!r} -> {to_st!r} on {did!r}")
            if ev.get("reason") == "superseded":
                alt = str(ev.get("alternative_ref") or "")
                if not alt or alt not in dec_by_id or alt == did:
                    errs.append(f"Event {ev.get('event_id')!r} with reason='superseded' requires valid distinct alternative_ref")
                else:
                    sup_adj.setdefault(did, set()).add(alt)
            if ev.get("caused_by") is not None and str(ev.get("caused_by")) not in dec_by_id:
                errs.append(f"state_events[{idx}] caused_by references unknown decision {ev.get('caused_by')!r}")
            ev_meta = ev.get("metadata")
            if isinstance(ev_meta, Mapping) and "verdict_override" in ev_meta and ev_meta["verdict_override"] is not None:
                vo = ev_meta["verdict_override"]
                if not isinstance(vo, str) or vo not in ALLOWED_DECISION_VERDICTS:
                    errs.append(f"state_events[{idx}] illegal metadata.verdict_override={vo!r}")
            cur_state[did] = to_st

        # Check supersession cycles
        color: dict[str, int] = {}
        for start in sorted(sup_adj):
            if color.get(start, 0) != 0:
                continue
            stack = [(start, sorted(sup_adj.get(start, ())), 0)]
            color[start] = 1
            while stack:
                node, nbrs, pos = stack[-1]
                if pos >= len(nbrs):
                    color[node] = 2
                    stack.pop()
                    continue
                nxt = nbrs[pos]
                stack[-1] = (node, nbrs, pos + 1)
                st_c = color.get(nxt, 0)
                if st_c == 1:
                    errs.append(f"Cycle detected in supersession chain involving {nxt!r}")
                    break
                if st_c == 0:
                    color[nxt] = 1
                    stack.append((nxt, sorted(sup_adj.get(nxt, ())), 0))

    missing_genesis_dids = [did for did in dec_by_id if did not in cur_state]

    if isinstance(corrs, list):
        seen_cseq: set[int] = set()
        prev_cseq = 0
        for idx, c in enumerate(corrs):
            if not isinstance(c, Mapping):
                continue
            did = str(c.get("decision_id") or "")
            if did not in dec_by_id:
                errs.append(f"corrections[{idx}] references unknown decision_id {did!r}")
            if c.get("receipt_ref") is not None:
                _check_receipt_ref(c.get("receipt_ref"), f"corrections[{idx}]")
            cseq = c.get("sequence")
            if isinstance(cseq, int) and not isinstance(cseq, bool):
                if cseq in seen_cseq or cseq <= prev_cseq:
                    errs.append(f"corrections[{idx}] has non-monotonic or duplicate sequence {cseq}")
                seen_cseq.add(cseq)
                prev_cseq = max(prev_cseq, cseq)
            verd_c = str(c.get("verdict") or "")
            if verd_c not in ALLOWED_DECISION_VERDICTS:
                errs.append(f"corrections[{idx}] illegal verdict={verd_c!r} on {did!r}")
            rat_c = str(c.get("rationale") or "")
            rref_c = c.get("receipt_ref")
            c_art_id = str(rref_c.get("receipt_id")) if isinstance(rref_c, Mapping) and rref_c.get("kind") == "lineage" and rref_c.get("receipt_id") else None
            exp_odig_v3 = sha256_hex(canonical_json([did, verd_c, rat_c, c_art_id]))
            rref_tup = (
                (
                    str(rref_c.get("kind") or ""),
                    str(rref_c.get("schema_version") or ""),
                    str(rref_c.get("receipt_id") or ""),
                    str(rref_c.get("receipt_digest") or ""),
                    str(rref_c.get("claim_digest") or ""),
                    str(rref_c.get("payload_sha256") or ""),
                    str(rref_c.get("locator") or ""),
                )
                if isinstance(rref_c, Mapping)
                else ()
            )
            exp_odig_v2 = sha256_hex(
                canonical_json(
                    {
                        "version": 1,
                        "verdict": verd_c,
                        "rationale": nfc_compact(rat_c),
                        "receipt": list(rref_tup),
                        "locator": c.get("locator"),
                    }
                )
            )
            if c.get("outcome_digest") not in (exp_odig_v3, exp_odig_v2):
                errs.append(f"corrections[{idx}] outcome_digest mismatch on {did!r}")
            if did in replayed_verdict_by_id and verd_c:
                replayed_verdict_by_id[did] = verd_c

    for did, exp_v in exported_verdict_by_id.items():
        rep_v = replayed_verdict_by_id.get(did)
        if rep_v is not None and exp_v != rep_v:
            errs.append(f"Decision {did!r} exported metadata.verdict={exp_v!r} disagrees with replayed correction outcome {rep_v!r}")

    # Verify verification_digest and ledger_digest integrity (v3.0 + v2.4 legacy compatible)
    try:
        exp_v_digest_v3 = sha256_hex(canonical_json(v_manifest))
        body_v3 = {
            "protocol": doc.get("protocol"),
            "verification_digest": doc.get("verification_digest"),
            "verification_manifest": v_manifest,
            "decisions": decs,
            "bases": bases,
            "forks": forks,
            "state_events": events,
            "corrections": corrs,
            "uncertainties": uncerts,
        }
        exp_l_digest_v3 = sha256_hex(canonical_json(body_v3))
        matches_v3 = doc.get("verification_digest") == exp_v_digest_v3 and doc.get("ledger_digest") == exp_l_digest_v3

        def _canon_raw_v2(rec_d: Mapping[str, Any]) -> dict[str, Any]:
            res_r: dict[str, Any] = {}
            for k_r, v_r in rec_d.items():
                if k_r == "metadata":
                    if isinstance(v_r, Mapping) and len(v_r) > 0:
                        res_r["metadata"] = dict(thaw(v_r))
                    continue
                if v_r is None:
                    continue
                if v_r == "" and k_r in ("locator", "context_work_id", "caused_by", "alternative_ref", "stop_reason", "closed_by", "reason"):
                    continue
                if k_r == "receipt_ref" and isinstance(v_r, Mapping):
                    res_r["receipt_ref"] = _canon_raw_v2(v_r)
                else:
                    res_r[k_r] = thaw(v_r)
            return res_r

        def _canon_dec_v2(d_item: Mapping[str, Any]) -> dict[str, Any]:
            ek_i = str(d_item.get("entry_kind") or ("negative_result" if d_item.get("decision_type") == "negative_result" else "decision"))
            act_i = d_item.get("decision_action")
            if act_i is None and ek_i != "negative_result":
                act_i = d_item.get("decision_type") or "explore"
            res_d: dict[str, Any] = {
                "id": d_item["id"],
                "title": d_item["title"],
                "normalized_title": nfc_compact(str(d_item["title"])),
                "entry_kind": ek_i,
                "decision_digest": d_item.get("decision_digest"),
            }
            if act_i is not None:
                res_d["decision_action"] = act_i
            if d_item.get("context_work_id"):
                res_d["context_work_id"] = d_item["context_work_id"]
            if d_item.get("locator"):
                res_d["locator"] = d_item["locator"]
            meta_i = d_item.get("metadata")
            if isinstance(meta_i, Mapping) and len(meta_i) > 0:
                res_d["metadata"] = dict(thaw(meta_i))
            return res_d

        matches_v2 = False
        if not matches_v3 and isinstance(decs, list) and isinstance(bases, list) and isinstance(forks, list) and isinstance(events, list) and isinstance(corrs, list):
            payload_v2 = {
                "protocol": doc.get("protocol"),
                "ledger_id": doc.get("ledger_id"),
                "decisions": sorted((_canon_dec_v2(d) for d in decs if isinstance(d, Mapping)), key=lambda x: x["id"]),
                "bases": sorted((_canon_raw_v2(e) for e in bases if isinstance(e, Mapping)), key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)),
                "forks": sorted((_canon_raw_v2(e) for e in forks if isinstance(e, Mapping)), key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)),
                "state_events": sorted((_canon_raw_v2(e) for e in events if isinstance(e, Mapping)), key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)),
                "corrections": sorted((_canon_raw_v2(e) for e in corrs if isinstance(e, Mapping)), key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False)),
            }
            exp_l_digest_v2 = sha256_hex(canonical_json(payload_v2))
            exp_v_digest_v2 = sha256_hex(canonical_json({"ledger_digest": exp_l_digest_v2, "receipts": v_manifest}))
            matches_v2 = doc.get("ledger_digest") == exp_l_digest_v2 and doc.get("verification_digest") == exp_v_digest_v2

        if not matches_v2:
            for did_mg in missing_genesis_dids:
                errs.append(f"Decision {did_mg!r} missing genesis event in state_events")
        if not (matches_v3 or matches_v2):
            if doc.get("verification_digest") != exp_v_digest_v3:
                errs.append(f"verification_digest mismatch: expected {exp_v_digest_v3}, got {doc.get('verification_digest')!r}")
            if doc.get("ledger_digest") != exp_l_digest_v3:
                errs.append(f"ledger_digest mismatch: expected {exp_l_digest_v3}, got {doc.get('ledger_digest')!r}")
    except Exception as exc:
        errs.append(f"Digest recomputation error: {exc}")

    if dec_content and (authoritative_artifacts is not None or receipts is not None):
        unknown_cp = sorted(set(dec_content) - known_content_keys)
        if unknown_cp:
            errs.append(f"content_payloads references unknown entity/artifact IDs: {unknown_cp!r}")

    return errs

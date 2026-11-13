"""Clean JSON-RPC 2.0 stdio MCP server for academic-research-kernel (Occam edition).

Replaces 1,742 lines of ``scripts/mcp_server.py`` (7x ``sys.path.insert``,
dual ``if __package__`` branches, ``spec_from_file_location`` loaders, and
hardware-probe/11-adapter envelope wrappers) with direct package imports and a
compact dispatch table backed by ``ResearchStateDB`` (stdlib ``sqlite3``).
"""
from __future__ import annotations

from dataclasses import asdict
import json
import sys
from typing import Any, Callable, Mapping

from . import (
    double_blind_sanitizer,
    identity,
    meta_core,
    openreview_audit,
    pre_submission_linter,
    recompute,
    verify_work,
    watch,
)
from ._stdlib import canonical_json, normalize_identifier, thaw, validate_schema

id_mod = identity
from ._version import __version__
from .state_db import ResearchStateDB

TOOLS: list[dict[str, Any]] = [
    {"name": "research_state_ingest", "description": "Atomically ingest research artifacts & lineage edges into SQLite STRICT state.", "inputSchema": {"type": "object", "required": ["items"], "properties": {"db_path": {"type": "string"}, "items": {"type": "array"}, "atomic": {"type": "boolean"}}}},
    {"name": "research_lineage_trace", "description": "Trace transitive ancestor artifacts via SQLite recursive CTE.", "inputSchema": {"type": "object", "required": ["artifact_id"], "properties": {"db_path": {"type": "string"}, "artifact_id": {"type": "string"}}}},
    {"name": "claim_evidence_add", "description": "Register a scholarly claim with supporting/contradicting artifact anchors and acyclic dependency edges.", "inputSchema": {"type": "object", "required": ["claim_id", "claim_text"], "properties": {"db_path": {"type": "string"}, "claim_id": {"type": "string"}, "claim_text": {"type": "string"}, "status": {"type": "string"}, "evidence": {"type": "array"}, "depends_on": {"type": "array"}}}},
    {"name": "decision_record", "description": "Append an immutable research decision or negative result (enforces positive-basis E405/E406 via SQLite triggers & FK).", "inputSchema": {"type": "object", "required": ["decision_id", "title"], "properties": {"db_path": {"type": "string"}, "decision_id": {"type": "string"}, "title": {"type": "string"}, "entry_kind": {"type": "string"}, "action": {"type": "string"}, "verdict": {"type": "string"}, "basis_decision_id": {"type": "string"}, "artifact_id": {"type": "string"}}}},
    {"name": "decision_transition", "description": "Append an acyclic prune/reopen state event to a recorded decision.", "inputSchema": {"type": "object", "required": ["decision_id", "new_state", "reason"], "properties": {"db_path": {"type": "string"}, "decision_id": {"type": "string"}, "new_state": {"type": "string"}, "reason": {"type": "string"}, "superseded_by_id": {"type": "string"}}}},
    {"name": "research_object_resolve", "description": "Normalize and resolve scholarly work metadata into a deterministic identity record.", "inputSchema": {"type": "object", "required": ["record"], "properties": {"record": {"type": "object"}}}},
    {"name": "academic_recompute_statistics", "description": "Recompute t/F/chi2/z p-values, Cohen's d, CI consistency, or power.", "inputSchema": {"type": "object", "required": ["kind"], "properties": {"kind": {"type": "string"}, "params": {"type": "object"}}}},
    {"name": "academic_check_percentage", "description": "GRIM-style integer numerator/denominator consistency check for reported percentages.", "inputSchema": {"type": "object", "required": ["count", "percent"], "properties": {"count": {"type": "integer"}, "percent": {"type": "number"}, "sample_size": {"type": "integer"}, "decimals": {"type": "integer"}}}},
    {"name": "academic_table_forensics", "description": "Audit partition conservation, constant-offset ablation deltas, and storage/bandwidth bounds.", "inputSchema": {"type": "object", "properties": {"partition": {"type": "object"}, "ablation_matrix": {"type": "object"}, "storage_bandwidth": {"type": "object"}}}},
    {"name": "academic_meta_analyze", "description": "Run fixed-effect and DerSimonian-Laird random-effects meta-analysis with Egger/trim-and-fill checks.", "inputSchema": {"type": "object", "required": ["studies"], "properties": {"studies": {"type": "array"}}}},
    {"name": "academic_verify_source", "description": "Normalize DOI/arXiv/PMID or compare OpenAlex and Crossref work records.", "inputSchema": {"type": "object", "required": ["identifier"], "properties": {"identifier": {"type": "string"}, "live": {"type": "boolean"}, "openalex": {"type": "object"}, "crossref": {"type": "object"}}}},
    {"name": "academic_openreview_audit", "description": "Audit OpenReview forum notes and review rating distributions.", "inputSchema": {"type": "object", "properties": {"forum_id": {"type": "string"}, "notes": {"type": "array"}}}},
    {"name": "academic_double_blind_sanitize", "description": "Scan manuscript file or directory for double-blind anonymity leaks.", "inputSchema": {"type": "object", "required": ["target"], "properties": {"target": {"type": "string"}, "forbidden_tokens": {"type": "array"}}}},
    {"name": "academic_pre_submission_lint", "description": "Check TeX bundle for missing abstract/sections, layout tampering, uncited/missing BibTeX keys, and blind leaks.", "inputSchema": {"type": "object", "required": ["tex"], "properties": {"tex": {"type": "string"}, "venue": {"type": "string"}, "double_blind": {"type": "boolean"}}}},
    {"name": "academic_retraction_watch", "description": "Check DOI retraction/correction deltas backed by SQLite WAL state.", "inputSchema": {"type": "object", "required": ["dois"], "properties": {"dois": {"type": "array"}, "db_path": {"type": "string"}, "live": {"type": "boolean"}}}},
]


def _with_db(args: Mapping[str, Any], fn: Callable[[ResearchStateDB], Any]) -> Any:
    db = ResearchStateDB(args.get("db_path") or ":memory:")
    try:
        return thaw(fn(db))
    finally:
        db.close()


def handle_tool_call(name: str, args: Mapping[str, Any] | None = None) -> dict[str, Any]:
    a = dict(args or {})
    if name == "research_state_ingest":
        res = _with_db(a, lambda db: {"receipts": db.batch_ingest(a["items"], atomic=a.get("atomic", True)), "state_digest": db.snapshot_digest()})
        return res
    if name == "research_lineage_trace":
        return _with_db(a, lambda db: {"artifact_id": a["artifact_id"], "ancestors": db.trace_lineage(a["artifact_id"])})
    if name == "claim_evidence_add":
        ev = [tuple(x) for x in a.get("evidence", ())]
        return _with_db(a, lambda db: db.add_claim(a["claim_id"], a["claim_text"], a.get("status", "supported"), ev, a.get("depends_on", ())))
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
                metadata=a.get("metadata"),
            ),
        )
    if name == "decision_transition":
        return _with_db(a, lambda db: db.transition_decision(a["decision_id"], a["new_state"], a["reason"], a.get("superseded_by_id")))
    if name == "research_object_resolve":
        return thaw(identity.resolve_work_identity(a["record"]) if hasattr(identity, "resolve_work_identity") else normalize_identifier(str(a["record"].get("doi") or a["record"].get("title") or "")))
    if name == "academic_check_percentage":
        return recompute.check_percentage(a["count"], a["percent"], denominator=a.get("sample_size", a.get("n", a.get("denominator"))), decimals=a.get("decimals"))
    if name == "academic_recompute_statistics":
        if "params" in a and "kind" in a:
            p = dict(a["params"] or {})
            dispatch = {
                "t": recompute.p_from_t, "f": recompute.p_from_f, "chi2": recompute.p_from_chi2,
                "z": recompute.z_from_beta_se, "cohens_d": recompute.cohens_d,
                "ci": recompute.check_ci_consistency, "power": recompute.achieved_power_ttest,
            }
            return dispatch[a["kind"]](**p)
        out_stat: dict[str, Any] = {}
        if "t_stat" in a:
            r = recompute.p_from_t(a["t_stat"], a["df"], reported=a.get("p_value"))
            out_stat.update(recomputed_p=r["recomputed"], p_receipt=r)
            if "p_value" in a:
                out_stat["p_match"] = recompute.check_p_match(
                    a.get("p_value_literal", a["p_value"]), r["recomputed"]
                )
        if "f_stat" in a:
            r = recompute.p_from_f(a["f_stat"], a["df1"], a["df2"], reported=a.get("p_value"))
            out_stat.update(recomputed_f_p=r["recomputed"], f_receipt=r)
        if "chi2_stat" in a:
            r = recompute.p_from_chi2(a["chi2_stat"], a.get("chi2_df", a.get("df")), reported=a.get("p_value"))
            out_stat.update(recomputed_chi2_p=r["recomputed"], chi2_receipt=r)
        if "beta" in a and "se" in a:
            r = recompute.z_from_beta_se(a["beta"], a["se"], reported=a.get("z_value"))
            out_stat.update(recomputed_z=r["recomputed"]["z"], recomputed_z_p=r["recomputed"]["p"], z_receipt=r)
        if "ci_estimate" in a:
            out_stat["ci_consistency"] = recompute.check_ci_consistency(
                a["ci_estimate"], a["ci_lower"], a["ci_upper"],
                level=a.get("ci_level", 0.95), log_scale=a.get("ci_log_scale", False), ci_method=a.get("ci_method"),
            )
        if "cell_a" in a:
            out_stat["or_rr"] = recompute.or_rr_from_2x2(
                a["cell_a"], a["cell_b"], a["cell_c"], a["cell_d"], level=a.get("ci_level", 0.95)
            )
        if "mean1" in a:
            r = recompute.cohens_d(a["mean1"], a["sd1"], a["n1"], a["mean2"], a["sd2"], a["n2"])
            out_stat.update(r["recomputed"] if isinstance(r.get("recomputed"), dict) else r)
        if "check_sd" in a:
            out_stat["sd_possible"] = recompute.check_sd_possible(a["check_sd"], a["scale_min"], a["scale_max"], n=a.get("sample_n"))
        if "sample_df" in a:
            out_stat["sample_size_from_df"] = recompute.check_sample_size_from_df(
                a["sample_df"], a["reported_n"], kind=a.get("df_kind", "ttest_2sample"), n_params=a.get("n_params")
            )
        if "effect_size_d" in a:
            out_stat["achieved_power"] = recompute.achieved_power_ttest(
                a["effect_size_d"], a["power_n1"], n2=a.get("power_n2"), alpha=a.get("alpha", 0.05)
            )
        return out_stat
    if name == "academic_table_forensics":
        out: dict[str, Any] = {}
        if "partition" in a:
            pt = a["partition"]
            out["partition_conservation"] = recompute.check_partition_conservation(pt["total"], pt["parts"], reported_shares=pt.get("reported_shares"))
        if "ablation_matrix" in a:
            ab = a["ablation_matrix"]
            mat = ab["matrix"] if isinstance(ab, dict) else ab
            out["ablation_delta_regularity"] = recompute.check_ablation_delta_regularity(mat)
        if "storage_bandwidth" in a:
            sb = a["storage_bandwidth"]
            out["storage_bandwidth_bounds"] = recompute.check_storage_bandwidth_bounds(**sb)
        out["consistent"] = all(v.get("consistent") is True for v in out.values() if isinstance(v, dict))
        return out
    if name == "academic_meta_analyze":
        yi = [float(s["yi"]) for s in a["studies"]]
        vi = [float(s["vi"]) for s in a["studies"]]
        return {
            "study_count": len(yi),
            "fixed_effect": asdict(meta_core.pool_fixed(yi, vi)),
            "random_effects_dl": asdict(meta_core.pool_random(yi, vi)),
        }
    if name == "academic_verify_source":
        norm = normalize_identifier(a["identifier"])
        parsed = []
        if a.get("openalex"):
            parsed.append(verify_work.parse_openalex_work(a["openalex"]))
        if a.get("crossref"):
            parsed.append(verify_work.parse_crossref_work(a["crossref"]))
        if a.get("live") and norm["kind"] == "doi":
            parsed.append(verify_work.parse_openalex_work(verify_work.fetch_openalex(norm["id"])))
            parsed.append(verify_work.parse_crossref_work(verify_work.fetch_crossref(norm["id"])))
        cmp = verify_work.compare_works(parsed, target_doi=norm["id"]) if parsed else None
        return {"normalized": norm, "comparison": cmp}
    if name == "academic_openreview_audit":
        if "notes" in a:
            return openreview_audit.parse_openreview_notes(a["notes"])
        return openreview_audit.parse_openreview_notes(openreview_audit.fetch_openreview_forum(a["forum_id"]))
    if name == "academic_double_blind_sanitize":
        return double_blind_sanitizer.scan_target(a["target"], a.get("forbidden_tokens") or [])
    if name == "academic_pre_submission_lint":
        return thaw(pre_submission_linter.lint_manuscript(a["tex"], venue=a.get("venue"), double_blind=a.get("double_blind", True)))
    if name == "academic_retraction_watch":
        return {"deltas": watch.check_retraction_signals(a["dois"], db_path=a.get("db_path") or ":memory:", live=bool(a.get("live")))}
    raise ValueError(f"Unknown MCP tool: {name!r}")


def handle_rpc(req: Mapping[str, Any]) -> dict[str, Any] | None:
    method = req.get("method")
    req_id = req.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        res = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "academic-research-kernel", "version": __version__}}
        return {"jsonrpc": "2.0", "id": req_id, "result": res}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = req.get("params") or {}
        try:
            payload = handle_tool_call(str(params.get("name", "")), params.get("arguments") or {})
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": canonical_json(payload)}], "isError": False}}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps({"error": str(exc)})}], "isError": True}}
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> int:
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        resp = handle_rpc(json.loads(line))
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

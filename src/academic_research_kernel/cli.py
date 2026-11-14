"""Unified lazy-loaded CLI for academic-research-kernel (Occam edition, hardened)."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys
from typing import Any

from ._version import __version__

EXPECTED_SCHEMAS = frozenset({
    "artifact-ingestion-receipt",
    "claim-evidence-graph",
    "computation-artifact",
    "compute-receipt",
    "cross-review-artifact",
    "decision-ledger-receipt",
    "evidence-receipt",
    "ingestion-kernel-state",
    "legacy-academic-evidence",
    "lineage-receipt",
    "literature-analysis-artifact",
    "literature-delta",
    "opaque-manuscript",
    "paper-comparison",
    "paper-extraction",
    "quantitative-audit",
    "reproduction-receipt",
    "research-artifact-envelope",
    "research-documents",
    "research-object",
    "retraction-delta",
    "review-finding",
    "review-panel-spec",
    "review-result",
    "review-run-receipt",
    "systematic-review-artifact",
})


def _mod(name: str) -> Any:
    return importlib.import_module(f".{name}", __package__ or "academic_research_kernel")


def _error_hint(step: str, reason: str) -> str:
    lower = reason.lower()
    if "signature missing" in lower or "not a pdf" in lower:
        return "File is not a valid PDF; provide a real PDF or full-text HTML/XML file"
    if "budget" in lower or "too large" in lower or (
        "exceeded" in lower and any(k in lower for k in ("size", "page", "zip", "archive", "content", "file"))
    ):
        return "Input exceeds size or page budget; provide a smaller file or extract relevant sections"
    if "pypdf" in lower or "fonttools" in lower or "academic-research-kernel[research]" in lower:
        return 'Install PDF support with: pip install "academic-research-kernel[research]"'
    if "stale" in lower or "fingerprint" in lower or "changed" in lower:
        return "Materials changed; re-run: academic-research-kernel research prepare <input> --project <dir>"
    if "semantic producer" in lower or "candidate" in lower or "schema" in lower:
        return "Have your Agent read the prepared materials using audit-paper/SKILL.md and pass --candidate"
    return f'Check inputs for step "{step}" or run: academic-research-kernel doctor'


def __getattr__(name: str) -> Any:
    if name in ("metadata", "resources", "util"):
        mod = importlib.import_module(f"importlib.{name}")
        globals()[name] = mod
        return mod
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _opt_ver(mod_name: str, dist_name: str | None = None) -> str:
    self_mod = sys.modules[__name__]
    try:
        if self_mod.util.find_spec(mod_name) is None:
            return "not installed; use [research]"
    except (ImportError, ValueError):
        return "not installed; use [research]"
    try:
        return self_mod.metadata.version(dist_name or mod_name)
    except Exception:
        return "available"


def _locate_portable_skill_dir() -> Path | None:
    self_mod = sys.modules[__name__]
    for skill_name in ("audit-paper", "paper-research"):
        try:
            ref = self_mod.resources.files("academic_research_kernel").joinpath("portable_skills", skill_name)
            if ref.joinpath("SKILL.md").is_file():
                return Path(str(ref))
        except Exception:
            pass
        pkg_skill = Path(__file__).resolve().parent / "portable_skills" / skill_name
        if (pkg_skill / "SKILL.md").is_file():
            return pkg_skill
        repo_skill = Path(__file__).resolve().parents[2] / "skills" / skill_name
        if (repo_skill / "SKILL.md").is_file():
            return repo_skill
    return None


def doctor() -> dict[str, Any]:
    """Offline diagnostic check inspecting actual packaged schemas, portable skill, and dependencies."""
    import platform

    self_mod = sys.modules[__name__]
    deps: dict[str, str] = {}
    errors: list[str] = []
    for name in ("jsonschema", "numpy", "scipy", "statsmodels"):
        try:
            present = self_mod.util.find_spec(name) is not None
        except (ImportError, ValueError):
            present = False
        if present:
            try:
                deps[name] = self_mod.metadata.version(name)
            except Exception:
                deps[name] = "available"
        else:
            deps[name] = "missing"
            errors.append(f"missing {name}")

    schema_status = "error"
    schema_count = 0
    try:
        from jsonschema import Draft7Validator, Draft202012Validator

        found_files = []
        try:
            pkg_root = self_mod.resources.files("academic_research_kernel")
            sdir = pkg_root.joinpath("schemas")
            if sdir.is_dir():
                found_files = [p for p in sdir.iterdir() if p.name.endswith(".schema.json")]
        except Exception:
            local_sdir = Path(__file__).resolve().parent / "schemas"
            if local_sdir.is_dir():
                found_files = list(local_sdir.glob("*.schema.json"))
        found_names = {p.name[: -len(".schema.json")] for p in found_files}
        missing_schemas = sorted(EXPECTED_SCHEMAS - found_names)
        if missing_schemas:
            errors.append(f"missing packaged schemas: {missing_schemas[:5]}")
        else:
            for sp in found_files:
                s_obj = json.loads(sp.read_text(encoding="utf-8"))
                if "draft-07" in str(s_obj.get("$schema") or ""):
                    Draft7Validator.check_schema(s_obj)
                else:
                    Draft202012Validator.check_schema(s_obj)
            schema_status = "ok"
            schema_count = len(found_files)
    except Exception as exc:
        errors.append(f"schemas: {type(exc).__name__}: {exc}")

    skill_dir = _locate_portable_skill_dir()
    if skill_dir is not None and (skill_dir / "SKILL.md").read_text(encoding="utf-8").strip():
        portable_skill = "available"
    else:
        portable_skill = "unavailable"
        errors.append("missing portable audit-paper/SKILL.md resource")

    mcp_tools = 0
    try:
        mcp_mod = _mod("mcp_server")
        mcp_tools = len(mcp_mod.TOOLS)
        pct = mcp_mod.handle_tool_call("academic_check_percentage", {"count": 10, "percent": 50, "sample_size": 20})
        if pct.get("consistent") is not True:
            errors.append("percentage smoke check failed")
    except Exception as exc:
        errors.append(f"mcp: {type(exc).__name__}: {exc}")

    pypdf_v = _opt_ver("pypdf")
    ft_v = _opt_ver("fontTools", "fonttools")
    pdf_ready = (
        not pypdf_v.startswith("not installed")
        and not ft_v.startswith("not installed")
        and portable_skill == "available"
    )
    status = "ok" if not errors else "error"
    return {
        "version": __version__,
        "status": status,
        "python": platform.python_version(),
        "dependencies": deps,
        "schema_resources": {"status": schema_status, "count": schema_count},
        "research": {
            "pdf_ready": pdf_ready,
            "pdf_parser": pypdf_v,
            "font_decoder": ft_v,
            "portable_skill": portable_skill,
        },
        "readiness": {
            "core_verification_and_mcp": "ready" if status == "ok" else "error",
            "pdf_reading": "ready" if pdf_ready else "not ready",
        },
        "mcp_tools": mcp_tools,
        "errors": errors,
    }


def _emit_json(payload: Any, *, pretty: bool = True) -> None:
    print(json.dumps(payload, indent=2 if pretty else None, ensure_ascii=False, allow_nan=False, default=str))


def main(argv: list[str] | None = None) -> int:
    if sys.platform == "win32":
        for s in (sys.stdout, sys.stderr):
            if s and hasattr(s, "reconfigure"):
                try:
                    s.reconfigure(encoding="utf-8")
                except Exception:
                    pass
    if not (3, 10) <= sys.version_info[:2] < (3, 15):
        print("academic-research-kernel requires Python 3.10–3.14", file=sys.stderr)
        return 2

    parser = argparse.ArgumentParser(prog="academic-research-kernel", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Offline diagnostic check")
    p_doc.add_argument("--json", action="store_true")
    sub.add_parser("mcp", help="Serve stdio JSON-RPC 2.0 MCP tools")

    for vw_alias in ("verify-source", "verify-work"):
        p_ver = sub.add_parser(vw_alias, help="Normalize identifier, verify metadata, check updates, or verify PDF")
        p_ver.add_argument("identifier", nargs="?")
        p_ver.add_argument("--doi")
        p_ver.add_argument("--live", action="store_true")
        p_ver.add_argument("--offline", action="store_true")
        p_ver.add_argument("--normalize-only", action="store_true")
        p_ver.add_argument("--openalex-json")
        p_ver.add_argument("--crossref-json")
        p_ver.add_argument("--check-updates", action="store_true")
        p_ver.add_argument("--records")
        p_ver.add_argument("--rows", type=int, default=100)
        p_ver.add_argument("--max-pages", type=int, default=10)
        p_ver.add_argument("--verify-pdf")
        p_ver.add_argument("--title")
        p_ver.add_argument("--pages", type=int, default=1)
        p_ver.add_argument("--threshold", type=float, default=0.8)

    for ma_alias in ("meta-analyze", "meta-pool"):
        p_meta = sub.add_parser(ma_alias, help="Fixed & random-effects pooling + LOO + Egger/trim-and-fill")
        p_meta.add_argument("--input", required=True)

    p_tf = sub.add_parser("table-forensics", help="Audit partition conservation, ablation deltas, and bandwidth bounds")
    p_tf.add_argument("--input", required=True)

    for lint_alias in ("pre-submission-lint", "lint-submission"):
        p_lint = sub.add_parser(lint_alias, help="Lint TeX manuscript bundle")
        p_lint.add_argument("tex_pos", nargs="?")
        p_lint.add_argument("--tex", dest="tex_opt")
        p_lint.add_argument("--venue", default="iclr")
        p_lint.add_argument("--phase", choices=["submission", "rebuttal", "camera_ready"], default="submission")
        p_lint.add_argument("--contribution-type", "--track", dest="contribution_type", default="general_empirical")
        p_lint.add_argument("--no-blind", action="store_true")
        p_lint.add_argument("--pdf")
        p_lint.add_argument("--ceg")
        p_lint.add_argument("--require-ceg-binding", action="store_true")
        p_lint.add_argument("--check-academic-style", action="store_true")
        p_lint.add_argument("--output")

    for sb_alias in ("sanitize-blind", "double-blind-sanitize", "sanitize-submission"):
        p_san = sub.add_parser(sb_alias, help="Scan manuscript for double-blind anonymity leaks")
        p_san.add_argument("target_pos", nargs="?")
        p_san.add_argument("--target", dest="target_opt")
        p_san.add_argument("--forbidden-token", action="append", default=[])

    for ltx_alias in ("receipt-to-latex", "generate-table"):
        p_ltx = sub.add_parser(ltx_alias, help="Render booktabs LaTeX table from JSON spec or research artifact")
        p_ltx.add_argument("input_pos", nargs="?")
        p_ltx.add_argument("--input", dest="input_opt")
        p_ltx.add_argument("--from-research", choices=["extraction", "results", "comparison"])
        p_ltx.add_argument("--left-extraction")
        p_ltx.add_argument("--right-extraction")
        p_ltx.add_argument("--rows")
        p_ltx.add_argument("--cols")
        p_ltx.add_argument("--output")
        p_ltx.add_argument("--caption")
        p_ltx.add_argument("--label")
        p_ltx.add_argument("--format", choices=["auto", "json", "tex"], default="auto")

    for vt_alias in ("venue-template", "check-venue"):
        p_vt = sub.add_parser(vt_alias, help="List venue contracts, scaffold workspace, verify styles, or export CEG anchors")
        p_vt.add_argument("--list", "--list-venues", dest="list", action="store_true")
        p_vt.add_argument("--action", choices=["list", "list-venues", "scaffold", "verify-styles", "export-ceg-anchors"], default="list-venues")
        p_vt.add_argument("--workspace-dir")
        p_vt.add_argument("--slug")
        p_vt.add_argument("--venue", default="iclr")
        p_vt.add_argument("--year", type=int, default=2027)
        p_vt.add_argument("--contribution-type", default="general_empirical")
        p_vt.add_argument("--force", action="store_true")
        p_vt.add_argument("--manuscript-dir")
        p_vt.add_argument("--ceg", "--export-ceg-anchors", dest="ceg")

    p_rc = sub.add_parser("repro-checklist", help="Adjudicate 14-stage reproducibility checklist")
    p_rc.add_argument("input_pos", nargs="?")
    p_rc.add_argument("--input", dest="input_opt")
    p_rc.add_argument("-o", "--out")
    p_rc.add_argument("--evidence-receipt")
    p_rc.add_argument("--generated-at")
    p_rc.add_argument("--pretty", action="store_true")

    p_rw = sub.add_parser("retraction-watch", help="SQLite-backed DOI retraction delta watcher")
    p_rw.add_argument("--watchlist")
    p_rw.add_argument("--dois", help="comma-separated DOI list alternative to --watchlist")
    p_rw.add_argument("--db", "--state", "--state-db", dest="db", default=":memory:")
    p_rw.add_argument("--import-legacy-json")
    p_rw.add_argument("--live", "--run", dest="live", action="store_true")
    p_rw.add_argument("--self-test", action="store_true")

    p_lw = sub.add_parser("literature-watch", help="SQLite-backed bounded incremental literature watcher")
    p_lw.add_argument("--watchlist")
    p_lw.add_argument("--db", "--state", "--state-db", dest="db", default=":memory:")
    p_lw.add_argument("--import-legacy-json")
    p_lw.add_argument("--live", "--run", dest="live", action="store_true")
    p_lw.add_argument("--days", type=int, default=7)
    p_lw.add_argument("--self-test", action="store_true")

    p_bib = sub.add_parser("bibliography", help="Convert formats, export BibTeX, deduplicate, merge layers, build citation graph, or render matrix")
    p_bib.add_argument("--action", choices=["convert", "export-bibtex", "deduplicate", "collect-corpus", "citation-graph", "review-matrix"], default="convert")
    p_bib.add_argument("--from", dest="src_fmt", choices=["bibtex", "ris", "csl", "crossref", "openalex"])
    p_bib.add_argument("--to", dest="dst_fmt", choices=["bibtex", "ris", "csl", "canonical"])
    p_bib.add_argument("--input")
    p_bib.add_argument("--source", choices=["crossref", "openalex"], default="crossref")
    p_bib.add_argument("--doi")
    p_bib.add_argument("--related-of")
    p_bib.add_argument("--wid")
    p_bib.add_argument("--per-page", type=int, default=25)
    p_bib.add_argument("--pages", type=int, default=4)
    p_bib.add_argument("--query")
    p_bib.add_argument("--date")

    p_cc = sub.add_parser("collect-corpus", help="Merge multi-layer candidate search exports or query OpenAlex concepts/related works")
    p_cc.add_argument("--input")
    p_cc.add_argument("--query")
    p_cc.add_argument("--per-page", type=int, default=10)
    p_cc.add_argument("--related-of")

    p_rf = sub.add_parser("repo-forensics", help="Classify repository Python composition (core vs vendored vs tests)")
    p_rf.add_argument("repo_dir", nargs="?")
    p_rf.add_argument("--local-repo", "--repo-dir", dest="local_repo")
    p_rf.add_argument("--tree-json")
    p_rf.add_argument("--github-repo")

    p_or = sub.add_parser("openreview-audit", help="Audit OpenReview notes JSON, mirror list, or live forum")
    p_or.add_argument("--forum-id", "--forum", dest="forum_id")
    p_or.add_argument("--input-json")
    p_or.add_argument("--mirror-json", "--mirror", dest="mirror_json")
    p_or.add_argument("--venue-stats", "--venue-summary", dest="venue_stats")
    p_or.add_argument("--topic-regex")

    p_oa = sub.add_parser("locate-oa", help="Locate open-access full text across arXiv, Unpaywall, OpenAlex, Semantic Scholar, and Europe PMC")
    p_oa.add_argument("identifier", nargs="?")
    p_oa.add_argument("--doi")
    p_oa.add_argument("--arxiv")
    p_oa.add_argument("--email", default=None)
    p_oa.add_argument("--fallback-openalex", action="store_true")
    p_oa.add_argument("--fallback-all", action="store_true")

    for cr_alias in ("cross-review", "review-panel"):
        p_cr = sub.add_parser(cr_alias, help="Multi-model sparse deliberation: blind plan, issue clustering, anonymous challenge, and minority-protected synthesis")
        p_cr.add_argument("stream_dir", nargs="?")
        p_cr.add_argument("--stream", dest="stream_opt")
        p_cr.add_argument("--stage", choices=["plan", "merge", "challenge", "synthesize", "all", "status", "pairings"], default="status")
        p_cr.add_argument("--mode", choices=["economy", "standard", "audit"], default="standard")
        p_cr.add_argument("--task")
        p_cr.add_argument("--models")
        p_cr.add_argument("--models-file")
        p_cr.add_argument("--timeout", type=int, default=900)

    p_cp = sub.add_parser("compute-probe", help="Probe CPU/GPU hardware, thread environment, numerical libraries, and optional ComputeReceipt")
    p_cp.add_argument("--receipt", action="store_true")
    p_cp.add_argument("--measure-candidates", action="store_true")
    p_cp.add_argument("--operation", default="matmul_f64")
    p_cp.add_argument("--scale", choices=["small", "medium", "large"], default="small")
    p_cp.add_argument("--dtype", choices=["float32", "float64"], default=None)
    p_cp.add_argument("--output")

    p_lg = sub.add_parser("ledger", help="Manage SQLite-backed Claim-Evidence Graph (CEG) and Research Decision Ledger")
    p_lg.add_argument("--db", "--state-db", dest="db", required=True)
    p_lg.add_argument(
        "--action",
        choices=[
            "register-artifact",
            "add-claim",
            "export-ceg",
            "validate-ceg",
            "trace-claim",
            "link-claims",
            "record-decision",
            "transition-decision",
            "correct-decision",
            "export-decisions",
            "trace-decision",
            "validate-decisions",
        ],
        required=True,
    )
    p_lg.add_argument("--claim-id")
    p_lg.add_argument("--target-claim-id")
    p_lg.add_argument("--relation", choices=["depends_on", "refines", "contradicts", "corroborates", "cites"], default="depends_on")
    p_lg.add_argument("--text")
    p_lg.add_argument("--claim-type", default="empirical_finding")
    p_lg.add_argument("--artifact-id")
    p_lg.add_argument("--artifact-kind", default="computed_evidence")
    p_lg.add_argument("--payload-json")
    p_lg.add_argument("--payload-file")
    p_lg.add_argument("--locator", default="")
    p_lg.add_argument("--stance", choices=["supports", "contradicts", "qualifies", "contextualizes"], default="supports")
    p_lg.add_argument("--decision-id")
    p_lg.add_argument("--basis-decision-id")
    p_lg.add_argument("--title")
    p_lg.add_argument("--rationale", "--reason", dest="rationale")
    p_lg.add_argument("--status", default="active")
    p_lg.add_argument("--verdict", choices=["positive", "negative", "inconclusive", "unverifiable"], default="inconclusive")
    p_lg.add_argument("--is-negative-result", action="store_true")
    p_lg.add_argument("--superseded-by")
    p_lg.add_argument("--output")

    p_res = sub.add_parser("research", help="Prepare/finish/replay/compare/skill paper research workflow")
    rsub = p_res.add_subparsers(dest="step", required=True)
    rp_prep = rsub.add_parser("prepare")
    rp_prep.add_argument("input")
    rp_prep.add_argument("--project", required=True)
    rp_fin = rsub.add_parser("finish")
    rp_fin.add_argument("--project", required=True)
    rp_fin.add_argument("--candidate", required=True)
    rp_rep = rsub.add_parser("replay")
    rp_rep.add_argument("--project", required=True)
    rp_cmp = rsub.add_parser("compare")
    rp_cmp.add_argument("left")
    rp_cmp.add_argument("right")
    rp_cmp.add_argument("--analysis", required=True)
    rp_cmp.add_argument("--output", required=True)
    rp_sk = rsub.add_parser("skill")
    rp_sk.add_argument("--output", required=True)

    args = parser.parse_args(argv)
    cmd = args.command

    if cmd == "mcp":
        return _mod("mcp_server").main()
    if cmd == "doctor":
        rep = doctor()
        if args.json:
            _emit_json(rep)
        else:
            print(f"academic-research-kernel {__version__}: {rep['status']}")
            for k, v in rep.items():
                if k not in ("version", "status"):
                    print(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        return 0 if rep["status"] == "ok" else 1

    try:
        from dataclasses import asdict
        import hashlib
        from importlib import resources
        from ._stdlib import normalize_doi, normalize_identifier, safe_path, thaw

        if cmd in ("verify-source", "verify-work"):
            modes = sum([bool(args.normalize_only), bool(args.check_updates), bool(args.verify_pdf)])
            if modes > 1:
                raise ValueError("--normalize-only, --check-updates, and --verify-pdf are mutually exclusive")
            if args.verify_pdf:
                vpi = _mod("verify_pdf_identity")
                doi_val = args.doi or args.identifier
                if not args.title and not doi_val:
                    raise ValueError("verify-source --verify-pdf requires --title and/or --doi")
                page_txt = vpi.read_pdf(safe_path(args.verify_pdf), max_pages=args.pages)
                res_pdf: dict[str, Any] = {"pdf": str(args.verify_pdf), "pages_inspected": args.pages}
                ok = True
                if args.title:
                    tc = vpi.compare_title(args.title, page_txt, threshold=args.threshold)
                    res_pdf["title_check"] = tc
                    ok = ok and bool(tc.get("matched", tc.get("passed", True)))
                if doi_val:
                    dc = vpi.find_doi(doi_val, page_txt)
                    res_pdf["doi_check"] = dc
                    ok = ok and bool(dc.get("matched", dc.get("found", True)))
                res_pdf["verified"] = ok
                _emit_json(res_pdf)
                return 0 if ok else 1

            raw_id = args.doi or args.identifier
            if not raw_id:
                raise ValueError("verify-source requires an identifier or --verify-pdf")
            if args.check_updates:
                cu = _mod("check_updates")
                if args.offline and not args.records:
                    raise ValueError("--offline with --check-updates requires --records")
                recs = cu._load_records(safe_path(args.records)) if args.records else cu.live_reverse_lookup(normalize_doi(raw_id), args.rows, args.max_pages)
                sigs = cu.update_signals(normalize_doi(raw_id), recs)
                _emit_json(cu.summarize_signals(sigs))
                return 0

            norm = normalize_identifier(raw_id)
            if args.normalize_only or norm["type"] != "doi":
                _emit_json(norm)
                return 0 if norm["type"] != "unknown" else 1
            oa = json.loads(safe_path(args.openalex_json).read_text("utf-8")) if args.openalex_json else None
            cr = json.loads(safe_path(args.crossref_json).read_text("utf-8")) if args.crossref_json else None
            use_live = bool(args.live) and not bool(args.offline)
            if not args.offline and oa is None and cr is None and not args.live:
                use_live = True
            out = _mod("mcp_server").handle_tool_call(
                "academic_verify_source",
                {"identifier": raw_id, "live": use_live, "offline": args.offline, "openalex": oa, "crossref": cr},
            )
            _emit_json(out)
            if args.offline or oa is not None or cr is not None:
                return 0
            return 0 if any(s.get("status") == "ok" for s in (out.get("sources") or {}).values()) else 1

        if cmd in ("meta-analyze", "meta-pool"):
            raw = json.loads(safe_path(args.input).read_text("utf-8"))
            studies = raw["studies"] if isinstance(raw, dict) and "studies" in raw else raw
            if not isinstance(studies, list) or not studies:
                raise ValueError("meta-analyze input must contain a non-empty 'studies' list")
            out = _mod("mcp_server").handle_tool_call("academic_meta_analyze", {"studies": studies})
            _emit_json(out)
            return 0

        if cmd == "table-forensics":
            spec = json.loads(safe_path(args.input).read_text("utf-8"))
            out = _mod("mcp_server").handle_tool_call("academic_table_forensics", spec)
            _emit_json(out)
            return 0 if out.get("consistent") is not False else 1

        if cmd in ("pre-submission-lint", "lint-submission"):
            tex_target = args.tex_opt or args.tex_pos
            if not tex_target:
                raise ValueError(f"{cmd} requires a positional TeX path or --tex")
            psl = _mod("pre_submission_linter")
            out = thaw(
                psl.lint_manuscript(
                    tex_target,
                    venue=args.venue,
                    double_blind=(False if args.no_blind else None),
                    phase=args.phase,
                    contribution_type=args.contribution_type,
                    pdf_path=args.pdf,
                    ceg_path=args.ceg,
                    require_ceg_binding=args.require_ceg_binding,
                    check_academic_style=args.check_academic_style,
                )
            )
            if args.output:
                out_p = safe_path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            _emit_json(out)
            return 0 if out["passed"] else 1

        if cmd in ("sanitize-blind", "double-blind-sanitize", "sanitize-submission"):
            target = args.target_opt or args.target_pos
            if not target:
                raise ValueError(f"{cmd} requires a target path or --target")
            dbs = _mod("double_blind_sanitizer")
            out = dbs.scan_target(Path(target), forbidden_tokens=args.forbidden_token)
            _emit_json(out)
            has_leaks = bool(out.get("findings")) or out.get("status") not in ("clean", "ok")
            return 1 if has_leaks else 0

        if cmd in ("receipt-to-latex", "generate-table"):
            src_in = args.input_opt or args.input_pos
            if not src_in:
                raise ValueError(f"{cmd} requires an input path or --input")
            rlt = _mod("receipt_to_latex_table")
            in_path = safe_path(src_in)
            raw_bytes = in_path.read_bytes()
            sha = hashlib.sha256(raw_bytes).hexdigest()
            data = json.loads(raw_bytes.decode("utf-8"))
            if args.from_research:
                left_ex = json.loads(safe_path(args.left_extraction).read_text("utf-8")) if args.left_extraction else None
                right_ex = json.loads(safe_path(args.right_extraction).read_text("utf-8")) if args.right_extraction else None
                spec = rlt.convert_research_artifact_to_spec(
                    data,
                    args.from_research,
                    caption=args.caption,
                    label=args.label,
                    left_extraction=left_ex,
                    right_extraction=right_ex,
                )
            else:
                spec = dict(data) if isinstance(data, dict) else data
                if isinstance(spec, dict):
                    if args.rows and "rows" not in spec:
                        cur_val: Any = spec
                        for part in args.rows.split("."):
                            cur_val = cur_val.get(part) if isinstance(cur_val, dict) else None
                        if isinstance(cur_val, list):
                            spec["rows"] = cur_val
                    if args.cols:
                        if args.cols in spec and isinstance(spec[args.cols], list):
                            spec["columns"] = spec[args.cols]
                        else:
                            col_list = [c.strip() for c in args.cols.split(",") if c.strip()]
                            if col_list:
                                spec["columns"] = col_list
                    if args.caption:
                        spec["caption"] = args.caption
                    if args.label:
                        spec["label"] = args.label
            tex_str = rlt.render_booktabs_table(spec, source_sha256=sha)
            if args.output:
                out_p = safe_path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(tex_str + "\n", encoding="utf-8")
            emit_fmt = args.format
            if emit_fmt == "json" or (emit_fmt == "auto" and cmd == "receipt-to-latex"):
                rows_list = spec.get("rows") if isinstance(spec, dict) and isinstance(spec.get("rows"), list) else []
                cols_list = spec.get("columns") if isinstance(spec, dict) and isinstance(spec.get("columns"), list) else []
                col_cnt = len(cols_list) if cols_list else (len(rows_list[0]) if rows_list and isinstance(rows_list[0], (list, tuple, dict)) else 0)
                _emit_json(
                    {
                        "status": "ok",
                        "source_sha256": sha,
                        "row_count": len(rows_list),
                        "col_count": col_cnt,
                        "latex": tex_str if tex_str.endswith("\n") else tex_str + "\n",
                    }
                )
            else:
                print(tex_str)
            return 0

        if cmd in ("venue-template", "check-venue"):
            vtm = _mod("venue_template_manager")
            raw_act = "list-venues" if args.action == "list" else args.action
            act = "list-venues" if args.list else ("export-ceg-anchors" if (args.ceg and raw_act == "list-venues") else raw_act)
            if act == "list-venues":
                _emit_json(vtm.list_venues())
                return 0
            if act == "scaffold":
                if not args.workspace_dir or not args.slug:
                    raise ValueError("venue-template --action scaffold requires --workspace-dir and --slug")
                created = vtm.scaffold_manuscript(
                    args.workspace_dir,
                    args.slug,
                    venue=args.venue,
                    year=args.year,
                    contribution_type=args.contribution_type,
                    force=args.force,
                )
                _emit_json({"status": "scaffolded", "manuscript_dir": str(created)})
                return 0
            if act == "verify-styles":
                if not args.manuscript_dir:
                    raise ValueError("venue-template --action verify-styles requires --manuscript-dir")
                _emit_json(vtm.verify_style_directory(args.manuscript_dir))
                return 0
            if not args.ceg:
                raise ValueError("venue-template --action export-ceg-anchors requires --ceg")
            _emit_json(vtm.export_ceg_anchors(args.ceg))
            return 0

        if cmd == "repro-checklist":
            rc_in = args.input_opt or args.input_pos
            rc = _mod("repro_checklist")
            if not rc_in or rc_in == "-":
                if sys.stdin is None or sys.stdin.isatty():
                    raise ValueError("repro-checklist requires an input file path, --input, or piped JSON on stdin")
                raw_stdin = sys.stdin.read(10 * 1024 * 1024 + 1)
                if len(raw_stdin) > 10 * 1024 * 1024:
                    raise ValueError("repro-checklist stdin exceeds 10 MiB limit")
                checklist = json.loads(raw_stdin)
            else:
                checklist = json.loads(safe_path(rc_in).read_text("utf-8"))
            if args.evidence_receipt:
                ev = json.loads(safe_path(args.evidence_receipt).read_text("utf-8"))
                checklist = rc.merge_evidence_receipt(checklist, ev)
            res = rc.adjudicate(rc.normalize(checklist), generated_at=args.generated_at)
            out_dict = asdict(res) if hasattr(res, "__dataclass_fields__") else (res.to_dict() if hasattr(res, "to_dict") else res)
            if args.out:
                out_p = safe_path(args.out)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(json.dumps(out_dict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            _emit_json(out_dict, pretty=bool(args.pretty or True))
            return 0

        if cmd == "retraction-watch":
            wmod = _mod("watch")
            if args.db != ":memory:" and str(args.db).lower().endswith(".json"):
                raise ValueError("v3.0.0 uses SQLite state (--state-db watch.sqlite3); migrate legacy JSON once with --import-legacy-json")
            if args.import_legacy_json:
                from .state_db import ResearchStateDB

                legacy_data = json.loads(safe_path(args.import_legacy_json, must_exist=True).read_text("utf-8"))
                with ResearchStateDB(args.db) as db:
                    mig = db.import_legacy_watch_json("retraction", legacy_data)
                if not args.self_test and not args.watchlist and not args.dois:
                    _emit_json(mig)
                    return 0
            if args.self_test:
                rep = wmod.check_retraction_report(
                    ["10.1000/selftest"],
                    db_path=":memory:",
                    mock_records={"10.1000/selftest": (True, ["retraction(publisher) update-doi=10.1000/notice"])},
                )
                _emit_json({"self_test": "passed" if len(rep["deltas"]) == 1 else "failed", "report": rep})
                return 0 if len(rep["deltas"]) == 1 else 1
            if args.dois:
                doi_list = [d.strip() for d in args.dois.split(",") if d.strip()]
            elif args.watchlist:
                doi_list = wmod.load_watchlist(args.watchlist)["dois"]
            else:
                raise ValueError("retraction-watch requires --watchlist, --dois, --import-legacy-json, or --self-test")
            _emit_json(wmod.check_retraction_report(doi_list, db_path=args.db, live=args.live))
            return 0

        if cmd == "literature-watch":
            wmod = _mod("watch")
            if args.db != ":memory:" and str(args.db).lower().endswith(".json"):
                raise ValueError("v3.0.0 uses SQLite state (--state-db watch.sqlite3); migrate legacy JSON once with --import-legacy-json")
            if args.import_legacy_json:
                from .state_db import ResearchStateDB

                legacy_data = json.loads(safe_path(args.import_legacy_json, must_exist=True).read_text("utf-8"))
                with ResearchStateDB(args.db) as db:
                    mig = db.import_legacy_watch_json("literature", legacy_data)
                if not args.self_test and not args.watchlist:
                    _emit_json(mig)
                    return 0
            if args.self_test:
                rep = wmod.run_literature_watch(
                    {"dois": [], "topics": ["test"], "authors": []},
                    db_path=":memory:",
                    fixture_works=[{"doi": "10.1000/lit1", "title": "Paper 1", "publication_year": 2026}],
                )
                _emit_json({"self_test": "passed" if rep["new_count"] == 1 else "failed", "report": rep})
                return 0 if rep["new_count"] == 1 else 1
            if not args.watchlist:
                raise ValueError("literature-watch requires --watchlist (or --self-test)")
            wl = wmod.load_watchlist(args.watchlist)
            _emit_json(wmod.run_literature_watch(wl, db_path=args.db, live=args.live, days=args.days))
            return 0

        if cmd == "collect-corpus" or (cmd == "bibliography" and args.action == "collect-corpus"):
            cc = _mod("collect_corpus")
            layers: dict[str, Any] = {}
            if args.input:
                loaded_layers = json.loads(safe_path(args.input, must_exist=True).read_text("utf-8"))
                if not isinstance(loaded_layers, dict):
                    raise ValueError("collect-corpus --input must map layer names to work lists")
                layers.update(loaded_layers)
            if getattr(args, "query", None):
                layers["text-search"] = cc.live_search(args.query, per_page=args.per_page)
            if getattr(args, "related_of", None):
                w_main = cc.live_work(normalize_doi(args.related_of))
                layers["algorithmic-related"] = [{"id": rid} for rid in (w_main.get("related_works") or [])]
                layers.setdefault("target-work", [w_main])
            if not layers:
                raise ValueError("collect-corpus requires --input, --query, or --related-of")
            merged = cc.merge_candidates(layers)
            merged["status"] = "ok"
            _emit_json(merged)
            return 0

        if cmd == "bibliography":
            act = args.action
            if act == "export-bibtex":
                eb = _mod("export_bibtex")
                if args.input:
                    works = eb._load_works(safe_path(args.input), args.source)
                    entries = [eb.openalex_to_entry(w) if args.source == "openalex" else eb.crossref_to_entry(w) for w in works]
                elif args.doi:
                    entries = [eb.crossref_to_entry(eb.live_crossref(normalize_doi(args.doi)))]
                else:
                    raise ValueError("bibliography --action export-bibtex requires --input or --doi")
                print("\n\n".join(eb.format_entry(e) for e in entries))
                return 0
            if act == "deduplicate":
                if not args.input:
                    raise ValueError("bibliography --action deduplicate requires --input")
                dd = _mod("deduplicate_works")
                raw = json.loads(safe_path(args.input).read_text("utf-8"))
                items = raw if isinstance(raw, list) else raw.get("works", raw.get("results", [raw]))
                _emit_json(dd.deduplicate_works(items))
                return 0
            if act == "citation-graph":
                cg = _mod("build_citation_graph")
                if args.input:
                    raw = json.loads(safe_path(args.input).read_text("utf-8"))
                    works = raw if isinstance(raw, list) else raw.get("results", raw.get("works", [raw]))
                elif args.wid:
                    works = cg.live_citation_pool(args.wid, args.per_page, args.pages)
                else:
                    raise ValueError("bibliography --action citation-graph requires --input or --wid")
                graph = cg.build_graph(works)
                _emit_json({"graph": graph, "in_degrees": cg.in_degrees(graph)})
                return 0
            if act == "review-matrix":
                if not args.input:
                    raise ValueError("bibliography --action review-matrix requires --input")
                rm = _mod("build_review_matrix")
                raw = json.loads(safe_path(args.input).read_text("utf-8"))
                works = raw if isinstance(raw, list) else raw.get("results", raw.get("works", [raw]))
                rows = rm.matrix_rows(works)
                print(rm.render_markdown(rows, {"query": args.query or "local", "date": args.date or "unspecified", "count": len(rows)}))
                return 0

            if not args.src_fmt or not args.dst_fmt or not args.input:
                raise ValueError("bibliography --action convert requires --from, --to, and --input")
            iop = _mod("interop")
            eb = _mod("export_bibtex")
            txt = safe_path(args.input).read_text("utf-8")
            if args.src_fmt == "bibtex":
                works = iop.from_bibtex(txt)
            elif args.src_fmt == "ris":
                works = iop.from_ris(txt)
            elif args.src_fmt == "csl":
                data = json.loads(txt)
                items = data if isinstance(data, list) else [data]
                works = [iop.from_csl_json(x) for x in items]
            elif args.src_fmt == "crossref":
                data = json.loads(txt)
                items = data if isinstance(data, list) else [data.get("message", data) if isinstance(data, dict) else data]
                works = [iop.from_crossref_json(x) for x in items]
            else:
                data = json.loads(txt)
                items = data if isinstance(data, list) else (data.get("results", [data]) if isinstance(data, dict) else [data])
                works = [iop.from_openalex_json(x) for x in items]

            if args.dst_fmt == "bibtex":
                print("\n\n".join(eb.protect_acronyms(iop.to_bibtex(w)) for w in works))
                return 0
            if args.dst_fmt == "ris":
                print("\n\n".join(iop.to_ris(w) for w in works))
                return 0
            if args.dst_fmt == "csl":
                _emit_json([iop.to_csl_json(w) for w in works])
                return 0
            _emit_json([asdict(w) for w in works])
            return 0

        if cmd == "repo-forensics":
            rf = _mod("github_repo_forensics")
            local_dir = args.local_repo or args.repo_dir
            if args.tree_json:
                tj = json.loads(safe_path(args.tree_json).read_text("utf-8"))
                if isinstance(tj, dict):
                    if "tree" not in tj or not isinstance(tj["tree"], list):
                        raise ValueError("--tree-json object must contain a 'tree' array")
                    entries = tj["tree"]
                    trunc = bool(tj.get("truncated"))
                    tree_sha = str(tj.get("sha") or "")
                else:
                    entries = tj
                    trunc = False
                    tree_sha = ""
                rep_rf = rf.analyze_entries(entries, truncated=trunc)
                rep_rf["mode"] = "tree-json"
                if tree_sha:
                    rep_rf["tree_sha"] = tree_sha
                _emit_json(rep_rf)
                return 0
            if args.github_repo:
                entries, trunc, tree_sha, mode_rf = rf.fetch_github_tree(args.github_repo)
                rep_rf = rf.analyze_entries(entries, truncated=trunc)
                rep_rf["mode"] = mode_rf
                if tree_sha:
                    rep_rf["tree_sha"] = tree_sha
                _emit_json(rep_rf)
                return 0
            if not local_dir:
                raise ValueError("repo-forensics requires a local repository directory, --tree-json, or --github-repo")
            entries = rf.scan_local_repo(safe_path(local_dir))
            rep_rf = rf.analyze_entries(entries, truncated=False)
            rep_rf["mode"] = "local-repo"
            _emit_json(rep_rf)
            return 0

        if cmd == "openreview-audit":
            ora = _mod("openreview_audit")
            if args.venue_stats:
                recs = json.loads(safe_path(args.venue_stats, must_exist=True).read_text("utf-8"))
                _emit_json(ora.summarize_venue_mirror(recs, topic_regex=args.topic_regex))
                return 0
            if args.input_json:
                payload = json.loads(safe_path(args.input_json, must_exist=True).read_text("utf-8"))
                _emit_json(ora.parse_openreview_notes(payload, forum_id=args.forum_id))
                return 0
            if args.mirror_json and not args.forum_id:
                raise ValueError("--mirror-json requires --forum-id")
            if args.forum_id:
                _emit_json(ora.audit_forum(args.forum_id, mirror_path=args.mirror_json))
                return 0
            raise ValueError("openreview-audit requires --forum-id, --input-json, --mirror-json, or --venue-stats")

        if cmd == "locate-oa":
            loa = _mod("locate_oa")
            raw_target = args.arxiv or args.doi or args.identifier
            if not raw_target:
                raise ValueError("locate-oa requires an identifier, --doi, or --arxiv")
            norm = normalize_identifier(raw_target if not args.arxiv else f"arxiv:{args.arxiv}")
            rc_oa, rep_oa = loa.resolve_oa(
                norm,
                email=args.email,
                fallback_openalex=bool(args.fallback_openalex),
                fallback_all=bool(args.fallback_all),
            )
            _emit_json(rep_oa)
            return 0 if rc_oa in (0, 2) else rc_oa

        if cmd in ("cross-review", "review-panel"):
            cr = _mod("cross_review")
            if args.stage == "pairings":
                parts = cr.parse_participants(args.models, args.models_file)
                _emit_json({"pairings": [{"reviewer": r, "target": t} for r, t in cr.pairings([p.id for p in parts])]})
                return 0
            raw_stream = args.stream_opt or args.stream_dir
            if not raw_stream:
                raise ValueError(f"{cmd} requires a stream directory positional argument or --stream")
            sdir = safe_path(raw_stream)
            if args.stage == "status":
                _emit_json(cr.stage_status(sdir))
                return 0
            parts = cr.parse_participants(args.models, args.models_file) or cr.discover_stream_participants(sdir)
            plan_failed = False
            chal_failed = False
            if args.stage in ("plan", "all"):
                if not args.task:
                    raise ValueError(f"{cmd} --stage {args.stage} requires --task")
                plan_res = cr.stage_plan(sdir, safe_path(args.task, must_exist=True), parts, timeout_s=args.timeout)
                plan_failed = bool(not plan_res.get("succeeded") or plan_res.get("missing_models"))
                if args.stage == "plan":
                    _emit_json(plan_res)
                    return 0 if plan_res.get("succeeded") and not plan_res.get("missing_models") else 1
                if not plan_res.get("succeeded"):
                    _emit_json(plan_res)
                    return 1
            if args.stage in ("merge", "all"):
                merge_res = cr.stage_merge(sdir, parts, mode=args.mode)
                if args.stage == "merge":
                    _emit_json(merge_res)
                    return 0
            if args.stage in ("challenge", "all"):
                task_ref = safe_path(args.task, must_exist=True) if args.task else (sdir / "run-manifest.json")
                chal_res = cr.stage_challenge(sdir, task_ref, parts, timeout_s=args.timeout)
                chal_failed = bool(chal_res.get("replied", 0) < chal_res.get("total", 0))
                if args.stage == "challenge":
                    _emit_json(chal_res)
                    return 0 if not chal_failed else 1
            syn_res = cr.stage_synthesize(sdir)
            _emit_json(syn_res)
            return 1 if (plan_failed or chal_failed) else 0

        if cmd == "compute-probe":
            cp = _mod("compute_probe")
            out_cp = (
                cp.build_compute_receipt(
                    operation=args.operation,
                    scale=args.scale,
                    dtype=args.dtype,
                    measure_candidates=bool(args.measure_candidates),
                )
                if args.receipt
                else cp.probe()
            )
            if args.output:
                out_p = safe_path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(json.dumps(out_cp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            _emit_json(out_cp)
            return 0

        if cmd == "ledger":
            from .state_db import ResearchStateDB

            mcp_m = _mod("mcp_server")
            act_l = args.action
            if act_l == "register-artifact":
                if not args.artifact_id:
                    raise ValueError("ledger --action register-artifact requires --artifact-id and (--payload-json or --payload-file)")
                if args.payload_file:
                    art_payload = json.loads(safe_path(args.payload_file, must_exist=True).read_text("utf-8"))
                elif args.payload_json:
                    art_payload = json.loads(args.payload_json)
                else:
                    raise ValueError("ledger --action register-artifact requires --payload-json or --payload-file")
                with ResearchStateDB(args.db) as db:
                    res_art = thaw(db.register_artifact(args.artifact_id, args.artifact_kind, art_payload))
                _emit_json(res_art)
                return 0

            def _ensure_registered_artifact(db: ResearchStateDB, aid: str) -> None:
                with db._read_snapshot() as conn:
                    has_art = conn.execute("SELECT 1 FROM artifacts WHERE artifact_id = ?", (aid,)).fetchone()
                if has_art is None:
                    if args.payload_file or args.payload_json:
                        art_payload = (
                            json.loads(safe_path(args.payload_file, must_exist=True).read_text("utf-8"))
                            if args.payload_file
                            else json.loads(args.payload_json)
                        )
                        db.register_artifact(aid, args.artifact_kind, art_payload)
                    else:
                        raise ValueError(
                            f"Unknown artifact_id {aid!r}; register empirical evidence artifact first via --action register-artifact (or supply --payload-json / --payload-file)"
                        )

            if act_l == "add-claim":
                if not args.claim_id or not args.text:
                    raise ValueError("ledger --action add-claim requires --claim-id and --text")
                st_norm = "qualifies" if args.stance == "contextualizes" else args.stance
                with ResearchStateDB(args.db) as db:
                    ev_tuples: list[tuple[str, str, str]] = []
                    if args.artifact_id:
                        _ensure_registered_artifact(db, args.artifact_id)
                        ev_tuples.append((args.artifact_id, st_norm, args.locator or ""))
                    res_c = thaw(db.add_claim(args.claim_id, args.text, evidence=ev_tuples, metadata={"claim_type": args.claim_type}))
                _emit_json(res_c)
                return 0
            if act_l == "link-claims":
                if not args.claim_id or not args.target_claim_id:
                    raise ValueError("ledger --action link-claims requires --claim-id and --target-claim-id")
                with ResearchStateDB(args.db) as db:
                    res_lc = thaw(db.add_claim_relation(args.claim_id, args.target_claim_id, args.relation))
                _emit_json(res_lc)
                return 0
            if act_l == "export-ceg":
                with ResearchStateDB(args.db) as db:
                    exported = thaw(db.export_ceg_dict())
                if args.output:
                    out_p = safe_path(args.output)
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    out_p.write_text(json.dumps(exported, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                _emit_json(exported)
                return 0
            if act_l == "validate-ceg":
                with ResearchStateDB(args.db) as db:
                    exported = thaw(db.export_ceg_dict())
                res_v = mcp_m.handle_tool_call("claim_evidence_validate", {"ceg": exported})
                _emit_json(res_v)
                return 0 if res_v.get("valid") else 1
            if act_l == "trace-claim":
                if not args.claim_id:
                    raise ValueError("ledger --action trace-claim requires --claim-id")
                _emit_json(mcp_m.handle_tool_call("claim_evidence_trace", {"db_path": args.db, "claim_id": args.claim_id}))
                return 0
            if act_l == "record-decision":
                if not args.decision_id or not args.title:
                    raise ValueError("ledger --action record-decision requires --decision-id and --title")
                st_init = "pruned" if args.status in ("abandoned", "rejected") else args.status
                with ResearchStateDB(args.db) as db:
                    if args.artifact_id:
                        _ensure_registered_artifact(db, args.artifact_id)
                    ek = "negative_result" if args.is_negative_result else "decision"
                    act_kind = "negative_result" if args.is_negative_result else "explore"
                    res_d = thaw(
                        db.record_decision(
                            args.decision_id,
                            args.title,
                            entry_kind=ek,
                            action=act_kind,
                            verdict=args.verdict,
                            basis_decision_id=args.basis_decision_id,
                            artifact_id=args.artifact_id,
                            initial_state=st_init,
                            metadata={"rationale": args.rationale} if args.rationale else {},
                        )
                    )
                _emit_json(res_d)
                return 0
            if act_l == "transition-decision":
                if not args.decision_id or not args.rationale:
                    raise ValueError("ledger --action transition-decision requires --decision-id, --status, and --rationale")
                st_target = "pruned" if args.status in ("abandoned", "rejected") else args.status
                with ResearchStateDB(args.db) as db:
                    res_td = thaw(db.transition_decision(args.decision_id, st_target, args.rationale, args.superseded_by))
                _emit_json(res_td)
                return 0
            if act_l == "correct-decision":
                if not args.decision_id or not args.rationale:
                    raise ValueError("ledger --action correct-decision requires --decision-id, --verdict, and --rationale")
                with ResearchStateDB(args.db) as db:
                    if args.artifact_id:
                        _ensure_registered_artifact(db, args.artifact_id)
                    res_cd = thaw(db.correct_decision_outcome(args.decision_id, args.verdict, args.rationale, args.artifact_id))
                _emit_json(res_cd)
                return 0
            if act_l == "export-decisions":
                with ResearchStateDB(args.db) as db:
                    exp_dl = thaw(db.export_decision_ledger_dict())
                if args.output:
                    out_p = safe_path(args.output)
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    out_p.write_text(json.dumps(exp_dl, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                _emit_json(exp_dl)
                return 0
            if act_l == "trace-decision":
                if not args.decision_id:
                    raise ValueError("ledger --action trace-decision requires --decision-id")
                _emit_json(mcp_m.handle_tool_call("decision_trace", {"db_path": args.db, "decision_id": args.decision_id}))
                return 0
            with ResearchStateDB(args.db) as db:
                res_vd = thaw(db.validate_decisions())
            _emit_json(res_vd)
            return 0 if res_vd.get("valid") else 1

        if cmd == "research":
            from .research import analysis, sources

            if args.step == "prepare":
                _emit_json(sources.prepare(args.input, args.project))
                return 0
            if args.step in ("finish", "replay"):
                cand = args.candidate if args.step == "finish" else str(safe_path(args.project) / "candidate.json")
                _emit_json(analysis.finish(args.project, cand))
                return 0
            if args.step == "compare":
                _emit_json(analysis.compare(args.left, args.right, args.analysis, args.output))
                return 0
            # step == "skill"
            skill_src = _locate_portable_skill_dir()
            if skill_src is None:
                raise FileNotFoundError("Portable audit-paper skill is unavailable in this installation")
            dst = safe_path(args.output)
            dst.mkdir(parents=True, exist_ok=True)
            for item in sorted(skill_src.rglob("*")):
                if item.is_file():
                    out_f = dst / item.relative_to(skill_src)
                    out_f.parent.mkdir(parents=True, exist_ok=True)
                    out_f.write_bytes(item.read_bytes())
            pkg_schemas = resources.files("academic_research_kernel").joinpath("schemas")
            for sname in ("paper-extraction", "paper-comparison", "research-documents"):
                sf = pkg_schemas.joinpath(f"{sname}.schema.json")
                out_s = dst / "references" / f"{sname}.schema.json"
                out_s.parent.mkdir(parents=True, exist_ok=True)
                out_s.write_bytes(sf.read_bytes())
            _emit_json({"skill": str(dst / "SKILL.md"), "version": __version__, "semantic_producer": "your local agent"})
            return 0

    except Exception as exc:
        if cmd == "research":
            print(
                json.dumps(
                    {"status": "error", "step": getattr(args, "step", ""), "reason": str(exc), "hint": _error_hint(getattr(args, "step", "research"), str(exc))},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 1
        _emit_json({"status": "error", "command": cmd, "error": str(exc), "hint": _error_hint(cmd, str(exc))})
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

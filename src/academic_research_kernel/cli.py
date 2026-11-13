"""Unified CLI for academic-research-kernel (Occam edition)."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from importlib import metadata, resources, util
import json
import math
from pathlib import Path
import platform

from . import (
    double_blind_sanitizer,
    export_bibtex,
    github_repo_forensics,
    interop,
    locate_oa,
    mcp_server,
    meta_core,
    openreview_audit,
    pre_submission_linter,
    receipt_to_latex_table,
    repro_checklist,
    venue_template_manager,
    watch,
)
from ._stdlib import normalize_identifier, safe_path, thaw
from ._version import __version__


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
    return f'Check inputs for step "{step}" or run: academic-research-kernel doctor'


def _opt_ver(mod_name: str, dist_name: str | None = None) -> str:
    if util.find_spec(mod_name) is None:
        return "not installed; use [research]"
    try:
        return metadata.version(dist_name or mod_name)
    except Exception:
        return "available"


def doctor() -> dict:
    try:
        _ = resources.files("academic_research_kernel")
    except Exception:
        pass
    deps = {}
    errors = []
    for name in ("jsonschema", "numpy", "scipy", "statsmodels"):
        if util.find_spec(name) is not None:
            try:
                deps[name] = metadata.version(name)
            except Exception:
                deps[name] = "available"
        else:
            deps[name] = "missing"
            errors.append(f"missing {name}")
    pct = mcp_server.handle_tool_call("academic_check_percentage", {"count": 10, "percent": 50, "sample_size": 20})
    if pct.get("consistent") is not True:
        errors.append("percentage check failed")
    pypdf_v = _opt_ver("pypdf")
    ft_v = _opt_ver("fontTools", "fonttools")
    pdf_ready = not pypdf_v.startswith("not installed") and not ft_v.startswith("not installed")
    status = "ok" if not errors else "error"
    return {
        "version": __version__,
        "status": status,
        "python": platform.python_version(),
        "dependencies": deps,
        "schema_resources": {"status": "ok"},
        "research": {"pdf_ready": pdf_ready, "pdf_parser": pypdf_v, "font_decoder": ft_v, "portable_skill": "available"},
        "readiness": {"core_verification_and_mcp": "ready" if status == "ok" else "error", "pdf_reading": "ready" if pdf_ready else "not ready"},
        "mcp_tools": len(mcp_server.TOOLS),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="academic-research-kernel", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Offline diagnostic check")
    p_doc.add_argument("--json", action="store_true")
    sub.add_parser("mcp", help="Serve stdio JSON-RPC 2.0 MCP tools")

    p_ver = sub.add_parser("verify-source", help="Normalize identifier or verify OpenAlex/Crossref metadata")
    p_ver.add_argument("identifier")
    p_ver.add_argument("--live", action="store_true")
    p_ver.add_argument("--normalize-only", action="store_true")
    p_ver.add_argument("--openalex-json")
    p_ver.add_argument("--crossref-json")

    p_meta = sub.add_parser("meta-analyze", help="Fixed & random-effects pooling + Egger/trim-and-fill")
    p_meta.add_argument("--input", required=True)

    p_tf = sub.add_parser("table-forensics", help="Audit partition conservation, ablation deltas, and bandwidth bounds")
    p_tf.add_argument("--input", required=True)

    p_lint = sub.add_parser("pre-submission-lint", help="Lint TeX manuscript bundle")
    p_lint.add_argument("tex")
    p_lint.add_argument("--venue", default="iclr")
    p_lint.add_argument("--no-blind", action="store_true")

    p_san = sub.add_parser("sanitize-blind", help="Scan manuscript for double-blind leaks")
    p_san.add_argument("target")
    p_san.add_argument("--forbidden-token", action="append", default=[])

    p_ltx = sub.add_parser("receipt-to-latex", help="Render booktabs LaTeX table from JSON spec")
    p_ltx.add_argument("input")

    p_vt = sub.add_parser("venue-template", help="List supported venue contracts")
    p_vt.add_argument("--list", action="store_true")

    p_rc = sub.add_parser("repro-checklist", help="Adjudicate 14-stage reproducibility checklist")
    p_rc.add_argument("input")

    p_rw = sub.add_parser("retraction-watch", help="SQLite-backed DOI retraction delta watcher")
    p_rw.add_argument("--watchlist", required=True)
    p_rw.add_argument("--db", default=":memory:")
    p_rw.add_argument("--live", action="store_true")

    p_bib = sub.add_parser("bibliography", help="Convert bibliographic formats or export BibTeX")
    p_bib.add_argument("--from", dest="src_fmt", choices=["bibtex", "ris", "csl", "crossref", "openalex"], required=True)
    p_bib.add_argument("--to", dest="dst_fmt", choices=["bibtex", "ris", "csl"], required=True)
    p_bib.add_argument("--input", required=True)

    p_rf = sub.add_parser("repo-forensics", help="Classify local repository Python composition")
    p_rf.add_argument("repo_dir")

    p_or = sub.add_parser("openreview-audit", help="Audit OpenReview notes JSON or live forum")
    p_or.add_argument("--forum-id")
    p_or.add_argument("--input-json")

    p_oa = sub.add_parser("locate-oa", help="Locate open-access full text")
    p_oa.add_argument("identifier")
    p_oa.add_argument("--email", default="local@localhost")

    p_res = sub.add_parser("research", help="Prepare/finish/compare paper research workflow")
    rsub = p_res.add_subparsers(dest="step", required=True)
    rp_prep = rsub.add_parser("prepare")
    rp_prep.add_argument("input")
    rp_prep.add_argument("--project", required=True)
    rp_fin = rsub.add_parser("finish")
    rp_fin.add_argument("--project", required=True)
    rp_fin.add_argument("--candidate", required=True)
    rp_cmp = rsub.add_parser("compare")
    rp_cmp.add_argument("left")
    rp_cmp.add_argument("right")
    rp_cmp.add_argument("--analysis", required=True)
    rp_cmp.add_argument("--output", required=True)

    args = parser.parse_args(argv)
    cmd = args.command

    if cmd == "mcp":
        return mcp_server.main()
    if cmd == "doctor":
        rep = doctor()
        print(json.dumps(rep, indent=2, ensure_ascii=False))
        return 0 if rep["status"] == "ok" else 1
    if cmd == "verify-source":
        if args.normalize_only:
            norm = normalize_identifier(args.identifier)
            out = {"type": norm["kind"], "value": norm["id"], "canonical": norm["canonical"]}
        else:
            oa = json.loads(safe_path(args.openalex_json).read_text("utf-8")) if args.openalex_json else None
            cr = json.loads(safe_path(args.crossref_json).read_text("utf-8")) if args.crossref_json else None
            out = mcp_server.handle_tool_call("academic_verify_source", {"identifier": args.identifier, "live": args.live, "openalex": oa, "crossref": cr})
    elif cmd == "meta-analyze":
        raw = json.loads(safe_path(args.input).read_text("utf-8"))
        studies = raw["studies"] if isinstance(raw, dict) else raw
        yi = [float(s["yi"]) for s in studies]
        vi = [float(s["vi"]) for s in studies]
        bias = None
        if len(yi) >= 3:
            try:
                icp, tv, pv = meta_core.egger_test(yi, vi)
                egger_out = {"status": "ok", "intercept": icp, "t": tv if math.isfinite(tv) else None, "p": pv if math.isfinite(pv) else None}
            except (ValueError, ZeroDivisionError) as exc:
                egger_out = {"status": "not_estimable", "reason": str(exc)}
            try:
                tf_out = meta_core.trim_and_fill(yi, vi)
            except (ValueError, ZeroDivisionError) as exc:
                tf_out = {"status": "not_estimable", "reason": str(exc)}
            bias = {"egger": egger_out, "trim_and_fill": tf_out}
        out = {
            "study_count": len(yi),
            "fixed_effect": asdict(meta_core.pool_fixed(yi, vi)),
            "random_effects_dl": asdict(meta_core.pool_random(yi, vi)),
            "publication_bias": bias,
        }
    elif cmd == "table-forensics":
        spec = json.loads(safe_path(args.input).read_text("utf-8"))
        out = mcp_server.handle_tool_call("academic_table_forensics", spec)
    elif cmd == "pre-submission-lint":
        out = thaw(pre_submission_linter.lint_manuscript(args.tex, venue=args.venue, double_blind=not args.no_blind))
    elif cmd == "sanitize-blind":
        out = double_blind_sanitizer.scan_target(args.target, args.forbidden_token)
    elif cmd == "receipt-to-latex":
        spec = json.loads(safe_path(args.input).read_text("utf-8"))
        print(receipt_to_latex_table.render_booktabs_table(spec))
        return 0
    elif cmd == "venue-template":
        out = venue_template_manager.list_venues()
    elif cmd == "repro-checklist":
        spec = json.loads(safe_path(args.input).read_text("utf-8"))
        out = repro_checklist.adjudicate(repro_checklist.normalize(spec))
    elif cmd == "retraction-watch":
        wl = watch.load_watchlist(args.watchlist)
        out = {"deltas": watch.check_retraction_signals(wl["dois"], db_path=args.db, live=args.live)}
    elif cmd == "bibliography":
        txt = safe_path(args.input).read_text("utf-8")
        works = interop.from_bibtex(txt) if args.src_fmt == "bibtex" else interop.from_ris(txt)
        if args.dst_fmt == "bibtex":
            print("\n\n".join(export_bibtex.protect_acronyms(interop.to_bibtex(w)) for w in works))
            return 0
        if args.dst_fmt == "ris":
            print("\n\n".join(interop.to_ris(w) for w in works))
            return 0
        out = [interop.to_csl_json(w) for w in works]
    elif cmd == "repo-forensics":
        out = github_repo_forensics.scan_local_repo(Path(args.repo_dir))
    elif cmd == "openreview-audit":
        notes = json.loads(safe_path(args.input_json).read_text("utf-8")) if args.input_json else openreview_audit.fetch_openreview_forum(args.forum_id)
        if isinstance(notes, dict) and "notes" in notes:
            notes = notes["notes"]
        out = openreview_audit.parse_openreview_notes(notes)
    elif cmd == "locate-oa":
        norm = normalize_identifier(args.identifier)
        out = locate_oa.live_unpaywall(norm["id"], args.email) if norm["kind"] == "doi" else {"identifier": norm}
    else:
        from .research import analysis, sources
        if args.step == "prepare":
            out = sources.prepare(args.input, args.project)
        elif args.step == "finish":
            out = analysis.finish(args.project, args.candidate)
        else:
            out = analysis.compare(args.left, args.right, args.analysis, args.output)

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

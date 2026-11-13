"""Unified lazy-loaded CLI for academic-research-kernel (Occam edition, hardened)."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib
from importlib import metadata, resources, util
import json
import math
import os
from pathlib import Path
import platform
import sys
from typing import Any

from ._stdlib import normalize_doi, normalize_identifier, safe_path, thaw
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
        return "Have your Agent read the prepared materials using paper-research/SKILL.md and pass --candidate"
    return f'Check inputs for step "{step}" or run: academic-research-kernel doctor'


def _opt_ver(mod_name: str, dist_name: str | None = None) -> str:
    try:
        if util.find_spec(mod_name) is None:
            return "not installed; use [research]"
    except (ImportError, ValueError):
        return "not installed; use [research]"
    try:
        return metadata.version(dist_name or mod_name)
    except Exception:
        return "available"


def _locate_portable_skill_dir() -> Path | None:
    try:
        ref = resources.files("academic_research_kernel").joinpath("portable_skills", "paper-research")
        if ref.joinpath("SKILL.md").is_file():
            return Path(str(ref))
    except Exception:
        pass
    pkg_skill = Path(__file__).resolve().parent / "portable_skills" / "paper-research"
    if (pkg_skill / "SKILL.md").is_file():
        return pkg_skill
    repo_skill = Path(__file__).resolve().parents[2] / "skills" / "paper-research"
    if (repo_skill / "SKILL.md").is_file():
        return repo_skill
    return None


def doctor() -> dict[str, Any]:
    """Offline diagnostic check inspecting actual packaged schemas, portable skill, and dependencies."""
    deps: dict[str, str] = {}
    errors: list[str] = []
    for name in ("jsonschema", "numpy", "scipy", "statsmodels"):
        try:
            present = util.find_spec(name) is not None
        except (ImportError, ValueError):
            present = False
        if present:
            try:
                deps[name] = metadata.version(name)
            except Exception:
                deps[name] = "available"
        else:
            deps[name] = "missing"
            errors.append(f"missing {name}")

    schema_status = "error"
    schema_count = 0
    try:
        from jsonschema import Draft202012Validator

        found_files = []
        try:
            pkg_root = resources.files("academic_research_kernel")
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
                Draft202012Validator.check_schema(json.loads(sp.read_text(encoding="utf-8")))
            schema_status = "ok"
            schema_count = len(found_files)
    except Exception as exc:
        errors.append(f"schemas: {type(exc).__name__}: {exc}")

    skill_dir = _locate_portable_skill_dir()
    if skill_dir is not None and (skill_dir / "SKILL.md").read_text(encoding="utf-8").strip():
        portable_skill = "available"
    else:
        portable_skill = "unavailable"
        errors.append("missing portable paper-research/SKILL.md resource")

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

    p_ver = sub.add_parser("verify-source", help="Normalize identifier, verify metadata, check updates, or verify PDF")
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

    p_meta = sub.add_parser("meta-analyze", help="Fixed & random-effects pooling + LOO + Egger/trim-and-fill")
    p_meta.add_argument("--input", required=True)

    p_tf = sub.add_parser("table-forensics", help="Audit partition conservation, ablation deltas, and bandwidth bounds")
    p_tf.add_argument("--input", required=True)

    p_lint = sub.add_parser("pre-submission-lint", help="Lint TeX manuscript bundle")
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

    for sb_alias in ("sanitize-blind", "double-blind-sanitize"):
        p_san = sub.add_parser(sb_alias, help="Scan manuscript for double-blind anonymity leaks")
        p_san.add_argument("target_pos", nargs="?")
        p_san.add_argument("--target", dest="target_opt")
        p_san.add_argument("--forbidden-token", action="append", default=[])

    p_ltx = sub.add_parser("receipt-to-latex", help="Render booktabs LaTeX table from JSON spec or research artifact")
    p_ltx.add_argument("input_pos", nargs="?")
    p_ltx.add_argument("--input", dest="input_opt")
    p_ltx.add_argument("--from-research", choices=["extraction", "results", "comparison"])
    p_ltx.add_argument("--left-extraction")
    p_ltx.add_argument("--right-extraction")
    p_ltx.add_argument("--output")
    p_ltx.add_argument("--caption")
    p_ltx.add_argument("--label")

    p_vt = sub.add_parser("venue-template", help="List venue contracts, scaffold workspace, verify styles, or export CEG anchors")
    p_vt.add_argument("--list", action="store_true")
    p_vt.add_argument("--action", choices=["list-venues", "scaffold", "verify-styles", "export-ceg-anchors"], default="list-venues")
    p_vt.add_argument("--workspace-dir")
    p_vt.add_argument("--slug")
    p_vt.add_argument("--venue", default="iclr")
    p_vt.add_argument("--year", type=int, default=2027)
    p_vt.add_argument("--contribution-type", default="general_empirical")
    p_vt.add_argument("--force", action="store_true")
    p_vt.add_argument("--manuscript-dir")
    p_vt.add_argument("--ceg")

    p_rc = sub.add_parser("repro-checklist", help="Adjudicate 14-stage reproducibility checklist")
    p_rc.add_argument("input_pos", nargs="?")
    p_rc.add_argument("--input", dest="input_opt")
    p_rc.add_argument("-o", "--out")
    p_rc.add_argument("--evidence-receipt")
    p_rc.add_argument("--generated-at")
    p_rc.add_argument("--pretty", action="store_true")

    p_rw = sub.add_parser("retraction-watch", help="SQLite-backed DOI retraction delta watcher")
    p_rw.add_argument("--watchlist")
    p_rw.add_argument("--db", "--state", dest="db", default=":memory:")
    p_rw.add_argument("--live", "--run", dest="live", action="store_true")
    p_rw.add_argument("--self-test", action="store_true")

    p_lw = sub.add_parser("literature-watch", help="SQLite-backed bounded incremental literature watcher")
    p_lw.add_argument("--watchlist")
    p_lw.add_argument("--db", "--state", dest="db", default=":memory:")
    p_lw.add_argument("--live", "--run", dest="live", action="store_true")
    p_lw.add_argument("--days", type=int, default=7)
    p_lw.add_argument("--self-test", action="store_true")

    p_bib = sub.add_parser("bibliography", help="Convert formats, export BibTeX, deduplicate, build citation graph, or render matrix")
    p_bib.add_argument("--action", choices=["convert", "export-bibtex", "deduplicate", "citation-graph", "review-matrix"], default="convert")
    p_bib.add_argument("--from", dest="src_fmt", choices=["bibtex", "ris", "csl", "crossref", "openalex"])
    p_bib.add_argument("--to", dest="dst_fmt", choices=["bibtex", "ris", "csl", "canonical"])
    p_bib.add_argument("--input")
    p_bib.add_argument("--source", choices=["crossref", "openalex"], default="crossref")
    p_bib.add_argument("--doi")
    p_bib.add_argument("--wid")
    p_bib.add_argument("--per-page", type=int, default=25)
    p_bib.add_argument("--pages", type=int, default=4)
    p_bib.add_argument("--query")
    p_bib.add_argument("--date")

    p_rf = sub.add_parser("repo-forensics", help="Classify repository Python composition (core vs vendored vs tests)")
    p_rf.add_argument("repo_dir", nargs="?")
    p_rf.add_argument("--local-repo", "--repo-dir", dest="local_repo")
    p_rf.add_argument("--tree-json")

    p_or = sub.add_parser("openreview-audit", help="Audit OpenReview notes JSON, mirror list, or live forum")
    p_or.add_argument("--forum-id", "--forum", dest="forum_id")
    p_or.add_argument("--input-json")
    p_or.add_argument("--mirror-json", "--mirror", dest="mirror_json")
    p_or.add_argument("--venue-stats")
    p_or.add_argument("--topic-regex")

    p_oa = sub.add_parser("locate-oa", help="Locate open-access full text")
    p_oa.add_argument("identifier", nargs="?")
    p_oa.add_argument("--doi")
    p_oa.add_argument("--arxiv")
    p_oa.add_argument("--email", default="local@localhost")

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
        if cmd == "verify-source":
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

        if cmd == "meta-analyze":
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

        if cmd == "pre-submission-lint":
            tex_target = args.tex_opt or args.tex_pos
            if not tex_target:
                raise ValueError("pre-submission-lint requires a positional TeX path or --tex")
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

        if cmd in ("sanitize-blind", "double-blind-sanitize"):
            target = args.target_opt or args.target_pos
            if not target:
                raise ValueError(f"{cmd} requires a target path or --target")
            dbs = _mod("double_blind_sanitizer")
            out = dbs.scan_target(Path(target), forbidden_tokens=args.forbidden_token)
            _emit_json(out)
            has_leaks = bool(out.get("findings")) or out.get("status") not in ("clean", "ok")
            return 1 if has_leaks else 0

        if cmd == "receipt-to-latex":
            src_in = args.input_opt or args.input_pos
            if not src_in:
                raise ValueError("receipt-to-latex requires an input path or --input")
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
                spec = data
                if args.caption:
                    spec["caption"] = args.caption
                if args.label:
                    spec["label"] = args.label
            tex_str = rlt.render_booktabs_table(spec, source_sha256=sha)
            if args.output:
                out_p = safe_path(args.output)
                out_p.parent.mkdir(parents=True, exist_ok=True)
                out_p.write_text(tex_str + "\n", encoding="utf-8")
            print(tex_str)
            return 0

        if cmd == "venue-template":
            vtm = _mod("venue_template_manager")
            act = "list-venues" if args.list else args.action
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
            if not rc_in:
                raise ValueError("repro-checklist requires an input file path or --input")
            rc = _mod("repro_checklist")
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
            if args.self_test:
                rep = wmod.check_retraction_report(
                    ["10.1000/selftest"],
                    db_path=":memory:",
                    mock_records={"10.1000/selftest": (True, ["retraction(publisher) update-doi=10.1000/notice"])},
                )
                _emit_json({"self_test": "passed" if len(rep["deltas"]) == 1 else "failed", "report": rep})
                return 0 if len(rep["deltas"]) == 1 else 1
            if not args.watchlist:
                raise ValueError("retraction-watch requires --watchlist (or --self-test)")
            wl = wmod.load_watchlist(args.watchlist)
            _emit_json(wmod.check_retraction_report(wl["dois"], db_path=args.db, live=args.live))
            return 0

        if cmd == "literature-watch":
            wmod = _mod("watch")
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
                entries = tj["tree"] if isinstance(tj, dict) and "tree" in tj else tj
                trunc = bool(tj.get("truncated")) if isinstance(tj, dict) else False
                _emit_json(rf.analyze_entries(entries, truncated=trunc))
                return 0
            if not local_dir:
                raise ValueError("repo-forensics requires a local repository directory or --tree-json")
            entries = rf.scan_local_repo(safe_path(local_dir))
            _emit_json(rf.analyze_entries(entries, truncated=False))
            return 0

        if cmd == "openreview-audit":
            ora = _mod("openreview_audit")
            if args.venue_stats:
                recs = json.loads(safe_path(args.venue_stats).read_text("utf-8"))
                _emit_json(ora.summarize_venue_mirror(recs, topic_regex=args.topic_regex))
                return 0
            if args.input_json:
                payload = json.loads(safe_path(args.input_json).read_text("utf-8"))
                _emit_json(ora.parse_openreview_notes(payload, forum_id=args.forum_id))
                return 0
            if args.mirror_json:
                if not args.forum_id:
                    raise ValueError("--mirror-json requires --forum-id")
                payload = json.loads(safe_path(args.mirror_json).read_text("utf-8"))
                _emit_json(ora.parse_openreview_notes(payload, forum_id=args.forum_id))
                return 0
            if args.forum_id:
                _emit_json(ora.parse_openreview_notes(ora.fetch_openreview_forum(args.forum_id), forum_id=args.forum_id))
                return 0
            raise ValueError("openreview-audit requires --forum-id, --input-json, --mirror-json, or --venue-stats")

        if cmd == "locate-oa":
            loa = _mod("locate_oa")
            raw_target = args.arxiv or args.doi or args.identifier
            if not raw_target:
                raise ValueError("locate-oa requires an identifier, --doi, or --arxiv")
            norm = normalize_identifier(raw_target if not args.arxiv else f"arxiv:{args.arxiv}")
            if norm["type"] == "doi":
                _emit_json(loa.live_unpaywall(norm["value"], args.email))
                return 0
            if norm["type"] == "arxiv":
                _emit_json({"identifier": norm, "oa_url": f"https://arxiv.org/pdf/{norm['value']}.pdf", "is_oa": True})
                return 0
            _emit_json({"identifier": norm, "is_oa": False})
            return 1

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
                raise FileNotFoundError("Portable paper-research skill is unavailable in this installation")
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

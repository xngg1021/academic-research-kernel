"""外部论文排版工作区脚手架与官方宏包契约登记工具。

不将体积庞大且按年变动的 .cls/.sty 宏包塞入内核代码库，而是在用户指定的外部论文工作区目录中：
1. 生成包含目标顶会（ICLR / NeurIPS / ICML / ACL / KDD / IEEE / ACM / arXiv）必含与推荐章节占位的 main.tex 起始骨架、references.bib 与 tables/ 目录；
2. 记录官方模板来源 URL、检索日期、贡献赛道与已导入 .sty/.cls 宏包的 SHA-256 清单（venue-manifest.json）；
3. 生成一键投稿前自检脚本 check_submission.py，自动串联 double_blind_sanitizer.py 与 pre_submission_linter.py。
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def _load_specs(specs_path: str | Path | None = None) -> dict[str, Any]:
    here = Path(__file__).resolve()
    candidates = [
        Path(specs_path) if specs_path else None,
        here.parents[1] / "references" / "venue-specs.json",
        here.parent / "venue-specs.json",
    ]
    for c in candidates:
        if c is not None and c.is_file():
            return json.loads(c.read_text(encoding="utf-8"))
    raise FileNotFoundError("venue-specs.json not found")


def list_venues(specs_path: str | Path | None = None) -> dict[str, Any]:
    specs = _load_specs(specs_path)
    out = {}
    for k, v in specs.get("venues", {}).items():
        out[k] = {
            "display_name": v["display_name"],
            "review_mode": v["review_mode"],
            "main_body_max_pages": v["main_body_max_pages"],
            "phase_max_pages": v.get("phase_max_pages", {}),
            "required_sections": v["required_sections"],
            "recommended_sections": v.get("recommended_sections", []),
            "official_guidelines_url": v["official_guidelines_url"],
            "official_template_url": v["official_template_url"],
        }
    return {
        "schema_version": specs.get("schema_version", "1.0.0"),
        "venues": out,
        "contribution_types": list(specs.get("contribution_types", {}).keys()),
        "methodological_lenses": [l["lens_id"] for l in specs.get("methodological_lenses", [])],
    }


def _render_main_tex(venue_key: str, vspec: dict[str, Any], year: int) -> str:
    author_line = "Anonymous Authors" if vspec["review_mode"] == "double_blind" else "Author Name"
    extra_sections = []
    for sec in vspec.get("required_sections", []):
        extra_sections.append(f"\\section*{{{sec}}}\nState compliance and reproducibility details for {sec} here.\n")
    for sec in vspec.get("recommended_sections", []):
        if sec not in vspec.get("required_sections", []):
            extra_sections.append(f"% Recommended section for {venue_key.upper()}:\n\\section*{{{sec}}}\nDiscuss scope boundaries and details for {sec} here.\n")
    extra_block = "\n".join(extra_sections)
    return (
        f"% Starter Skeleton for Target Venue: {vspec['display_name']} ({year})\n"
        f"% Review Mode: {vspec['review_mode']} (Max initial-submission main-body pages: {vspec['main_body_max_pages']})\n"
        "% Official style package URL is recorded in venue-manifest.json\n"
        "\\documentclass[11pt]{article}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{hyperref}\n\n"
        "\\title{Manuscript Title}\n"
        f"\\author{{{author_line}}}\n"
        "\\date{}\n\n"
        "\\begin{document}\n"
        "\\maketitle\n\n"
        "\\begin{abstract}\n"
        "% Attach verified CEG anchors via venue-template --action export-ceg-anchors --ceg <path>\n"
        "State the formal problem, core method, and receipt-backed findings here.\n"
        "\\end{abstract}\n\n"
        "\\section{Introduction}\n"
        "Introduce the research question and contribution scope.\n\n"
        "\\section{Method}\n"
        "Formally define notation, assumptions, and algorithm.\n\n"
        "\\section{Experiments}\n"
        "Report equal-budget baseline comparisons, ablations, and multi-seed dispersion.\n\n"
        "\\section{Conclusion}\n"
        "Summarize verified conclusions within the tested boundary.\n\n"
        f"{extra_block}\n"
        "\\bibliographystyle{plain}\n"
        "\\bibliography{references}\n"
        "\\end{document}\n"
    )


def _render_check_submission_py(venue_key: str, ctype_key: str) -> str:
    return (
        '"""Automated pre-submission gate for this manuscript workspace."""\n'
        "from pathlib import Path\n"
        "import subprocess\n"
        "import sys\n\n"
        "HERE = Path(__file__).resolve().parent\n\n"
        "def main() -> int:\n"
        "    rc1 = subprocess.call([sys.executable, '-m', 'academic_research_kernel', 'sanitize-blind', '--target', str(HERE)])\n"
        f"    rc2 = subprocess.call([sys.executable, '-m', 'academic_research_kernel', 'pre-submission-lint', '--tex', str(HERE / 'main.tex'), '--venue', {venue_key!r}, '--contribution-type', {ctype_key!r}])\n"
        "    return 0 if (rc1 == 0 and rc2 == 0) else 1\n\n"
        "if __name__ == '__main__':\n"
        "    raise SystemExit(main())\n"
    )


def scaffold_manuscript(
    workspace_dir: str | Path,
    project_slug: str,
    venue: str = "iclr",
    year: int = 2027,
    contribution_type: str = "general_empirical",
    force: bool = False,
    specs_path: str | Path | None = None,
) -> Path:
    slug = project_slug.strip()
    if not SLUG_RE.fullmatch(slug) or slug in (".", ".."):
        raise ValueError(f"Invalid project_slug {project_slug!r}; must be alphanumeric/hyphen/underscore")
    specs = _load_specs(specs_path)
    venues = specs.get("venues", {})
    vkey = venue.strip().lower()
    if vkey not in venues:
        raise ValueError(f"Unknown venue {venue!r}")
    vspec = venues[vkey]

    ctypes = specs.get("contribution_types", {})
    ckey = contribution_type.strip().lower()
    if ckey not in ctypes:
        raise ValueError(f"Unknown contribution_type {contribution_type!r}")

    raw_base = Path(workspace_dir)
    _reject_symlink_chain(raw_base, raw_base)
    base = raw_base.resolve()
    target_dir = base / slug
    if _is_link_or_reparse(target_dir) or not target_dir.resolve().is_relative_to(base):
        raise ValueError("Resolved target directory escapes workspace_dir or is a symlink")
    target_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ("tables", "figures", "styles"):
        sd = target_dir / subdir
        if _is_link_or_reparse(sd):
            raise ValueError(f"Subdirectory {subdir} is a symlink")
        sd.mkdir(exist_ok=True)

    manifest_path = target_dir / "venue-manifest.json"
    if manifest_path.is_file() and not force:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing.get("venue") != vkey:
            raise ValueError(
                f"Workspace {slug!r} is already initialized for venue {existing.get('venue')!r}; pass force=True to overwrite for {vkey!r}"
            )

    main_tex = target_dir / "main.tex"
    if main_tex.is_symlink():
        raise ValueError("main.tex cannot be a symlink")
    if not main_tex.exists() or force:
        main_tex.write_text(_render_main_tex(vkey, vspec, year), encoding="utf-8")

    bib_path = target_dir / "references.bib"
    if bib_path.is_symlink():
        raise ValueError("references.bib cannot be a symlink")
    if not bib_path.exists():
        bib_path.write_text(
            "% Verified BibTeX entries exported via: academic-research-kernel bibliography --action export-bibtex\n",
            encoding="utf-8",
        )

    check_py = target_dir / "check_submission.py"
    if check_py.is_symlink():
        raise ValueError("check_submission.py cannot be a symlink")
    if not check_py.exists() or force:
        check_py.write_text(_render_check_submission_py(vkey, ckey), encoding="utf-8")

    if manifest_path.is_symlink():
        raise ValueError("venue-manifest.json cannot be a symlink")
    manifest = {
        "schema_version": "1.0.0",
        "project_slug": slug,
        "venue": vkey,
        "venue_display_name": vspec["display_name"],
        "target_year": int(year),
        "review_mode": vspec["review_mode"],
        "contribution_type": ckey,
        "main_body_max_pages": vspec["main_body_max_pages"],
        "phase_max_pages": vspec.get("phase_max_pages", {}),
        "required_sections": vspec["required_sections"],
        "recommended_sections": vspec.get("recommended_sections", []),
        "official_guidelines_url": vspec["official_guidelines_url"],
        "official_template_url": vspec["official_template_url"],
        "official_style_installed": False,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "style_files": [],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return target_dir


def _is_link_or_reparse(path: Path) -> bool:
    if path.parent == Path("/") and path.name in ("var", "tmp", "etc"):
        return False
    try:
        if path.is_symlink():
            return True
    except OSError:
        return True
    is_junc = getattr(os.path, "isjunction", None)
    if is_junc is not None:
        try:
            if is_junc(path):
                return True
        except OSError:
            return True
    try:
        st = os.lstat(path)
        if bool(getattr(st, "st_file_attributes", 0) & 0x400):
            return True
    except FileNotFoundError:
        pass
    except OSError:
        return True
    return False


def _reject_symlink_chain(root: Path, target: Path) -> None:
    cur_anc = root
    while True:
        if _is_link_or_reparse(cur_anc):
            raise ValueError(f"Workspace path cannot be a symlink or junction: {cur_anc}")
        if cur_anc.parent == cur_anc:
            break
        cur_anc = cur_anc.parent
    root_res = root.resolve()
    rel_parts = target.relative_to(root).parts if target != root else ()
    cur = root
    for part in rel_parts:
        cur = cur / part
        if _is_link_or_reparse(cur):
            raise ValueError(f"Symlink or junction not permitted in workspace path: {cur}")
    if target.exists() and not target.resolve().is_relative_to(root_res):
        raise ValueError(f"Path escapes workspace root: {target}")


def verify_style_directory(manuscript_dir: str | Path, specs_path: str | Path | None = None) -> dict[str, Any]:
    raw_mdir = Path(manuscript_dir)
    _reject_symlink_chain(raw_mdir, raw_mdir / "venue-manifest.json")
    mdir = raw_mdir.resolve()
    manifest_path = mdir / "venue-manifest.json"
    if _is_link_or_reparse(manifest_path) or not manifest_path.is_file():
        raise ValueError(f"venue-manifest.json not found or invalid in {mdir}")
    style_candidates: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(mdir, followlinks=False):
        dp = Path(dirpath)
        _reject_symlink_chain(mdir, dp)
        for dname in dirnames:
            _reject_symlink_chain(mdir, dp / dname)
        for fname in filenames:
            fpath = dp / fname
            _reject_symlink_chain(mdir, fpath)
            if fpath.suffix.lower() in (".sty", ".cls", ".bst"):
                style_candidates.append(fpath)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    specs = _load_specs(specs_path)
    vspec = specs["venues"][manifest["venue"]]

    style_records = []
    warnings = []
    trusted_hashes = set(vspec.get("trusted_style_sha256") or [])
    verified_count = 0
    ext_order = {".sty": 0, ".cls": 1, ".bst": 2}
    for f in sorted(style_candidates, key=lambda p: (ext_order.get(p.suffix.lower(), 9), str(p))):
        _reject_symlink_chain(mdir, f)
        if not f.is_file():
            continue
        raw = f.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        rel = f.relative_to(mdir).as_posix()
        is_verified_file = bool(trusted_hashes and sha in trusted_hashes)
        if is_verified_file:
            verified_count += 1
        style_records.append({"path": rel, "sha256": sha, "size_bytes": len(raw), "verified_origin": is_verified_file})
        for pat in vspec.get("forbidden_patterns_in_review", []):
            if f.stem in pat:
                warnings.append(f"Style file {rel} matches forbidden legacy pattern {pat!r}")

    official_verified = bool(style_records and trusted_hashes and verified_count == len(style_records))
    manifest["style_files"] = style_records
    manifest["style_files_detected"] = len(style_records) > 0
    manifest["official_style_verified"] = official_verified
    manifest["official_style_installed"] = official_verified
    manifest["style_verification_status"] = (
        "verified_official_style" if official_verified else ("unverified_local_style" if style_records else "no_style_files")
    )
    manifest["style_warnings"] = warnings
    _reject_symlink_chain(raw_mdir, raw_mdir / "venue-manifest.json")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def export_ceg_anchors(ceg_path: str | Path) -> dict[str, Any]:
    """Read-only export of all CEG claims with support/contradiction status and CEG SHA-256 fingerprint."""
    p = Path(ceg_path)
    cur = p
    while True:
        if _is_link_or_reparse(cur):
            raise ValueError(f"CEG path cannot be a symlink or junction: {cur}")
        if cur.parent == cur:
            break
        cur = cur.parent
    if not p.is_file():
        raise FileNotFoundError(f"CEG file not found: {p}")
    raw_bytes = p.read_bytes()
    ceg_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    data = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("CEG file must be a JSON object")

    ceg_root = data.get("ceg") if isinstance(data.get("ceg"), dict) else data
    raw_claims = ceg_root.get("claims")
    raw_edges = (
        ceg_root.get("support_edges")
        if ceg_root.get("support_edges") is not None
        else (ceg_root.get("edges") if ceg_root.get("edges") is not None else data.get("support_edges"))
    )
    raw_evidence = (
        ceg_root.get("evidence_anchors")
        if ceg_root.get("evidence_anchors") is not None
        else (
            ceg_root.get("evidence")
            if ceg_root.get("evidence") is not None
            else (
                data.get("evidence_anchors")
                if data.get("evidence_anchors") is not None
                else data.get("evidence")
            )
        )
    )

    # Normalize claims
    claims_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw_claims, dict):
        for cid, cobj in raw_claims.items():
            if not isinstance(cobj, dict):
                raise ValueError(f"Claim entry {cid!r} must be an object")
            cid_s = str(cid)
            if "\r" in cid_s or "\n" in cid_s:
                raise ValueError(f"claim_id must not contain line breaks: {cid_s!r}")
            cid_s = cid_s.strip()
            if not cid_s:
                raise ValueError("Claim key must not be empty")
            if cid_s in claims_by_id:
                raise ValueError(f"Duplicate claim_id in CEG: {cid_s!r}")
            claims_by_id[cid_s] = cobj
    elif isinstance(raw_claims, list):
        for idx, cobj in enumerate(raw_claims):
            if not isinstance(cobj, dict):
                raise ValueError(f"claims[{idx}] must be an object")
            cid = str(cobj.get("id") or cobj.get("claim_id") or "")
            if "\r" in cid or "\n" in cid:
                raise ValueError(f"claim_id must not contain line breaks: {cid!r}")
            cid = cid.strip()
            if not cid:
                raise ValueError(f"claims[{idx}] is missing 'id' / 'claim_id'")
            if cid in claims_by_id:
                raise ValueError(f"Duplicate claim_id in CEG: {cid!r}")
            claims_by_id[cid] = cobj
    else:
        raise ValueError("CEG must contain a 'claims' list or object")

    # Normalize evidence IDs if an evidence collection is present
    known_evidence_ids: set[str] | None = None
    if isinstance(raw_evidence, dict):
        known_evidence_ids = {str(k) for k in raw_evidence.keys()}
    elif isinstance(raw_evidence, list):
        known_evidence_ids = {
            str(e.get("id") or e.get("evidence_id"))
            for e in raw_evidence
            if isinstance(e, dict) and (e.get("id") or e.get("evidence_id"))
        }

    pos_by_claim: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claims_by_id}
    neg_by_claim: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claims_by_id}
    unresolved_by_claim: dict[str, int] = {cid: 0 for cid in claims_by_id}
    dangling_edges: list[dict[str, Any]] = []

    if raw_edges is not None:
        if not isinstance(raw_edges, list):
            raise ValueError("CEG edges / support_edges must be a list")
        for idx, edge in enumerate(raw_edges):
            if not isinstance(edge, dict):
                raise ValueError(f"edges[{idx}] must be an object")
            cid = str(edge.get("claim_id") or edge.get("target_claim_id") or edge.get("target") or "").strip()
            ev_id = str(edge.get("evidence_id") or edge.get("source_id") or edge.get("source") or "").strip()
            if not cid or cid not in claims_by_id:
                dangling_edges.append({"edge_index": idx, "reason": "unknown_claim_id", "claim_id": cid or None})
                continue
            endpoint_problem = None
            if not ev_id:
                endpoint_problem = "missing_evidence_id"
            elif known_evidence_ids is None:
                endpoint_problem = "evidence_collection_missing"
            elif ev_id not in known_evidence_ids:
                endpoint_problem = "unknown_evidence_id"
            if endpoint_problem is not None:
                dangling_edges.append({
                    "edge_index": idx,
                    "reason": endpoint_problem,
                    "claim_id": cid,
                    "evidence_id": ev_id or None,
                })
                unresolved_by_claim[cid] += 1
                continue
            status = str(
                edge.get("support_status")
                if edge.get("support_status") is not None
                else (edge.get("status") or edge.get("relation") or edge.get("polarity") or "")
            ).strip().lower()
            if status in ("supported", "supports", "support", "verified_by"):
                pos_by_claim[cid].append(edge)
            elif status in ("contradicted", "contradicts", "refuted", "refutes"):
                neg_by_claim[cid].append(edge)
            else:
                unresolved_by_claim[cid] += 1

    anchors: list[dict[str, Any]] = []
    for cid, cobj in claims_by_id.items():
        raw_txt = str(cobj.get("text") or cobj.get("statement") or "").strip()
        norm_txt = " ".join(raw_txt.split()).rstrip(".").strip()
        c_status = str(cobj.get("support_status") or cobj.get("status") or "").strip().lower()
        pos_cnt = len(pos_by_claim.get(cid, ()))
        neg_cnt = len(neg_by_claim.get(cid, ()))
        unres_cnt = unresolved_by_claim.get(cid, 0)
        if neg_cnt > 0 or c_status in ("conflicted", "contradicted", "refuted"):
            anchor_status = "conflicted"
        elif pos_cnt > 0 and norm_txt and unres_cnt == 0 and c_status not in ("unverifiable", "out_of_scope"):
            anchor_status = "eligible"
        else:
            anchor_status = "unsupported"
        anchors.append({
            "claim_id": cid,
            "anchor_comment": f"% ark:claim={cid}",
            "anchor_status": anchor_status,
            "claim_status": c_status or "unknown",
            "normalized_text": norm_txt,
            "support_edge_count": pos_cnt,
            "contradiction_edge_count": neg_cnt,
            "unresolved_edge_count": unres_cnt,
        })

    return {
        "schema_version": "1.0.0",
        "ceg_sha256": ceg_sha256,
        "total_claims": len(anchors),
        "eligible_count": sum(1 for a in anchors if a["anchor_status"] == "eligible"),
        "conflicted_count": sum(1 for a in anchors if a["anchor_status"] == "conflicted"),
        "unsupported_count": sum(1 for a in anchors if a["anchor_status"] == "unsupported"),
        "dangling_edges": dangling_edges,
        "anchors": anchors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="External manuscript workspace and venue template manager.")
    parser.add_argument(
        "--action",
        choices=["list-venues", "scaffold", "verify-styles", "export-ceg-anchors"],
        default="list-venues",
    )
    parser.add_argument("--workspace-dir", help="Target parent workspace directory for scaffold")
    parser.add_argument("--slug", help="Project directory slug")
    parser.add_argument("--venue", default="iclr", help="Venue key")
    parser.add_argument("--year", type=int, default=2027, help="Target conference/publication year")
    parser.add_argument("--contribution-type", default="general_empirical", help="Contribution type key")
    parser.add_argument("--force", action="store_true", help="Overwrite existing main.tex and venue-manifest.json if venue differs")
    parser.add_argument("--manuscript-dir", help="Manuscript directory for verify-styles")
    parser.add_argument("--ceg", help="ClaimEvidenceGraph or kernel-state JSON path for export-ceg-anchors")
    args = parser.parse_args(argv)

    if args.action == "list-venues":
        print(json.dumps(list_venues(), ensure_ascii=False, indent=2))
        return 0
    if args.action == "scaffold":
        if not args.workspace_dir or not args.slug:
            parser.error("--action scaffold requires --workspace-dir and --slug")
        out = scaffold_manuscript(
            workspace_dir=args.workspace_dir,
            project_slug=args.slug,
            venue=args.venue,
            year=args.year,
            contribution_type=args.contribution_type,
            force=args.force,
        )
        print(json.dumps({"status": "scaffolded", "manuscript_dir": str(out)}, ensure_ascii=False, indent=2))
        return 0
    if args.action == "verify-styles":
        if not args.manuscript_dir:
            parser.error("--action verify-styles requires --manuscript-dir")
        res = verify_style_directory(args.manuscript_dir)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    if args.action == "export-ceg-anchors":
        if not args.ceg:
            parser.error("--action export-ceg-anchors requires --ceg")
        res = export_ceg_anchors(args.ceg)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

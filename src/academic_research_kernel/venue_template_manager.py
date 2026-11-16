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


def validate_ceg_semantics(
    data: Any,
    *,
    receipts: dict[str, Any] | None = None,
    content_payloads: dict[str, Any] | None = None,
    authoritative_artifacts: Any = None,
) -> dict[str, Any]:
    """Semantic, referential, and receipt-binding validator for Claim-Evidence Graphs."""
    if not isinstance(data, dict):
        raise ValueError("CEG must be a JSON object")
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
    raw_relations = ceg_root.get("claim_relations")

    claims_by_id: dict[str, dict[str, Any]] = {}
    semantic_errors: list[str] = []
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

    from ._stdlib import canonical_json as _cjson, sha256_hex as _sha256
    from .state_db import (
        canonical_evidence_claim_digest,
        decode_content_payloads_map,
        validate_academic_evidence_payload,
        validate_lineage_receipt_semantics,
        validate_receipt_ref_dict,
    )

    dec_content: dict[str, bytes] | None = None
    if content_payloads is not None:
        try:
            dec_content = decode_content_payloads_map(content_payloads)
        except ValueError as exc:
            semantic_errors.append(str(exc))

    ext_receipts: dict[str, dict[str, Any]] = {}
    if receipts is not None:
        if not isinstance(receipts, dict):
            semantic_errors.append("receipts must be a JSON object mapping receipt keys to receipt payloads")
        else:
            for rk_in, rv_in in receipts.items():
                if not isinstance(rk_in, str) or not rk_in or not isinstance(rv_in, dict):
                    semantic_errors.append(f"receipts[{rk_in!r}] must map a non-empty string key to a JSON object")
                else:
                    ext_receipts[rk_in] = rv_in

    missing_receipt_subjects = {
        str(u.get("subject_id") or "")
        for u in (ceg_root.get("uncertainties") if isinstance(ceg_root.get("uncertainties"), list) else ())
        if isinstance(u, dict) and u.get("kind") == "missing_receipt"
    }

    def _lineage_usable(l_doc: dict[str, Any]) -> bool:
        return (
            l_doc.get("topology_status") == "valid_dag"
            and l_doc.get("verification_status") not in ("hash_mismatch", "missing_artifact", "missing_input", "broken_chain", "cycle_detected")
            and l_doc.get("content_verification") not in ("hash_mismatch", "missing_artifact")
        )

    _hex64_re = re.compile(r"^[0-9a-f]{64}\Z")
    known_content_keys: set[str] = set()

    def _record_lineage_ents_ceg(l_doc: dict[str, Any]) -> None:
        for ent_i in (l_doc.get("entities") or ()):
            if isinstance(ent_i, dict) and isinstance(ent_i.get("id"), str) and ent_i["id"] == ent_i["id"].strip() and ent_i["id"]:
                known_content_keys.add(ent_i["id"])

    def _verify_rref(rref: Any, ctx: str, subject_id: str = "") -> tuple[bool, bool]:
        if rref is None:
            return True, True
        ref_errs = validate_receipt_ref_dict(rref)
        if ref_errs:
            semantic_errors.append(f"{ctx} invalid receipt_ref: {ref_errs[0]}")
            return False, False
        rk = rref.get("kind")
        if rk == "lineage":
            rid = str(rref.get("receipt_id") or "")
            rdig = str(rref.get("receipt_digest") or "").lower()
            if rref.get("schema_version") != "lineage-receipt-1.0" or not rid or not _hex64_re.match(rdig):
                semantic_errors.append(f"{ctx} malformed lineage receipt_ref")
                return False, False
            if rref.get("claim_digest") is not None or rref.get("payload_sha256") is not None:
                semantic_errors.append(f"{ctx} lineage receipt_ref must not carry academic_evidence fields")
                return False, False
            if authoritative_artifacts is not None:
                if rid not in authoritative_artifacts:
                    semantic_errors.append(f"{ctx} lineage receipt_id {rid!r} missing from authoritative DB")
                    return False, False
                db_kind, db_sha, db_pay = authoritative_artifacts[rid]
                if db_kind == "lineage_receipt" and isinstance(db_pay, dict):
                    _record_lineage_ents_ceg(db_pay)
                    l_errs_db = validate_lineage_receipt_semantics(
                        db_pay, decoded_content=dec_content, strict_unknown_entities=False
                    )
                    if l_errs_db or str(db_pay.get("receipt_digest") or "").lower() != rdig:
                        semantic_errors.append(f"{ctx} lineage receipt verification failed vs DB lineage_receipt {rid!r}")
                        return False, False
                    if not _lineage_usable(db_pay):
                        semantic_errors.append(f"{ctx} lineage_receipt {rid!r} has failed status {db_pay.get('verification_status')!r}")
                        return False, False
                else:
                    known_content_keys.add(rid)
                    if str(db_sha).lower() != rdig:
                        semantic_errors.append(f"{ctx} lineage receipt_digest mismatch vs DB artifact {rid!r}")
                        return False, False
                    if dec_content is not None and rid in dec_content and _sha256(dec_content[rid]) != rdig:
                        semantic_errors.append(f"{ctx} content_payloads[{rid!r}] SHA-256 mismatch vs DB artifact")
                        return False, False
                return True, True
            if rid in ext_receipts:
                phys = ext_receipts[rid]
                if phys.get("protocol") == "lineage-receipt-1.0":
                    _record_lineage_ents_ceg(phys)
                    l_errs = validate_lineage_receipt_semantics(
                        phys, decoded_content=dec_content, strict_unknown_entities=False
                    )
                    if l_errs or str(phys.get("receipt_digest") or "").lower() != rdig:
                        semantic_errors.append(f"{ctx} physical lineage receipt failed verification for {rid!r}")
                        return False, False
                    if not _lineage_usable(phys):
                        return True, False
                    return True, True
                if _sha256(_cjson(phys)) == rdig:
                    known_content_keys.add(rid)
                    if dec_content is not None and rid in dec_content and _sha256(dec_content[rid]) != rdig:
                        semantic_errors.append(f"{ctx} content_payloads[{rid!r}] SHA-256 mismatch")
                        return False, False
                    return True, True
                semantic_errors.append(f"{ctx} physical artifact SHA-256 mismatch for {rid!r}")
                return False, False
            if receipts is not None and subject_id not in missing_receipt_subjects:
                semantic_errors.append(f"{ctx} lineage receipt_id {rid!r} missing from supplied receipts")
                return False, False
            return True, False
        if rk == "academic_evidence":
            cdig = str(rref.get("claim_digest") or "").lower()
            psha = str(rref.get("payload_sha256") or "").lower()
            if rref.get("schema_version") != "1.0" or not _hex64_re.match(cdig) or not _hex64_re.match(psha):
                semantic_errors.append(f"{ctx} malformed academic_evidence receipt_ref")
                return False, False
            if rref.get("receipt_id") is not None or rref.get("receipt_digest") is not None:
                semantic_errors.append(f"{ctx} academic_evidence receipt_ref must not carry lineage fields")
                return False, False
            if authoritative_artifacts is not None:
                for _, (_, db_sha, db_pay) in authoritative_artifacts.items():
                    if str(db_sha).lower() == psha and not validate_academic_evidence_payload(db_pay):
                        if any(isinstance(ci, dict) and canonical_evidence_claim_digest(ci) == cdig for ci in db_pay["claims"]):
                            return True, True
                semantic_errors.append(f"{ctx} academic_evidence ({cdig[:12]}, {psha[:12]}) not backed by authoritative DB")
                return False, False
            for cand in (ext_receipts.get(cdig), ext_receipts.get(psha), *ext_receipts.values()):
                if isinstance(cand, dict) and _sha256(_cjson(cand)) == psha and not validate_academic_evidence_payload(cand):
                    if any(isinstance(ci, dict) and canonical_evidence_claim_digest(ci) == cdig for ci in cand["claims"]):
                        return True, True
            if cdig in ext_receipts or psha in ext_receipts:
                semantic_errors.append(f"{ctx} physical academic_evidence payload failed verification for {cdig[:12]}")
                return False, False
            if receipts is not None and subject_id not in missing_receipt_subjects:
                semantic_errors.append(f"{ctx} academic_evidence ({cdig[:12]}, {psha[:12]}) missing from supplied receipts")
                return False, False
            return True, False
        semantic_errors.append(f"{ctx} unsupported receipt_ref kind {rk!r}")
        return False, False

    known_evidence_ids: set[str] | None = None
    anchor_verified_by_id: dict[str, bool] = {}
    if isinstance(raw_evidence, dict):
        known_evidence_ids = set()
        for k, eobj in raw_evidence.items():
            ks = str(k).strip()
            if not ks:
                semantic_errors.append("Empty evidence_anchor key")
            elif ks in known_evidence_ids:
                semantic_errors.append(f"Duplicate evidence_id in CEG: {ks!r}")
            else:
                known_evidence_ids.add(ks)
                _, c_ver = _verify_rref(eobj.get("receipt_ref") if isinstance(eobj, dict) else None, f"evidence_anchors[{ks!r}]", subject_id=ks)
                if authoritative_artifacts is not None and isinstance(eobj, dict):
                    emeta = eobj.get("metadata")
                    if isinstance(emeta, dict) and emeta.get("artifact_id"):
                        aid_ref = str(emeta["artifact_id"])
                        if aid_ref not in authoritative_artifacts:
                            semantic_errors.append(f"evidence_anchors[{ks!r}] metadata.artifact_id {aid_ref!r} not in authoritative DB")
                            c_ver = False
                anchor_verified_by_id[ks] = c_ver
    elif isinstance(raw_evidence, list):
        known_evidence_ids = set()
        for idx_e, e in enumerate(raw_evidence):
            if not isinstance(e, dict):
                semantic_errors.append(f"evidence_anchors[{idx_e}] must be an object")
                continue
            ks = str(e.get("id") or e.get("evidence_id") or "").strip()
            if not ks:
                semantic_errors.append(f"evidence_anchors[{idx_e}] missing id")
            elif ks in known_evidence_ids:
                semantic_errors.append(f"Duplicate evidence_id in CEG: {ks!r}")
            else:
                known_evidence_ids.add(ks)
                _, c_ver = _verify_rref(e.get("receipt_ref"), f"evidence_anchors[{idx_e}]", subject_id=ks)
                if authoritative_artifacts is not None:
                    emeta = e.get("metadata")
                    if isinstance(emeta, dict) and emeta.get("artifact_id"):
                        aid_ref = str(emeta["artifact_id"])
                        if aid_ref not in authoritative_artifacts:
                            semantic_errors.append(f"evidence_anchors[{idx_e}] metadata.artifact_id {aid_ref!r} not in authoritative DB")
                            c_ver = False
                anchor_verified_by_id[ks] = c_ver

    pos_by_claim: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claims_by_id}
    neg_by_claim: dict[str, list[dict[str, Any]]] = {cid: [] for cid in claims_by_id}
    unresolved_by_claim: dict[str, int] = {cid: 0 for cid in claims_by_id}
    unverified_rref_by_claim: dict[str, int] = {cid: 0 for cid in claims_by_id}
    dangling_edges: list[dict[str, Any]] = []

    if raw_edges is not None:
        if isinstance(raw_edges, dict):
            edge_iter: list[Any] = list(raw_edges.values())
        elif isinstance(raw_edges, list):
            edge_iter = raw_edges
        else:
            raise ValueError("CEG edges / support_edges must be a list or object")
        for idx, edge in enumerate(edge_iter):
            if not isinstance(edge, dict):
                raise ValueError(f"edges[{idx}] must be an object")
            cid = str(edge.get("claim_id") or edge.get("target_claim_id") or edge.get("target") or "").strip()
            ev_id = str(edge.get("evidence_id") or edge.get("source_id") or edge.get("source") or "").strip()
            claim_missing = (not cid) or (cid not in claims_by_id)
            if claim_missing:
                dangling_edges.append({"edge_index": idx, "reason": "unknown_claim_id", "claim_id": cid or None})
                semantic_errors.append(f"dangling support edge[{idx}]: unknown claim_id {cid!r}")
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
                    "claim_id": cid or None,
                    "evidence_id": ev_id or None,
                })
                semantic_errors.append(f"dangling support edge[{idx}]: {endpoint_problem} {ev_id!r}")
                if not claim_missing:
                    unresolved_by_claim[cid] += 1
                continue
            if claim_missing:
                continue
            _, edge_rref_ver = _verify_rref(edge.get("receipt_ref"), f"support_edges[{idx}]", subject_id=str(edge.get("id") or cid))
            is_rref_verified = anchor_verified_by_id.get(ev_id, True) and edge_rref_ver
            status = str(
                edge.get("support_status")
                if edge.get("support_status") is not None
                else (edge.get("status") or edge.get("relation") or edge.get("polarity") or "")
            ).strip().lower()
            if status in ("supported", "supports", "support", "verified_by"):
                if is_rref_verified:
                    pos_by_claim[cid].append(edge)
                else:
                    unverified_rref_by_claim[cid] += 1
            elif status in ("contradicted", "contradicts", "refuted", "refutes"):
                neg_by_claim[cid].append(edge)
            else:
                unresolved_by_claim[cid] += 1

    dep_adj: dict[str, set[str]] = {}
    contra_claim_ids: set[str] = set()
    rel_iter: list[Any] | None = (
        list(raw_relations.values())
        if isinstance(raw_relations, dict)
        else (raw_relations if isinstance(raw_relations, list) else None)
    )
    if rel_iter is not None:
        for idx_r, rel in enumerate(rel_iter):
            if not isinstance(rel, dict):
                semantic_errors.append(f"claim_relations[{idx_r}] must be an object")
                continue
            sc = str(rel.get("source_claim_id") or rel.get("src_claim_id") or "").strip()
            tc = str(rel.get("target_claim_id") or rel.get("dst_claim_id") or "").strip()
            rtype = str(rel.get("relation_type") or rel.get("relation") or "").strip()
            if not sc or sc not in claims_by_id:
                semantic_errors.append(f"dangling claim_relations[{idx_r}]: unknown source_claim_id {sc!r}")
            if not tc or tc not in claims_by_id:
                semantic_errors.append(f"dangling claim_relations[{idx_r}]: unknown target_claim_id {tc!r}")
            if sc and sc == tc and rtype in ("contradicts", "depends_on", "entails", "refines"):
                semantic_errors.append(f"claim_relations[{idx_r}]: self-loop {rtype} on {sc!r}")
            elif sc in claims_by_id and tc in claims_by_id:
                if rtype in ("depends_on", "entails", "refines"):
                    dep_adj.setdefault(sc, set()).add(tc)
                elif rtype == "contradicts":
                    contra_claim_ids.add(sc)
                    contra_claim_ids.add(tc)
            ev_refs = rel.get("evidence_refs")
            if isinstance(ev_refs, list) and known_evidence_ids is not None:
                for er in ev_refs:
                    ers = str(er).strip()
                    if not ers or ers not in known_evidence_ids:
                        semantic_errors.append(f"dangling claim_relations[{idx_r}] evidence_ref: {ers!r}")

    uncert_conflict_ids: set[str] = set()
    uncert_unverifiable_ids: set[str] = set()
    raw_uncerts = ceg_root.get("uncertainties")
    if isinstance(raw_uncerts, list):
        for u in raw_uncerts:
            if isinstance(u, dict):
                sid = str(u.get("subject_id") or "").strip()
                uk = str(u.get("kind") or "").strip()
                if sid:
                    if uk == "unresolved_contradiction":
                        uncert_conflict_ids.add(sid)
                    elif uk in ("unverifiable_claim", "missing_receipt", "ambiguous_locator", "generic_uncertainty"):
                        uncert_unverifiable_ids.add(sid)

    # Iterative cycle detection across directed claim dependency relations
    color: dict[str, int] = {}
    for start_c in sorted(dep_adj):
        if color.get(start_c, 0) != 0:
            continue
        stack_c: list[tuple[str, list[str], int]] = [(start_c, sorted(dep_adj.get(start_c, ())), 0)]
        color[start_c] = 1
        while stack_c:
            cur_c, nbrs, idx_n = stack_c[-1]
            if idx_n >= len(nbrs):
                color[cur_c] = 2
                stack_c.pop()
                continue
            stack_c[-1] = (cur_c, nbrs, idx_n + 1)
            nxt_c = nbrs[idx_n]
            st_c = color.get(nxt_c, 0)
            if st_c == 1:
                semantic_errors.append(f"claim_relations cycle detected involving {cur_c!r} -> {nxt_c!r}")
                break
            if st_c == 0:
                color[nxt_c] = 1
                stack_c.append((nxt_c, sorted(dep_adj.get(nxt_c, ())), 0))

    # Content-addressed integrity checks on canonical claim-evidence-graph-1.0 documents (v3.0 + v2.4 legacy compatible)
    if ceg_root.get("protocol") == "claim-evidence-graph-1.0":
        from ._stdlib import canonical_json, nfc_compact, sha256_hex

        for cid, cobj in claims_by_id.items():
            raw_t = str(cobj.get("text") or "")
            exp_nt = nfc_compact(raw_t)
            if "normalized_text" in cobj and cobj.get("normalized_text") != exp_nt:
                semantic_errors.append(f"claim {cid!r} normalized_text disagrees with text")
            exp_cd_v3 = sha256_hex(exp_nt)
            exp_cd_v2 = sha256_hex(
                canonical_json(
                    {
                        "claim_type": cobj.get("claim_type", "empirical_finding"),
                        "locator": cobj.get("locator") or "",
                        "target_work_id": cobj.get("target_work_id") or "",
                        "text": exp_nt,
                    }
                )
            )
            if "claim_digest" in cobj and cobj.get("claim_digest") not in (exp_cd_v3, exp_cd_v2):
                semantic_errors.append(f"claim {cid!r} claim_digest mismatch (expected {exp_cd_v3})")
        if "graph_digest" in ceg_root:
            body_for_digest = {
                "protocol": "claim-evidence-graph-1.0",
                "claims": ceg_root.get("claims"),
                "evidence_anchors": ceg_root.get("evidence_anchors"),
                "support_edges": ceg_root.get("support_edges"),
                "claim_relations": ceg_root.get("claim_relations"),
                "uncertainties": ceg_root.get("uncertainties"),
            }
            exp_gd_v3 = sha256_hex(canonical_json(body_for_digest))
            exp_gd_v2 = sha256_hex(canonical_json(dict(body_for_digest, graph_id=ceg_root.get("graph_id"))))
            act_gd = ceg_root.get("graph_digest")
            if act_gd not in (exp_gd_v3, exp_gd_v2):
                semantic_errors.append(f"graph_digest mismatch (expected {exp_gd_v3}, got {act_gd!r})")
            gid_s = str(ceg_root.get("graph_id") or "")
            if act_gd == exp_gd_v3 and gid_s.startswith("ceg-") and len(gid_s) == 20 and gid_s != f"ceg-{exp_gd_v3[:16]}":
                semantic_errors.append(f"graph_id {gid_s!r} disagrees with graph_digest prefix ceg-{exp_gd_v3[:16]}")

    if dec_content and (authoritative_artifacts is not None or receipts is not None):
        unknown_cp = sorted(set(dec_content) - known_content_keys)
        if unknown_cp:
            semantic_errors.append(f"content_payloads references unknown entity/artifact IDs: {unknown_cp!r}")

    has_graph_errors = bool(semantic_errors)
    anchors: list[dict[str, Any]] = []
    for cid, cobj in claims_by_id.items():
        raw_txt = str(cobj.get("text") or cobj.get("statement") or "").strip()
        norm_txt = " ".join(raw_txt.split()).rstrip(".").strip()
        meta_c = cobj.get("metadata") if isinstance(cobj.get("metadata"), dict) else {}
        c_status = str(cobj.get("support_status") or cobj.get("status") or meta_c.get("status") or "").strip().lower()
        pos_cnt = len(pos_by_claim.get(cid, ()))
        neg_cnt = len(neg_by_claim.get(cid, ()))
        unres_cnt = unresolved_by_claim.get(cid, 0)
        if has_graph_errors:
            anchor_status = "invalid_graph"
        elif (
            neg_cnt > 0
            or cid in contra_claim_ids
            or cid in uncert_conflict_ids
            or c_status in ("conflicted", "contested", "contradicted", "refuted")
        ):
            anchor_status = "conflicted"
        elif (
            pos_cnt > 0
            and norm_txt
            and unres_cnt == 0
            and cid not in uncert_unverifiable_ids
            and c_status not in ("unverifiable", "unresolved", "out_of_scope")
        ):
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
        "total_claims": len(anchors),
        "eligible_count": sum(1 for a in anchors if a["anchor_status"] == "eligible"),
        "conflicted_count": sum(1 for a in anchors if a["anchor_status"] == "conflicted"),
        "unsupported_count": sum(1 for a in anchors if a["anchor_status"] == "unsupported"),
        "dangling_edges": dangling_edges,
        "semantic_errors": semantic_errors,
        "anchors": anchors,
    }


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
    if p.exists() and not p.is_file():
        raise ValueError(f"CEG path must be a regular file: {p}")
    if not p.is_file():
        raise FileNotFoundError(f"CEG file not found: {p}")
    raw_bytes = p.read_bytes()
    ceg_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    data = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("CEG file must be a JSON object")
    rep = validate_ceg_semantics(data)
    return {
        "schema_version": "1.0.0",
        "ceg_sha256": ceg_sha256,
        "total_claims": rep["total_claims"],
        "eligible_count": rep["eligible_count"],
        "conflicted_count": rep["conflicted_count"],
        "unsupported_count": rep["unsupported_count"],
        "dangling_edges": rep["dangling_edges"],
        "semantic_errors": rep["semantic_errors"],
        "anchors": rep["anchors"],
    }

"""投稿前版式、双盲宏包、必含章节、统计离散度与论断收据绑定确定性检查器。

严格遵循确定性核验与非打分原则：
- 只输出带文件、行号或 PDF 页码定位的确定性命中清单（hits）与分类计数（summary_counts），绝不合成任何主观审稿分数或录用概率。
- 将会刊官方硬性规定（如双盲禁用终稿宏、必含 Limitations / Checklist 章节、正文页数上限）与方法论完整度提示（如实验数值表缺少误差棒/置信区间、摘要定量论断未绑定 CEG 收据）分层报告。
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

MAX_INCLUDE_DEPTH = 5
MAX_TEX_FILES = 64
MAX_TOTAL_BYTES = 20 * 1024 * 1024

INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
PACKAGE_OR_CLASS_RE = re.compile(r"\\(?:usepackage|documentclass)\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}", re.S)
SECTION_RE = re.compile(
    r"\\(?:section|subsection|paragraph|chapter)\*?\s*\{([^}]+)\}|^#{1,3}\s+(.+)$",
    re.M,
)
CHECKLIST_ENV_RE = re.compile(r"\\begin\{(?:checklist|neuripschecklist)\}", re.I)
UNRESOLVED_REF_RE = re.compile(
    r"(?:\\cite[a-zA-Z*]*\s*\{[^}]*\?[^}]*\}|\\(?:ref|eqref|autoref|Cref|cref)\s*\{\s*(?:\?+)?\s*\}|\b(?:Section|Table|Figure|Fig\.|Eq\.|Equation|Theorem|Appendix)\s+\?\?(?!\w))",
)
TODO_MARKER_RE = re.compile(r"\b(?:TODO|FIXME|TBD|XXX)\b")
TABLE_BLOCK_RE = re.compile(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", re.S)
NUMERIC_ROW_RE = re.compile(r"&[^\\]*\b\d+\.\d+\b")
DISPERSION_MARKER_RE = re.compile(
    r"(?:\\pm\b|±|\b(?:SD|SE|SEM|CI|IQR|std|stdev|variance|p\s*[<=>]|p-value|wilcoxon|mann-whitney|confidence\s+interval|seed|seeds)\b|\(\s*[+-]?\d+\.\d+\s*\))",
    re.I,
)
ABSTRACT_BLOCK_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
CONCLUSION_BLOCK_RE = re.compile(
    r"\\section\*?\{[^}]*(?:Conclusion|Conclusions|Discussion)[^}]*\}(.*?)(?=\\section\*?\{|\\bibliography|\\appendix|\\end\{document\}|$)",
    re.S | re.I,
)
QUANT_CLAIM_RE = re.compile(
    r"([^.\n]{10,240}?\b(?:\d+(?:\.\d+)?\s*(?:%|\\%|percent|x\b|×|fold|times\s+(?:faster|higher|lower|smaller|better))|(?:outperforms?|improves?|reduces?|accelerates?)[^.\n]{0,60}?\b\d+(?:\.\d+)?\s*(?:%|\\%|x\b|×))[^.\n]{0,120}\.)",
    re.I,
)
INLINE_CEG_TAG_RE = re.compile(r"%\s*(?:ark|ceg):(?:claim|receipt)=([A-Za-z0-9_.:-]+)")
REFERENCES_HEADING_RE = re.compile(r"^\s*(?:References|Bibliography|参考文献)\s*$", re.M | re.I)
APPENDIX_HEADING_RE = re.compile(r"^\s*(?:Appendix|Appendices|Supplementary\s+Material|附录)\b", re.M | re.I)
EXEMPT_STATEMENT_HEADING_RE = re.compile(
    r"^\s*(?:\d+(?:\.\d+)*\s+)?(?:Reproducibility\s+Statement|Ethics\s+Statement|Broader\s+Impacts?|Impact\s+Statement|Acknowledgments?|Acknowledgements?)\s*$",
    re.M | re.I,
)
FORBIDDEN_DOUBLE_BLIND_OPTION_TOKENS = {"final", "accepted", "preprint", "cameraready", "camera-ready", "nonblind"}


def _default_specs_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "references" / "venue-specs.json",
        here.parent / "venue-specs.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError("venue-specs.json not found near pre_submission_linter.py")


def load_venue_specs(specs_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(specs_path) if specs_path else _default_specs_path()
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_latex_comments(text: str) -> str:
    """Strip unescaped % comments line by line while preserving line numbers."""
    out_lines = []
    for line in text.splitlines():
        m = re.search(r"(?<!\\)%", line)
        if m:
            out_lines.append(line[: m.start()])
        else:
            out_lines.append(line)
    return "\n".join(out_lines)


def collect_tex_tree(entry_tex: Path) -> tuple[list[tuple[Path, str]], list[dict[str, Any]]]:
    r"""Collect entry .tex and bounded relative \input / \include files without escaping manuscript root."""
    entry_tex = entry_tex.resolve()
    if not entry_tex.is_file():
        raise ValueError(f"TeX entry file does not exist: {entry_tex}")
    root_dir = entry_tex.parent
    visited: set[Path] = set()
    collected: list[tuple[Path, str]] = []
    include_hits: list[dict[str, Any]] = []
    total_bytes = 0

    def _resolve_include_candidate(current_file: Path, target: str) -> Path:
        for base_dir in (root_dir, current_file.parent):
            cand = base_dir / target
            if not cand.suffix:
                cand_tex = cand.with_suffix(".tex")
                if cand_tex.exists() or not cand.exists():
                    cand = cand_tex
            resolved = cand.resolve()
            if not resolved.is_relative_to(root_dir):
                raise ValueError(f"TeX include escapes manuscript root: {target}")
            if resolved.is_file():
                return resolved
        fallback = root_dir / target
        if not fallback.suffix:
            fallback = fallback.with_suffix(".tex")
        resolved_fb = fallback.resolve()
        if not resolved_fb.is_relative_to(root_dir):
            raise ValueError(f"TeX include escapes manuscript root: {target}")
        return resolved_fb

    def _walk(current: Path, depth: int, caller_locator: str | None = None) -> None:
        nonlocal total_bytes
        if depth > MAX_INCLUDE_DEPTH:
            include_hits.append({
                "code": "TEX_BUNDLE_TRUNCATED",
                "severity": "blocker",
                "locator": caller_locator or current.name,
                "message": f"TeX include depth exceeded maximum limit ({MAX_INCLUDE_DEPTH}); bundle coverage is incomplete.",
                "excerpt": str(current.name),
            })
            return
        if len(collected) >= MAX_TEX_FILES:
            include_hits.append({
                "code": "TEX_BUNDLE_TRUNCATED",
                "severity": "blocker",
                "locator": caller_locator or current.name,
                "message": f"TeX file count exceeded maximum limit ({MAX_TEX_FILES}); bundle coverage is incomplete.",
                "excerpt": str(current.name),
            })
            return
        resolved = current.resolve()
        if resolved in visited:
            return
        if not resolved.is_relative_to(root_dir):
            raise ValueError(f"TeX include escapes manuscript root: {current}")
        if not resolved.is_file():
            include_hits.append({
                "code": "UNRESOLVED_TEX_INCLUDE",
                "severity": "blocker",
                "locator": caller_locator or resolved.name,
                "message": f"Included TeX file not found: {resolved.relative_to(root_dir).as_posix()!r}.",
                "excerpt": str(resolved.name),
            })
            return
        size = resolved.stat().st_size
        if total_bytes + size > MAX_TOTAL_BYTES:
            raise ValueError(f"TeX bundle exceeds maximum byte budget ({MAX_TOTAL_BYTES} bytes)")
        visited.add(resolved)
        total_bytes += size
        raw = resolved.read_text(encoding="utf-8", errors="replace")
        collected.append((resolved, raw))
        uncommented = _strip_latex_comments(raw)
        rel_self = resolved.relative_to(root_dir).as_posix()
        for m in INPUT_RE.finditer(uncommented):
            target = m.group(1).strip()
            if not target:
                continue
            line_no = uncommented[: m.start()].count("\n") + 1
            cand = _resolve_include_candidate(resolved, target)
            _walk(cand, depth + 1, caller_locator=f"{rel_self}:L{line_no}")

    _walk(entry_tex, 0)
    return collected, include_hits


def _extract_pdf_page_texts(pdf_path: Path) -> tuple[list[str] | None, str | None]:
    """Extract per-page text using fitz (PyMuPDF) or pypdf (bundled with [research] extra)."""
    try:
        import fitz  # type: ignore
        doc = fitz.open(str(pdf_path))
        try:
            return [doc[idx].get_text("text") or "" for idx in range(len(doc))], "pymupdf"
        finally:
            doc.close()
    except ImportError:
        pass
    except Exception as exc:
        return None, f"invalid_pdf:{exc}"

    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(pdf_path))
        return [(page.extract_text() or "") for page in reader.pages], "pypdf"
    except ImportError:
        return None, "missing_dependency"
    except Exception as exc:
        return None, f"invalid_pdf:{exc}"


def _has_main_body_before_heading(page_text: str, heading_match: re.Match) -> bool:
    """Return True if substantive main-body text appears on the same page prior to the heading."""
    prefix = page_text[: heading_match.start()].strip()
    if not prefix:
        return False
    meaningful_lines = []
    for line in prefix.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.fullmatch(r"\d+", s):
            continue
        if re.search(r"(?:Under review as a conference paper|Anonymous Author|Preprint\.|Submitted to)", s, re.I):
            continue
        if EXEMPT_STATEMENT_HEADING_RE.match(s):
            continue
        meaningful_lines.append(s)
    return len(meaningful_lines) > 0


def _inspect_pdf_pages(
    pdf_path: Path,
    max_main_pages: int | None,
    references_unlimited: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hits: list[dict[str, Any]] = []
    info: dict[str, Any] = {
        "pdf_inspected": False,
        "parser": None,
        "total_pages": None,
        "references_start_page": None,
        "appendix_start_page": None,
        "main_body_pages": None,
        "main_body_max_pages": max_main_pages,
        "references_unlimited": references_unlimited,
    }
    page_texts, status_or_parser = _extract_pdf_page_texts(pdf_path)
    if page_texts is None:
        if status_or_parser == "missing_dependency":
            info["note"] = "Neither pypdf nor pymupdf is installed; requested PDF check could not be executed."
            hits.append({
                "code": "PDF_INSPECTION_UNAVAILABLE",
                "severity": "blocker",
                "locator": pdf_path.name,
                "message": "PDF page-limit verification was requested via --pdf, but neither pypdf nor pymupdf is installed.",
                "excerpt": "Install academic-research-kernel[research] to enable PDF inspection.",
            })
        else:
            info["note"] = f"Failed to parse PDF file: {status_or_parser}"
            hits.append({
                "code": "INVALID_PDF_FILE",
                "severity": "blocker",
                "locator": pdf_path.name,
                "message": f"Supplied PDF file could not be parsed ({status_or_parser}).",
                "excerpt": pdf_path.name,
            })
        return info, hits

    total_pages = len(page_texts)
    ref_page = None
    ref_shared_with_body = False
    app_page = None
    app_shared_with_body = False

    for idx, page_text in enumerate(page_texts):
        m_ref = REFERENCES_HEADING_RE.search(page_text)
        if ref_page is None and m_ref:
            ref_page = idx + 1
            ref_shared_with_body = _has_main_body_before_heading(page_text, m_ref)
        m_app = APPENDIX_HEADING_RE.search(page_text)
        if app_page is None and m_app:
            app_page = idx + 1
            app_shared_with_body = _has_main_body_before_heading(page_text, m_app)

    if not references_unlimited:
        if app_page is not None:
            main_pages = app_page if app_shared_with_body else max(1, app_page - 1)
        else:
            main_pages = total_pages
    else:
        cutoffs: list[int] = []
        if ref_page is not None:
            cutoffs.append(ref_page if ref_shared_with_body else max(1, ref_page - 1))
        if app_page is not None:
            cutoffs.append(app_page if app_shared_with_body else max(1, app_page - 1))
        main_pages = min(cutoffs) if cutoffs else total_pages

    info.update({
        "pdf_inspected": True,
        "parser": status_or_parser,
        "total_pages": total_pages,
        "references_start_page": ref_page,
        "appendix_start_page": app_page,
        "main_body_pages": main_pages,
    })
    if max_main_pages is not None and main_pages > max_main_pages:
        hits.append({
            "code": "MAIN_BODY_PAGE_LIMIT_EXCEEDED",
            "severity": "blocker",
            "locator": f"{pdf_path.name}:page={main_pages}",
            "message": f"Estimated main body spans {main_pages} pages, exceeding venue limit of {max_main_pages} pages.",
            "excerpt": f"total_pages={total_pages}, references_start_page={ref_page}, appendix_start_page={app_page}",
        })
    return info, hits


def _load_ceg_verified_claims(ceg_path: Path | None) -> set[str]:
    """Return set of verified claim IDs and statements that have positive support and zero contradiction."""
    if ceg_path is None or not ceg_path.is_file():
        return set()
    data = json.loads(ceg_path.read_text(encoding="utf-8"))
    claims = data.get("claims") or data.get("ceg", {}).get("claims") or []
    edges = data.get("support_edges") or data.get("edges") or data.get("ceg", {}).get("support_edges") or []

    supported_ids: set[str] = set()
    contradicted_ids: set[str] = set()
    for e in edges:
        if not isinstance(e, dict):
            continue
        cid = str(e.get("claim_id") or e.get("target_claim_id") or "")
        if not cid:
            continue
        status = str(
            e.get("support_status")
            if e.get("support_status") is not None
            else (e.get("relation") or e.get("polarity") or "")
        ).strip().lower()
        if status in ("supported", "supports", "support", "verified_by"):
            supported_ids.add(cid)
        elif status in ("contradicted", "contradicts", "refuted", "refutes", "unverifiable", "out_of_scope"):
            contradicted_ids.add(cid)

    verified: set[str] = set()
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or c.get("claim_id") or "")
        txt = str(c.get("text") or c.get("statement") or "").strip()
        c_status = str(c.get("support_status") or c.get("status") or "").strip().lower()
        if cid in contradicted_ids or c_status in ("contradicted", "unverifiable", "out_of_scope"):
            continue
        has_positive_support = (
            cid in supported_ids
            or c_status == "supported"
            or (bool(c.get("receipt_refs") or c.get("evidence_ids")) and not edges)
        )
        if cid and has_positive_support:
            verified.add(cid)
            if txt:
                verified.add(txt)
    return verified


def _check_package_options_for_double_blind(uncommented: str, rel_name: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for m in PACKAGE_OR_CLASS_RE.finditer(uncommented):
        opts_raw = m.group(1) or ""
        pkg_name = (m.group(2) or "").strip()
        if not opts_raw:
            continue
        line_no = uncommented[: m.start()].count("\n") + 1
        tokens = [t.strip().lower().replace(" ", "") for t in opts_raw.split(",") if t.strip()]
        for tok in tokens:
            if tok in FORBIDDEN_DOUBLE_BLIND_OPTION_TOKENS or tok == "anonymous=false" or tok == "review=false":
                hits.append({
                    "code": "FORBIDDEN_REVIEW_PATTERN",
                    "severity": "blocker",
                    "locator": f"{rel_name}:L{line_no}",
                    "message": f"De-anonymizing or camera-ready package option {tok!r} on {pkg_name!r} is forbidden in double-blind review.",
                    "excerpt": " ".join(m.group(0).split())[:160],
                })
    return hits


def lint_manuscript(
    tex_path: str | Path,
    venue: str = "iclr",
    contribution_type: str = "general_empirical",
    phase: str = "submission",
    pdf_path: str | Path | None = None,
    ceg_path: str | Path | None = None,
    require_ceg_binding: bool = False,
    specs_path: str | Path | None = None,
) -> dict[str, Any]:
    specs = load_venue_specs(specs_path)
    venues = specs.get("venues", {})
    venue_key = venue.strip().lower()
    if venue_key not in venues:
        raise ValueError(f"Unknown venue {venue!r}. Available venues: {sorted(venues.keys())}")
    vspec = venues[venue_key]

    phase_key = phase.strip().lower()
    if phase_key not in ("submission", "rebuttal", "camera_ready"):
        raise ValueError(f"Unknown phase {phase!r}. Must be 'submission', 'rebuttal', or 'camera_ready'.")

    ctypes = specs.get("contribution_types", {})
    ctype_key = contribution_type.strip().lower()
    if ctype_key not in ctypes:
        raise ValueError(f"Unknown contribution_type {contribution_type!r}. Available: {sorted(ctypes.keys())}")
    cspec = ctypes[ctype_key]

    entry_tex = Path(tex_path).resolve()
    tex_files, include_hits = collect_tex_tree(entry_tex)
    hits: list[dict[str, Any]] = list(include_hits)
    discovered_sections: list[str] = []

    verified_ceg = _load_ceg_verified_claims(Path(ceg_path) if ceg_path else None)

    for fpath, raw in tex_files:
        rel_name = fpath.name if len(tex_files) == 1 else fpath.relative_to(entry_tex.parent).as_posix()
        uncommented = _strip_latex_comments(raw)
        lines = uncommented.splitlines()

        if phase_key != "camera_ready":
            for pat in vspec.get("forbidden_patterns_in_review", []):
                for idx, line in enumerate(lines, 1):
                    if pat in line:
                        hits.append({
                            "code": "FORBIDDEN_REVIEW_PATTERN",
                            "severity": "blocker",
                            "locator": f"{rel_name}:L{idx}",
                            "message": f"Forbidden pattern {pat!r} detected for {vspec['display_name']} ({vspec['review_mode']}).",
                            "excerpt": line.strip()[:160],
                        })
            if vspec.get("review_mode") == "double_blind":
                hits.extend(_check_package_options_for_double_blind(uncommented, rel_name))

        for m in SECTION_RE.finditer(uncommented):
            sec_title = (m.group(1) or m.group(2) or "").strip()
            if sec_title:
                discovered_sections.append(sec_title)
        if CHECKLIST_ENV_RE.search(uncommented):
            discovered_sections.append("NeurIPS Paper Checklist")

        for idx, line in enumerate(lines, 1):
            m_ref = UNRESOLVED_REF_RE.search(line)
            if m_ref:
                hits.append({
                    "code": "UNRESOLVED_LATEX_REFERENCE",
                    "severity": "blocker",
                    "locator": f"{rel_name}:L{idx}",
                    "message": "Unresolved citation or cross-reference placeholder detected.",
                    "excerpt": m_ref.group(0)[:160],
                })
            m_todo = TODO_MARKER_RE.search(line)
            if m_todo:
                hits.append({
                    "code": "LEFT_OVER_TODO_MARKER",
                    "severity": "warning",
                    "locator": f"{rel_name}:L{idx}",
                    "message": f"Draft marker {m_todo.group(0)!r} left in manuscript text.",
                    "excerpt": line.strip()[:160],
                })

        for m_tbl in TABLE_BLOCK_RE.finditer(uncommented):
            tbl_body = m_tbl.group(1)
            start_line = uncommented[: m_tbl.start()].count("\n") + 1
            if NUMERIC_ROW_RE.search(tbl_body) and not DISPERSION_MARKER_RE.search(tbl_body):
                hits.append({
                    "code": "TABLE_MISSING_DISPERSION",
                    "severity": "warning",
                    "locator": f"{rel_name}:L{start_line}",
                    "message": "Numeric result table reports point estimates without dispersion/uncertainty indicators (\\pm, SD, SE, CI, p-value, or seed count).",
                    "excerpt": " ".join(tbl_body.split())[:160],
                })

        if require_ceg_binding or ceg_path is not None:
            for block_kind, block_re in (("abstract", ABSTRACT_BLOCK_RE), ("conclusion", CONCLUSION_BLOCK_RE)):
                for m_blk in block_re.finditer(raw):
                    blk_raw = m_blk.group(1)
                    blk_uncommented = _strip_latex_comments(blk_raw)
                    blk_start_line = raw[: m_blk.start(1)].count("\n") + 1
                    block_tags = set(INLINE_CEG_TAG_RE.findall(blk_raw))
                    valid_block_tags = block_tags & verified_ceg
                    for m_q in QUANT_CLAIM_RE.finditer(blk_uncommented):
                        claim_sentence = " ".join(m_q.group(1).split())
                        line_offset = blk_uncommented[: m_q.start()].count("\n")
                        loc_line = blk_start_line + line_offset
                        text_matched = any(
                            v in claim_sentence or claim_sentence in v
                            for v in verified_ceg
                            if len(v) > 8
                        )
                        if not valid_block_tags and not text_matched:
                            hits.append({
                                "code": "UNGROUNDED_QUANTITATIVE_CLAIM",
                                "severity": "warning",
                                "locator": f"{rel_name}:L{loc_line}",
                                "message": f"Quantitative claim in {block_kind} has no verified ClaimEvidenceGraph support edge or resolved % ark:claim=<id> anchor.",
                                "excerpt": claim_sentence[:180],
                            })

    for req_sec in vspec.get("required_sections", []):
        pat = re.compile(re.escape(req_sec), re.I)
        if not any(pat.search(s) for s in discovered_sections):
            hits.append({
                "code": "MISSING_REQUIRED_SECTION",
                "severity": "blocker",
                "locator": f"{entry_tex.name}:global",
                "message": f"Missing required dedicated section or checklist for {vspec['display_name']}: {req_sec!r}.",
                "excerpt": f"Discovered sections: {discovered_sections[:10]}",
            })

    phase_limits = vspec.get("phase_max_pages") or {}
    eff_max_pages = phase_limits.get(phase_key, vspec.get("main_body_max_pages"))
    pdf_info: dict[str, Any] = {"pdf_inspected": False, "main_body_max_pages": eff_max_pages, "phase": phase_key}
    if pdf_path is not None:
        p_path = Path(pdf_path)
        if not p_path.is_file():
            raise ValueError(f"PDF file does not exist: {pdf_path}")
        pdf_info, pdf_hits = _inspect_pdf_pages(
            p_path,
            eff_max_pages,
            references_unlimited=bool(vspec.get("references_unlimited", True)),
        )
        pdf_info["phase"] = phase_key
        hits.extend(pdf_hits)

    by_code = dict(Counter(h["code"] for h in hits))
    by_severity = dict(Counter(h["severity"] for h in hits))
    blocker_count = by_severity.get("blocker", 0)

    return {
        "schema_version": "1.0.0",
        "passed": blocker_count == 0,
        "venue": venue_key,
        "venue_display_name": vspec["display_name"],
        "phase": phase_key,
        "review_mode": vspec["review_mode"],
        "contribution_type": ctype_key,
        "contribution_label": cspec["label"],
        "files_scanned": len(tex_files),
        "discovered_sections": discovered_sections,
        "pdf_check": pdf_info,
        "summary_counts": {
            "total_hits": len(hits),
            "blockers": blocker_count,
            "warnings": by_severity.get("warning", 0),
            "by_code": by_code,
        },
        "hits": hits,
        "prereview_checklist": {
            "contribution_specific_evidence": cspec["primary_evidence_requirements"],
            "official_venue_rules": vspec.get("official_guideline_rules", []),
            "recommended_sections": vspec.get("recommended_sections", []),
            "observed_form_metadata": vspec.get("observed_form_metadata", {}),
            "review_dimensions": specs.get("review_dimensions", []),
            "methodological_lenses": specs.get("methodological_lenses", []),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic pre-submission manuscript linter.")
    parser.add_argument("--tex", required=True, help="Path to main .tex entry file")
    parser.add_argument("--venue", default="iclr", help="Target venue key (iclr, neurips, icml, acl, kdd, ieee_tmm, acm_tois, arxiv_preprint)")
    parser.add_argument("--phase", choices=["submission", "rebuttal", "camera_ready"], default="submission", help="Submission phase")
    parser.add_argument("--contribution-type", default="general_empirical", help="Contribution type key")
    parser.add_argument("--pdf", help="Optional compiled PDF path for main-body page limit verification")
    parser.add_argument("--ceg", help="Optional ClaimEvidenceGraph JSON snapshot path")
    parser.add_argument("--require-ceg-binding", action="store_true", help="Flag quantitative claims in Abstract/Conclusion without CEG binding")
    parser.add_argument("--output", help="Optional output JSON file path")
    args = parser.parse_args(argv)

    report = lint_manuscript(
        tex_path=args.tex,
        venue=args.venue,
        contribution_type=args.contribution_type,
        phase=args.phase,
        pdf_path=args.pdf,
        ceg_path=args.ceg,
        require_ceg_binding=args.require_ceg_binding,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

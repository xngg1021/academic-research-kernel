"""Deterministic, bounded, fail-closed pre-submission manuscript linter (Occam edition).

Enforces hard aggregate byte/file/depth traversal budgets and deterministic
submission blockers (missing includes, unresolved references, missing/undefined
bibliography, venue required sections, review-phase anonymity/final-option leaks,
table dispersion warnings, PDF page limits, and verified CEG claim anchors)
without attempting Turing-complete TeX macro interpretation.
"""
from __future__ import annotations

from importlib import resources
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Optional

from ._stdlib import freeze, is_link_or_reparse, safe_path
from .double_blind_sanitizer import strip_tex_comments

MAX_INCLUDE_DEPTH = 16
MAX_TEX_FILES = 64
MAX_BIB_FILES = 32
MAX_WALK_ENTRIES = 2000
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 20 MiB aggregate budget across TeX + Bib

_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")
_ARK_CLAIM_RE = re.compile(r"(?<!\\)%\s*ark:claim=([^\s%]+)")
_INPUT_RE = re.compile(
    r"\\(?:input|include)(?![A-Za-z@])(?:\s*\{([^{}]+)\}|\s*\"([^\"]+)\"|\s*([^\s\\{}%\"]+))"
)
_ASSET_INPUT_RE = re.compile(
    r"\\(?:verbatiminput|lstinputlisting|includegraphics|includepdf)\*?\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}"
    r"|\\inputminted\*?\s*(?:\[[^\]]*\]\s*)*\{[^{}]+\}\s*\{([^{}]+)\}"
)
_SUBFILE_RE = re.compile(r"\\subfile\*?\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}")
_IMPORT_PKG_RE = re.compile(r"\\(?:sub)?import\*?\s*\{([^{}]+)\}\s*\{([^{}]+)\}")
_VIRTUAL_TEX_INCLUDES = frozenset({"glyphtounicode", "glyphtounicode-cmex", "glyphtounicode-cmr"})
_DOC_CLASS_RE = re.compile(r"\\documentclass(?:\s*\[([^\]]*)\])?\s*\{([^{}]+)\}")
_USEPKG_RE = re.compile(r"\\usepackage(?:\s*\[([^\]]*)\])?\s*\{([^{}]+)\}")
_BENIGN_FINAL_PACKAGES = frozenset({
    "microtype", "graphicx", "hyperref", "listings", "babel", "showkeys",
    "draftwatermark", "changes", "todonotes", "lineno", "pdfpages",
    "subfig", "caption", "cleveref", "minted", "tcolorbox", "tikz",
})
_SECTION_RE = re.compile(r"\\(?:section|subsection|paragraph)\*?\s*\{([^{}]+)\}", re.IGNORECASE)
_CITE_RE = re.compile(r"\\cite[a-zA-Z*]*\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}")
_NOCITE_STAR_RE = re.compile(r"\\nocite\s*\{\s*\*\s*\}")
_LABEL_RE = re.compile(r"\\label\s*\{([^{}]+)\}")
_REF_RE = re.compile(r"\\(?:ref|eqref|autoref|cref|Cref|pageref)\s*\{([^{}]+)\}")
_BIB_ENTRY_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s{}]+)\s*,", re.IGNORECASE)
_BIB_CROSSREF_RE = re.compile(r"\b(?:crossref|xdata)\s*=\s*(?:\{([^{}]+)\}|\"([^\"]+)\")", re.IGNORECASE)
_BIBITEM_RE = re.compile(r"\\bibitem(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}")
_BIB_DECL_RE = re.compile(r"\\(bibliography|addbibresource)\s*(?:\[[^\]]*\]\s*)*\{([^{}]+)\}")
_FORBIDDEN_LAYOUT_RE = re.compile(
    r"\\(?:vspace\s*\{\s*-\d|baselinestretch|setlength\s*\{\s*\\(?:textwidth|textheight|topmargin|evensidemargin|oddsidemargin))"
)
_FINAL_COPY_RE = re.compile(
    r"\\(?:iclrfinalcopy|neuripsfinalcopy|aclfinalcopy|icmlfinalcopy|cameraready)\b", re.IGNORECASE
)
_ACK_ENV_RE = re.compile(
    r"\\begin\s*\{\s*(?:ack|acknowledgments?|acknowledgements?)\s*\}|\\section\*?\s*\{\s*acknowledg(?:e)?ments?\s*\}",
    re.IGNORECASE,
)
_FUNDING_RE = re.compile(
    r"\b(?:supported\s+by\s+(?:grant|nsf|nih|darpa|erc|nsfc)|grant\s+(?:no\.|number|#)\s*[A-Z0-9-]+)\b",
    re.IGNORECASE,
)
_NON_ANON_HOST_RE = re.compile(
    r"https?://(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org|huggingface\.co)/(?!anonymous\b)[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)
_TODO_RE = re.compile(r"\\todo\s*\{|\b(?:TODO|FIXME|XXX)\b")
_TABULAR_RE = re.compile(r"\\begin\{tabular\}.*?\\end\{tabular\}", re.DOTALL)
_DISPERSION_RE = re.compile(r"\\pm\b|±|\b(?:std|sd|se|ci|iqr)\b", re.IGNORECASE)
_QUANT_SENTENCE_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:(?:\\%|%|×)(?!\w)|(?:x|\\times|ms|s|dB|pp)\b)"
    r"|\bp\s*[<=>]\s*0?\.\d+\b"
    r"|\b(?:improves?|reduces?|outperforms?|increases?|decreases?|speedup|faster|smaller)\b[^\n.]{0,40}\b\d+(?:\.\d+)?\b)",
    re.IGNORECASE,
)
_OVERCLAIM_STYLE_RE = re.compile(
    r"\b(?:prove[sd]?\s+beyond\s+doubt|100\s*%?\s+guaranteed|universally\s+superior|eliminates?\s+all\s+errors)\b",
    re.IGNORECASE,
)


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, max(0, offset)) + 1


def _extract_braced_blocks(text: str, command: str) -> list[tuple[int, str]]:
    """Multiline-aware balanced brace extractor for commands such as \\author{...} and \\thanks{...}."""
    out: list[tuple[int, str]] = []
    pat = re.compile(r"\\" + re.escape(command) + r"\s*(?:\[[^\]]*\]\s*)*\{")
    pos = 0
    while True:
        m = pat.search(text, pos)
        if not m:
            break
        start_brace = m.end() - 1
        depth = 0
        i = start_brace
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == "\\":
                i += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    out.append((_line_of(text, m.start()), text[start_brace + 1 : i]))
                    pos = i + 1
                    break
            i += 1
        else:
            out.append((_line_of(text, m.start()), text[start_brace + 1 :]))
            break
    return out


def load_venue_specs(specs_path: str | Path | None = None) -> dict[str, Any]:
    if specs_path is not None:
        raw = safe_path(specs_path).read_text(encoding="utf-8")
        return json.loads(raw)
    try:
        ref = resources.files("academic_research_kernel").joinpath("venue-specs.json")
        if ref.is_file():
            return json.loads(ref.read_text(encoding="utf-8"))
    except Exception:
        pass
    pkg_local = Path(__file__).resolve().parent / "venue-specs.json"
    if pkg_local.is_file():
        return json.loads(pkg_local.read_text(encoding="utf-8"))
    fallback = Path(__file__).resolve().parents[2] / "skills" / "academic-writing" / "references" / "venue-specs.json"
    if fallback.is_file():
        return json.loads(fallback.read_text(encoding="utf-8"))
    return {"venues": {}}


def collect_tex_tree(
    entry_tex: str | Path,
    *,
    max_files: int = MAX_TEX_FILES,
    max_depth: int = MAX_INCLUDE_DEPTH,
    max_bytes: int = MAX_TOTAL_BYTES,
) -> tuple[Path, list[tuple[Path, str, str]], list[dict[str, Any]], int]:
    """Bounded TeX bundle collector returning (root, [(path, raw, stripped)], blocker_findings, bytes_used)."""
    entry = safe_path(entry_tex)
    if entry.is_dir() and (entry / "main.tex").is_file():
        entry = safe_path(entry / "main.tex", root=entry)
    if not entry.is_file():
        raise FileNotFoundError(f"TeX entry file not found: {entry_tex}")
    root = entry.parent
    visited: set[Path] = set()
    active_stack: set[Path] = set()
    ordered: list[tuple[Path, str, str]] = []
    findings: list[dict[str, Any]] = []
    bytes_used = 0
    budget_tripped = False

    def _walk(cur: Path, depth: int, ref_from: Optional[Path], ref_line: int) -> None:
        nonlocal bytes_used, budget_tripped
        if budget_tripped:
            return
        try:
            checked = safe_path(cur, root=root)
        except ValueError as exc:
            findings.append({
                "code": "UNSAFE_INCLUDE_PATH",
                "severity": "error",
                "file": ref_from.relative_to(root).as_posix() if ref_from else str(cur),
                "line": ref_line,
                "detail": str(exc),
            })
            return
        if checked in active_stack:
            findings.append({
                "code": "INCLUDE_CYCLE",
                "severity": "error",
                "file": checked.relative_to(root).as_posix(),
                "line": ref_line,
                "detail": f"Cyclic \\input/\\include detected at {checked.name}",
            })
            return
        if checked in visited:
            return
        if not checked.is_file():
            findings.append({
                "code": "MISSING_INCLUDE",
                "severity": "error",
                "file": ref_from.relative_to(root).as_posix() if ref_from else checked.name,
                "line": ref_line,
                "detail": f"Included TeX file not found: {cur.name}",
            })
            return
        if depth > max_depth:
            budget_tripped = True
            findings.append({
                "code": "INCOMPLETE_COVERAGE",
                "severity": "error",
                "file": checked.relative_to(root).as_posix(),
                "line": ref_line,
                "detail": f"Include nesting exceeds max_depth={max_depth}",
            })
            return
        if len(visited) >= max_files:
            budget_tripped = True
            findings.append({
                "code": "INCOMPLETE_COVERAGE",
                "severity": "error",
                "file": checked.relative_to(root).as_posix(),
                "line": ref_line,
                "detail": f"Bundle exceeds max_files={max_files}; refusing partial pass",
            })
            return
        fsize = checked.stat().st_size
        if bytes_used + fsize > max_bytes:
            budget_tripped = True
            findings.append({
                "code": "INCOMPLETE_COVERAGE",
                "severity": "error",
                "file": checked.relative_to(root).as_posix(),
                "line": 1,
                "detail": f"Bundle exceeds aggregate {max_bytes} byte budget",
            })
            return

        visited.add(checked)
        active_stack.add(checked)
        bytes_used += fsize
        raw_txt = checked.read_text(encoding="utf-8", errors="replace")
        cleaned = strip_tex_comments(raw_txt)
        ordered.append((checked, raw_txt, cleaned))
        for m in _INPUT_RE.finditer(cleaned):
            rel = (m.group(1) or m.group(2) or m.group(3) or "").strip()
            if not rel:
                continue
            ln = _line_of(cleaned, m.start())
            rel_tex = rel if Path(rel).suffix.lower() == ".tex" else f"{rel}.tex"
            # LaTeX resolves \input/\include relative to the manuscript root working directory first;
            # fall back to the including file's directory only when root-relative does not exist.
            cand_root = root / rel_tex
            cand_local = checked.parent / rel_tex
            cand = cand_local if (not cand_root.exists() and cand_local.exists()) else cand_root
            if not cand.exists() and Path(rel).name.lower() in _VIRTUAL_TEX_INCLUDES and Path(rel).parent == Path("."):
                continue
            _walk(cand, depth + 1, checked, ln)
        for m_sub in _SUBFILE_RE.finditer(cleaned):
            rel_sf = (m_sub.group(1) or "").strip()
            if not rel_sf:
                continue
            ln_sf = _line_of(cleaned, m_sub.start())
            rel_sf_tex = rel_sf if Path(rel_sf).suffix.lower() == ".tex" else f"{rel_sf}.tex"
            cand_sf_r = root / rel_sf_tex
            cand_sf_l = checked.parent / rel_sf_tex
            cand_sf = cand_sf_l if (not cand_sf_r.exists() and cand_sf_l.exists()) else cand_sf_r
            _walk(cand_sf, depth + 1, checked, ln_sf)
        for m_asset in _ASSET_INPUT_RE.finditer(cleaned):
            rel_a = (m_asset.group(1) or m_asset.group(2) or "").strip()
            if not rel_a:
                continue
            ln_a = _line_of(cleaned, m_asset.start())
            rel_file = checked.relative_to(root).as_posix()
            if Path(rel_a).is_absolute():
                findings.append({
                    "code": "UNSAFE_INCLUDE_PATH",
                    "severity": "error",
                    "file": rel_file,
                    "line": ln_a,
                    "detail": f"Absolute asset/listing include path {rel_a!r} escapes manuscript root",
                })
                continue
            cand_ra = root / rel_a
            cand_la = checked.parent / rel_a
            cand_a = cand_la if (not cand_ra.exists() and cand_la.exists()) else cand_ra
            try:
                safe_path(cand_a, root=root)
            except ValueError as exc:
                findings.append({
                    "code": "UNSAFE_INCLUDE_PATH",
                    "severity": "error",
                    "file": rel_file,
                    "line": ln_a,
                    "detail": str(exc),
                })
        for m_imp in _IMPORT_PKG_RE.finditer(cleaned):
            imp_dir, imp_file = m_imp.group(1).strip(), m_imp.group(2).strip()
            ln_i = _line_of(cleaned, m_imp.start())
            rel_file = checked.relative_to(root).as_posix()
            if Path(imp_dir).is_absolute() or Path(imp_file).is_absolute():
                findings.append({
                    "code": "UNSAFE_INCLUDE_PATH",
                    "severity": "error",
                    "file": rel_file,
                    "line": ln_i,
                    "detail": f"Absolute \\import path ({imp_dir!r}, {imp_file!r}) escapes manuscript root",
                })
                continue
            imp_tex = imp_file if Path(imp_file).suffix.lower() == ".tex" else f"{imp_file}.tex"
            cand_imp = (checked.parent / imp_dir / imp_tex) if m_imp.group(0).startswith(r"\sub") else (root / imp_dir / imp_tex)
            _walk(cand_imp, depth + 1, checked, ln_i)
        active_stack.discard(checked)

    _walk(entry, 0, None, 1)
    return root, ordered, findings, bytes_used


def _parse_single_bib_text(txt: str, keys: set[str], dups: list[str], crossrefs: dict[str, set[str]]) -> None:
    matches = [m for m in _BIB_ENTRY_RE.finditer(txt) if m.group(1).lower() not in ("comment", "preamble", "string")]
    for idx, m in enumerate(matches):
        k = m.group(2).strip()
        if not k:
            continue
        if k in keys:
            dups.append(k)
        keys.add(k)
        end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(txt)
        body = txt[m.end() : end_pos]
        for cm in _BIB_CROSSREF_RE.finditer(body):
            parent_raw = (cm.group(1) or cm.group(2) or "").strip()
            for pk in parent_raw.split(","):
                pks = pk.strip()
                if pks:
                    crossrefs.setdefault(k, set()).add(pks)


def parse_bib_keys(
    root: Path,
    *,
    declared_bibs: Optional[list[str]] = None,
    bytes_already_used: int = 0,
    max_bib_files: int = MAX_BIB_FILES,
    max_walk_entries: int = MAX_WALK_ENTRIES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> tuple[set[str], list[str], dict[str, set[str]], list[dict[str, Any]]]:
    """Bounded .bib scanner: scans ONLY declared .bib resources when present, falling back to root walk otherwise."""
    keys: set[str] = set()
    dups: list[str] = []
    crossrefs: dict[str, set[str]] = {}
    findings: list[dict[str, Any]] = []
    bib_files: list[Path] = []
    entries_seen = 0
    bytes_used = bytes_already_used

    if declared_bibs:
        seen_paths: set[Path] = set()
        for raw_decl in declared_bibs:
            rel_b = raw_decl if raw_decl.lower().endswith(".bib") else f"{raw_decl}.bib"
            try:
                checked = safe_path(root / rel_b, root=root)
            except ValueError as exc:
                findings.append({
                    "code": "UNSAFE_BIB_PATH",
                    "severity": "error",
                    "file": rel_b,
                    "line": 1,
                    "detail": str(exc),
                })
                continue
            if not checked.is_file():
                findings.append({
                    "code": "MISSING_BIBLIOGRAPHY",
                    "severity": "error",
                    "file": rel_b,
                    "line": 1,
                    "detail": f"Declared bibliography file not found: {rel_b}",
                })
                continue
            if checked not in seen_paths:
                seen_paths.add(checked)
                bib_files.append(checked)
                if len(bib_files) > max_bib_files:
                    findings.append({
                        "code": "INCOMPLETE_COVERAGE",
                        "severity": "error",
                        "file": checked.relative_to(root).as_posix(),
                        "line": 1,
                        "detail": f"Exceeded max_bib_files={max_bib_files}",
                    })
                    return keys, sorted(set(dups)), crossrefs, findings
    else:
        for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
            dp = Path(dirpath)
            kept_dirs: list[str] = []
            for dn in sorted(dirnames):
                entries_seen += 1
                if entries_seen > max_walk_entries:
                    findings.append({
                        "code": "INCOMPLETE_COVERAGE",
                        "severity": "error",
                        "file": ".",
                        "line": 1,
                        "detail": f"Directory walk exceeded {max_walk_entries} entries while scanning .bib files",
                    })
                    return keys, sorted(set(dups)), crossrefs, findings
                sub = dp / dn
                if is_link_or_reparse(sub):
                    findings.append({
                        "code": "UNSAFE_BIB_SYMLINK",
                        "severity": "error",
                        "file": sub.relative_to(root).as_posix(),
                        "line": 1,
                        "detail": f"Symlink or reparse directory rejected: {dn}",
                    })
                    continue
                kept_dirs.append(dn)
            dirnames[:] = kept_dirs

            for fn in sorted(filenames):
                entries_seen += 1
                if entries_seen > max_walk_entries:
                    findings.append({
                        "code": "INCOMPLETE_COVERAGE",
                        "severity": "error",
                        "file": ".",
                        "line": 1,
                        "detail": f"Directory walk exceeded {max_walk_entries} entries while scanning .bib files",
                    })
                    return keys, sorted(set(dups)), crossrefs, findings
                if not fn.lower().endswith(".bib"):
                    continue
                bp = dp / fn
                checked = safe_path(bp, root=root)
                bib_files.append(checked)
                if len(bib_files) > max_bib_files:
                    findings.append({
                        "code": "INCOMPLETE_COVERAGE",
                        "severity": "error",
                        "file": checked.relative_to(root).as_posix(),
                        "line": 1,
                        "detail": f"Exceeded max_bib_files={max_bib_files}",
                    })
                    return keys, sorted(set(dups)), crossrefs, findings

    for checked in sorted(bib_files):
        fsize = checked.stat().st_size
        if bytes_used + fsize > max_total_bytes:
            findings.append({
                "code": "INCOMPLETE_COVERAGE",
                "severity": "error",
                "file": checked.relative_to(root).as_posix(),
                "line": 1,
                "detail": f"Bibliography file {checked.name} ({fsize} bytes) exceeds aggregate {max_total_bytes} byte budget",
            })
            return keys, sorted(set(dups)), crossrefs, findings
        bytes_used += fsize
        txt = checked.read_text(encoding="utf-8", errors="replace")
        _parse_single_bib_text(txt, keys, dups, crossrefs)
    return keys, sorted(set(dups)), crossrefs, findings


def _check_pdf_page_limit(pdf_path: str | Path, max_pages: int) -> list[dict[str, Any]]:
    from .research.sources import controlled_read_pdf_pages

    checked_pdf = safe_path(pdf_path)
    if not checked_pdf.is_file():
        return [{"code": "MISSING_PDF", "severity": "error", "file": str(pdf_path), "line": 1, "detail": "Compiled PDF not found"}]
    try:
        res = controlled_read_pdf_pages(checked_pdf, max_pages=500, timeout_sec=20.0)
    except Exception as exc:
        msg = str(exc)
        if "Neither pymupdf nor pypdf" in msg:
            return [{
                "code": "PDF_CHECK_UNAVAILABLE",
                "severity": "error",
                "file": checked_pdf.name,
                "line": 1,
                "detail": 'Install PDF support with: pip install "academic-research-kernel[research]" to verify page limits',
            }]
        return [{
            "code": "PDF_CHECK_FAILED",
            "severity": "error",
            "file": checked_pdf.name,
            "line": 1,
            "detail": msg,
        }]
    pages = list(res.get("pages") or [])
    total_pages = int(res.get("page_count") or len(pages))
    body_pages = total_pages
    ref_pat = re.compile(r"(?:^|\n)\s*(?:\d+\.?\s+)?(?:references|bibliography)\s*(?:\n|$)", re.IGNORECASE)
    running_hdr_pat = re.compile(
        r"^(?:page\s*\d+(?:\s*(?:/|of)\s*\d+)?"
        r"|under\s+review\s+as\s+a\s+conference\s+paper\b.*"
        r"|published\s+as\s+a\s+conference\s+paper\b.*"
        r"|anonymous\s+authors?"
        r"|preprint\.?\s*under\s+review.*)$",
        re.IGNORECASE,
    )
    for idx, txt in enumerate(pages):
        m_ref = ref_pat.search(txt or "")
        if m_ref:
            prefix = (txt or "")[: m_ref.start()].strip()
            non_trivial_lines = [
                ln.strip()
                for ln in prefix.splitlines()
                if ln.strip()
                and not re.fullmatch(r"[\d\s\-–—.|/]+", ln.strip())
                and not running_hdr_pat.fullmatch(ln.strip())
            ]
            if non_trivial_lines:
                body_pages = idx + 1
            else:
                body_pages = idx
            break
    if body_pages > max_pages:
        return [{
            "code": "PDF_PAGE_LIMIT_EXCEEDED",
            "severity": "error",
            "file": checked_pdf.name,
            "line": 1,
            "detail": f"Main body spans {body_pages} pages (total={total_pages}), exceeding venue limit of {max_pages} pages",
        }]
    return []


_UNIT_ALIASES: Mapping[str, str] = {
    "%": "%",
    "percent": "%",
    "percentage": "%",
    "pp": "pp",
    "ms": "ms",
    "millisecond": "ms",
    "milliseconds": "ms",
    "us": "us",
    "μs": "us",
    "microsecond": "us",
    "microseconds": "us",
    "ns": "ns",
    "nanosecond": "ns",
    "nanoseconds": "ns",
    "s": "s",
    "sec": "s",
    "secs": "s",
    "second": "s",
    "seconds": "s",
    "min": "min",
    "mins": "min",
    "minute": "min",
    "minutes": "min",
    "h": "h",
    "hr": "h",
    "hrs": "h",
    "hour": "h",
    "hours": "h",
    "hz": "hz",
    "khz": "khz",
    "mhz": "mhz",
    "ghz": "ghz",
    "b": "b",
    "kb": "kb",
    "mb": "mb",
    "gb": "gb",
    "tb": "tb",
    "kib": "kib",
    "mib": "mib",
    "gib": "gib",
    "x": "x",
    "×": "x",
    "times": "x",
    "db": "db",
    "unit": "units",
    "units": "units",
}
_UP_POLARITY_WORDS = frozenset({
    "increase", "increases", "increased", "increasing",
    "improve", "improves", "improved", "improving", "improvement",
    "gain", "gains", "higher", "faster", "larger", "greater",
    "boost", "boosts", "boosted", "outperform", "outperforms", "outperformed",
    "rise", "rises", "rose", "positive", "accelerate", "accelerates",
})
_DOWN_POLARITY_WORDS = frozenset({
    "decrease", "decreases", "decreased", "decreasing",
    "reduce", "reduces", "reduced", "reducing", "reduction",
    "drop", "drops", "dropped", "lower", "slower", "smaller", "fewer",
    "worse", "worsen", "worsens", "worsened", "decline", "declines", "declined",
    "negative", "degrade", "degrades", "degraded",
})
_NEGATION_WORDS = frozenset({"not", "no", "never", "neither", "without", "fail", "fails", "failed"})
_SIGNED_QTY_RE = re.compile(
    r"(?<![A-Za-z0-9.])([+\-−]?)\s*(\d+(?:\.\d+)?)\s*(%|×|[A-Za-zμ]+)?",
)


_NON_SEMANTIC_TEX_TAG_RE = re.compile(
    r"\\(?:cite[a-zA-Z*]*|[cC]?ref|autoref|eqref|pageref|label|index)\*?\s*(?:\[[^\]]*\]\s*)*\{[^{}]*\}"
)
_CLAUSE_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "that", "this", "and",
})
_FORMATTING_MACRO_RE = re.compile(
    r"\\(?:textbf|textit|emph|texttt|textrm|textsf|textsc|textup|textnormal|text|mbox|hbox|"
    r"mathrm|mathbf|mathit|mathsf|mathtt|underline|uline|small|large|normalsize)\*?"
    r"\s*(?:\[[^\]]*\]\s*)*\{([^{}]*)\}"
)


def _strip_tex_markup_preserving_semantics(text: str) -> str:
    s = text.replace(r"\%", "%").replace(r"\times", "×").replace(r"\pm", "±")
    # Preserve TeX & Unicode relational/approximation operators before macro and '~' spacing stripping
    for tex_rel, canon_rel in (
        (r"\leq", " <= "),
        (r"\le", " <= "),
        (r"\geq", " >= "),
        (r"\ge", " >= "),
        (r"\neq", " != "),
        (r"\ne", " != "),
        (r"\lt", " < "),
        (r"\gt", " > "),
        (r"\approx", " op_approx "),
        (r"\simeq", " op_approx "),
        (r"\sim", " op_approx "),
    ):
        s = re.sub(rf"{re.escape(tex_rel)}(?![A-Za-z])", canon_rel, s)
    s = s.replace("≤", " <= ").replace("≥", " >= ").replace("≠", " != ").replace("≈", " op_approx ")
    # Strip citation, cross-reference, and label tags completely (do NOT splice bibkeys into prose)
    while True:
        nxt = _NON_SEMANTIC_TEX_TAG_RE.sub(" ", s)
        if nxt == s:
            break
        s = nxt
    s = re.sub(r"\(\s*\)|\[\s*\]", " ", s)
    # Expand TeX spacing escapes (\, \; \: \! \~ \quad \qquad) before unwrapping formatting macros
    s = re.sub(r"\\(?:[,;:! ]|quad\b|qquad\b)", " ", s)
    s = s.replace("~", " ")
    s = re.sub(r"\$\s*([+\-−])\s*\$", r"\1", s)
    s = s.replace("$", " ")
    # Unwrap ONLY explicit typography/font macros; preserve semantic math operators (\sqrt{40}, \frac{1}{2}, \log{x})
    while True:
        nxt = _FORMATTING_MACRO_RE.sub(r"\1", s)
        if nxt == s:
            break
        s = nxt
    # Render remaining TeX control words as explicit operator tokens (\sqrt{40} -> op_sqrt(40)) so they never collapse to bare 40
    s = re.sub(r"\\([A-Za-z]+)\*?\s*\{([^{}]*)\}", r" op_\1(\2) ", s)
    s = re.sub(r"\\([A-Za-z]+)\*?", r" op_\1 ", s)
    s = s.replace("{", "").replace("}", "").replace("\\", "")
    s = s.replace("−", "-")
    return " ".join(s.split())


def _normalize_statement_for_ceg(text: str) -> str:
    return _strip_tex_markup_preserving_semantics(text)


def _extract_signed_quantities(text: str) -> list[tuple[bool, str, str]]:
    norm = _normalize_statement_for_ceg(text)
    out: list[tuple[bool, str, str]] = []
    for m in _SIGNED_QTY_RE.finditer(norm):
        raw_sign, num_s, raw_unit = m.group(1) or "", m.group(2), (m.group(3) or "").strip()
        is_neg = raw_sign in ("-", "−")
        unit_low = " ".join(raw_unit.lower().split())
        canon_unit = _UNIT_ALIASES.get(unit_low, unit_low)
        out.append((is_neg, num_s, canon_unit))
    return out


def _canonicalize_statement_for_binding(text: str) -> str:
    s = _strip_tex_markup_preserving_semantics(text).lower().strip()
    # Canonicalize standard unit aliases attached to numbers (both '40ms' and '40 milliseconds' -> '40 millisecond')
    for u_raw, u_canon in sorted(_UNIT_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if u_raw and u_canon:
            s = re.sub(rf"(\d)\s*{re.escape(u_raw)}(?![a-z])", rf"\1 {u_canon}", s)
    s = re.sub(r"[.\s]+$", "", s)
    return " ".join(s.split())


def _statement_diverges_from_claim(claim_txt: str, manuscript_line: str, *, strict: bool = False) -> bool:
    c_canon = _canonicalize_statement_for_binding(claim_txt)
    m_canon = _canonicalize_statement_for_binding(manuscript_line)
    if strict:
        return c_canon != m_canon

    c_norm = _normalize_statement_for_ceg(claim_txt)
    m_norm = _normalize_statement_for_ceg(manuscript_line)

    c_qtys = _extract_signed_quantities(c_norm)
    m_qtys = _extract_signed_quantities(m_norm)
    if m_qtys != c_qtys:
        return True

    # Clause-by-clause polarity & ordered entity/role alignment so swapped subjects/objects (Drug A vs Drug B) diverge
    c_clauses = [cl.strip() for cl in re.split(r"[;；]|\bwhile\b|\bwhereas\b", c_canon) if cl.strip()]
    m_clauses = [cl.strip() for cl in re.split(r"[;；]|\bwhile\b|\bwhereas\b", m_canon) if cl.strip()]
    if len(c_clauses) != len(m_clauses):
        return True
    def _canon_pol_token(tok: str) -> str:
        if tok in _UP_POLARITY_WORDS:
            return "+UP+"
        if tok in _DOWN_POLARITY_WORDS:
            return "+DOWN+"
        if tok in _NEGATION_WORDS:
            return "+NEG+"
        return tok

    for cc, mc in zip(c_clauses, m_clauses):
        c_words = re.findall(r"(?:op_[a-z0-9_]+\([^()]*\)|<=|>=|!=|[<>~=]|[a-z0-9%×_]+)", cc)
        m_words = re.findall(r"(?:op_[a-z0-9_]+\([^()]*\)|<=|>=|!=|[<>~=]|[a-z0-9%×_]+)", mc)
        ct = set(c_words)
        mt = set(m_words)
        if (bool(ct & _UP_POLARITY_WORDS) != bool(mt & _UP_POLARITY_WORDS)) or (
            bool(ct & _DOWN_POLARITY_WORDS) != bool(mt & _DOWN_POLARITY_WORDS)
        ):
            return True
        if bool(ct & _NEGATION_WORDS) != bool(mt & _NEGATION_WORDS):
            return True
        c_seq = [_canon_pol_token(w) for w in c_words if w not in _CLAUSE_STOPWORDS]
        m_seq = [_canon_pol_token(w) for w in m_words if w not in _CLAUSE_STOPWORDS]
        if c_seq != m_seq:
            return True
    return False


def lint_manuscript(
    entry_tex: str | Path | None = None,
    venue: Optional[str] = "iclr",
    specs_path: str | Path | None = None,
    double_blind: Optional[bool] = None,
    *,
    tex_path: str | Path | None = None,
    phase: str = "submission",
    contribution_type: str = "general_empirical",
    pdf_path: str | Path | None = None,
    ceg_path: str | Path | None = None,
    require_ceg_binding: bool = False,
    check_academic_style: bool = False,
    workspace_root: str | Path | None = None,
) -> Mapping[str, Any]:
    target_tex = tex_path if tex_path is not None else entry_tex
    if target_tex is None:
        raise ValueError("lint_manuscript requires entry_tex / tex_path")
    if workspace_root is not None:
        ws_p = safe_path(workspace_root, must_exist=True)
        target_tex = safe_path(target_tex, root=ws_p, must_exist=True)
        if pdf_path is not None:
            pdf_path = safe_path(pdf_path, root=ws_p, must_exist=True)
        if ceg_path is not None:
            ceg_path = safe_path(ceg_path, root=ws_p, must_exist=True)

    specs_doc = load_venue_specs(specs_path)
    venues = specs_doc.get("venues", {})
    vspec: Optional[dict[str, Any]] = None
    vkey: Optional[str] = None
    if venue is not None and str(venue).strip():
        vkey = str(venue).strip().lower()
        if vkey not in venues:
            raise ValueError(f"Unknown venue {venue!r}; supported={sorted(venues)}")
        vspec = venues[vkey]

    ctypes = specs_doc.get("contribution_types", {})
    if contribution_type and ctypes and contribution_type not in ctypes:
        raise ValueError(f"Unknown contribution_type {contribution_type!r}; supported={sorted(ctypes)}")

    if phase not in ("submission", "rebuttal", "camera_ready"):
        raise ValueError(f"Invalid submission phase {phase!r}")

    effective_blind = (
        bool(double_blind)
        if double_blind is not None
        else (phase != "camera_ready" and (vspec is None or vspec.get("review_mode") == "double_blind"))
    )

    root, files, findings, bytes_used = collect_tex_tree(target_tex)
    if not files:
        raise ValueError(f"No readable TeX source at {target_tex}")

    merged_raw = "\n".join(raw for _, raw, _ in files)
    merged = "\n".join(cleaned for _, _, cleaned in files)

    doc_classes: list[str] = []
    pkg_names: set[str] = set()
    sections_lower: list[str] = []
    labels: set[str] = set()
    cited: set[str] = set()
    bibitem_keys: set[str] = {m.group(1).strip() for m in _BIBITEM_RE.finditer(merged) if m.group(1).strip()}
    declared_bibs: list[str] = []
    for m_bd in _BIB_DECL_RE.finditer(merged):
        for bpart in m_bd.group(2).split(","):
            bs = bpart.strip()
            if bs:
                declared_bibs.append(bs)
    has_bib_decl = bool(declared_bibs) or bool(bibitem_keys) or (r"\begin{thebibliography}" in merged)
    has_nocite_star = bool(_NOCITE_STAR_RE.search(merged))

    for fpath, raw_txt, cleaned in files:
        rel_name = fpath.relative_to(root).as_posix()
        for m in _DOC_CLASS_RE.finditer(cleaned):
            opts = [o.strip().lower() for o in (m.group(1) or "").split(",") if o.strip()]
            cls_name = m.group(2).strip()
            doc_classes.append(cls_name)
            if effective_blind and any(tok in opts or any(tok in o for o in opts) for tok in ("final", "preprint", "cameraready")):
                findings.append({
                    "code": "FINAL_MODE_IN_REVIEW",
                    "severity": "error",
                    "file": rel_name,
                    "line": _line_of(cleaned, m.start()),
                    "detail": f"Documentclass option {m.group(1)!r} disables double-blind review mode",
                })
        for m in _USEPKG_RE.finditer(cleaned):
            raw_opt = m.group(1) or ""
            opts = [o.strip().lower() for o in raw_opt.split(",") if o.strip()]
            for pkg in m.group(2).split(","):
                p = pkg.strip()
                if p:
                    pkg_names.add(p)
                    p_low = p.lower()
                    has_preprint = any(tok in o for o in opts for tok in ("preprint", "cameraready"))
                    has_final = any(o == "final" or o.startswith("final=") and not o.endswith("false") for o in opts)
                    if effective_blind and (has_preprint or (has_final and p_low not in _BENIGN_FINAL_PACKAGES)):
                        findings.append({
                            "code": "FINAL_MODE_IN_REVIEW",
                            "severity": "error",
                            "file": rel_name,
                            "line": _line_of(cleaned, m.start()),
                            "detail": f"Package {p!r} loaded with camera-ready/preprint option [{raw_opt}] in double-blind mode",
                        })
        if effective_blind:
            m_fc = _FINAL_COPY_RE.search(cleaned)
            if m_fc:
                findings.append({
                    "code": "FINAL_MODE_IN_REVIEW",
                    "severity": "error",
                    "file": rel_name,
                    "line": _line_of(cleaned, m_fc.start()),
                    "detail": f"Final-copy macro {m_fc.group(0)} active under double-blind review",
                })
            from .double_blind_sanitizer import (
                SELF_OWNED_URL_CUE_RE,
                _extract_balanced_braces,
                _is_strictly_anonymous_tex_body,
            )

            for ln_no, auth_body in _extract_balanced_braces(raw_txt):
                compact_auth = " ".join(auth_body.split())
                if compact_auth and not _is_strictly_anonymous_tex_body(auth_body):
                    findings.append({
                        "code": "BLIND_AUTHOR_LEAK",
                        "severity": "error",
                        "file": rel_name,
                        "line": ln_no,
                        "detail": "Explicit non-anonymous author/affiliation macro block under double-blind review",
                    })
            for ln_no, _ in _extract_braced_blocks(cleaned, "thanks"):
                findings.append({
                    "code": "BLIND_THANKS_LEAK",
                    "severity": "error",
                    "file": rel_name,
                    "line": ln_no,
                    "detail": "\\thanks{...} present under double-blind review",
                })
            m_ack = _ACK_ENV_RE.search(cleaned)
            if m_ack:
                findings.append({
                    "code": "BLIND_ACK_LEAK",
                    "severity": "error",
                    "file": rel_name,
                    "line": _line_of(cleaned, m_ack.start()),
                    "detail": "Acknowledgments section/environment must be omitted in double-blind submission",
                })
            m_fund = _FUNDING_RE.search(cleaned)
            if m_fund:
                findings.append({
                    "code": "BLIND_FUNDING_LEAK",
                    "severity": "error",
                    "file": rel_name,
                    "line": _line_of(cleaned, m_fund.start()),
                    "detail": "Explicit grant/funding disclosure detected under double-blind submission",
                })
            from .double_blind_sanitizer import scan_repository_urls

            for url_hit in scan_repository_urls(cleaned, is_tex=True, already_masked_tex=True):
                is_self_url = bool(url_hit["is_self"])
                findings.append({
                    "code": "BLIND_URL_LEAK",
                    "severity": url_hit["severity"],
                    "file": rel_name,
                    "line": url_hit["line"],
                    "detail": (
                        "Author-associated repository URL detected under double-blind submission"
                        if is_self_url
                        else "Public repository URL detected under double-blind submission; verify it does not identify the authors"
                    ),
                })

        m_lay = _FORBIDDEN_LAYOUT_RE.search(cleaned)
        if m_lay:
            findings.append({
                "code": "LAYOUT_TAMPER",
                "severity": "error",
                "file": rel_name,
                "line": _line_of(cleaned, m_lay.start()),
                "detail": "Negative vspace or manual margin/baselinestretch override detected",
            })

        m_todo = _TODO_RE.search(cleaned)
        if m_todo:
            findings.append({
                "code": "UNRESOLVED_TODO",
                "severity": "warning",
                "file": rel_name,
                "line": _line_of(cleaned, m_todo.start()),
                "detail": f"Leftover draft marker {m_todo.group(0)!r}",
            })

        if "??" in cleaned:
            pos_q = cleaned.find("??")
            findings.append({
                "code": "UNRESOLVED_REFERENCE",
                "severity": "error",
                "file": rel_name,
                "line": _line_of(cleaned, pos_q),
                "detail": "Literal '??' placeholder detected in manuscript",
            })

        for m in _SECTION_RE.finditer(cleaned):
            sections_lower.append(m.group(1).strip().lower())
        for m in _LABEL_RE.finditer(cleaned):
            labels.add(m.group(1).strip())
        for m in _CITE_RE.finditer(cleaned):
            for k in m.group(1).split(","):
                ks = k.strip()
                if ks and ks != "*":
                    cited.add(ks)

        for m in _TABULAR_RE.finditer(cleaned):
            tbl_body = m.group(0)
            if re.search(r"\d+\.\d+", tbl_body) and not _DISPERSION_RE.search(tbl_body):
                findings.append({
                    "code": "TABLE_MISSING_DISPERSION",
                    "severity": "warning",
                    "file": rel_name,
                    "line": _line_of(cleaned, m.start()),
                    "detail": "Numeric results table lacks visible uncertainty/dispersion indicator (\\pm, SD, SE, or CI)",
                })

    # Second pass for \ref / \cref{a,b} against all collected \label{...}
    for fpath, _, cleaned in files:
        rel_name = fpath.relative_to(root).as_posix()
        for m in _REF_RE.finditer(cleaned):
            raw_ref = m.group(1).strip()
            cmd_head = m.group(0).split("{", 1)[0].strip()
            ref_parts = [rp.strip() for rp in raw_ref.split(",")] if cmd_head.lower().endswith("cref") else [raw_ref]
            for ref_key in ref_parts:
                if ref_key == "??" or (ref_key and ref_key not in labels):
                    findings.append({
                        "code": "UNRESOLVED_REFERENCE",
                        "severity": "error",
                        "file": rel_name,
                        "line": _line_of(cleaned, m.start()),
                        "detail": f"Reference {cmd_head}{{{ref_key}}} has no matching \\label in bundle",
                    })

    has_abstract = r"\begin{abstract}" in merged or any("abstract" in s for s in sections_lower)
    if not has_abstract:
        findings.append({"code": "MISSING_ABSTRACT", "severity": "error", "file": files[0][0].name, "line": 1, "detail": "No abstract environment or section found"})

    if "geometry" in pkg_names and vkey:
        findings.append({"code": "FORBIDDEN_PACKAGE", "severity": "error", "file": files[0][0].name, "line": 1, "detail": "Explicit geometry package violates venue style contract"})

    bib_keys, dup_bib, bib_crossrefs, bib_findings = parse_bib_keys(
        root,
        declared_bibs=declared_bibs if declared_bibs else None,
        bytes_already_used=bytes_used,
    )
    all_defined_bib = bib_keys | bibitem_keys
    findings.extend(bib_findings)
    if dup_bib:
        findings.append({"code": "DUPLICATE_BIB_KEY", "severity": "error", "file": "references.bib", "line": 1, "detail": f"Duplicate BibTeX keys: {dup_bib}"})
    if cited and not all_defined_bib:
        findings.append({
            "code": "MISSING_BIBLIOGRAPHY",
            "severity": "error",
            "file": files[0][0].name,
            "line": 1,
            "detail": f"Manuscript cites {sorted(cited)[:5]} but no .bib entries or \\bibitem definitions were found",
        })
    elif all_defined_bib:
        missing_cite = sorted(cited - all_defined_bib)
        # Transitive closure over crossref / xdata parents so parent proceedings are not flagged uncited
        cited_closure = set(cited)
        stack_c = list(cited)
        while stack_c:
            ck = stack_c.pop()
            for pk in bib_crossrefs.get(ck, ()):
                if pk not in cited_closure:
                    cited_closure.add(pk)
                    stack_c.append(pk)
        uncited = [] if has_nocite_star else sorted(all_defined_bib - cited_closure)
        if missing_cite:
            findings.append({"code": "UNDEFINED_CITATION", "severity": "error", "file": files[0][0].name, "line": 1, "detail": f"Cited keys missing from .bib: {missing_cite}"})
        if uncited:
            findings.append({
                "code": "UNCITED_BIBLIOGRAPHY_ENTRY" if check_academic_style else "UNCITED_BIB_ENTRY",
                "severity": "warning",
                "file": "references.bib",
                "line": 1,
                "detail": f"Uncited bibliography entries: {uncited}",
            })
        if cited and not has_bib_decl:
            findings.append({"code": "MISSING_BIBLIOGRAPHY_DIRECTIVE", "severity": "warning", "file": files[0][0].name, "line": 1, "detail": "Citations present without \\bibliography or \\addbibresource"})

    if check_academic_style:
        for fpath, _, cleaned in files:
            rel_name = fpath.relative_to(root).as_posix()
            for m_oc in _OVERCLAIM_STYLE_RE.finditer(cleaned):
                findings.append({
                    "code": "OVERCLAIM_PHRASING",
                    "severity": "warning",
                    "file": rel_name,
                    "line": _line_of(cleaned, m_oc.start()),
                    "detail": f"Unqualified absolutist phrasing {m_oc.group(0)!r}; scope claim to verified evidence",
                })

    if vspec is not None:
        for req_sec in vspec.get("required_sections", ()):
            if not any(req_sec.lower() in s for s in sections_lower):
                findings.append({
                    "code": "MISSING_REQUIRED_SECTION",
                    "severity": "error",
                    "file": files[0][0].name,
                    "line": 1,
                    "detail": f"Missing venue-required section: {req_sec}",
                })
        if pdf_path is not None:
            phase_limits = vspec.get("phase_max_pages") or {}
            page_cap = phase_limits.get(phase, vspec.get("main_body_max_pages"))
            if isinstance(page_cap, int) and page_cap > 0:
                findings.extend(_check_pdf_page_limit(pdf_path, page_cap))

    if ceg_path is not None or require_ceg_binding:
        # Collect per-line claim bindings alongside non-comment manuscript prose
        tagged_lines: list[tuple[str, int, str, list[str]]] = []
        untagged_quant_lines: list[tuple[str, int, str]] = []
        for fpath, raw_txt, cleaned in files:
            rel_name = fpath.relative_to(root).as_posix()
            raw_lines = raw_txt.splitlines()
            clean_lines = cleaned.splitlines()
            for idx_ln, rline in enumerate(raw_lines):
                cline = clean_lines[idx_ln] if idx_ln < len(clean_lines) else ""
                tags_here = [m.group(1).strip() for m in _ARK_CLAIM_RE.finditer(rline) if m.group(1).strip()]
                if tags_here:
                    tagged_lines.append((rel_name, idx_ln + 1, cline, tags_here))
                elif _QUANT_SENTENCE_RE.search(cline):
                    untagged_quant_lines.append((rel_name, idx_ln + 1, cline))

        if ceg_path is None:
            if tagged_lines:
                f0, ln0, _, t0 = tagged_lines[0]
                findings.append({
                    "code": "UNVERIFIED_CEG_ANCHOR",
                    "severity": "error" if require_ceg_binding else "warning",
                    "file": f0,
                    "line": ln0,
                    "detail": f"Manuscript contains '% ark:claim={t0[0]}' without a --ceg graph file to verify against",
                })
            if require_ceg_binding and (untagged_quant_lines or tagged_lines):
                f_q, ln_q, _ = untagged_quant_lines[0] if untagged_quant_lines else (tagged_lines[0][0], tagged_lines[0][1], "")
                findings.append({
                    "code": "UNGROUNDED_QUANT_CLAIM",
                    "severity": "error",
                    "file": f_q,
                    "line": ln_q,
                    "detail": "Quantitative claims present while no verified --ceg file was supplied",
                })
        else:
            from . import venue_template_manager

            ceg_rep = venue_template_manager.export_ceg_anchors(ceg_path)
            anchor_by_id = {a["claim_id"]: a for a in ceg_rep.get("anchors", ())}
            if ceg_rep.get("dangling_edges"):
                findings.append({
                    "code": "CEG_DANGLING_EDGES",
                    "severity": "error",
                    "file": str(ceg_path),
                    "line": 1,
                    "detail": f"CEG contains {len(ceg_rep['dangling_edges'])} dangling evidence edges",
                })
            if ceg_rep.get("semantic_errors"):
                findings.append({
                    "code": "CEG_SEMANTIC_ERROR",
                    "severity": "error",
                    "file": str(ceg_path),
                    "line": 1,
                    "detail": "; ".join(str(e) for e in ceg_rep["semantic_errors"][:5]),
                })
            for rel_name, ln_no, cline, tags_here in tagged_lines:
                for bc in tags_here:
                    anc = anchor_by_id.get(bc)
                    st = anc["anchor_status"] if anc is not None else None
                    if st != "eligible":
                        findings.append({
                            "code": "INVALID_CEG_BINDING",
                            "severity": "error",
                            "file": rel_name,
                            "line": ln_no,
                            "detail": f"Bound claim {bc!r} has status {st!r} (must be 'eligible')",
                        })
                        continue
                    claim_txt = str(anc.get("normalized_text") or "")
                    if _statement_diverges_from_claim(claim_txt, cline, strict=bool(require_ceg_binding)):
                        findings.append({
                            "code": "CEG_CLAIM_TEXT_MISMATCH",
                            "severity": "error" if require_ceg_binding else "warning",
                            "file": rel_name,
                            "line": ln_no,
                            "detail": f"Manuscript statement on line {ln_no} diverges from CEG claim {bc!r} ({claim_txt!r})",
                        })
            if require_ceg_binding and untagged_quant_lines:
                f_q, ln_q, _ = untagged_quant_lines[0]
                findings.append({
                    "code": "UNGROUNDED_QUANT_CLAIM",
                    "severity": "error",
                    "file": f_q,
                    "line": ln_q,
                    "detail": "Quantitative claim lacks a '% ark:claim=<id>' CEG anchor on that line",
                })

    errors = [f for f in findings if f["severity"] == "error"]
    return freeze({
        "passed": len(errors) == 0,
        "venue": vkey,
        "phase": phase,
        "double_blind": effective_blind,
        "files_scanned": len(files),
        "documentclass": doc_classes[0] if doc_classes else None,
        "cited_count": len(cited),
        "bib_count": len(bib_keys),
        "error_count": len(errors),
        "findings": findings,
        "hits": findings,
    })

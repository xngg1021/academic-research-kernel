r"""双盲审稿匿名化自检门禁：扫描论文手稿与复现包中的身份泄露线索。

检测范围：
1. 用户通过 --forbidden-token 显式指定的敏感词（同时检查文件内容与文件/目录相对路径）
2. 指向具体账户的 GitHub 仓库或工单链接 (github.com/<owner>/<repo>, raw.githubusercontent.com, gist.github.com)
3. 真实 ORCID 标识符 (0000-xxxx-... / 0009-xxxx-...)
4. 邮箱地址与本机用户路径（含 Windows、macOS、Linux 与 WSL 挂载用户目录）
5. LaTeX 中跨行或带嵌套宏的非匿名 \author{...}、\icmlauthor{...}、\affiliation{...}、\institute{...}、pdfauthor=... 声明及 PDF 元数据
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

TEXT_SUFFIXES = {
    ".tex", ".md", ".bib", ".bbl", ".sty", ".cls", ".txt", ".py",
    ".json", ".yaml", ".yml", ".sh", ".toml", ".ipynb", ".cff", ".cfg", ".ini", ".r", ".jl",
}
EXCLUDED_DIRS = {
    ".git", ".venv", "venv", "env", "node_modules", "site-packages",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}
GITHUB_URL_RE = re.compile(
    r"(?:https?://|git@)?(?:www\.|raw\.|gist\.)?github(?:usercontent)?\.com[:/][A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
    re.I,
)
ORCID_RE = re.compile(r"\b000[0-9]-[0-9]{4}-[0-9]{4}-[0-9]{3}[0-9X]\b")
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
WIN_PATH_RE = re.compile(r"(?i)(?:\b[A-Z]:|/mnt/[a-z])[/\\]+Users[/\\]+(?!<|Public\b|Default\b)[\w.-]+")
UNIX_PATH_RE = re.compile(r"""/(?:Users|home)/(?!<|runner(?=[/"'\s,;)]|$)|ubuntu(?=[/"'\s,;)]|$))[\w.-]+(?=[/"'\s,;)]|$)""")
LATEX_MACRO_START_RE = re.compile(
    r"\\(?:author|icmlauthor|authorrunning|affiliation|affil|institute|icmlaffiliation)\b|\bpdfauthor\s*="
)
UNBRACED_PDFAUTHOR_RE = re.compile(r"\bpdfauthor\s*=\s*(?!\{)([^,\}\r\n]+)")
SAFE_FORMATTING_MACROS = {
    "textbf", "textit", "emph", "large", "Large", "LARGE", "small", "footnotesize",
    "bf", "it", "rm", "sf", "tt", "centering", "and", "quad", "qquad", "vspace",
    "hspace", "thanks", "footnotemark", "inst", "IEEEauthorblockN", "IEEEauthorblockA",
}
ANONYMOUS_PLACEHOLDERS = {
    "", "anonymous", "anonymous author", "anonymous authors",
    "anonymous submission", "paper under double-blind review",
    "under double-blind review", "double-blind review", "withheld for double-blind review",
}


def _strip_tex_comments(text: str) -> str:
    """Delegate to the shared verbatim/verb-aware TeX lexical masker in pre_submission_linter."""
    from .pre_submission_linter import strip_tex_comments

    return strip_tex_comments(text)


def _extract_balanced_braces(text: str) -> list[tuple[int, str]]:
    """Return list of (line_no, body_str) for LaTeX author/affiliation macros and pdfauthor declarations."""
    cleaned = _strip_tex_comments(text)
    results = []
    for m in LATEX_MACRO_START_RE.finditer(cleaned):
        pos = m.end()
        n = len(cleaned)
        while pos < n and cleaned[pos].isspace():
            pos += 1
        if pos < n and cleaned[pos] == "[":
            depth_opt = 1
            pos += 1
            while pos < n and depth_opt > 0:
                if cleaned[pos] == "[":
                    depth_opt += 1
                elif cleaned[pos] == "]":
                    depth_opt -= 1
                pos += 1
            while pos < n and cleaned[pos].isspace():
                pos += 1
        if pos >= n or cleaned[pos] != "{":
            continue
        line_no = cleaned.count("\n", 0, m.start()) + 1
        depth = 1
        pos += 1
        start_body = pos
        while pos < n and depth > 0:
            ch = cleaned[pos]
            if ch == "\\":
                pos += 2
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            pos += 1
        if depth == 0:
            body = cleaned[start_body : pos - 1]
            results.append((line_no, body))
    for m_unbraced in UNBRACED_PDFAUTHOR_RE.finditer(cleaned):
        line_no = cleaned.count("\n", 0, m_unbraced.start()) + 1
        results.append((line_no, m_unbraced.group(1).strip()))
    return results


def _is_strictly_anonymous_tex_body(body: str) -> bool:
    # Check if unknown custom macros (e.g. \realname or \myauthor) are present
    for m_cmd in re.finditer(r"\\([A-Za-z]+)\*?(?:\s*\[[^\]]*\])?", body):
        cmd_name = m_cmd.group(1)
        if cmd_name not in SAFE_FORMATTING_MACROS:
            return False
    plain = re.sub(r"\\[A-Za-z]+\*?(?:\s*\[[^\]]*\])?", " ", body)
    plain = re.sub(r"[{}\\]", " ", plain)
    plain = " ".join(plain.split()).strip().lower().strip(".,;:-")
    return plain in ANONYMOUS_PLACEHOLDERS


def _match_forbidden_token(tok: str, text_line: str) -> bool:
    if len(tok) <= 4 and tok.isalnum() and tok.isascii():
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(tok)}(?![A-Za-z0-9])", text_line, re.I))
    return tok.lower() in text_line.lower()


def scan_text_for_leaks(text: str, rel_path: str, forbidden_tokens: list[str] | None = None) -> list[dict]:
    findings = []
    tokens = [t.strip() for t in (forbidden_tokens or []) if t and t.strip()]

    for tok in tokens:
        if _match_forbidden_token(tok, rel_path):
            findings.append({
                "file": rel_path,
                "line": 0,
                "kind": "forbidden_token_in_path",
                "matched": tok,
            })

    for line_no, line in enumerate(text.splitlines(), 1):
        for tok in tokens:
            if _match_forbidden_token(tok, line):
                findings.append({
                    "file": rel_path,
                    "line": line_no,
                    "kind": "forbidden_token",
                    "matched": tok,
                })
        for m in GITHUB_URL_RE.finditer(line):
            u_low = m.group(0).lower()
            if any(w in u_low for w in ("github.com/iclr/", "github.com/acl-org/", "github.com/neurips/")):
                continue
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "non_anonymous_github_url",
                "matched": m.group(0),
            })
        for m in ORCID_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "orcid_identifier",
                "matched": m.group(0),
            })
        for m in EMAIL_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "email_address",
                "matched": m.group(0),
            })
        for m in WIN_PATH_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "local_user_path",
                "matched": m.group(0),
            })
        for m in UNIX_PATH_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "local_user_path",
                "matched": m.group(0),
            })

    if rel_path.lower().endswith((".tex", ".sty", ".cls", ".bbl")):
        for line_no, body in _extract_balanced_braces(text):
            if not _is_strictly_anonymous_tex_body(body):
                compact = " ".join(body.split())
                findings.append({
                    "file": rel_path,
                    "line": line_no,
                    "kind": "non_anonymous_latex_author",
                    "matched": compact[:100],
                })
    return findings


def _extract_xmp_entries(xmp_xml: str) -> list[tuple[str, str]]:
    """Parse XMP XML packet and return (ancestor_path_key, text_value) pairs preserving container semantics."""
    cleaned = xmp_xml.strip()
    if not cleaned:
        raise ValueError("Empty XMP metadata stream")
    cleaned = re.sub(r"<\?xpacket[^>]*\?>", "", cleaned).strip()
    if not cleaned:
        raise ValueError("XMP metadata stream contains no XML root")
    root = ET.fromstring(cleaned)
    entries: list[tuple[str, str]] = []

    def _walk_elem(elem: ET.Element, prefix: str) -> None:
        local_tag = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
        cur_key = f"{prefix}/{local_tag}" if prefix else f"xmp:{local_tag}"
        if elem.text and elem.text.strip():
            entries.append((cur_key, elem.text.strip()))
        if elem.tail and elem.tail.strip():
            entries.append((f"{cur_key}#tail", elem.tail.strip()))
        for attr_k, attr_v in elem.attrib.items():
            local_attr = attr_k.split("}", 1)[-1] if "}" in attr_k else attr_k
            if attr_v and attr_v.strip():
                entries.append((f"{cur_key}@{local_attr}", attr_v.strip()))
        for child in list(elem):
            _walk_elem(child, cur_key)

    _walk_elem(root, "")
    return entries


def _scan_pdf_file(pdf_path: Path, rel_path: str, forbidden_tokens: list[str] | None = None) -> tuple[list[dict], bool]:
    """Scan all PDF metadata string fields, full XMP XML stream, and extracted page text via isolated subprocess worker."""
    from .research.sources import controlled_read_pdf_pages

    findings: list[dict] = []
    try:
        res = controlled_read_pdf_pages(pdf_path, max_pages=500, timeout_sec=20.0)
        raw_meta = res.get("metadata") or {}
        meta_dict: dict[str, Any] = {str(k): str(v) for k, v in raw_meta.items() if v is not None}
        meta_author = str(
            meta_dict.get("Author") or meta_dict.get("/Author") or meta_dict.get("author") or ""
        ).strip()
        has_xmp_stream = bool(res.get("has_xmp_stream"))
        xmp_xml = str(res.get("xmp_xml") or "")
        page_texts: list[str] | None = list(res.get("pages") or [])
    except Exception:
        return [], False

    if has_xmp_stream:
        try:
            xmp_entries = _extract_xmp_entries(xmp_xml)
        except Exception:
            return [], False
    else:
        xmp_entries = []

    if meta_author and meta_author.lower() not in ANONYMOUS_PLACEHOLDERS:
        findings.append({
            "file": rel_path,
            "line": 0,
            "kind": "non_anonymous_pdf_metadata_author",
            "matched": meta_author[:100],
        })
    for m_key, m_val in sorted(meta_dict.items()):
        val_str = str(m_val).strip()
        if not val_str:
            continue
        for f in scan_text_for_leaks(val_str, rel_path, forbidden_tokens=forbidden_tokens):
            f["line"] = 0
            f["metadata_key"] = m_key
            findings.append(f)
    for xmp_key, xmp_val in xmp_entries:
        key_low = xmp_key.lower()
        attr_part = key_low.split("@", 1)[1] if "@" in key_low else ""
        if (
            any(a in key_low for a in ("creator", "author", "artist", "owner", "contributor"))
            and not key_low.endswith("creatortool")
            and attr_part not in ("parsetype", "xmptk", "begin", "id", "about", "resource")
        ):
            if xmp_val.lower() not in ANONYMOUS_PLACEHOLDERS:
                findings.append({
                    "file": rel_path,
                    "line": 0,
                    "kind": "non_anonymous_pdf_metadata_author",
                    "metadata_key": xmp_key,
                    "matched": xmp_val[:100],
                })
        for f in scan_text_for_leaks(xmp_val, rel_path, forbidden_tokens=forbidden_tokens):
            f["line"] = 0
            f["metadata_key"] = xmp_key
            findings.append(f)
    for idx, ptxt in enumerate(page_texts or [], 1):
        for f in scan_text_for_leaks(ptxt, rel_path, forbidden_tokens=forbidden_tokens):
            f["page"] = idx
            findings.append(f)
    return findings, True


def _decode_file_bytes(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def _is_link_or_junction(p: Path) -> bool:
    if p.parent == Path("/") and p.name in ("var", "tmp", "etc"):
        return False
    try:
        if p.is_symlink():
            return True
    except OSError:
        return True
    is_junc = getattr(os.path, "isjunction", None)
    if is_junc is not None:
        try:
            if is_junc(p):
                return True
        except OSError:
            return True
    try:
        st = os.lstat(p)
        if bool(getattr(st, "st_file_attributes", 0) & 0x400):
            return True
    except FileNotFoundError:
        pass
    except OSError:
        return True
    return False


def _has_ancestor_link_or_junction(p: Path) -> bool:
    cur = p
    while True:
        if _is_link_or_junction(cur):
            return True
        if cur.parent == cur:
            break
        cur = cur.parent
    return False


def scan_target(target: Path, forbidden_tokens: list[str] | None = None, *, root: Path | None = None) -> dict:
    from ._stdlib import safe_path

    raw_target = Path(target)
    if root is not None:
        raw_target = safe_path(raw_target, root=root, must_exist=True)
    if not raw_target.exists() and not _is_link_or_junction(raw_target):
        raise ValueError(f"Target path does not exist: {target}")
    if _has_ancestor_link_or_junction(raw_target):
        return {
            "status": "incomplete",
            "files_scanned": 0,
            "unsupported_files": [raw_target.name],
            "skipped_symlinks": [raw_target.name],
            "leak_count": 0,
            "findings": [],
        }
    target = raw_target.resolve()
    files: list[Path] = []
    pdf_files: list[Path] = []
    unsupported_files: list[str] = []
    skipped_symlinks: list[str] = []

    if target.is_file():
        suf = target.suffix.lower()
        if suf in TEXT_SUFFIXES:
            files.append(target)
        elif suf == ".pdf":
            pdf_files.append(target)
        else:
            unsupported_files.append(target.name)
    else:
        for dirpath, dirnames, filenames in os.walk(target, followlinks=False):
            rel_dir = Path(dirpath).relative_to(target)
            kept_dirs: list[str] = []
            for d in sorted(dirnames):
                if d.lower() in EXCLUDED_DIRS or d.lower().endswith(".egg-info"):
                    continue
                full_d = Path(dirpath) / d
                if _is_link_or_junction(full_d):
                    rel_d = (rel_dir / d).as_posix() if rel_dir.parts else d
                    skipped_symlinks.append(rel_d)
                    unsupported_files.append(rel_d)
                    continue
                kept_dirs.append(d)
            dirnames[:] = kept_dirs
            for fn in sorted(filenames):
                full_p = Path(dirpath) / fn
                rel_posix = (rel_dir / fn).as_posix() if rel_dir.parts else fn
                if _is_link_or_junction(full_p):
                    skipped_symlinks.append(rel_posix)
                    unsupported_files.append(rel_posix)
                    continue
                if not full_p.is_file():
                    continue
                suf = full_p.suffix.lower()
                if suf in TEXT_SUFFIXES:
                    files.append(full_p)
                elif suf == ".pdf":
                    pdf_files.append(full_p)
                else:
                    unsupported_files.append(rel_posix)

    all_findings = []
    tokens = [t.strip() for t in (forbidden_tokens or []) if t and t.strip()]
    if target.is_dir():
        for tok in tokens:
            if _match_forbidden_token(tok, target.name):
                all_findings.append({
                    "file": target.name,
                    "line": 0,
                    "kind": "forbidden_token_in_path",
                    "matched": tok,
                })
    for f in files:
        rel = f.name if target.is_file() else f.relative_to(target).as_posix()
        try:
            txt = _decode_file_bytes(f.read_bytes())
        except UnicodeDecodeError as exc:
            all_findings.append({
                "file": rel,
                "line": 0,
                "kind": "unreadable_encoding",
                "matched": str(exc),
            })
            continue
        all_findings.extend(scan_text_for_leaks(txt, rel, forbidden_tokens=forbidden_tokens))

    scanned_pdf_count = 0
    for pf in pdf_files:
        rel = pf.name if target.is_file() else pf.relative_to(target).as_posix()
        p_findings, ok = _scan_pdf_file(pf, rel, forbidden_tokens=forbidden_tokens)
        if ok:
            scanned_pdf_count += 1
            all_findings.extend(p_findings)
        else:
            unsupported_files.append(rel)

    total_scanned = len(files) + scanned_pdf_count
    if all_findings:
        status = "leaks_detected"
    elif total_scanned == 0 or unsupported_files:
        status = "incomplete"
    else:
        status = "clean"

    return {
        "status": status,
        "files_scanned": total_scanned,
        "unsupported_files": unsupported_files,
        "skipped_symlinks": skipped_symlinks,
        "leak_count": len(all_findings),
        "findings": all_findings,
    }

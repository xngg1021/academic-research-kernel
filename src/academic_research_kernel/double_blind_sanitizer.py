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
REPO_URL_RE = re.compile(
    r"(?:https?://|git@)?(?:www\.|raw\.|gist\.)?"
    r"(?:github(?:usercontent)?\.com|gitlab\.com|bitbucket\.org|huggingface\.co)"
    r"[:/][A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
    re.I,
)
GITHUB_URL_RE = REPO_URL_RE
_NEUTRAL_REPO_PREFIXES = (
    "github.com/iclr/",
    "github.com/acl-org/",
    "github.com/neurips/",
    "github.com/anonymous/",
    "gitlab.com/anonymous/",
    "bitbucket.org/anonymous/",
    "huggingface.co/anonymous/",
)
SELF_OWNED_URL_CUE_RE = re.compile(
    r"\b(?:our\s+(?:source\s+|anonymous\s+)?(?:code|repo|repository|implementation|package|project|library|artifact|data|dataset|benchmark|model|framework|system|tool|supplement|scripts?)\b"
    r"|we\s+(?:release|provide|open[- ]source|publish|host|maintain)\b"
    r"|(?:code|implementation|repository|artifact)\s+(?:is\s+)?(?:available|released|hosted)\b"
    r"|source\s+code\s*[:=])",
    re.I,
)
_BLOCK_BREAK_RE = re.compile(
    r"\n[ \t]*\n|\\(?:par|(?:sub)*section\*?|paragraph\*?|item|begin|end)\b"
)
_ABBREV_DOT_RE = re.compile(
    r"\b(?:e\.g|i\.e|et\s+al|cf|vs|fig|figs|tab|tabs|sec|secs|eq|eqs)\.",
    re.I,
)
_SENT_END_RE = re.compile(r"[.!?;](?=\s|$)")
_INLINE_URL_MASK_RE = re.compile(r"https?://[^\s{}]+", re.I)
_TEX_LINK_OR_FN_CMD_RE = re.compile(r"\\(href|url|footnote|footnotetext|footnotemark)\b")
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


def _skip_ws(text: str, pos: int) -> int:
    n = len(text)
    while pos < n and text[pos].isspace():
        pos += 1
    return pos


def _read_optional_bracket_arg(text: str, pos: int) -> tuple[str | None, int]:
    p = _skip_ws(text, pos)
    n = len(text)
    if p >= n or text[p] != "[":
        return None, pos
    depth = 1
    p += 1
    start = p
    while p < n and depth > 0:
        ch = text[p]
        if ch == "\\":
            p += 2
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
        p += 1
    if depth != 0:
        return None, pos
    return text[start : p - 1].strip(), p


def _read_brace_group(text: str, pos: int) -> tuple[int, int, int] | None:
    p = _skip_ws(text, pos)
    n = len(text)
    if p >= n or text[p] != "{":
        return None
    depth = 1
    p += 1
    start = p
    while p < n and depth > 0:
        ch = text[p]
        if ch == "\\":
            p += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        p += 1
    if depth != 0:
        return None
    return start, p - 1, p


def _enclosing_sentence(text: str, span_start: int, span_end: int) -> str:
    p_start = 0
    for m in _BLOCK_BREAK_RE.finditer(text):
        if m.end() <= span_start:
            p_start = m.end()
        else:
            break
    m_after = _BLOCK_BREAK_RE.search(text, span_end)
    p_end = m_after.start() if m_after is not None else len(text)
    para = text[p_start:p_end]
    if not para:
        return ""
    r_start = max(0, min(len(para), span_start - p_start))
    r_end = max(r_start, min(len(para), span_end - p_start))

    masked = list(para)
    for idx in range(r_start, r_end):
        masked[idx] = "x"
    for m_u in _INLINE_URL_MASK_RE.finditer(para):
        for idx in range(m_u.start(), m_u.end()):
            masked[idx] = "x"
    for m_u2 in REPO_URL_RE.finditer(para):
        for idx in range(m_u2.start(), m_u2.end()):
            masked[idx] = "x"
    for m_cmd in _TEX_LINK_OR_FN_CMD_RE.finditer(para):
        _, p_cur = _read_optional_bracket_arg(para, m_cmd.end())
        g1 = _read_brace_group(para, p_cur)
        if g1 is not None:
            end_g = g1[2]
            if m_cmd.group(1) == "href":
                g2 = _read_brace_group(para, end_g)
                if g2 is not None:
                    end_g = g2[2]
            for idx in range(m_cmd.start(), end_g):
                masked[idx] = "x"
    for m_ab in _ABBREV_DOT_RE.finditer(para):
        masked[m_ab.end() - 1] = " "

    masked_str = "".join(masked)
    s_start = 0
    for m_se in _SENT_END_RE.finditer(masked_str):
        if m_se.start() < r_start:
            s_start = m_se.end()
        else:
            break
    m_next = _SENT_END_RE.search(masked_str, r_end)
    s_end = m_next.end() if m_next is not None else len(para)
    return " ".join(para[s_start:s_end].split())


def scan_repository_urls(
    text: str,
    *,
    is_tex: bool,
    forbidden_tokens: list[str] | None = None,
    already_masked_tex: bool = False,
) -> list[dict[str, Any]]:
    """Bounded repository-URL scanner shared by double_blind_sanitizer and pre_submission_linter."""
    tokens = [t.strip() for t in (forbidden_tokens or []) if t and t.strip()]
    work = text if (not is_tex or already_masked_tex) else _strip_tex_comments(text)

    # Record TeX construct spans: (span_start, span_end, extra_contexts, include_local_body_sentence)
    tex_spans: list[tuple[int, int, list[str], bool]] = []
    if is_tex:
        numbered_marks: dict[str, str] = {}
        unnumbered_marks: list[str] = []
        last_mark_sent: str = ""
        for m_cmd in _TEX_LINK_OR_FN_CMD_RE.finditer(work):
            kind_cmd = m_cmd.group(1)
            c_start = m_cmd.start()
            anch_start = c_start - 1 if (c_start > 0 and work[c_start - 1] in ".!?;)") else c_start
            if kind_cmd == "footnotemark":
                opt_k, after_opt = _read_optional_bracket_arg(work, m_cmd.end())
                sent = _enclosing_sentence(work, anch_start, after_opt)
                last_mark_sent = sent
                if opt_k:
                    numbered_marks[opt_k] = sent
                else:
                    unnumbered_marks.append(sent)
            elif kind_cmd == "href":
                g1 = _read_brace_group(work, m_cmd.end())
                if g1 is None:
                    continue
                g2 = _read_brace_group(work, g1[2])
                if g2 is None:
                    tex_spans.append((g1[0], g1[1], [_enclosing_sentence(work, anch_start, g1[2])], False))
                    continue
                label_txt = " ".join(work[g2[0] : g2[1]].split())
                outer_sent = _enclosing_sentence(work, anch_start, g2[2])
                tex_spans.append((g1[0], g1[1], [label_txt, outer_sent], False))
            elif kind_cmd == "url":
                g1 = _read_brace_group(work, m_cmd.end())
                if g1 is None:
                    continue
                tex_spans.append((g1[0], g1[1], [_enclosing_sentence(work, anch_start, g1[2])], False))
            elif kind_cmd == "footnote":
                _, after_opt = _read_optional_bracket_arg(work, m_cmd.end())
                g1 = _read_brace_group(work, after_opt)
                if g1 is None:
                    continue
                outer_sent = _enclosing_sentence(work, anch_start, g1[2])
                tex_spans.append((g1[0], g1[1], [outer_sent], True))
            elif kind_cmd == "footnotetext":
                opt_k, after_opt = _read_optional_bracket_arg(work, m_cmd.end())
                g1 = _read_brace_group(work, after_opt)
                if g1 is None:
                    continue
                paired = ""
                if opt_k and opt_k in numbered_marks:
                    paired = numbered_marks[opt_k]
                elif unnumbered_marks:
                    paired = unnumbered_marks.pop(0)
                elif last_mark_sent:
                    paired = last_mark_sent
                tex_spans.append((g1[0], g1[1], [paired] if paired else [], True))

    hits: list[dict[str, Any]] = []
    for m_url in REPO_URL_RE.finditer(work):
        raw_matched = m_url.group(0)
        trimmed = raw_matched.rstrip(".,;:!?)>]}") if not raw_matched.lower().endswith(".git") else raw_matched
        u_end = m_url.start() + len(trimmed)
        hit_tok = any(_match_forbidden_token(tok, trimmed) for tok in tokens)
        u_low = trimmed.lower()
        if not hit_tok and any(pref in u_low for pref in _NEUTRAL_REPO_PREFIXES):
            continue

        ctxs: list[str] = []
        matched_span = False
        if is_tex:
            for sp_s, sp_e, extra_c, inc_body in tex_spans:
                if sp_s <= m_url.start() and u_end <= sp_e:
                    matched_span = True
                    ctxs.extend(extra_c)
                    if inc_body:
                        ctxs.append(_enclosing_sentence(work[sp_s:sp_e], m_url.start() - sp_s, u_end - sp_s))
        if not matched_span:
            ctxs.append(_enclosing_sentence(work, m_url.start(), u_end))

        is_self = hit_tok or any(SELF_OWNED_URL_CUE_RE.search(c) is not None for c in ctxs if c)
        hits.append({
            "line": work.count("\n", 0, m_url.start()) + 1,
            "matched": trimmed,
            "is_self": is_self,
            "severity": "error" if is_self else "warning",
        })
    return hits


def scan_text_for_leaks(text: str, rel_path: str, forbidden_tokens: list[str] | None = None) -> list[dict]:
    findings = []
    tokens = [t.strip() for t in (forbidden_tokens or []) if t and t.strip()]
    is_tex_doc = rel_path.lower().endswith((".tex", ".sty", ".cls", ".bbl"))

    for tok in tokens:
        if _match_forbidden_token(tok, rel_path):
            findings.append({
                "file": rel_path,
                "line": 0,
                "kind": "forbidden_token_in_path",
                "severity": "error",
                "matched": tok,
            })

    for line_no, line in enumerate(text.splitlines(), 1):
        for tok in tokens:
            if _match_forbidden_token(tok, line):
                findings.append({
                    "file": rel_path,
                    "line": line_no,
                    "kind": "forbidden_token",
                    "severity": "error",
                    "matched": tok,
                })
        for m in ORCID_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "orcid_identifier",
                "severity": "error",
                "matched": m.group(0),
            })
        for m in EMAIL_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "email_address",
                "severity": "error",
                "matched": m.group(0),
            })
        for m in WIN_PATH_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "local_user_path",
                "severity": "error",
                "matched": m.group(0),
            })
        for m in UNIX_PATH_RE.finditer(line):
            findings.append({
                "file": rel_path,
                "line": line_no,
                "kind": "local_user_path",
                "severity": "error",
                "matched": m.group(0),
            })

    for url_hit in scan_repository_urls(text, is_tex=is_tex_doc, forbidden_tokens=tokens):
        findings.append({
            "file": rel_path,
            "line": url_hit["line"],
            "kind": "non_anonymous_github_url" if url_hit["is_self"] else "public_repo_url_review",
            "severity": url_hit["severity"],
            "matched": url_hit["matched"],
        })

    if is_tex_doc:
        for line_no, body in _extract_balanced_braces(text):
            if not _is_strictly_anonymous_tex_body(body):
                compact = " ".join(body.split())
                findings.append({
                    "file": rel_path,
                    "line": line_no,
                    "kind": "non_anonymous_latex_author",
                    "severity": "error",
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
            "warning_count": 0,
            "findings": [],
            "warnings": [],
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
    hard_findings = [f for f in all_findings if f.get("severity", "error") != "warning"]
    advisory_warnings = [f for f in all_findings if f.get("severity") == "warning"]
    if hard_findings:
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
        "leak_count": len(hard_findings),
        "warning_count": len(advisory_warnings),
        "findings": hard_findings,
        "warnings": advisory_warnings,
    }

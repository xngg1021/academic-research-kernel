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

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

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
    out_lines = []
    for line in text.splitlines():
        i = 0
        while i < len(line):
            if line[i] == "%" and (i == 0 or line[i - 1] != "\\"):
                line = line[:i]
                break
            i += 1
        out_lines.append(line)
    return "\n".join(out_lines)


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
            if ch == "{" and (pos == 0 or cleaned[pos - 1] != "\\"):
                depth += 1
            elif ch == "}" and (pos == 0 or cleaned[pos - 1] != "\\"):
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


def _scan_pdf_file(pdf_path: Path, rel_path: str, forbidden_tokens: list[str] | None = None) -> tuple[list[dict], bool]:
    """Scan PDF metadata (/Author) and extracted page text using pypdf or fitz."""
    findings: list[dict] = []
    meta_author = ""
    page_texts: list[str] | None = None

    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(pdf_path))
        meta = reader.metadata or {}
        meta_author = str(meta.get("/Author") or meta.get("Author") or "").strip()
        page_texts = [(p.extract_text() or "") for p in reader.pages]
    except ImportError:
        try:
            import fitz  # type: ignore
            doc = fitz.open(str(pdf_path))
            try:
                meta = doc.metadata or {}
                meta_author = str(meta.get("author") or "").strip()
                page_texts = [(doc[i].get_text("text") or "") for i in range(len(doc))]
            finally:
                doc.close()
        except ImportError:
            return [], False
        except Exception:
            return [], False
    except Exception:
        return [], False

    if meta_author and meta_author.lower() not in ANONYMOUS_PLACEHOLDERS:
        findings.append({
            "file": rel_path,
            "line": 0,
            "kind": "non_anonymous_pdf_metadata_author",
            "matched": meta_author[:100],
        })
    for idx, ptxt in enumerate(page_texts or [], 1):
        for f in scan_text_for_leaks(ptxt, rel_path, forbidden_tokens=forbidden_tokens):
            f["page"] = idx
            findings.append(f)
    return findings, True


def _decode_file_bytes(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def scan_target(target: Path, forbidden_tokens: list[str] | None = None) -> dict:
    if not target.exists():
        raise ValueError(f"Target path does not exist: {target}")
    target = target.resolve()
    files: list[Path] = []
    pdf_files: list[Path] = []
    unsupported_files: list[str] = []

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
            dirnames[:] = sorted(
                d for d in dirnames
                if d.lower() not in EXCLUDED_DIRS and not d.lower().endswith(".egg-info")
            )
            rel_dir = Path(dirpath).relative_to(target)
            for fn in sorted(filenames):
                full_p = Path(dirpath) / fn
                if full_p.is_symlink() or not full_p.is_file():
                    continue
                rel_posix = (rel_dir / fn).as_posix() if rel_dir.parts else fn
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
        "leak_count": len(all_findings),
        "findings": all_findings,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target_pos", nargs="?", help="待扫描的手稿文件或复现包目录（位置参数）")
    parser.add_argument("--target", dest="target_opt", help="待扫描的手稿文件或复现包目录")
    parser.add_argument("--forbidden-token", action="append", default=[],
                        help="禁止出现的实名/项目代号/工单号（可多次传入）")
    args = parser.parse_args(argv)
    target_val = args.target_opt or args.target_pos
    if not target_val:
        parser.error("必须提供 --target <path> 或位置参数 <path>")
    try:
        report = scan_target(Path(target_val), forbidden_tokens=args.forbidden_token)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "clean" else 1
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

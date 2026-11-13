"""Shared Python standard-library primitives for academic-research-kernel (Occam edition).

Replaces 4 copies of custom FrozenDict/FrozenJSONMap, 15 scattered reparse checks,
8 canonical-JSON helpers, 6 DOI normalizers, 3 LaTeX escapers, and 300+ lines of
hand-rolled msvcrt/fcntl/kernel32 lockfiles with CPython built-in C primitives:
- ``types.MappingProxyType`` + ``tuple`` for zero-overhead immutable views
- ``sqlite3`` WAL + ``STRICT`` + ``busy_timeout`` for cross-platform ACID state
- ``os.lstat`` + ``stat.FILE_ATTRIBUTE_REPARSE_POINT`` for single-point path safety
"""
from __future__ import annotations

import collections.abc
import hashlib
import json
import math
import os
import re
import sqlite3
import stat
import threading
from jsonschema import Draft202012Validator

_SQLITE_INIT_LOCK = threading.RLock()
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterator, Mapping, Optional

_REPARSE_ATTR = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_ARXIV_RE = re.compile(
    r"^(?:https?://arxiv\.org/(?:abs|pdf)/|arxiv:\s*)(\d{4}\.\d{4,5}(?:v\d+)?|[a-z-]+/\d{7}(?:v\d+)?)(?:\.pdf)?$",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")
_LATEX_ESCAPES = str.maketrans({
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
})


def freeze(value: Any) -> Any:
    """Recursively freeze JSON-domain values using CPython's C MappingProxyType."""
    if isinstance(value, MappingProxyType):
        return value
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite float not allowed: {value!r}")
        return value
    if isinstance(value, collections.abc.Mapping):
        return MappingProxyType({str(k): freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(v) for v in value)
    raise TypeError(f"Unsupported non-JSON value type: {type(value).__name__}")


def thaw(value: Any) -> Any:
    """Convert frozen MappingProxyType / tuple views back into plain JSON types."""
    if isinstance(value, collections.abc.Mapping):
        return {str(k): thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    """Deterministic RFC-style compact UTF-8 JSON without NaN/Infinity."""
    return json.dumps(thaw(value), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256_hex(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def nfc_compact(text: str) -> str:
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", str(text))).strip()


def is_link_or_reparse(path: Path) -> bool:
    """Cross-platform symlink & Windows NTFS junction/reparse check via os.lstat."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _REPARSE_ATTR)


def safe_path(path: str | Path, root: Optional[Path] = None) -> Path:
    """Reject symlinks/reparse points along path chain and optionally enforce root containment."""
    p = Path(path).expanduser()
    probe = p if p.is_absolute() else (Path.cwd() / p)
    cur = Path(probe.anchor) if probe.anchor else Path(".")
    for part in probe.parts[1 if probe.anchor else 0 :]:
        cur = cur / part
        if cur.exists() and is_link_or_reparse(cur):
            raise ValueError(f"Symlink or NTFS reparse point rejected: {cur}")
    resolved = probe.resolve(strict=False)
    if root is not None:
        root_resolved = Path(root).resolve(strict=False)
        if resolved != root_resolved and root_resolved not in resolved.parents:
            raise ValueError(f"Path escapes workspace root ({root_resolved}): {resolved}")
    return resolved


def normalize_doi(value: Any) -> str:
    text = _DOI_PREFIX_RE.sub("", str(value or "").strip()).strip().lower()
    return text


def normalize_identifier(raw: str) -> dict[str, str]:
    text = str(raw or "").strip()
    m_arxiv = _ARXIV_RE.match(text)
    if m_arxiv:
        aid = m_arxiv.group(1).lower()
        return {"kind": "arxiv", "id": aid, "canonical": f"arxiv:{aid}"}
    doi = normalize_doi(text)
    if doi.startswith("10.") and "/" in doi:
        return {"kind": "doi", "id": doi, "canonical": f"doi:{doi}"}
    if text.upper().startswith("PMID:"):
        pmid = text.split(":", 1)[1].strip()
        return {"kind": "pmid", "id": pmid, "canonical": f"pmid:{pmid}"}
    return {"kind": "raw", "id": nfc_compact(text), "canonical": nfc_compact(text)}


def tex_escape(text: Any) -> str:
    return str(text or "").translate(_LATEX_ESCAPES)


@contextmanager
def open_sqlite(db_path: str | Path = ":memory:") -> Iterator[sqlite3.Connection]:
    """Cross-platform ACID connection using Python's built-in C SQLite engine.

    Replaces custom msvcrt/fcntl/kernel32 PID lease files, .lock.guard files,
    tempfile+fsync state JSONs, and manual in-memory .clone() rollback loops.
    """
    if str(db_path) != ":memory:":
        target = safe_path(db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        dsn = str(target)
    else:
        dsn = ":memory:"
    conn = sqlite3.connect(dsn, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
        if dsn != ":memory:":
            with _SQLITE_INIT_LOCK:
                cur_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                if cur_mode != "wal":
                    conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        yield conn
    finally:
        conn.close()


def validate_schema(instance: Any, schema_name: str) -> list[str]:
    """Validate JSON instance against schemas/<schema_name>."""
    repo_schemas = Path(__file__).resolve().parents[2] / "schemas" / schema_name
    pkg_schemas = Path(__file__).resolve().parent / "schemas" / schema_name
    schema_path = pkg_schemas if pkg_schemas.is_file() else repo_schemas
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}" for err in validator.iter_errors(instance)]

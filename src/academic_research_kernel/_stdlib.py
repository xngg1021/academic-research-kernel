"""Shared Python standard-library primitives for academic-research-kernel (Occam edition).

Provides one audited implementation of:
- ``freeze`` / ``thaw``: deep recursive copy + validation over ``types.MappingProxyType`` and ``tuple``
- ``safe_path``: fail-closed unconditional ``os.lstat`` symlink & Windows NTFS reparse guard
- ``normalize_identifier`` / ``normalize_doi``: strict grammar for DOI, arXiv, PMID, and OpenAlex IDs
- ``open_sqlite``: cross-process retryable WAL setup, ``recursive_triggers = ON``, ``application_id`` guard, and read-only URI mode
- ``validate_schema``: ``importlib.resources``-first JSON Schema Draft 2020-12 validation
"""
from __future__ import annotations

import collections.abc
from contextlib import contextmanager
import errno
import hashlib
from importlib import resources
import json
import math
import os
from pathlib import Path
import random
import re
import sqlite3
import stat
import threading
import time
from types import MappingProxyType
from typing import Any, Iterator, Optional
import unicodedata

_SQLITE_INIT_LOCK = threading.RLock()
_REPARSE_ATTR = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_MAX_FREEZE_DEPTH = 64

ARK_SQLITE_APP_ID = 0x41524B33  # 'ARK3'
ARK_SQLITE_USER_VERSION = 3


class ImmutableStateError(ValueError):
    """Raised when attempting to overwrite an append-only state record with conflicting content."""

DOI_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)
ARXIV_PREFIXES = ("https://arxiv.org/abs/", "http://arxiv.org/abs/", "arxiv:")
PMID_PREFIXES = ("https://pubmed.ncbi.nlm.nih.gov/", "http://pubmed.ncbi.nlm.nih.gov/", "pmid:")
OPENALEX_PREFIX = "https://openalex.org/"

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ARXIV_NEW_RE = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
ARXIV_OLD_RE = re.compile(r"^[a-z][a-z-]*(\.[a-z]{2})?/\d{7}(v\d+)?$", re.IGNORECASE)
PMID_RE = re.compile(r"^\d{1,9}$")
OPENALEX_RE = re.compile(r"^[WASTCPFI]\d+$")

_DOI_STRIP_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
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


def _freeze_inner(value: Any, depth: int, seen: set[int]) -> Any:
    if depth > _MAX_FREEZE_DEPTH:
        raise ValueError(f"JSON nesting exceeds maximum depth ({_MAX_FREEZE_DEPTH})")
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite float not allowed: {value!r}")
        return value
    if isinstance(value, collections.abc.Mapping):
        oid = id(value)
        if oid in seen:
            raise ValueError("Circular reference detected during freeze()")
        seen.add(oid)
        try:
            copied: dict[str, Any] = {}
            for k, v in value.items():
                if type(k) is not str:
                    raise TypeError(f"JSON mapping keys must be str, got {type(k).__name__}: {k!r}")
                copied[k] = _freeze_inner(v, depth + 1, seen)
            return MappingProxyType(copied)
        finally:
            seen.discard(oid)
    if isinstance(value, (list, tuple)):
        oid = id(value)
        if oid in seen:
            raise ValueError("Circular reference detected during freeze()")
        seen.add(oid)
        try:
            return tuple(_freeze_inner(v, depth + 1, seen) for v in value)
        finally:
            seen.discard(oid)
    raise TypeError(f"Unsupported non-JSON value type: {type(value).__name__}")


def freeze(value: Any) -> Any:
    """Recursively copy, validate, and freeze JSON-domain values into MappingProxyType / tuple."""
    return _freeze_inner(value, 0, set())


def thaw(value: Any) -> Any:
    """Convert frozen MappingProxyType / tuple views into fresh plain JSON containers."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite float not allowed: {value!r}")
        return value
    if isinstance(value, collections.abc.Mapping):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if type(k) is not str:
                raise TypeError(f"JSON mapping keys must be str, got {type(k).__name__}: {k!r}")
            out[k] = thaw(v)
        return out
    if isinstance(value, (list, tuple)):
        return [thaw(v) for v in value]
    raise TypeError(f"Unsupported non-JSON value type: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    """Deterministic compact UTF-8 JSON rejecting non-string keys, cycles, and NaN/Infinity."""
    validated = thaw(freeze(value))
    return json.dumps(validated, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def sha256_hex(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def nfc_compact(text: str) -> str:
    return _WS_RE.sub(" ", unicodedata.normalize("NFC", str(text))).strip()


def _lstat_is_reparse(path: Path) -> bool:
    """Fail-closed symlink & Windows NTFS junction/reparse check via unconditional os.lstat."""
    if path.parent == Path("/") and path.name in ("var", "tmp", "etc"):
        return False
    is_junc = getattr(os.path, "isjunction", None)
    if is_junc is not None:
        try:
            if is_junc(path):
                return True
        except OSError as exc:
            if exc.errno not in (errno.ENOENT, errno.ENOTDIR, errno.EINVAL):
                raise ValueError(f"Unable to inspect path junction state ({path}): {exc}") from exc
    try:
        st = os.lstat(path)
    except OSError as exc:
        if exc.errno in (errno.ENOENT, errno.ENOTDIR):
            return False
        raise ValueError(f"Unable to lstat path component ({path}): {exc}") from exc
    if stat.S_ISLNK(st.st_mode):
        return True
    return bool(getattr(st, "st_file_attributes", 0) & _REPARSE_ATTR)


def is_link_or_reparse(path: str | Path) -> bool:
    """Public predicate returning True if path is a symlink/junction (including dangling links)."""
    return _lstat_is_reparse(Path(path))


def _walk_lexical_no_reparse(target: Path) -> None:
    cur = Path(target.anchor) if target.anchor else Path(".")
    start_idx = 1 if target.anchor else 0
    for part in target.parts[start_idx:]:
        if part in ("", "."):
            continue
        cur = cur / part
        if _lstat_is_reparse(cur):
            raise ValueError(f"Symlink or NTFS reparse point rejected: {cur}")


def safe_path(path: str | Path, root: Optional[str | Path] = None) -> Path:
    """Reject symlinks/dangling junctions along every lexical component and enforce optional root containment."""
    raw_str = str(path)
    if not raw_str.strip() or "\x00" in raw_str:
        raise ValueError("Invalid empty or NUL-containing path")
    p = Path(raw_str).expanduser()
    if root is not None:
        raw_root = Path(root).expanduser()
        abs_root = raw_root if raw_root.is_absolute() else (Path.cwd() / raw_root)
        _walk_lexical_no_reparse(abs_root)
        root_resolved = abs_root.resolve(strict=False)
        probe = p if p.is_absolute() else (root_resolved / p)
        _walk_lexical_no_reparse(probe)
        resolved = probe.resolve(strict=False)
        if not resolved.is_relative_to(root_resolved):
            raise ValueError(f"Path escapes workspace root ({root_resolved}): {resolved}")
        return resolved
    probe = p if p.is_absolute() else (Path.cwd() / p)
    _walk_lexical_no_reparse(probe)
    return probe.resolve(strict=False)


def normalize_doi(value: Any) -> str:
    text = _DOI_STRIP_RE.sub("", str(value or "").strip()).strip().rstrip(".").lower()
    return text


def _unknown_id(raw: Any) -> dict[str, Any]:
    return {"input": raw, "type": "unknown", "value": None, "canonical": None}


def normalize_identifier(raw: str) -> dict[str, Any]:
    """Strict deterministic scholarly identifier normalizer (DOI / arXiv / PMID / OpenAlex)."""
    if not isinstance(raw, str):
        return _unknown_id(raw)
    text = raw.strip()
    if not text:
        return _unknown_id(raw)
    lowered = text.lower()

    for prefix in DOI_PREFIXES:
        if lowered.startswith(prefix):
            candidate = text[len(prefix) :].strip().lower().rstrip(".")
            if DOI_RE.match(candidate):
                return {"input": raw, "type": "doi", "value": candidate, "canonical": "https://doi.org/" + candidate}
            return _unknown_id(raw)

    arxiv_text = text
    if lowered.startswith(("https://arxiv.org/pdf/", "http://arxiv.org/pdf/")):
        arxiv_text = lowered.split("/pdf/", 1)[1]
        if not arxiv_text.strip():
            return _unknown_id(raw)
        arxiv_text = re.sub(r"\.pdf$", "", arxiv_text, flags=re.IGNORECASE)
    else:
        for prefix in ARXIV_PREFIXES:
            if arxiv_text.lower().startswith(prefix):
                arxiv_text = arxiv_text[len(prefix) :]
                break
    if arxiv_text != text or ARXIV_NEW_RE.match(arxiv_text) or ARXIV_OLD_RE.match(arxiv_text):
        candidate = arxiv_text.strip().strip("/")
        if ARXIV_NEW_RE.match(candidate) or ARXIV_OLD_RE.match(candidate):
            return {"input": raw, "type": "arxiv", "value": candidate, "canonical": "https://arxiv.org/abs/" + candidate}
        if arxiv_text != text:
            return _unknown_id(raw)

    for prefix in PMID_PREFIXES:
        if lowered.startswith(prefix):
            candidate = text[len(prefix) :].strip().strip("/")
            if PMID_RE.match(candidate):
                return {
                    "input": raw,
                    "type": "pmid",
                    "value": candidate,
                    "canonical": "https://pubmed.ncbi.nlm.nih.gov/" + candidate + "/",
                }
            return _unknown_id(raw)

    if lowered.startswith(OPENALEX_PREFIX):
        candidate = text[len(OPENALEX_PREFIX) :].strip().strip("/").upper()
        if OPENALEX_RE.match(candidate):
            return {"input": raw, "type": "openalex", "value": candidate, "canonical": OPENALEX_PREFIX + candidate}
        return _unknown_id(raw)

    if DOI_RE.match(lowered):
        return {"input": raw, "type": "doi", "value": lowered, "canonical": "https://doi.org/" + lowered}
    if OPENALEX_RE.match(text.upper()):
        candidate = text.upper()
        return {"input": raw, "type": "openalex", "value": candidate, "canonical": OPENALEX_PREFIX + candidate}
    if PMID_RE.match(text):
        return {"input": raw, "type": "pmid", "value": text, "canonical": "https://pubmed.ncbi.nlm.nih.gov/" + text + "/"}
    return _unknown_id(raw)


def tex_escape(text: Any) -> str:
    return str(text or "").translate(_LATEX_ESCAPES)


def configure_sqlite_connection(conn: sqlite3.Connection, *, readonly: bool = False) -> None:
    """Apply and verify mandatory per-connection SQLite safety pragmas."""
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA recursive_triggers = ON")
    fk_on = int(conn.execute("PRAGMA foreign_keys").fetchone()[0])
    rt_on = int(conn.execute("PRAGMA recursive_triggers").fetchone()[0])
    if fk_on != 1 or rt_on != 1:
        raise RuntimeError("SQLite failed to enable foreign_keys or recursive_triggers")
    if readonly:
        conn.execute("PRAGMA query_only = ON")


def verify_or_claim_sqlite_identity(conn: sqlite3.Connection, *, readonly: bool = False) -> None:
    """Prevent accidental mutation or misinterpretation of unrelated SQLite databases."""
    app_id = int(conn.execute("PRAGMA application_id").fetchone()[0])
    if app_id == ARK_SQLITE_APP_ID:
        return
    tables = [
        str(r[0])
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    ]
    if readonly:
        if not tables:
            raise ValueError("Database is empty or uninitialized")
        raise ValueError(f"Refusing to read non-ARK SQLite database (application_id={app_id:#x})")
    if app_id != 0 or tables:
        raise ValueError(f"Refusing to initialize or mutate non-ARK SQLite database (application_id={app_id:#x}, tables={tables})")


def run_with_sqlite_retry(fn, *, max_attempts: int = 16):
    """Bounded exponential backoff + jitter for cold cross-process WAL/schema initialization races."""
    for attempt in range(max_attempts):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            if attempt + 1 >= max_attempts:
                raise
            time.sleep(min(0.25, 0.008 * (1.6 ** attempt)) + random.uniform(0.0, 0.012))


@contextmanager
def open_sqlite(
    db_path: str | Path = ":memory:",
    *,
    readonly: bool = False,
    root: Optional[str | Path] = None,
) -> Iterator[sqlite3.Connection]:
    """Open a configured SQLite connection with reparse checks, application_id guard, and WAL retry."""
    if str(db_path) == ":memory:":
        if readonly:
            raise ValueError("Cannot open transient ':memory:' database in read-only mode")
        conn = sqlite3.connect(":memory:", timeout=10.0, isolation_level=None)
        try:
            configure_sqlite_connection(conn, readonly=False)
            yield conn
        finally:
            conn.close()
        return

    target = safe_path(db_path, root=root)
    if readonly:
        if not target.is_file():
            raise FileNotFoundError(f"Research state database not found: {target}")
        uri = target.as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=10.0, isolation_level=None)
        try:
            configure_sqlite_connection(conn, readonly=True)
            verify_or_claim_sqlite_identity(conn, readonly=True)
            yield conn
        finally:
            conn.close()
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    target = safe_path(target, root=root)
    conn = sqlite3.connect(str(target), timeout=10.0, isolation_level=None)
    try:
        configure_sqlite_connection(conn, readonly=False)

        def _init_wal() -> None:
            with _SQLITE_INIT_LOCK:
                verify_or_claim_sqlite_identity(conn, readonly=False)
                cur_mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                if cur_mode != "wal":
                    conn.execute("PRAGMA journal_mode = WAL")
                conn.execute("PRAGMA synchronous = NORMAL")

        run_with_sqlite_retry(_init_wal)
        yield conn
    finally:
        conn.close()


def read_packaged_schema(schema_name: str) -> dict[str, Any]:
    """Load a canonical JSON schema from package resources first, then repository root."""
    if "/" in schema_name or "\\" in schema_name or ".." in schema_name:
        raise ValueError(f"Invalid schema name: {schema_name!r}")
    try:
        ref = resources.files("academic_research_kernel").joinpath("schemas", schema_name)
        if ref.is_file():
            return json.loads(ref.read_text(encoding="utf-8"))
    except Exception:
        pass
    pkg_schemas = Path(__file__).resolve().parent / "schemas" / schema_name
    if pkg_schemas.is_file():
        return json.loads(pkg_schemas.read_text(encoding="utf-8"))
    repo_schemas = Path(__file__).resolve().parents[2] / "schemas" / schema_name
    if repo_schemas.is_file():
        return json.loads(repo_schemas.read_text(encoding="utf-8"))
    raise FileNotFoundError(f"Schema resource not found: {schema_name}")


def validate_schema(instance: Any, schema_name: str) -> list[str]:
    """Validate JSON instance against schemas/<schema_name> using Draft 2020-12."""
    from jsonschema import Draft202012Validator

    schema = read_packaged_schema(schema_name)
    validator = Draft202012Validator(schema)
    return [f"{'/'.join(str(p) for p in err.path) or '<root>'}: {err.message}" for err in validator.iter_errors(instance)]

"""Unified OpenAlex/Crossref literature & retraction watcher backed by stdlib sqlite3.

Replaces 1,057 lines across ``skills/retraction-watch/scripts/watch.py`` (610 lines)
and ``skills/literature-watch/scripts/watch.py`` (447 lines), eliminating 300+ lines
of hand-rolled ``msvcrt``/``fcntl``/``kernel32.OpenProcess`` ``.lock.guard`` files
and ``tempfile.mkstemp`` JSON state replacement in favor of ``ResearchStateDB``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import quote
from urllib.request import Request

from ._stdlib import freeze, normalize_doi, safe_path
from .research.sources import controlled_urlopen
from .state_db import ResearchStateDB

OPENALEX_BASE = "https://api.openalex.org"
CROSSREF_BASE = "https://api.crossref.org/v1"
USER_AGENT = "academic-research-kernel/3.0-occam (mailto:local@localhost)"


def load_watchlist(path: str | Path) -> dict[str, list[str]]:
    p = safe_path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Watchlist must be a JSON object")
    dois = [normalize_doi(d) for d in (data.get("dois") or []) if str(d).strip()]
    topics = [str(t).strip() for t in (data.get("topics") or []) if str(t).strip()]
    authors = [str(a).strip() for a in (data.get("authors") or []) if str(a).strip()]
    return {"dois": dois, "topics": topics, "authors": authors}


def _fetch_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with controlled_urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def update_signals_from_records(records: Iterable[dict[str, Any]], target_doi: str) -> list[str]:
    target = normalize_doi(target_doi)
    found: set[str] = set()
    for rec in records:
        notice_doi = normalize_doi(rec.get("DOI") or "")
        for upd in rec.get("update-to") or []:
            if normalize_doi(upd.get("DOI") or "") == target:
                kind = str(upd.get("type") or "update")
                source = str(upd.get("source") or "unknown")
                upd_doi = notice_doi or target or "?"
                stamp = str(upd.get("date") or upd.get("timestamp") or "").strip()
                sig = f"{kind}({source}) update-doi={upd_doi}"
                if stamp:
                    sig += f" date={stamp}"
                found.add(sig)
    return sorted(found)


def check_retraction_signals(
    dois: Sequence[str],
    db_path: str | Path = ":memory:",
    live: bool = False,
    mock_records: dict[str, tuple[bool, list[str]]] | None = None,
) -> list[dict[str, Any]]:
    """Record DOI retraction/correction status in SQLite WAL and return ONLY changed items."""
    db = ResearchStateDB(db_path)
    deltas: list[dict[str, Any]] = []
    try:
        for raw_doi in dois:
            doi = normalize_doi(raw_doi)
            if not doi:
                continue
            if mock_records is not None and doi in mock_records:
                is_ret, sigs = mock_records[doi]
            elif live:
                oa = _fetch_json(f"{OPENALEX_BASE}/works/https://doi.org/{quote(doi, safe='')}")
                is_ret = bool(oa.get("is_retracted"))
                cr = _fetch_json(f"{CROSSREF_BASE}/works?filter=updates:{quote(doi, safe='')}&rows=50")
                items = (cr.get("message") or {}).get("items") or []
                sigs = update_signals_from_records(items, doi)
                if any("retract" in s.lower() for s in sigs):
                    is_ret = True
            else:
                is_ret, sigs = False, []
            res = db.update_doi_watch("retraction", doi, is_ret, sigs)
            if res["changed"]:
                deltas.append(dict(res))
    finally:
        db.close()
    return deltas


def filter_new_literature(
    works: Sequence[dict[str, Any]],
    db_path: str | Path = ":memory:",
) -> list[dict[str, Any]]:
    """Deduplicate incoming works against SQLite state, returning only unseen works."""
    db = ResearchStateDB(db_path)
    unseen: list[dict[str, Any]] = []
    try:
        for w in works:
            key = normalize_doi(w.get("doi") or "") or str(w.get("id") or w.get("title") or "").strip().lower()
            if not key:
                continue
            res = db.update_doi_watch("literature", key, False, [str(w.get("publication_year") or "")])
            if res["version"] == 1 and res["changed"]:
                unseen.append(dict(freeze(w)))
    finally:
        db.close()
    return unseen

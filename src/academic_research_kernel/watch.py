"""Unified OpenAlex/Crossref literature & retraction watcher backed by stdlib sqlite3.

Preserves three-valued observation semantics ('retracted' | 'not_retracted' | 'unknown'),
pre-network monotonic sequence reservation (CAS), structured Crossref update-type
classification, truncation reporting, and durable unacknowledged-delta outbox delivery.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence
from urllib.parse import quote
from urllib.request import Request

from ._stdlib import freeze, normalize_doi, safe_path
from .research.sources import controlled_urlopen
from .state_db import ResearchStateDB

OPENALEX_BASE = "https://api.openalex.org"
CROSSREF_BASE = "https://api.crossref.org/v1"
USER_AGENT = "academic-research-kernel/3.0.0 (mailto:local@localhost)"

RETRACTION_UPDATE_TYPES: frozenset[str] = frozenset({
    "retraction",
    "withdrawal",
    "removal",
    "expression_of_concern",
    "expression-of-concern",
})


def load_watchlist(path: str | Path) -> dict[str, list[str]]:
    p = safe_path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Watchlist must be a JSON object")
    dois = [normalize_doi(d) for d in (data.get("dois") or []) if str(d).strip()]
    topics = [str(t).strip() for t in (data.get("topics") or []) if str(t).strip()]
    authors = [str(a).strip() for a in (data.get("authors") or []) if str(a).strip()]
    return {"dois": dois, "topics": topics, "authors": authors}


def _fetch_json(url: str, timeout: float = 15.0, max_bytes: int = 8 * 1024 * 1024) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with controlled_urlopen(req, timeout=timeout, max_bytes=max_bytes) as resp:
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"Watcher response exceeds {max_bytes} byte cap")
        parsed = json.loads(raw.decode("utf-8"))
        if not isinstance(parsed, dict):
            raise ValueError("Provider JSON response must be an object")
        return parsed


def classify_crossref_updates(records: Iterable[dict[str, Any]], target_doi: str) -> tuple[list[str], bool]:
    """Extract structured update signals targeting ``target_doi`` and whether any is a retraction-class notice."""
    target = normalize_doi(target_doi)
    found: set[str] = set()
    has_retraction_notice = False
    for rec in records:
        if not isinstance(rec, dict):
            continue
        notice_doi = normalize_doi(rec.get("DOI") or "")
        for upd in rec.get("update-to") or []:
            if not isinstance(upd, dict):
                continue
            if normalize_doi(upd.get("DOI") or "") == target:
                kind = str(upd.get("type") or "update").strip()
                kind_low = kind.lower()
                if kind_low in RETRACTION_UPDATE_TYPES:
                    has_retraction_notice = True
                source = str(upd.get("source") or "unknown").strip()
                upd_doi = notice_doi or target or "?"
                stamp = str(upd.get("date") or upd.get("timestamp") or "").strip()
                sig = f"{kind}({source}) update-doi={upd_doi}"
                if stamp:
                    sig += f" date={stamp}"
                found.add(sig)
    return sorted(found), has_retraction_notice


def update_signals_from_records(records: Iterable[dict[str, Any]], target_doi: str) -> list[str]:
    sigs, _ = classify_crossref_updates(records, target_doi)
    return sigs


def check_retraction_report(
    dois: Sequence[str],
    db_path: str | Path = ":memory:",
    *,
    live: bool = False,
    mock_records: dict[str, tuple[Optional[bool], list[str]]] | None = None,
    db: Optional[ResearchStateDB] = None,
    root: Optional[str | Path] = None,
    rows: int = 100,
) -> dict[str, Any]:
    """Check DOI retraction/correction deltas with CAS ordering, offline safety, and outbox delivery."""
    owns_db = db is None
    state_db = db if db is not None else ResearchStateDB(db_path, root=root)
    norm_dois: list[str] = []
    errors: list[dict[str, str]] = []
    truncated_dois: list[str] = []
    results: list[dict[str, Any]] = []
    try:
        for raw_doi in dois:
            doi = normalize_doi(raw_doi)
            if not doi:
                continue
            norm_dois.append(doi)
            seq = state_db.reserve_watch_seq("retraction", doi)
            if mock_records is not None and doi in mock_records:
                flag, sigs = mock_records[doi]
                status = "unknown" if flag is None else ("retracted" if flag else "not_retracted")
                res = state_db.commit_watch_observation("retraction", doi, seq=seq, status=status, signals=sigs)
                results.append(dict(res))
                continue
            if not live:
                # Offline invocation without mock fixture: record unknown without mutating confirmed state
                res = state_db.commit_watch_observation("retraction", doi, seq=seq, status="unknown", signals=())
                results.append(dict(res))
                continue

            oa_flag: Optional[bool] = None
            oa_err: Optional[str] = None
            cr_err: Optional[str] = None
            sigs: list[str] = []
            has_ret_upd = False
            is_truncated = False

            try:
                oa = _fetch_json(f"{OPENALEX_BASE}/works/https://doi.org/{quote(doi, safe='')}")
                if not isinstance(oa, dict) or not isinstance(oa.get("is_retracted"), bool):
                    oa_err = "openalex: invalid_response: missing boolean is_retracted"
                else:
                    oa_flag = oa["is_retracted"]
            except Exception as exc:
                oa_err = f"openalex: {type(exc).__name__}: {exc}"

            try:
                cr = _fetch_json(f"{CROSSREF_BASE}/works?filter=updates:{quote(doi, safe='')}&rows={int(rows)}")
                msg = cr.get("message") if isinstance(cr, dict) and isinstance(cr.get("message"), dict) else None
                tot = msg.get("total-results") if msg is not None else None
                if (
                    msg is None
                    or not isinstance(msg.get("items"), list)
                    or not isinstance(tot, int)
                    or isinstance(tot, bool)
                ):
                    cr_err = "crossref: invalid_response: missing message.items or integer total-results"
                else:
                    items = msg["items"]
                    sigs, has_ret_upd = classify_crossref_updates(items, doi)
                    if tot > len(items):
                        is_truncated = True
                        truncated_dois.append(doi)
            except Exception as exc:
                cr_err = f"crossref: {type(exc).__name__}: {exc}"

            err_parts = [e for e in (oa_err, cr_err) if e]
            err_msg = "; ".join(err_parts) if err_parts else None
            if err_msg:
                errors.append({"doi": doi, "error": err_msg})

            if oa_flag is True or has_ret_upd:
                obs_status = "retracted"
            elif oa_flag is False and cr_err is None and not is_truncated:
                obs_status = "not_retracted"
            else:
                obs_status = "unknown"

            res = state_db.commit_watch_observation(
                "retraction",
                doi,
                seq=seq,
                status=obs_status,
                signals=sigs,
                signals_complete=(cr_err is None and not is_truncated),
                truncated=is_truncated,
                error=err_msg,
            )
            results.append(dict(res))

        deltas = state_db.drain_unacked_watch_deltas("retraction", norm_dois)
        return {
            "checked_count": len(norm_dois),
            "deltas": deltas,
            "results": results,
            "truncated_dois": truncated_dois,
            "errors": errors,
            "partial_coverage": bool(errors or truncated_dois),
        }
    finally:
        if owns_db:
            state_db.close()


def check_retraction_signals(
    dois: Sequence[str],
    db_path: str | Path = ":memory:",
    live: bool = False,
    mock_records: dict[str, tuple[Optional[bool], list[str]]] | None = None,
    *,
    db: Optional[ResearchStateDB] = None,
    root: Optional[str | Path] = None,
) -> list[dict[str, Any]]:
    """Return unacknowledged retraction/update deltas (preserving committed alerts across partial errors)."""
    rep = check_retraction_report(dois, db_path=db_path, live=live, mock_records=mock_records, db=db, root=root)
    return rep["deltas"]


def filter_new_literature(
    works: Sequence[dict[str, Any]],
    db_path: str | Path = ":memory:",
    *,
    db: Optional[ResearchStateDB] = None,
    root: Optional[str | Path] = None,
) -> list[dict[str, Any]]:
    """Atomically deduplicate incoming works in a single SQLite transaction, returning unseen items."""
    owns_db = db is None
    state_db = db if db is not None else ResearchStateDB(db_path, root=root)
    unseen: list[dict[str, Any]] = []
    try:
        with state_db.transaction():
            for w in works:
                if not isinstance(w, dict):
                    continue
                key = normalize_doi(w.get("doi") or "") or str(w.get("id") or w.get("title") or "").strip().lower()
                if not key:
                    continue
                seq = state_db.reserve_watch_seq("literature", key)
                res = state_db.commit_watch_observation(
                    "literature",
                    key,
                    seq=seq,
                    status="not_retracted",
                    signals=[str(w.get("publication_year") or "")],
                )
                if res["version"] == 1 and res["changed"]:
                    unseen.append(dict(freeze(w)))
            state_db.drain_unacked_watch_deltas("literature")
    finally:
        if owns_db:
            state_db.close()
    return unseen


def run_literature_watch(
    watchlist: dict[str, list[str]],
    db_path: str | Path = ":memory:",
    *,
    live: bool = False,
    days: int = 7,
    per_page: int = 25,
    max_pages: int = 2,
    fixture_works: Optional[Sequence[dict[str, Any]]] = None,
    db: Optional[ResearchStateDB] = None,
    root: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Bounded incremental literature collector over topics, authors, and citing works of watched DOIs."""
    collected: list[dict[str, Any]] = list(fixture_works or ())
    source_errors: list[str] = []
    truncated = False

    if live:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))).strftime("%Y-%m-%d")
        queries: list[tuple[str, str]] = []
        for topic in watchlist.get("topics") or ():
            queries.append(("topic", f"{OPENALEX_BASE}/works?search={quote(topic)}&filter=from_publication_date:{cutoff}"))
        for author in watchlist.get("authors") or ():
            flt = f"authorships.author.id:{quote(author)}" if author.upper().startswith("A") and author[1:].isdigit() else f"raw_author_name.search:{quote(author)}"
            queries.append(("author", f"{OPENALEX_BASE}/works?filter={flt},from_publication_date:{cutoff}"))
        for doi in watchlist.get("dois") or ():
            queries.append(("citing_doi", f"{OPENALEX_BASE}/works?filter=cites:https://doi.org/{quote(doi, safe='')},from_publication_date:{cutoff}"))

        for q_kind, base_url in queries:
            for page in range(1, max(1, int(max_pages)) + 1):
                try:
                    resp = _fetch_json(f"{base_url}&per-page={int(per_page)}&page={page}")
                    results = resp.get("results") if isinstance(resp.get("results"), list) else []
                    collected.extend(r for r in results if isinstance(r, dict))
                    meta = resp.get("meta") if isinstance(resp.get("meta"), dict) else {}
                    count = meta.get("count")
                    if isinstance(count, int) and count > page * int(per_page):
                        if page == int(max_pages):
                            truncated = True
                    else:
                        break
                except Exception as exc:
                    source_errors.append(f"{q_kind}[page={page}]: {type(exc).__name__}: {exc}")
                    break

    new_items = filter_new_literature(collected, db_path=db_path, db=db, root=root)
    return {
        "fetched_count": len(collected),
        "new_count": len(new_items),
        "new_works": new_items,
        "truncated": truncated,
        "source_errors": source_errors,
        "partial_coverage": bool(truncated or source_errors),
    }

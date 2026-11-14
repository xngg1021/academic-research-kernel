"""Order-independent multi-layer candidate corpus merger and OpenAlex concept/related search.

Merges `{layer_name: [work, ...]}` across `text-search`, `algorithmic-related`, `topic-cross`,
and `citation-pool` using Union-Find equivalence while keeping conflicting non-empty DOIs separate.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Mapping
from urllib.error import HTTPError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request

from ._stdlib import canonical_json, normalize_doi
from .research.sources import controlled_urlopen

USER_AGENT = "academic-research-kernel/3.0.0"
KNOWN_LAYERS = ("text-search", "algorithmic-related", "topic-cross", "citation-pool")


def normalize_title(title: Any) -> str:
    return " ".join(re.findall(r"[^\W_]+", str(title or "").lower()))


def _work_key(work: Mapping[str, Any]) -> str | None:
    doi = normalize_doi(str(work.get("doi") or ""))
    if doi:
        return f"doi:{doi}"
    openalex_id = str(work.get("id") or work.get("openalex_id") or "").strip()
    if openalex_id:
        return "openalex:" + openalex_id.split("/")[-1]
    title = normalize_title(work.get("title"))
    if not title:
        return None
    year = str(work.get("publication_year") or work.get("year") or "").strip()
    return f"title:{title}#{year}" if year else f"title:{title}"


def merge_candidates(layers: Mapping[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Union-Find multi-layer candidate merger preserving distinct DOI conflicts and full metadata."""
    if not isinstance(layers, Mapping):
        raise ValueError("layers must be a mapping from layer name to list of work dicts")
    all_items: list[dict[str, Any]] = []
    skipped = 0
    for layer, works in layers.items():
        if not isinstance(layer, str) or not layer.strip():
            raise ValueError("layer names must be non-empty strings")
        if works is not None and not isinstance(works, list):
            raise ValueError(f"layer {layer!r} must map to a list of work objects")
        for work in works or []:
            if not isinstance(work, dict):
                skipped += 1
                continue
            k = _work_key(work)
            if k is None:
                skipped += 1
                continue
            doi = normalize_doi(str(work.get("doi") or "")) or None
            oa_raw = str(work.get("id") or work.get("openalex_id") or "").strip()
            oa_id = oa_raw.split("/")[-1] if oa_raw else None
            all_items.append({
                "work": work,
                "layer": layer,
                "key": k,
                "doi": doi,
                "oa_id": oa_id,
            })

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        if parent.setdefault(x, x) != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            if rx.startswith("doi:"):
                parent[ry] = rx
            else:
                parent[rx] = ry

    for item in all_items:
        find(item["key"])

    oa_to_dois: dict[str, set[str]] = {}
    for item in all_items:
        if item["oa_id"] and item["doi"]:
            oa_to_dois.setdefault(item["oa_id"], set()).add(item["doi"])

    for item in all_items:
        if item["doi"] and item["oa_id"] and len(oa_to_dois.get(item["oa_id"], set())) <= 1:
            union(f"doi:{item['doi']}", f"openalex:{item['oa_id']}")

    def _pick_str(a: Any, b: Any) -> Any:
        sa = str(a).strip() if a is not None else ""
        sb = str(b).strip() if b is not None else ""
        if not sa and not sb:
            return None
        if not sa:
            return sb
        if not sb:
            return sa
        return sa if (len(sa), sa) >= (len(sb), sb) else sb

    def _pick_seq(a: Any, b: Any) -> Any:
        la = len(a) if isinstance(a, list) else -1
        lb = len(b) if isinstance(b, list) else -1
        if la < 0:
            return b
        if lb < 0:
            return a
        if la != lb:
            return a if la > lb else b
        return a if canonical_json(a) >= canonical_json(b) else b

    merged: dict[str, dict[str, Any]] = {}
    for item in all_items:
        work = item["work"]
        layer = item["layer"]
        canonical = find(item["key"])
        w_year = work.get("publication_year") if work.get("publication_year") is not None else work.get("year")
        w_authors = work.get("authors") if work.get("authors") is not None else work.get("authorships")
        w_cited = work.get("cited_by_count")
        w_rel = work.get("relevance_score")
        w_title = _pick_str(work.get("title"), None)
        w_abstract = _pick_str(work.get("abstract"), None)
        entry = merged.get(canonical)
        if entry is None:
            entry = {
                "key": canonical,
                "title": w_title,
                "year": w_year,
                "doi": item["doi"],
                "openalex_id": item["oa_id"],
                "cited_by_count": w_cited,
                "relevance_score": w_rel,
                "authors": w_authors,
                "abstract": w_abstract,
                "referenced_works": work.get("referenced_works"),
                "source_layers": [layer],
            }
            merged[canonical] = entry
        else:
            if item["doi"] and (entry.get("doi") is None or str(item["doi"]) < str(entry["doi"])):
                entry["doi"] = item["doi"]
            if item["oa_id"] and (entry.get("openalex_id") is None or str(item["oa_id"]) < str(entry["openalex_id"])):
                entry["openalex_id"] = item["oa_id"]
            entry["title"] = _pick_str(entry.get("title"), w_title)
            entry["abstract"] = _pick_str(entry.get("abstract"), w_abstract)
            if w_year is not None:
                entry["year"] = w_year if entry.get("year") is None else min(int(entry["year"]), int(w_year))
            if w_cited is not None:
                entry["cited_by_count"] = w_cited if entry.get("cited_by_count") is None else max(int(entry["cited_by_count"]), int(w_cited))
            if w_rel is not None:
                entry["relevance_score"] = w_rel if entry.get("relevance_score") is None else max(float(entry["relevance_score"]), float(w_rel))
            entry["authors"] = _pick_seq(entry.get("authors"), w_authors)
            entry["referenced_works"] = _pick_seq(entry.get("referenced_works"), work.get("referenced_works"))
            if layer not in entry["source_layers"]:
                entry["source_layers"].append(layer)
                entry["source_layers"].sort()

    candidates = list(merged.values())
    candidates.sort(
        key=lambda c: (
            0 if c["relevance_score"] is not None else 1,
            -float(c["relevance_score"] or 0.0),
            -int(c["cited_by_count"] or 0),
            str(c["key"]),
        )
    )
    return {
        "candidates": candidates,
        "count": len(candidates),
        "skipped_unidentifiable": skipped,
        "known_layers": list(KNOWN_LAYERS),
    }


def _live_get(url: str) -> dict[str, Any]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    key = os.environ.get("OPENALEX_API_KEY", "").strip()
    if urlsplit(url).netloc == "api.openalex.org" and key:
        headers["Authorization"] = f"Bearer {key}"
    for attempt in range(3):
        try:
            with controlled_urlopen(Request(url, headers=headers), timeout=20) as response:
                data = json.load(response)
                return data if isinstance(data, dict) else {}
        except HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            retry = error.headers.get("Retry-After", "")
            delay = float(retry) if retry.isdigit() else float(2**attempt)
            if delay > 10:
                raise
            time.sleep(delay)
    return {}


def live_search(query: str, per_page: int = 10) -> list[dict[str, Any]]:
    params = {
        "search": query,
        "per_page": max(1, min(int(per_page), 100)),
        "sort": "relevance_score:desc",
        "select": "id,title,publication_year,cited_by_count,doi,relevance_score",
    }
    res = _live_get("https://api.openalex.org/works?" + urlencode(params)).get("results")
    return [x for x in (res or []) if isinstance(x, dict)]


def live_work(doi: str) -> dict[str, Any]:
    clean = normalize_doi(doi)
    select = "id,title,publication_year,cited_by_count,doi,related_works,topics,primary_topic"
    return _live_get(
        "https://api.openalex.org/works/https://doi.org/"
        + quote(clean, safe="")
        + "?"
        + urlencode({"select": select})
    )

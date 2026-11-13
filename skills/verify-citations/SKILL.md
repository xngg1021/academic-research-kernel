---
name: verify-citations
description: "Verify DOIs, track retractions, merge corpora, find OA."
version: 3.0.0
author: Junfu Shi (SJF, xngg1021)
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, citations, retraction-watch, openalex, crossref, unpaywall]
    related_skills: [audit-paper, meta-analysis, check-submission]
---

# Verify Citations (`verify-citations`)

Citation authenticity, Crossref update/correction lookup, transactional SQLite retraction and literature monitoring, multi-layer corpus merging, and five-source Open Access resolution via `academic-research-kernel` (`3.0.0`). Consolidates `academic-source-verification`, `retraction-watch`, `literature-watch`, and `collect_corpus`.

## When to Use

- Verifying whether cited DOIs, titles, authors, venues, or local PDFs match Crossref and OpenAlex (`verify-work`), or checking Crossref `update-to` retraction/correction notices (`verify-work --check-updates`).
- Monitoring a DOI list or watchlist JSON for retraction signals (`retraction-watch`) or tracking newly published works by topic/author/DOI (`literature-watch`) with SQLite `STRICT` + `WAL` state.
- Merging multi-channel candidate lists (`text-search`, `algorithmic-related`, `topic-cross`, `citation-pool`) with Union-Find deduplication that preserves conflicting DOIs (`collect-corpus`).
- Resolving legal Open Access PDFs across `arXiv`, `Unpaywall`, `OpenAlex` institutional repositories, `Semantic Scholar`, and `Europe PMC` (`locate-oa --fallback-all`).

## Quick CLI Commands

```bash
# 1. Dual-source DOI verification, Crossref update-to lookup, and local PDF identity check
academic-research-kernel verify-work "10.1038/nature14539"
academic-research-kernel verify-work "10.1038/nature14539" --check-updates
academic-research-kernel verify-work --verify-pdf ./paper.pdf --title "Expected Paper Title" --doi "10.1038/nature14539"

# 2. Transactional retraction & literature watch (plus one-time v2.x JSON state migration)
academic-research-kernel retraction-watch --dois "10.1038/nature14539" --state-db ./watch.sqlite3 --live
academic-research-kernel retraction-watch --import-legacy-json ./old-watch.json --state-db ./watch.sqlite3
academic-research-kernel literature-watch --watchlist ./watchlist.json --state-db ./watch.sqlite3 --live --days 7

# 3. Multi-layer candidate corpus collection & Union-Find deduplication
academic-research-kernel collect-corpus --input ./candidate-layers.json
academic-research-kernel collect-corpus --query "retrieval augmented generation" --per-page 20
academic-research-kernel collect-corpus --related-of "10.1038/nature14539"

# 4. Five-source Open Access full-text resolution (arXiv -> Unpaywall -> OpenAlex -> S2 -> Europe PMC)
academic-research-kernel locate-oa "10.1038/nature14539" --email "you@example.edu" --fallback-all
```

## MCP Tools

- `academic_verify_source`
- `academic_retraction_watch`

## Reliability Guarantees

1. Dual-source fault isolation: if one upstream provider times out or returns malformed JSON during `retraction-watch`, confirmed signals from the healthy peer provider are preserved (`signals_complete=false`).
2. Order-independent Union-Find merging: `collect-corpus` bridges OpenAlex IDs and DOIs deterministically while refusing to merge distinct non-empty DOIs mapped to the same alias.

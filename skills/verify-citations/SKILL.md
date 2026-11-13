---
name: verify-citations
description: "Verify DOIs, check retractions, and locate OA copies."
version: 3.0.0
author: Junfu Shi (xngg1021), Hermes Agent
license: SLL-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, citations, retraction-watch, openalex, crossref]
    related_skills: [audit-paper, meta-analysis, check-submission]
---

# Verify Citations (`verify-citations`)

Citation authenticity, dual-source retraction monitoring, incremental literature tracking, and Open Access full-text resolution via `academic-research-kernel` (`3.0.0`). Consolidates legacy `academic-source-verification`, `retraction-watch`, and `literature-watch`.

## When to Use

- Verifying whether cited DOIs, titles, authors, and venues exist in Crossref and OpenAlex (catching hallucinated or mismatched references).
- Monitoring a DOI list or watchlist JSON for retraction and correction signals with transactional SQLite `STRICT` + `WAL` state (`retraction-watch`).
- Tracking newly published works by topic, author, or DOI watchlist (`literature-watch`).
- Resolving legal Open Access full-text URLs via Unpaywall (`--email` or `UNPAYWALL_EMAIL`) with OpenAlex fallback (`locate-oa`).

## Quick CLI Commands

```bash
# 1. Dual-source bibliographic verification & local PDF title/DOI check
academic-research-kernel verify-work "10.1038/nature14539"
academic-research-kernel verify-work --verify-pdf ./paper.pdf --title "Expected Paper Title"

# 2. Transactional retraction watch backed by SQLite STRICT + WAL
academic-research-kernel retraction-watch --dois "10.1038/nature14539" --state-db ./watch.sqlite3 --live

# 3. Migrate legacy v2.4.x JSON watch state into SQLite (one-time)
academic-research-kernel retraction-watch --import-legacy-json ./old-watch.json --state-db ./watch.sqlite3

# 4. Locate Open Access PDF / landing URL
academic-research-kernel locate-oa "10.1038/nature14539" --email "you@example.edu" --fallback-openalex

# 5. Incremental literature watch & BibTeX deduplication/export
academic-research-kernel literature-watch --watchlist ./watchlist.json --state-db ./watch.sqlite3 --live
academic-research-kernel bibliography --action deduplicate --input ./works.json
```

## MCP Tools

- `academic_verify_source`
- `academic_retraction_watch`

## Reliability Guarantees

1. Dual-source fault isolation: if one upstream provider times out or returns malformed JSON during `retraction-watch`, previously confirmed signals from the healthy provider are preserved (`signals_complete=false`) rather than overwritten.
2. Out-of-order sequence safety: late-arriving confirmed retraction observations update `confirmed_seq` and emit `unacked_delta` alerts even if a higher observation sequence recorded a transient `unknown` timeout.

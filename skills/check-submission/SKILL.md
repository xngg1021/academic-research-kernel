---
name: check-submission
description: "Check TeX submissions for anonymity, pages, and BibTeX."
version: 3.0.0
author: Junfu Shi (xngg1021), Hermes Agent
license: SLL-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, latex, double-blind, submission, bibtex, tables]
    related_skills: [audit-paper, verify-citations]
---

# Check Submission (`check-submission`)

Pre-submission LaTeX/PDF gatekeeper, double-blind anonymity scanner, Claim-Evidence Graph (`CEG`) grounding verifier, and receipt-backed `booktabs` table generator via `academic-research-kernel` (`3.0.0`). Replaces legacy `academic-writing`.

## When to Use

- Running a pre-submission checklist on a multi-file LaTeX manuscript (`\input{sub/sec}` or braceless `\input sec`) and compiled PDF before uploading to OpenReview or CMT (`lint-submission`).
- Scanning a submission directory or compiled PDF (including `/Info` dictionaries and raw XMP XML metadata streams inside an isolated worker subprocess) for author names, affiliations, non-anonymous GitHub URLs, acknowledgments, or camera-ready `[final]` flags (`sanitize-submission`).
- Verifying that quantitative claims in TeX (`% ark:claim=C1`, including escaped `12.5\%`) resolve to `eligible` claims in a verified Claim-Evidence Graph (`--ceg`) with matching numeric content.
- Rendering publication-ready LaTeX `booktabs` tables directly from verified JSON receipts or research extraction artifacts (`generate-table`).

## Quick CLI Commands

```bash
# 1. Inspect venue specs or export ready % ark:claim=<id> anchors from a CEG file
academic-research-kernel check-venue --list-venues
academic-research-kernel check-venue --export-ceg-anchors ./ceg.json

# 2. Render verified JSON experiment receipts into Decimal-rounded booktabs LaTeX tables
academic-research-kernel generate-table ./results-receipt.json --caption "Main Results" --label "tab:main"

# 3. Double-blind anonymity scan across TeX, BibTeX, and compiled PDF (/Info + XMP)
academic-research-kernel sanitize-submission ./submission-bundle --forbidden-token "Alice Smith"

# 4. Pre-submission gate (TeX tree + declared .bib + PDF main-body page limit + CEG binding + style)
academic-research-kernel lint-submission ./paper/main.tex \
  --venue iclr --phase submission --pdf ./paper/main.pdf \
  --ceg ./ceg.json --require-ceg-binding --check-academic-style
```

## MCP Tools

- `academic_pre_submission_lint`
- `academic_double_blind_sanitize`

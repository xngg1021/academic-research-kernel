---
name: check-submission
description: "Check TeX anonymity, pages, tables, and venue styles."
version: 3.0.0
author: Junfu Shi (SJF, xngg1021)
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, latex, double-blind, submission, bibtex, booktabs]
    related_skills: [audit-paper, verify-citations, cross-review]
---

# Check Submission (`check-submission`)

Pre-submission LaTeX/PDF gatekeeper, double-blind anonymity scanner, venue workspace scaffolder, Claim-Evidence Graph (`CEG`) grounding verifier, and receipt-backed `booktabs` table generator via `academic-research-kernel` (`3.0.0`). Consolidates `academic-writing`.

## When to Use

- Scaffolding a new venue-compliant manuscript directory (`--action scaffold`), listing built-in venue page/section specs (`--list-venues`), verifying local `.sty`/`.bst` files (`--action verify-styles`), or exporting ready `% ark:claim=<id>` anchors (`--export-ceg-anchors`).
- Rendering `booktabs` LaTeX tables from raw experiment JSON receipts (`--rows` / `--cols`) or directly from `audit-paper` extraction/results/comparison artifacts (`--from-research`).
- Scanning a submission bundle or compiled PDF (`/Info` dictionary and nested XMP `rdf:Seq` / `dc:creator` streams in an isolated subprocess) for double-blind leaks (`sanitize-submission`).
- Running the pre-submission gate (`lint-submission`) across nested `\input` trees, declared `.bib` files, compiled PDF body page limits, `% ark:claim=<id>` numeric grounding, and academic prose style.

## Quick CLI Commands

```bash
# 1. List venue contracts, scaffold a new manuscript workspace, verify styles, or export CEG anchors
academic-research-kernel check-venue --list-venues
academic-research-kernel check-venue --action scaffold --workspace-dir ./papers --slug my-iclr-paper --venue iclr --year 2027
academic-research-kernel check-venue --action verify-styles --manuscript-dir ./papers/my-iclr-paper
academic-research-kernel check-venue --export-ceg-anchors ./ceg.json

# 2. Render verified JSON receipts or paper-audit artifacts into Decimal-rounded booktabs tables
academic-research-kernel generate-table ./results-receipt.json --caption "Main Results" --label "tab:main"
academic-research-kernel generate-table ./nested.json --rows "experiments.main" --cols "Model,Acc,F1"
academic-research-kernel generate-table ./comparison.json --from-research comparison \
  --left-extraction ./left/extraction.json --right-extraction ./right/extraction.json --output ./comp.tex

# 3. Double-blind anonymity scan across TeX, BibTeX, and compiled PDF (/Info + nested XMP)
academic-research-kernel sanitize-submission ./submission-bundle --forbidden-token "Alice Smith"

# 4. Full pre-submission gate (TeX tree + declared .bib + PDF body page limit + CEG binding + style)
academic-research-kernel lint-submission ./paper/main.tex \
  --venue iclr --phase submission --pdf ./paper/main.pdf \
  --ceg ./ceg.json --require-ceg-binding --check-academic-style
```

## MCP Tools

- `academic_pre_submission_lint`
- `academic_double_blind_sanitize`

## Supporting References

- `references/submission-and-style-guide.md` — Cover letter, rebuttal / response-to-reviewers matrix, arXiv preprint checklist, and ISO 690 / APA 7th / MLA 9th / Chicago 18th / IEEE citation formatting rules.

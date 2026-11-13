---
name: audit-peer-review
description: "Audit OpenReview scores, reviews, and repo forensics."
version: 3.0.0
author: Junfu Shi (xngg1021), Hermes Agent
license: SLL-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, openreview, peer-review, iclr, neurips, icml]
    related_skills: [audit-paper, verify-citations]
---

# Audit Peer Review (`audit-peer-review`)

Peer-review score distribution analysis, machine-review anomaly forensics, single-paper forum inspection, and companion repository forensics via `academic-research-kernel` (`3.0.0`).

## When to Use

- Summarizing venue-wide score quantiles, reviewer word counts, unanimous identical-score rates, confidence-stratified review lengths, and zero-discussion rates across offline OpenReview mirrors (ICLR, ICML, NeurIPS, COLM).
- Auditing a specific OpenReview forum (`--forum-id` with `--mirror-json` or `--input-json`) without triggering live `openreview.net` Cloudflare `403` blocks.
- Inspecting a companion code repository (`repo-forensics`) to separate first-party code from vendored third-party trees and test directories.

## Quick CLI Commands

```bash
# 1. Venue-wide statistical & peer-review forensics summary on an offline mirror
academic-research-kernel openreview-audit --venue-summary ./iclr2027.json
academic-research-kernel openreview-audit --venue-summary ./nips2025.json --topic-regex "agent|memory"

# 2. Audit a specific forum inside an offline OpenReview mirror
academic-research-kernel openreview-audit --forum-id "Forum_ID_Here" --mirror-json ./iclr2027.json

# 3. Companion repository composition forensics (first-party vs vendored vs tests)
academic-research-kernel repo-forensics ./companion-repo
```

## MCP Tools

- `academic_openreview_audit`

## Supported Venue Schemas

- **ICLR (2024–2027+)**: `rating` (10-point or 2027 4-point scale), `confidence`, `soundness`, `presentation`, `contribution`, and 2027 `informativeness`, plus `wc_review` and `replies_avg`.
- **ICML (2025–2026+)**: `recommendation` (5-point scale), `confidence`, `wc_review`, and `replies_avg`.
- **NeurIPS (2024–2026+)**: `rating` (6-point scale), `confidence`, `clarity`, `quality`, `significance`, `originality`, `wc_strengths_and_weaknesses`, and `wc_limitations`.
- **COLM**: `rating` (10-point scale), `confidence`, `soundness`, `excitement`, `wc_review`, and `replies_avg`.

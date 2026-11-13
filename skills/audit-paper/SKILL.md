---
name: audit-paper
description: "Audit a paper's statistics, tables, claims, and code."
version: 3.0.0
author: Junfu Shi (xngg1021), Hermes Agent
license: SLL-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, paper-audit, statistics, reproducibility, provenance]
    related_skills: [verify-citations, audit-peer-review, check-submission]
---

# Audit Paper (`audit-paper`)

Deterministic single-paper audit workflow backed by `academic-research-kernel` (`3.0.0`). Consolidates legacy fragmented skills (`paper-research`, `quantitative-paper-audit`, `research-reproducibility`, `research-object-identity`) into one verifiable CLI and MCP surface.

## When to Use

- Reading a paper PDF, LaTeX source bundle, HTML/JATS document, or supplementary archive and checking whether reported numbers appear verbatim at their declared source locators.
- Recomputing $p$-values (`t`, `F`, `chi2`, Wald `z`), confidence intervals, `2x2` odds/risk ratios, `Cohen's d` / `Hedges' g`, percentage denominators, bounded-scale SD bounds, partition conservation, ablation constant-offset shifts, and uncompressed storage/bandwidth lower bounds.
- Adjudicating the 14-stage reproducibility checklist (`repro-checklist`) from a file or piped `stdin`.
- Persisting claims, evidence anchors, and object provenance inside a transactional SQLite `STRICT` + `WAL` state database.

## Quick CLI Commands

```bash
# 1. Prepare a PDF or multi-file LaTeX bundle, then validate & recompute extracted numbers
academic-research-kernel research prepare ./paper.pdf --project ./paper-audit
academic-research-kernel research finish --project ./paper-audit --candidate ./candidate.json
academic-research-kernel research replay --project ./paper-audit

# 2. Audit table partition conservation, ablation delta shifts, and physical bandwidth bounds
academic-research-kernel table-forensics --input ./table-spec.json

# 3. Adjudicate a 14-stage reproducibility checklist (file path or piped JSON)
academic-research-kernel repro-checklist ./repro-manifest.json
```

## MCP Tools

- `academic_recompute_statistics`, `academic_check_percentage`, `academic_table_forensics`
- `research_state_ingest`, `research_artifact_ingest`, `research_artifact_validate`, `research_receipt_verify`
- `research_object_resolve`, `research_lineage_trace`
- `claim_evidence_add`, `claim_evidence_validate`, `claim_evidence_trace`
- `decision_record`, `decision_transition`, `decision_ledger_validate`, `decision_trace`

## Workflow Rules

1. Run deterministic recomputation before writing prose conclusions; distinguish half-ULP decimal rounding boundaries from genuine reporting errors (`references/contract.md`).
2. Keep source assertions, recomputed receipts, and unresolved unknowns separate.
3. Inline lineage graphs without verified SHA-256 content hashes report `verification_status="unchecked"`; `"intact"` is reserved strictly for hash-verified provenance chains.

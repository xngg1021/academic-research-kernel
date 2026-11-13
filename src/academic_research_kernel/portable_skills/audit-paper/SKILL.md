---
name: audit-paper
description: "Audit paper statistics, tables, claims, and ledgers."
version: 3.0.0
author: Junfu Shi (SJF, xngg1021)
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, paper-audit, statistics, reproducibility, provenance, ceg]
    related_skills: [verify-citations, audit-peer-review, cross-review, check-submission]
---

# Audit Paper (`audit-paper`)

Deterministic single-paper and two-paper audit workflow backed by `academic-research-kernel` (`3.0.0`). Consolidates `paper-research`, `quantitative-paper-audit`, `research-reproducibility`, `research-object-identity`, `claim-evidence-graph`, and `decision-ledger` into one unified CLI and MCP surface.

## When to Use

- Reading a paper PDF, multi-file LaTeX bundle, HTML/JATS document, or supplementary archive and checking whether extracted numbers match their declared source locators (`research prepare` / `finish` / `replay`) or comparing two papers side by side (`research compare`).
- Recomputing $p$-values (`t`, `F`, `chi2`, Wald `z`), confidence intervals, `2x2` odds/risk ratios, `Cohen's d` / `Hedges' g`, percentage denominators, bounded-scale SD limits, table partition conservation, ablation constant-offset shifts, and physical storage/bandwidth bounds (`table-forensics`; see `references/formulas-and-mismatches.md`).
- Adjudicating the 14-stage reproducibility checklist (`repro-checklist`) from a JSON file or piped `stdin` (`references/reproducibility-and-ledgers.md`).
- Registering claims, evidence anchors, object provenance, research decisions, and negative results inside a transactional SQLite `STRICT` + `WAL` database (`ledger`).

## Quick CLI Commands

```bash
# 1. Single-paper prepare, semantic extraction verification, and deterministic replay
academic-research-kernel research prepare ./paper.pdf --project ./paper-audit
academic-research-kernel research finish --project ./paper-audit --candidate ./candidate.json
academic-research-kernel research replay --project ./paper-audit

# 2. Structured two-paper comparison & portable skill export
academic-research-kernel research compare ./left-audit ./right-audit --analysis ./comparison-input.json --output ./comparison.json
academic-research-kernel research skill --output ./exported-audit-skill

# 3. Table partition conservation, ablation delta shifts, and physical bandwidth bounds
academic-research-kernel table-forensics --input ./table-spec.json

# 4. Adjudicate 14-stage reproducibility checklist (file path or piped stdin)
academic-research-kernel repro-checklist ./repro-manifest.json

# 5. Claim-Evidence Graph (CEG) & Research Decision Ledger (SQLite STRICT + WAL)
academic-research-kernel ledger --db ./state.sqlite3 --action add-claim --claim-id c1 --text "Accuracy reaches 92.5% on 400 test cases." --artifact-id exp_receipt --locator "Table 1"
academic-research-kernel ledger --db ./state.sqlite3 --action export-ceg --output ./ceg.json
academic-research-kernel ledger --db ./state.sqlite3 --action validate-ceg
academic-research-kernel ledger --db ./state.sqlite3 --action record-decision --decision-id d0 --title "Explore heuristic pruning" --rationale "Initial hypothesis"
academic-research-kernel ledger --db ./state.sqlite3 --action record-decision --decision-id d1 --basis-decision-id d0 --title "Heuristic degraded F1" --rationale "Ablation dropped F1 by 3.2 points" --is-negative-result --artifact-id exp_receipt
academic-research-kernel ledger --db ./state.sqlite3 --action transition-decision --decision-id d0 --status pruned --reason contradicted
```

## MCP Tools

- Statistical & table forensics: `academic_recompute_statistics`, `academic_check_percentage`, `academic_table_forensics`
- Artifact & provenance kernel: `research_state_ingest`, `research_artifact_ingest`, `research_artifact_validate`, `research_receipt_verify`, `research_object_resolve`, `research_lineage_trace`
- Claim-Evidence Graph (`CEG`): `claim_evidence_add`, `claim_evidence_validate`, `claim_evidence_trace`
- Decision & negative-result ledger: `decision_record`, `decision_transition`, `decision_ledger_validate`, `decision_trace`

## Supporting References

- `references/contract.md` — Candidate JSON schema and half-ULP decimal rounding rules.
- `references/formulas-and-mismatches.md` — Statistical recomputation formulas and 8-type mismatch classification rules.
- `references/reproducibility-and-ledgers.md` — 14-stage reproducibility adjudication tiers, CEG anchor workflow, and decision-ledger invariants.

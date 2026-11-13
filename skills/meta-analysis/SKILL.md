---
name: meta-analysis
description: "Pool effect sizes, measure heterogeneity, test bias."
version: 3.0.0
author: Junfu Shi (xngg1021), Hermes Agent
license: SLL-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, meta-analysis, prisma, effect-size, heterogeneity]
    related_skills: [audit-paper, verify-citations]
---

# Meta-Analysis (`meta-analysis`)

Deterministic effect-size pooling, heterogeneity diagnostics, leave-one-out sensitivity, Egger small-study bias regression, trim-and-fill, and literature review matrix construction via `academic-research-kernel` (`3.0.0`). Consolidates legacy `systematic-review-meta-analysis` and `literature-analysis`.

## When to Use

- Pooling multi-study effect estimates (`yi`, `vi`) under fixed-effect and DerSimonian-Laird random-effects models with $Q$, $I^2$, and $	au^2$ heterogeneity statistics, leave-one-out sensitivity, Egger regression, and trim-and-fill (`meta-analyze`).
- Converting two-arm continuous outcomes (`Cohen's d`, `Hedges' g`) or binary `2x2` counts (`OR`, `RR`) via `academic_recompute_statistics`.
- Deduplicating multi-database search exports, converting BibTeX / RIS / CSL-JSON, building citation graphs, and rendering structured literature review matrices (`bibliography`).

## Quick CLI Commands

```bash
# 1. Fixed & DerSimonian-Laird random-effects pooling + Q / I^2 / tau^2 + LOO + Egger + trim-and-fill
academic-research-kernel meta-analyze --input ./studies.json

# 2. Deduplicate multi-source works & build a Markdown literature review matrix
academic-research-kernel bibliography --action deduplicate --input ./works.json
academic-research-kernel bibliography --action review-matrix --input ./works.json --query "retrieval"

# 3. Convert between BibTeX (with acronym brace protection), RIS, and CSL-JSON
academic-research-kernel bibliography --action convert --from bibtex --to csl --input ./refs.bib
```

## MCP Tools

- `academic_meta_analyze`
- `academic_recompute_statistics`

## Numerical Safeguards

1. Inverse-variance weights scale internally by `min(vi) / vi`, preventing IEEE-754 `1 / vi -> inf` and `inf / inf -> NaN` overflow on ultra-small variances down to `1e-320`.
2. Zero-residual-variance degenerate inputs in Egger regression fail explicitly with a descriptive `ValueError` rather than dividing by zero, and oscillating trim-and-fill iterations report `converged=False` cleanly.

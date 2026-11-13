---
name: meta-analysis
description: "Pool effect sizes, run subgroup WLS, and map literature."
version: 3.0.0
author: Junfu Shi (SJF, xngg1021)
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, meta-analysis, prisma, bibliography, literature-review]
    related_skills: [audit-paper, verify-citations, cross-review]
---

# Meta-Analysis & Literature Synthesis (`meta-analysis`)

Deterministic effect-size pooling, subgroup $Q_{\text{between}}$ decomposition, weighted least squares (`WLS`) meta-regression, publication-bias diagnostics, citation graph analysis, and literature synthesis workflows via `academic-research-kernel` (`3.0.0`). Consolidates `systematic-review-meta-analysis` and `literature-analysis`.

## When to Use

- Pooling multi-study effect estimates (`yi`, `vi`) under fixed-effect and DerSimonian-Laird random-effects models with $Q$, $I^2$, and $\tau^2$ heterogeneity statistics, leave-one-out sensitivity, Egger regression, trim-and-fill, subgroup analysis (`subgroup`), and univariate WLS meta-regression (`moderator`).
- Deduplicating multi-database exports, converting `BibTeX` / `RIS` / `CSL-JSON`, exporting acronym-protected `BibTeX`, building `OpenAlex` citation graphs (`in_degrees`), merging multi-layer corpora, and rendering Markdown literature review matrices (`bibliography`).
- Applying structured PRISMA screening ledgers, logical fallacy checklists, simulated peer-review rubrics, research-gap mapping, and bilingual close-reading protocols (`references/prisma-and-literature-guide.md`).

## Quick CLI Commands

```bash
# 1. Fixed & DL random-effects pooling + Q / I^2 / tau^2 + LOO + Egger + trim-and-fill
#    (Automatically runs subgroup Q_between & WLS meta-regression if studies include "subgroup" / "moderator")
academic-research-kernel meta-analyze --input ./studies.json

# 2. Deduplicate works, merge multi-layer candidates, and render a literature review matrix
academic-research-kernel bibliography --action deduplicate --input ./works.json
academic-research-kernel bibliography --action collect-corpus --input ./layers.json
academic-research-kernel bibliography --action review-matrix --input ./works.json --query "retrieval" --date "2026-11-14"

# 3. Export acronym-protected BibTeX, convert BibTeX/RIS/CSL, and build citation graphs
academic-research-kernel bibliography --action export-bibtex --doi "10.1038/nature14539"
academic-research-kernel bibliography --action convert --from bibtex --to csl --input ./refs.bib
academic-research-kernel bibliography --action citation-graph --input ./works.json
```

## MCP Tools

- `academic_meta_analyze`
- `academic_recompute_statistics`

## Supporting References

- `references/prisma-and-literature-guide.md` — Effect-size conversions (`d`, `g`, `log OR`, `RR`, `r`), PRISMA 2020 checklist, logical fallacy taxonomy, simulated peer-review template, sentence overlap, and research-gap mapping.

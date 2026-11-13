# Paper Audit Output Contract (`v3.0.0`)

Every deterministic paper audit run (`academic-research-kernel research run`) writes schema-validated outputs into `--workspace`:

1. `manifest.json` — Normalized intake sources, SHA-256 digests, parser metadata, and controlled byte budgets.
2. `audit-report.json` — Statistical recomputation findings (`recompute-pvalue`, `GRIM`, `GRIMMER`, `2x2`, percentage conservation), citation checks, and explicit coverage boundaries.
3. `report.md` — Human-readable audit report separating verified findings, inconclusive items, and unverified external dependencies.

## Evidence Discipline

- Never fabricate missing degrees of freedom, sample sizes, or standard deviations; record missing inputs as `inconclusive`.
- Inline lineage graphs without content hashes report `verification_status: "unchecked"`, reserving `"intact"` strictly for SQLite hash-verified provenance chains.

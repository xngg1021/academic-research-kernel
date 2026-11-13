# Paper Audit & Research Workflow Output Contract (`v3.0.0`)

Every deterministic paper audit workflow (`academic-research-kernel research ...`) reads and writes schema-validated artifacts inside `--project <dir>`:

1. `academic-research-kernel research prepare <pdf-url-or-doi> --project <dir>`
   - Writes `prepared.json` containing normalized intake sources, SHA-256 content digests, extracted text/tables, bibliographic cross-checks, and byte budgets.
2. `academic-research-kernel research finish --project <dir> --candidate <candidate.json>` (and `research replay --project <dir>`)
   - Validates `candidate.json` claims against `prepared.json` and writes `receipt.json` (deterministic `AcademicEvidenceReceipt` + recomputation checks) and `report.md` (human-readable audit report separating verified findings, inconclusive items, and external gaps).
3. `academic-research-kernel research compare <left> <right> --analysis <json> --output <dir>`
   - Writes `comparison.json` and `comparison.md` contrasting methods, assumptions, and verified metrics across two prepared works.

## Provenance & Lineage Discipline

- Never fabricate missing degrees of freedom, sample sizes, or standard deviations; record missing inputs as `inconclusive`.
- SQLite provenance (`research_lineage_trace` with `db_path`) recomputes `payload_sha256` across target and ancestor rows in `artifacts`, returning `verification_status: "intact"`, `"corrupted"`, or `"missing_input"` alongside `root_ancestors` and `chain_length`.
- Inline lineage graphs without stored content hashes return `verification_status: "unchecked"`.

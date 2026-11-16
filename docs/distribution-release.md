# Distribution, Packaging & Release Gate (`v3.0.0`)

## Package & Extra Layout

`academic-research-kernel` (`3.0.0`) ships as a single pure-Python wheel and reproducible source distribution (`sdist`) supporting Python `3.10`–`3.14`:

```bash
# Core CLI + 24-tool stdio MCP server + statistical & meta-analysis engines
uv tool install "academic-research-kernel==3.0.0"

# Recommended: include deterministic digital PDF parsing (pypdf==7.0.0, fonttools==4.65.0)
uv tool install "academic-research-kernel[research]==3.0.0"
academic-research-kernel doctor
```

| Dependency group | Packages & purpose |
| --- | --- |
| Base install | `jsonschema>=4.23,<5`, `numpy>=1.26,<3`, `scipy>=1.11,<2`, `statsmodels>=0.14,<0.16` (loaded lazily on statistical calls; SQLite state, CLI dispatch, and MCP handshake use Python's standard library). |
| `[research]` | `pypdf==7.0.0` and `fonttools==4.65.0` for isolated subprocess PDF text, `/Info`, and XMP stream extraction. |
| `[qa]` | `pytest>=8,<10`, `build>=1.2,<2`, `twine>=6,<7`, `pyyaml>=6,<7`, and `tomli>=2,<3; python_version < '3.11'` for test suites, strict wheel/sdist metadata checks, and skill frontmatter validation. |

> **Repository tests vs. unpacked `sdist` scope**: The source distribution (`sdist`) bundles `src/academic_research_kernel/`, `skills/`, `examples/`, `tests/`, and license/provenance manifests so package unit tests and `--package-acceptance` (isolated wheel + sdist-rebuilt wheel installs, CLI `doctor`, skill export, and 24-tool stdio MCP discovery plus live RPC smoke check) run cleanly outside the Git tree. Repository-only benchmark and workflow contract assertions that inspect `docs/benchmarks/*`, `tools/benchmarks/*`, or `.github/workflows/*` execute against a full Git checkout and skip cleanly when those non-packaged directories are absent.

---

## Deterministic Build & Release Gate (`academic_research_kernel.release_gate`)

All release verification lives inside `src/academic_research_kernel/release_gate.py` (invocable on a bare Python `3.11+` standard library via `tomllib`, or Python `3.10` with `tomli` installed):

```bash
# 1. Lock check & build sdist + wheel
uv lock --check
uv build --no-create-gitignore

# 2. Strict metadata check via frozen QA environment
uv run --frozen --extra qa --no-editable python -m twine check --strict dist/*

# 3. Out-of-tree isolated venv install + doctor + skill export + real stdio MCP JSON-RPC round-trip
PYTHONPATH=src python -m academic_research_kernel.release_gate --package-acceptance --dist dist
```

For tagged GitHub Releases (`vX.Y.Z` on `main`), `.github/workflows/publish-pypi.yml` executes four deterministic gates through `academic_research_kernel.release_gate`:
1. **`--validate-target`**: Confirms `vX.Y.Z` is an annotated Git tag whose commit is an ancestor of `origin/main`, matches `src/academic_research_kernel/_version.py`, and preserves every SHA-256 digest listed in `SLL-APPLICATION.json`.
2. **Release bundle & PyPI idempotency planning**: Verifies `release-manifest.json`, `SHA256SUMS`, `server.json`, wheel (`26` schemas + portable skill), and sdist (`uv.lock`, `requirements-qa.txt`, `CHANGELOG.md`, `SLL-APPLICATION.json`). Queries PyPI's JSON API so already-published same-hash files are skipped cleanly while byte conflicts abort immediately.
3. **`twine check --strict` + `--package-acceptance`**: Validates exact bidirectional source-file sets (`src/academic_research_kernel/**` + `skills/**`) and `RECORD` SHA-256 / `entry_points.txt` console scripts on both wheel and sdist, builds an independent wheel from the sdist, and exercises both isolated out-of-tree virtual environments (`venv-wheel` and `venv-sdist-wheel`) using the installed `academic-research-kernel` executable and stdio JSON-RPC (`tools/list` verifying `24` tools plus a live `tools/call` RPC smoke check) before Trusted Publishing (`OIDC`).
4. **`--distribution-smoke`**: Verifies the live PyPI package via `uvx --no-cache` in a scrubbed temporary directory.

---

## `v2.4.2 -> v3.0.0` Breaking Changes, Compatibility Adapters & Retired Interfaces

| Area | `v2.4.2` Legacy Surface | `v3.0.0` Behavior & Migration Contract |
| --- | --- | --- |
| Package & MCP server | `python scripts/mcp_server.py` (18 tools) | `academic-research-kernel mcp` (24 tools: all 18 legacy tool names preserved + 6 new tools). |
| Statistical recompute & table forensics | `target_power`, `sample_ratio`, `p_value_decimals`, `required-sample-size`; flat `partition_*` / `ablation_*` / `bandwidth_*` fields inside `academic_recompute_statistics` | `academic_recompute_statistics` preserves `target_power`, `sample_ratio`, `p_value_decimals`, `required-sample-size`, and emits both `required_sample_size` and legacy alias `required_n`. Table-forensics parameters (`partition`, `ablation_matrix`, `bandwidth`) are separated into the dedicated `academic_table_forensics` tool. |
| Table rendering | `receipt-to-latex` JSON wrapper | `receipt-to-latex` emits legacy JSON (`{status, source_sha256, row_count, col_count, latex}`); `generate-table` emits raw booktabs TeX (`--format {auto,json,tex}`). |
| Pre-submission lint | `hits` list on return dict | Returns both `findings` (canonical) and `hits` (legacy alias). |
| State persistence & legacy envelopes | Multi-file JSON snapshots (`--state watch.json`, `artifact-envelope-1.0`, `receipt_payload`, inline `graph`/`ledger` trace) | Primary store is transactional SQLite `STRICT + WAL` (`--state-db`, `user_version = 4`, auto-migrating `v3 -> v4`). Compatibility adapters remain active on `research_artifact_validate` (`envelope`), `research_artifact_ingest` (`envelope` + `dry_run`), `research_receipt_verify` (`receipt_ref` + `receipt_payload` / `content_payloads`), `claim_evidence_trace` (`graph`), and `decision_trace` (`ledger`). Import legacy JSON watch state once via `--import-legacy-json`. |
| Inline cross-review replies | Unbound plain-string `challenge_replies` | `academic_cross_review` (`deliberate_inline`) requires two-step SHA-bound reply envelopes: `{cid: {"text": "...", "bundle_sha256": "<64-hex>"}}` matching `challenge_plan[*].bundle_sha256`, where `text` is a strict line-anchored verdict document (optional `# Review` header plus one single-line verdict per `Proposal-N`); plain-string replies or any non-verdict/fenced/quoted/conflicting lines reject the reply fail-closed. |
| Compute probe & backend admission | Multi-file `scripts/scfabric/*` | Consolidated into `compute-probe --receipt [--measure-candidates]` and `academic_scfabric_hardware_probe` (`measure_candidates=true` runs paired numerical parity + material-gain admission; unmeasured external candidates are always marked `REFERENCE` / `unverified_external_candidate`). |

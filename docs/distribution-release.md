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
| Base install | `jsonschema>=4.23,<5`, `numpy>=1.26,<3`, `scipy>=1.11,<2`, `statsmodels>=0.14,<1` (loaded lazily on statistical calls; SQLite state, CLI dispatch, and MCP handshake use Python's standard library). |
| `[research]` | `pypdf==7.0.0` and `fonttools==4.65.0` for isolated subprocess PDF text, `/Info`, and XMP stream extraction. |
| `[qa]` | `pytest>=8,<10`, `build>=1.2,<2`, `twine>=6,<7`, and `pyyaml>=6,<7` for test suites, strict wheel/sdist metadata checks, and skill frontmatter validation. |

---

## Deterministic Build & Release Gate (`academic_research_kernel.release_gate`)

All release verification lives inside `src/academic_research_kernel/release_gate.py` (invocable on a bare Python `3.10+` standard library before third-party dependencies are installed):

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
3. **`twine check --strict` + `--package-acceptance`**: Validates built distributions and exercises an out-of-tree wheel installation over real stdio JSON-RPC (`24` tools) before Trusted Publishing (`OIDC`).
4. **`--distribution-smoke`**: Verifies the live PyPI package via `uvx --no-cache` in a scrubbed temporary directory.

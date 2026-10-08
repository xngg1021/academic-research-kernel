# Distribution and paper research release 2.1.0

The backward-compatible paper workflow adds `research prepare`, `research finish`,
`research compare` and `research skill`; `doctor` and all 12 public MCP tool names
remain available. The repository has 14 skills and 26 schemas. The wheel includes
only `paper-research` from the skill tree, plus its contract reference; the export
command copies the three canonical schemas into the exported reference folder.
Other skill implementation files retain the existing explicit runtime mappings.

Install `academic-research-kernel[research]==2.1.0` for digital PDF input. The
optional parser and font decoder are fixed at `pypdf==6.19.0` and
`fonttools==4.65.0`, verified against their official PyPI releases on 2026-10-08.
Both support Python 3.10; fonttools 4.66.1 requires Python 3.11, so it is not used
for this Python 3.10–3.14 release. Including the font decoder prevents pypdf's
optional CFF decoding path from varying between QA and clean `[research]`
installations. Actual fonttools versions are part of parser identity and cache
invalidation. HTML/XML and bounded DOCX/XLSX parsing use Python's standard library.
The base MCP dependencies are unchanged; `qa` includes `research` so source and
archive tests exercise the parser without global dependencies. Version metadata:
[fonttools 4.65.0](https://pypi.org/pypi/fonttools/4.65.0/json),
[fonttools 4.66.1](https://pypi.org/pypi/fonttools/4.66.1/json).

The current Work/Agent is the semantic producer. The program prepares locatable
material, validates its typed extraction, computes eligible statistics using the
existing implementation, ingests research state, and renders reports. The
[portable workflow](../skills/paper-research/SKILL.md) requires the same task to
continue through report generation and independent source review. Standalone CLI
preparation is accurately marked as awaiting semantic reading.

Build and inspect candidate bytes with the existing pinned build tools. After
normal merge and verified main CI, freeze commit/tree, create annotated `v2.1.0`,
build the final wheel/sdist and run fresh installation acceptance. Publish the
same frozen files to GitHub and PyPI, then publish the exact MCP Registry version
`io.github.xngg1021/academic-research-kernel` pointing to PyPI 2.1.0. Partial uploads
stage only missing same-hash files; conflicting existing bytes stop that write.
Record publication receipts outside the tagged source.

The pinned PyPI action generates `.github/.tmp/.generated-actions` in its original
checkout. The post-upload verification creates a separate detached worktree at
the already validated release commit and passes it as `--repo`. It still requires
an entirely clean checkout, annotated tag, main ancestry, exact source identity,
internal metadata and distribution hashes. No generated-file exception is added
to the source gate. Regression coverage retains dirty-source rejection and tests
this separation using the action's actual generated-path shape.

The historical 2.0.0 recipe below is retained as its original release record.

---

# Distribution and runtime release 2.0.0

PR #13 packages the existing deterministic kernel. It preserves the 13 skills,
12 MCP tool names, schema v1 contracts and `academic-skills` plugin identity.
The base is main commit `476df4eca502264f17bc245927c749e15e6a8b99`.

## Candidate discipline

Development stays Draft without `full-ci`. After local source and installed
artifact gates pass, one `full-ci` label event runs the candidate matrix.
The subsequent Ready transition triggers review without repeating CI. At most
one consolidated repair candidate, two full CI waves and two review rounds are
allowed. Tags and release artifacts are finalized only after normal merge and
post-merge verification. Publication status must be established independently
for GitHub, PyPI and the MCP Registry.

## Separate version axes

The package, console, MCP server and repository release share product version
2.0.0. Individual skill versions, schema protocols such as
`artifact-envelope-1.0`, and Source Lineage License 1.0 are separate identities.
Product release manifests do not change the historical SLL application record.

## Deferred product decision

Native Research Workflow Surface / Kernel Adoption Layer remains a post-PR13
decision: direct literature search, source verification, statistical
recomputation, retraction checks, evidence ingestion, claim tracing and decision
recording. Current deterministic state machinery does not replace the existing
skill workflows. Method/Supplement Miner versus Constraint Compiler, translation
backlog, credential-bound scholarly checks, independent primitive-framework
validation and experimental SCFabric expansion remain separate work.

## Dependency and resource audit

| Class | Packages / scope |
| --- | --- |
| Base MCP | jsonschema validates input, envelope and receipt contracts; NumPy/SciPy and statsmodels implement statistical recomputation. statsmodels transitively needs pandas and related numerical libraries. All four direct dependencies are mandatory. |
| Optional `full` | pandas, sympy, mpmath, matplotlib, scikit-learn, networkx, lifelines, arch and pingouin for extended skill examples. Torch/CuPy remain separately installed, platform-specific optional backends. |
| Optional `qa` | `full`, PyYAML, pytest, build and twine. No QA dependency is needed to launch MCP. |
| External services | OpenAlex, Unpaywall, Scite, Web of Science, Scopus and Dimensions configuration is optional, never probed over the network by doctor. |

The wheel contains the CLI, the existing MCP implementation, identity/provenance,
CEG, Ledger, ingestion, shared receipt contracts, statistics and hardware probe,
23 schemas, and the adapter matrix. Hatch's explicit file mappings package the
same implementation used by checkout tests; no generated second implementation
is maintained. Installed imports are namespaced, resources use `importlib.resources`,
and checkout entrypoints retain their legacy imports. No checkout is required.

Python 3.10 is the minimum: the existing code uses PEP 604 unions and
`Path.is_relative_to`; dependencies have compatible 3.10 releases. Support is
bounded below 3.15 until that version is tested. The existing 3.10–3.14 matrix
remains the source correctness gate. Package-specific fresh wheel/sdist tests
run on Linux x86_64, hosted macOS ARM64 and Windows x86_64.

## Reproduction and QA scope

`uv.lock` records the complete resolution with distribution hashes and
Python-specific markers. Reproduce that environment from the tagged checkout
using `uv sync --frozen --no-dev --no-editable`. The portable Hermes plugin uses
this same lock. Ordinary PyPI/uvx installs respect supported dependency bounds;
they do not promise the identical transitive resolution across dates. Reproduce
published bytes using the immutable release artifacts and their SHA-256 values.

Build with uv 0.12.17 and the pinned Hatchling 1.29.0 backend. Set
`SOURCE_DATE_EPOCH` to the tagged commit's timestamp, then run `uv build` (sdist,
then wheel from sdist). [release manifest tool](../scripts/release_manifest.py) inspects every archive file
and writes the source commit/tree, artifact hashes and build metadata. The
final manifest is a release asset, avoiding a self-referential source commit.
It is separate from `SLL-APPLICATION.json`, which is unchanged.

QA reads `git ls-files` in checkouts. Add new source files to the index before
local QA. Source archives use a pruned walk of explicit source roots. Both
paths exclude environment/build/cache trees and symlinks; malformed tracked
source still fails. Arbitrary untracked files are outside the QA contract.
The poison regression contains non-UTF8 `.venv` files and unrelated untracked
Markdown. Runtime wheel and sdist contents receive an independent secret/path
and archive-inventory check.

## Hermes evidence and limitations

The pinned Hermes loader at `245e48008fa814b3251f50755eb656bd9fb86cb1` and
current upstream inspected at `5dd70d7cb6560c3ff8aff294ec44ec4f8d1558e5` support
bare executable tokens, separate arguments, `env`, and `${PLUGIN_ROOT}` /
`${PLUGIN_DATA}` expansion. No invented install hook or environment manifest
field is used. [Hermes runtime smoke](../scripts/hermes_runtime_smoke.py) invokes the real loader and its
translated command, verifies the isolated 3.12 interpreter, enumerates 12 tools
and dispatches a percentage calculation. Existing pinned tap discovery stays
unchanged; main CI runs the pinned lifecycle and current canary. This does not
claim coverage of every conversational Hermes workflow.

Sources checked 2026-09-21: [Hermes portable plugin documentation](https://hermes-agent.nousresearch.com/docs/developer-guide/plugins),
[uv tools](https://docs.astral.sh/uv/guides/tools/),
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/),
[MCP publishing quickstart](https://modelcontextprotocol.io/registry/quickstart),
and [MCP PyPI ownership requirements](https://modelcontextprotocol.io/registry/package-types).
The registry schema fixture is the unmodified official
[2025-12-11 schema](https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json).
The README's `mcp-name` marker matches `server.json`; PyPI is a supported package type.

## Publication checkpoints

No 2.0.0 tag, GitHub Release or PyPI project existed at the initial live check.
A PyPI 404 indicates no public project, not a guarantee that the name can be
registered by this account. Publication status is recorded in the release asset,
not inferred from a successful local-wheel test.

After normal merge and automatic main checks, create `v2.0.0` once, build from
that clean tag, and generate `release-manifest.json` with `--release`. Attach
both distributions, the manifest, and `server.json` to the GitHub Release.
Do not move an existing tag or replace existing distribution bytes.

The external PyPI account action, if no publisher is configured, is to register
a pending Trusted Publisher for project `academic-research-kernel`, GitHub owner
`xngg1021`, repository `academic-research-kernel`, workflow `publish-pypi.yml`,
environment `pypi`. Then dispatch that workflow from main. It verifies tagged
source and GitHub Release hashes, repeats fresh installs, publishes using OIDC
and tests the actual public package with a clean uvx cache. No long-lived token
is stored. Do not retry an already-published version with different bytes.

After public PyPI verification, authenticate with `mcp-publisher login github`
as the namespace owner and run `mcp-publisher publish server.json` according to
the installed publisher's help. Record registry confirmation before changing its
publication status. PyPI authorization and MCP namespace authentication are
separate external checkpoints; source merge does not depend on claiming either.

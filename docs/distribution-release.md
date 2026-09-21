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

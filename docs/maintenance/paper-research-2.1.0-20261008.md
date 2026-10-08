# Paper research 2.1.0 acceptance

The new `research prepare/finish/compare/replay/skill` CLI and portable
`paper-research` skill form one Agent-driven paper workflow. The current Agent
reads original material and writes typed candidates; the installed program
validates sources, calls existing MCP statistics, saves kernel state and renders
Chinese Markdown/HTML reports. Standalone preparation explicitly requires a
semantic producer. No new model account or background model is implied.

The public MCP inventory remains twelve tools. The new CLI workflow is not an
invented MCP tool. The package adds three registered schemas (26 total), one
structured ingestion adapter, and one portable skill (14 total). Exact inventory,
authoring, long-tail, source identity and archive gates remain enabled.

## Real material and reading

Four papers were frozen from five attempted candidates. Full sources and all
research work products are outside the source tree and distribution archives.

| Role | Original paper | Material and scope |
|---|---|---|
| Development | [Cyclists, PLOS ONE 2016](https://doi.org/10.1371/journal.pone.0159907) | Official HTML/JATS/PDF and both independent XLSX supplements. Work read the sources; existing recomputation calculates Cohen d from group mean/SD/n. |
| Development | [Placebo/nocebo Stroop, PLOS ONE 2013](https://doi.org/10.1371/journal.pone.0075701) | Official HTML/JATS/PDF and four independent DOCX supplements. Two explicit one-tailed tests, two age diagnostics and two descriptive effect sizes. |
| Development | [Deep Residual Learning, CVPR 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/He_Deep_Residual_Learning_CVPR_2016_paper.html) | Digital PDF, separate author arXiv v1 appendix, static author README/deploy files pinned at a7026cb6d478e131b765b898c312e25f9f6dc031. No third-party training or setup execution. |
| Holdout | [Densely Connected Convolutional Networks, CVPR 2017](https://openaccess.thecvf.com/content_cvpr_2017/html/Huang_Densely_Connected_Convolutional_CVPR_2017_paper.html) | Fresh-context Work producer first installs candidate wheel and exports its skill. Methods/answers were not supplied as extractor input. Original failed attempt is retained; later results are feedback regression. |

Each bundle records exact version, acquisition time, original URL, role and
SHA-256. Abstract landing pages remain parse failures, distinct from full text.
PDF addresses are physical pages; printed pages are not inferred from indices.
Targeted visual reading checked ResNet's interleaved columns and table footnotes.
No claim is made that rotated plot labels were fully parsed.

An independent role froze raw-source reference fields before seeing each
production output. Review is an explicit sample of applicable fields, not a
claim that every sentence was independently verified. Decimal/mpmath reference
calculations do not import production recomputation. A real Stroop positive-group
test reports t=-1.98, df=14 and one-tailed p=.035; recomputation from the reported
inputs gives .033854..., rounding to .034. Original inputs and the separate
df=13 sensitivity calculation remain distinct; the workflow does not silently
replace the author's df.

## General defects found and repaired

- Full HTML reached through a DOI is validated and promoted from metadata;
  relative downloads resolve against the final publisher URL.
- XML error responses and abstract-only JATS cannot pass as full text.
- Percentage checks cannot compare a displayed reported field different from
  the actual percentage input; direct comparison matches numeric fields both ways.
- The holdout exposed sentence punctuation (`256.`) being consumed as decimal
  precision. Numeric tokenization now separates sentence stops, preserves trailing
  zeros, and supports valid PDF thousands groups such as `1, 000`.
- Multiple short source quotes retain actual continuous text when PDF columns
  interleave. Comparison links use the same stable location anchors and PDF page
  fragments as individual reports.
- A clean holdout installation exposed pypdf's optional CFF font decoder changing
  extracted text (`[17]` versus `[ 17]`) when fontTools was absent. The `research`
  extra and QA requirements now pin `fonttools==4.65.0` alongside pypdf. This
  version supports Python 3.10, while 4.66.1 requires Python 3.11. Parser identity
  records the actual fonttools version so dependency changes invalidate derived
  material. This is a general environment repair; no paper-specific text rewrite
  is used. The affected holdout is now a feedback regression case.

No DOI/title/page-specific extraction branch or embedded paper answer was added.

## Reproducible acceptance boundaries

Synthetic mutation copies exercise small p/precision, wrong count/denominator,
SD/SE/units, body/supplement conflicts, same-name different-group fields, missing
attachments, corrupt files and invalid locators. Tests also exercise interruption,
idempotent ingestion, material/parser/extractor changes, and network-disabled
snapshot rebuilding. Real originals are never mutated. Source and installed
archive tests are separate from actual publisher acquisition.

Windows installation tests cover noneditable wheel/sdist imports, exported skill
and schema byte equality, Chinese paths with spaces, all existing MCP tools, kernel
reload and deterministic replay. Hosted CI supplies the existing cross-platform
matrix; local Windows evidence is not claimed as local macOS/Linux execution.

The pinned PyPI action's generated temporary checkout files are isolated by
post-upload verification in a second clean immutable worktree. Clean-source,
commit/tree, annotated-tag, internal metadata and artifact hash checks are retained.
Release receipts belong to release assets/PR and external handoff, not a rewrite
of the tagged source. Publication success requires live exact-version readback.

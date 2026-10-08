# Paper research candidate contract

The installed `research skill --output DIRECTORY` command exports this skill and the canonical `paper-extraction.schema.json`, `paper-comparison.schema.json` and `research-documents.schema.json` beside this reference. Read the actual JSON schemas for required fields, enums and type constraints. The CLI validates these contracts and original source locators before accepting a candidate.

An extraction (`paper-extraction-1.0`, `schema_version: "1.0"`) carries:

- `project_fingerprint`: the current prepared project identity, copied without editing.
- `paper`: original `title`, `identifier` and `version`.
- `producer`: `kind` (`work`, `agent` or `human`), `name` and `model` (known string or `null`). Record the producer actually used.
- `search_scope`: document IDs of every successfully read main text and supplement. Parse failures remain in the preparation manifest rather than being claimed as read.
- `fields`: at least ten actually extracted applicable fields. Each has a unique `id`, `name`, `type`, `status`, `literal`, normalized `value`, `unit`, `context`, `sources` and `reason` as the schema requires. Context keys are `group`, `timepoint`, `dataset`, `analysis_set` and `condition`; unavailable context is `null`. Types are `number`, `integer`, `p_value`, `text` and `boolean`.
- `sources`: each extracted source binds `document_id`, exact prepared `locator` and `quote`. Whitespace-normalized quotes must occur continuously in the named original segment. Multiple sources can establish a single field.
- `summary`: `objective`, `design`, `main_results` and `attention`; each has `text` and supporting `field_ids`.
- `checks`: `id`, `kind` (`t_p`, `effect_size` or `percentage`), `inputs` mapping function argument names to field IDs, `reported` field ID or `null`, `tail` (`two`, `one` or `null`) and `note` according to the schema. One-sided t checks additionally require an explicit `alternative` (`less` or `greater`) justified by the hypothesis and contrast definition. The program derives values from the original fields, calls the existing MCP two-sided probability, records the one-sided conversion and uses the existing reported-precision comparator. A missing direction remains uncomputed.

Use `not_found` for a field sought but not found in all read material; `explicitly_unreported` requires actual documentary support for that statement. `parse_failed` identifies an unreadable region; `not_applicable` identifies a method that does not apply. Do not convert uncertainty into an extracted value. Keep an original p-value literal, its trailing zeros and comparison operator; let the program enforce reported precision.

For `percentage`, `inputs` uses `count`, `percent` and `sample_size` field IDs;
`reported` must equal the field ID in `inputs.percent`. For `t_p`, use `t_stat`
and `df`; for `effect_size`, use `mean1`, `sd1`, `n1`, `mean2`, `sd2` and `n2`.
An absent input may refer to an explicitly unavailable field so the result
records its precise uncomputed reason. An unreported effect size uses
`reported: null`; it must not be described as matching an author's reported d.

A comparison (`paper-comparison-1.0`) carries `schema_version`, the producer, both current project fingerprints and `rows`. Each row gives `dimension`, `left_field_ids`, `right_field_ids`, `assessment` (`direct`, `conditional`, `not_comparable`, `not_applicable`) and `reason`. `conclusion` contains `text` and field IDs from both projects. Establish compatibility using data/population, time point, metric definition, model/configuration and evaluation conditions. Missing information prevents a claim of direct comparability.

The prepared documents schema describes the parser output, not a semantic answer. Use its identity, source hash and original segment locator exactly. Candidate files contain reading judgments; their ingestion does not turn those judgments into mathematical proof.

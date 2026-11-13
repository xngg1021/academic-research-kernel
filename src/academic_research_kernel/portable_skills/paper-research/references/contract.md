# Paper research candidate contract

The installed `research skill --output DIRECTORY` command exports this skill and the canonical `paper-extraction.schema.json`, `paper-comparison.schema.json` and `research-documents.schema.json` beside this reference. Read the actual JSON schemas for required fields, enums and type constraints. The CLI validates these contracts and original source locators before accepting a candidate.

An extraction (`paper-extraction-1.0`, `schema_version: "1.0"`) carries:

- `project_fingerprint`: the current prepared project identity, copied without editing.
- `paper`: original `title`, `identifier` and `version`.
- `producer`: `kind` (`work`, `agent` or `human`), `name` and `model` (known string or `null`). Record the producer actually used.
- `search_scope`: document IDs of every successfully read main text and supplement. Parse failures remain in the preparation manifest rather than being claimed as read.
- `fields`: at least ten actually extracted applicable fields. Each has a unique `id`, `name`, `type`, `status`, `literal`, normalized `value`, `unit`, `context`, `sources` and `reason` as the schema requires. Context keys are `group`, `timepoint`, `dataset`, `analysis_set` and `condition`; unavailable context is `null`. Types are `number`, `integer`, `p_value`, `text` and `boolean`.
- `sources`: each extracted source binds `document_id`, exact prepared `locator` (including PDF `page=N`, HTML/XML segment IDs, LaTeX `tex:abstract=1` / `tex:table=N` / `tex:block=N`, and BibTeX `bib:entry=<citekey>`) and `quote`. Whitespace-normalized quotes must occur continuously in the named original segment. Multiple sources can establish a single field.
- `summary`: `objective`, `design`, `main_results` and `attention`; each has `text` and supporting `field_ids`.
- `checks`: `id`, `kind` (`t_p`, `f_p`, `chi2_p`, `z_beta_se`, `ci_consistency`, `or_rr_2x2`, `effect_size`, `hedges_g`, `percentage`, `sd_possible`, `sample_size_df` or `power_ttest`), `inputs` mapping function argument names to field IDs, `reported` field ID or `null`, `tail` (`two`, `one` or `null`), optional `alternative` (`less` or `greater`), optional `metric` (`cohens_d`, `hedges_g`, `odds_ratio`, `risk_ratio`, `z` or `p`), optional `log_scale` (`true` or `false`), optional `df_kind` (`ttest_2sample`, `ttest_1sample`, `ttest_paired`, `ttest_2sample_welch` or `regression`), optional `claim_id` and `note` according to the schema. One-sided `t_p` and `z_beta_se` checks require an explicit `alternative` (`less` or `greater`) justified by the hypothesis and contrast definition. Right-tailed `f_p` and `chi2_p` checks use `tail: one` or `null`; `power_ttest` uses `tail: two` or `null`.

Use `not_found` for a field sought but not found in all read material; `explicitly_unreported` requires actual documentary support for that statement. `parse_failed` identifies an unreadable region; `not_applicable` identifies a method that does not apply. Do not convert uncertainty into an extracted value. Keep an original p-value literal, its trailing zeros and comparison operator; let the program enforce reported precision.

Required `inputs` keys by check `kind`:
- `t_p`: `t_stat`, `df` (`reported`: p-value field ID or `null`).
- `f_p`: `f_stat`, `df1`, `df2` (`reported`: p-value field ID or `null`).
- `chi2_p`: `chi2_stat`, `df` (`reported`: p-value field ID or `null`).
- `z_beta_se`: `beta`, `se` (`reported`: z-statistic or p-value field ID, controlled by `metric: z | p`).
- `ci_consistency`: `estimate`, `lower`, `upper`, optional `level` (set `log_scale: true` for OR/RR/HR).
- `or_rr_2x2`: `a`, `b`, `c`, `d`, optional `level` (`metric: odds_ratio | risk_ratio` selects which reported ratio to compare).
- `effect_size` / `hedges_g`: `mean1`, `sd1`, `n1`, `mean2`, `sd2`, `n2` (`metric: cohens_d | hedges_g`).
- `percentage`: `count`, `percent`, `sample_size` (`reported` must equal `inputs.percent`).
- `sd_possible`: `sd`, `minimum`, `maximum`, optional `n` (checks bounded-scale SD feasibility).
- `sample_size_df`: `df`, `reported_n`, optional `n_params` (and optional `df_kind`).
- `power_ttest`: `d`, `n1`, `n2`, optional `alpha` (`reported`: power field ID or `null`).
An absent input may refer to an explicitly unavailable field so the result records its precise uncomputed reason. An unreported effect size uses `reported: null`; it must not be described as matching an author's reported value.

A comparison (`paper-comparison-1.0`) carries `schema_version`, the producer, both current project fingerprints and `rows`. Each row gives `dimension`, `left_field_ids`, `right_field_ids`, `assessment` (`direct`, `conditional`, `not_comparable`, `not_applicable`) and `reason`. `conclusion` contains `text` and field IDs from both projects. Establish compatibility using data/population, time point, metric definition, model/configuration and evaluation conditions. Missing information prevents a claim of direct comparability.

The prepared documents schema describes the parser output, not a semantic answer. Use its identity, source hash and original segment locator exactly. Candidate files contain reading judgments; their ingestion does not turn those judgments into mathematical proof.

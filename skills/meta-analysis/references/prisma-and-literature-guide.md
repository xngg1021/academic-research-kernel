# Effect-Size Conversions, PRISMA 2020 Workflow, and Literature Analysis Guide

## 1. Exact `meta_core` Function Signatures (`academic_research_kernel.meta_core`)

- **Standardized mean difference**:
  - `cohens_d(n1, n2, m1, m2, sd1, sd2)` — pooled-SD Cohen's $d = (m_1 - m_2) / s_{\text{pooled}}$ with $df = n_1 + n_2 - 2$.
  - `var_d(d, n1, n2)` — large-sample sampling variance $\frac{n_1 + n_2}{n_1 n_2} + \frac{d^2}{2(n_1 + n_2 - 2)}$.
  - `hedges_j(df)` — small-sample factor $J(df) = 1 - \frac{3}{4\,df - 1}$.
  - `hedges_g(d, n1, n2)` and `var_g(g, n1, n2)` — small-sample bias-corrected $g = J(n_1 + n_2 - 2)\,d$ and exact $J^2\,\text{var}_d(g/J, n_1, n_2)$. Normalize small-sample continuous outcomes ($n < 20$ per arm) to Hedges' $g$ before pooling.
- **Binary outcomes**:
  - `log_or(n_events1, n1, n_events0, n0)` — takes `(events_treatment, total_treatment, events_control, total_control)` and returns `(lor, var)`. All four cells ($a = \text{events}_1$, $b = n_1 - \text{events}_1$, $c = \text{events}_0$, $d = n_0 - \text{events}_0$) must be strictly positive; if any cell is zero, apply a $+0.5$ Haldane-Anscombe continuity correction ($a+0.5, n_1+1, c+0.5, n_0+1$) *before* calling and record the continuity adjustment in the screening log.
  - `or_to_rr(or_, p0)` and `rr_to_or(rr, p0)` where $p_0 \in (0, 1)$ is the baseline control event rate. Never pool raw `OR` and `RR` directly unless $p_0$ yields $<5\%$ divergence.
- **Cross-family bridges (sensitivity / exploratory use only)**:
  - `d_to_log_or(d)` ($\frac{\pi}{\sqrt{3}}\,d$), `log_or_to_d(lor)`, `var_log_or_from_d(v_d)`, `d_to_r(d, n1=None, n2=None)`, `r_to_d(r)`.
- **Subgroup & moderator tests**:
  - `subgroup_analysis(yi, vi, groups)`: partitions fixed-effect $Q_{\text{total}} = Q_{\text{within}} + Q_{\text{between}}$ ($df = G - 1$) and reports DerSimonian-Laird estimates within each subgroup. Test subgroup differences strictly via $p_{\text{between}}$, never by comparing subgroup-specific $p$-values against $0.05$.
  - `meta_regression(yi, vi, moderators, model="random")`: scale-invariant WLS slope $\beta_1$ with DL weights $w_i^* = 1/(v_i + \tau^2)$ and residual heterogeneity $Q_E$ ($df = k - 2$).

## 2. PRISMA 2020, Study-vs-Report Discipline, and Risk-of-Bias Rubrics

1. **`Study` vs `Report` separation (PRISMA 2020 Item 16a/17)**:
   - A single underlying *study* (cohort / RCT registration / benchmark run) may appear across multiple *reports* (arXiv preprint, conference paper, journal extension, erratum). Link companion reports to one canonical `study_id` before calling `meta-pool` so participant counts $N$ are never double-counted.
2. **Search & exclusion accounting (PRISMA-S)**:
   - Record exact query strings, date bounds, and retrieved counts per source (`OpenAlex`, `Crossref`, `PubMed`, `arXiv`).
   - Run `bibliography --action deduplicate` and maintain a full-text exclusion log (`report_id`, `stage`, `exclusion_reason`).
3. **Structured Risk-of-Bias (`RoB`) domain checklists**:
   - **RCTs (`RoB 2`, 5 domains)**: (D1) randomization process; (D2) deviations from intended interventions; (D3) missing outcome data; (D4) measurement of the outcome; (D5) selection of the reported result (`Low` / `Some concerns` / `High`).
   - **Non-randomized studies (`ROBINS-I`, 7 domains)**: confounding, selection of participants, classification of interventions, deviations, missing data, measurement of outcomes, selection of reported result (`Low` / `Moderate` / `Serious` / `Critical` / `No information`).
   - **Diagnostic accuracy (`QUADAS-2`, 4 domains)**: patient selection, index test, reference standard, flow and timing.

## 3. Close Reading, Fallacy Audit, Author Trajectory, and Venue Matching

1. **Bilingual / technical close-reading template**:
   - Extract in 6 anchored blocks with exact section/equation/table locators: (1) Problem formulation & formal assumptions; (2) Core mechanism / estimator; (3) Identification or theoretical guarantee (and what breaks it); (4) Empirical setup & baselines; (5) Verified numbers vs headline claims; (6) Open failure modes. Keep original technical terms in parentheses when summarizing across languages.
2. **Logical fallacy checklist (record locator, fallacy class, broken inference link, factual rewrite)**:
   - *Structural*: circular reasoning, strawman baseline, false dichotomy, appeal to authority/novelty.
   - *Evidentiary*: single-benchmark over-generalization, survivorship bias, cherry-picked ablations, train-test leakage.
   - *Statistical*: correlation framed as causation, unadjusted multiple comparisons, $p$-value without effect size/CI, regression to the mean.
3. **Simulated peer review (label explicitly as simulated pre-submission review)**:
   - Score-free 6-part diagnostic: contribution clarity, baseline fairness, statistical/error-bar validity, claim-evidence alignment, explicit limitations, reproducibility artifacts.
4. **Author research-trajectory profile & journal/venue matching**:
   - Build author profiles strictly from verified OpenAlex/Crossref works (`verify-work` / `collect-corpus`): group verified publications by period, recurring methods, co-author clusters, and retraction/correction status without speculating on unverified affiliations or demographics.
   - Match manuscripts to target venues by comparing empirical scope, page/format limits (`check-venue --action list`), open-access mandates, review model (double-blind vs single-blind), and verified reference overlap in `citation-graph`.

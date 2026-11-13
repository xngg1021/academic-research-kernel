# Academic Prose Editing, Submission Letters, Rebuttal, and Citation Style Guide

## 1. Manuscript Section Structure & Prose Editing Workflow

1. **Section-level diagnostic (IMRaD & CS/ML systems papers)**:
   - *Abstract (150-250 words)*: context (1 sentence) -> specific bottleneck (1 sentence) -> core method/mechanism (1-2 sentences) -> verified quantitative result with baseline & dataset (1-2 sentences) -> scope boundary (optional).
   - *Introduction*: state the concrete gap in prior literature with verified citations (`verify-work`), list 2-4 falsifiable contributions mapped to exact sections/theorems/tables, and avoid unquantified superlatives ("revolutionary", "vastly superior").
   - *Method / Results / Limitations*: keep notation one-to-one (never reuse the same symbol for distinct quantities), pair every point estimate with dispersion (`SD`, `SE`, or `95% CI`) and sample size $N$, and place an explicit *Limitations* subsection before conclusions.
2. **Line-by-line academic prose tightening**:
   - Lead each paragraph with a falsifiable topic sentence; convert ambiguous passive voice ("experiments were conducted") into explicit methodology ("we evaluate on 5 benchmarks across 3 seeds") while preserving exact numeric precision and never inventing citations or experimental details.
   - Calibrate claim hedging to evidence strength: reserve *proves / guarantees* for formal theorems, *demonstrates / reduces by X%* for verified experiments, and *suggests / is consistent with* for observational or exploratory findings.

## 2. Cover Letter & Rebuttal Discipline

1. **Journal cover letter (half page max)**:
   - State target journal, manuscript title, and article category.
   - Summarize core problem, method, and concrete distinction from closest prior work in three factual sentences without repeating the abstract verbatim.
   - Include only verified author approvals, conflict-of-interest disclosures, and data-availability facts; mark unconfirmed items `[TODO]`.
2. **Conference / journal rebuttal (`Response to Reviewers`)**:
   - Restate each reviewer concern accurately in neutral language before answering.
   - Cite exact manuscript diff locations (section, table, line numbers, or new experiment receipt) for completed revisions; state concrete scope/resource boundaries when an extra experiment is infeasible.
   - Maintain a 3-column tracking table: `Reviewer Comment | Factual Response | Manuscript Change Locator`.
3. **arXiv preprint preparation**:
   - Ensure `.bbl` is compiled and self-contained alongside `.tex` sources, verify license choice with co-authors, and run `lint-submission --venue arxiv_preprint --no-blind` before packaging.

## 3. Citation Style Quick Reference (Mark Missing Fields `[TODO]`)

- **ISO 690:2021**: `LASTNAME, Firstname, Year. Article title. Journal Title. Vol. x, no. y, pp. xx-xx. DOI: 10.xxxx/xxxx.`
- **APA 7th**: `Author, A. A., & Author, B. B. (Year). Title of article. Journal Name, Vol(Issue), pages. https://doi.org/xxxx` (up to 20 authors; for 21+, list first 19, `...`, final author).
- **IEEE**: `[1] J. Smith and M. Jones, "Title of article," Journal Name, vol. 12, no. 3, pp. 45-67, Mar. 2020, doi: 10.xxxx/xxxx.`
- **MLA 9th**: `Last, First. "Title of Article." Journal Name, vol. X, no. Y, Year, pp. xx-xx. DOI.`
- **Chicago 18th (Author-Date)**: `Smith, John, and Mary Jones. 2020. "Title of Article." Journal Name 12 (3): 45-67. https://doi.org/xxxx.`

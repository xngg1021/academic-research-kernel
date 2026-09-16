# Academic Knowledge Work Pain Atlas, Version 0

Status: working inventory. Compiled 2026-09-16. Sources are community discussions, published surveys and empirical studies; each quantitative claim is marked with its verification state. This document records friction points, not their relative frequency.

## 1. Scope and method

The atlas enumerates friction in academic knowledge work across the research life cycle, from discovery to maintenance and learning. Items were collected by cross-model synthesis of public sources. The atlas is enumerative: it does not rank pain points by frequency, and it does not claim that a listed friction is unsolved by all existing tools. Relative coverage of architectural primitives is the subject of the factor decomposition matrix in the research plan (docs/research-plan-v0.en.md).

Provenance note (added 2026-09-17 after the agenda audit): the synthesizing models and the cross-confirmation method behind each individual item were not recorded at compilation time. From this revision on, every newly added item must name its source model and confirmation method. For the existing items, the quantitative claims continue to be governed by the source verification record in section 2.

## 2. Source verification record

| Claim | State | Source |
| --- | --- | --- |
| Approximately 150,000 incorrect citation links pointed to Springer Nature works in the Crossref database; matching strategy updated on 29 January to prevent that error class | verified | Crossref community forum, "Improving our reference matching strategy to reduce incorrect citation links", post 15417 |
| In a 201-review adverse-events reproducibility study, 85.1% of reviews (171 of 201) had at least one meta-analysis with a data extraction error; 66.8% of meta-analyses (554 of 829) contained at least one error; 17.0% of trials (1,762 of 10,386) could not be reproduced from extraction | verified against the abstract and record | Xu et al., BMJ 2022;377:e069155 |
| A community survey of a German NFDI neuroscience initiative reports that 70% of respondents need more than one day to prepare reusable data and 26% more than one week; uncertainty about data ownership, repository choice and metadata/provenance recording is widespread | title and venue verified; percentages not re-read in full text | Community survey, eNeuro 2023, PMC9933933 |
| Meta-analysis of the interleaving effect: moderate overall effect (Hedges g = 0.42) across 59 studies, 238 effect sizes, 158 samples; strongest for paintings (g = 0.67) and visual materials; small for mathematics (g = 0.34); ambiguous or nonsignificant for expository texts | verified | Brunmair and Richter, Psychol Bull 2019;145(11):1029-1052, PMID 31556629 |
| A health-professions systematic review reports significant benefits of distributed/retrieval practice in 43 of 63 experiments | unverified: the original source could not be located; the circulating citation attaches a Reddit thread | attribution pending |
| NIH 2026 changes to biosketch/Common Forms and DMS plan formats made some old forms submission-blocking | unverified: policy pages were not readable at compile time | NIH grants site, biosketch directory |

## 3. Pain inventory

Items are grouped by life-cycle region. Each item is one friction point; wording is compressed.

### Discovery

- Relevant material is scattered across Scholar, PubMed, arXiv, conferences, RSS, email and colleague messages.
- Alert streams overlap; only a minority of items matter.
- Search results show what was found, never what was missed.
- A paper is treated as new even when it was read three years ago.
- Synonym substitution changes result sets wholesale.
- Cross-disciplinary terminology breaks recall.
- Foundational, incremental, replication and critique work are mixed into one relevance ranking.
- Citation count is conflated with usefulness for the current question.
- Conference, preprint and journal versions enter the reading queue as separate items.

### Reading queue

- Saving outpaces reading.
- The reason a paper was saved is not recorded, so its purpose is lost months later.
- Important, interesting and maybe-useful items share one folder.
- Abstract-only versus full-read versus figure-check versus re-derived computation are not distinguished.
- Priority does not re-rank with the active project.
- An old paper that becomes relevant again does not resurface.

### Bibliographic identity

- DOI, arXiv ID, PMID, OpenAlex ID and publisher URL are several names for one object.
- Preprints and versions of record are not reliably merged.
- Conference and extended journal versions are hard to pair.
- Correction, erratum and retraction notices are hard to trace to the original.
- Supplementary material is detached from the main text.
- Book chapters, books, theses and proceedings are mis-matched by metadata matchers.
- Author name variants, renames and Chinese name inversion split one person.
- Publisher PDF, author manuscript and preprint are several binaries of one work.
- A merged item in the reference manager leaves stale embedded citations in the Word document.

### Full-text acquisition

- Open-access copies exist in several places; which one is best is unclear.
- A publisher 403 does not distinguish paywall, bot wall and transient failure.
- Institutional proxy URLs break across devices.
- Supplementary archives, code and data sit on unrelated hosts.
- Source pages rot; archive snapshots have no lineage to the current version.

### PDF and document parsing

- Two-column reading order is reconstructed incorrectly.
- OCR destroys formulas, subscripts, superscripts and Greek letters.
- Tables look fine visually and fall apart on copy.
- Some data exist only inside figures, without raw numbers.
- Footnotes and endnotes are dropped by parsers.
- A claim's method details span main text, methods, appendix and a GitHub repository.

### Notes

- Note-taking becomes a second job.
- Notes are taken and the paper is still re-read later.
- Excerpts lose page, section and context.
- Paraphrase, after time, cannot be told apart from the author's original words.
- One claim copied into several project notes diverges.
- Tag taxonomies grow until their owner stops using them.
- Topic tags cannot express supports, contradicts, method or example relations.
- Notes freeze the understanding of the year they were written.
- Outdated facts and changed interpretations are not distinguished.

### Citation and evidence

- A remembered claim cannot be located in a known paper.
- The supporting passage of a citation cannot be found.
- Citation-of-citation replaces reading the original source.
- A citation supports half a sentence, not the assertion it is attached to.
- Secondary citations drop the qualifiers of the original.
- Corrections and retractions do not propagate to old drafts.
- A number copied through reviews loses its source.
- Numbers in figures disagree with numbers in text.

### Concepts and terminology

- The same term means different things in different fields.
- Definitions drift over decades.
- A new paper renames an old concept.
- Abbreviations collide.
- Formula symbols coincide while definitions differ.
- A default assumption of one field does not hold in another.

### Research gaps

- Not finding something is mistaken for nobody having done it.
- English-only search produces fake novelty.
- Theses, proceedings and preprints are skipped.
- Old terminology hides historical work from retrieval.
- A little-known paper may have already filled the claimed gap.
- Absence of research and inconsistency of results are conflated.

### Method extraction

- Methods sections are too brief.
- Key parameters hide in supplements.
- Reagent versions, software versions and random seeds are missing.
- Preprocessing is described incompletely.
- Paper defaults and repository defaults differ.
- Methods cite other methods, requiring recursive lookup.
- Following-X descriptions conceal actual modifications.
- Protocol changes during the experiment are not versioned in the publication.
- Exclusion criteria are scattered.

### Experiment records

- Work happens at the bench; records are written in the evening.
- Failed experiments are the least recorded.
- One protocol exists as paper, Word and Notion copies.
- Raw-data file names cannot be traced to experiments.
- Sample IDs and notebook IDs are disconnected.
- A figure cannot be traced to the analysis run that produced it.
- The rationale of a past decision is absent.
- Negative results and abandoned attempts disappear and are repeated later.
- Experimental conditions live only in one researcher's memory.

### Data management

- Raw, cleaned and analysis-ready states are confused.
- Spreadsheet software silently retypes CSV columns.
- Units are inconsistent.
- Missing values mix 0, NA, blank and 999.
- Column names change between batches.
- The codebook is separated from the dataset.
- Exclusion decisions leave no ledger.
- Cleaning is irreversible.
- Provenance is lost on copy and paste.
- File names accumulate: final.csv, final2.csv, really_final.csv.

### Quantitative analysis

- Reported p values and statistics do not match.
- Confidence intervals disagree with estimates.
- Percentage denominators change without note.
- N differs between abstract, tables and flowchart.
- SD and SE are interchanged.
- One-tailed and two-tailed are unspecified.
- Multiple-testing correction is unclear.
- Transformed and raw scales are mixed.
- Effect-size definitions are ambiguous.
- Graph-only values require digitization.
- Statistical package defaults change across versions.

### Systematic review

- The query cannot be reproduced exactly.
- Database export formats are mutually incompatible.
- Deduplication kills genuinely distinct papers and misses version duplicates.
- Title and abstract screening is mechanical.
- Exclusion reasons are backfilled, weakening the ledger.
- Missing full texts bias selection.
- Multiple reports of one study are counted as multiple studies.
- One cohort across several papers is double counted.
- Arms, units and time points are extracted incorrectly.
- Data are read off graphs by hand.
- Effect directions are inverted.
- Reviewer disagreement in extraction is hard to trace.
- Meta-analysis inputs cannot be traced back to the paper's tables.

### Qualitative research

- Transcripts and audio timestamps are disconnected.
- Interview to open code to axial code to theme lineage is weak.
- The codebook changes during analysis.
- Merged codes lose the reason old segments were reclassified.
- Inter-coder disagreement is not kept in structured form.
- Negative and disconfirming cases drown in the main narrative.
- Participant attributes are disconnected from quotes.
- Anonymization destroys analytic context.

### Code reproduction

- A repository exists without an exact commit.
- Requirements are unpinned.
- CUDA, Python and package matrices are brittle.
- Dataset download links die.
- The dataset version is unknown.
- Checkpoints do not match the paper.
- Preprocessing is hidden.
- Random seeds are unpublished.
- Evaluation scripts differ from descriptions.
- Numerical behavior depends on hardware.
- Notebook cells do not record actual execution order.
- Shell commands work only on the author's machine.
- Absolute paths are hard-coded.
- External APIs and databases change after publication.
- Published code contains inference but not training.

### Computational artifacts

- Notebooks run once and cannot rerun.
- Manual dataframe edits leave code unaware.
- Figures do not record generation parameters.
- Post-hoc Illustrator edits break the figure-data link.
- Manuscript tables are copied by hand and go stale.
- Report numbers come from an old model version.
- Rounding errors accumulate across copies.

### Collaboration

- The latest version is unknown.
- PI annotates in Word, the student edits in Overleaf, and the two diverge.
- Key decisions in Slack and email never enter project records.
- Departing students leave data nobody can find.
- A collaborator changes a column without a reason.
- Permissions leave results accessible to one person.
- Newcomers do not know which routes were tried and failed.
- Handoffs contain files but no decision history.

### Writing

- Claims are written first and citations hunted afterwards.
- Papers update after citations are added; claims do not sync.
- Similar claims in an introduction draw on duplicated literature.
- Methods drift from the actual code.
- Results drift from tables and figures.
- Abstract numbers do not track body revisions.
- Limitations are written late and omit known caveats.
- Terminology is inconsistent across sections.
- A missing analysis is discovered late in the manuscript.

### Submission

- Journal requirements differ per venue.
- Transfer means redoing citations, word limits, sections and figures.
- The reporting guideline is chosen wrongly.
- CONSORT, STROBE and PRISMA items are completed just before submission.
- Author contributions, conflicts and data availability are filled at the end.
- Blinded manuscripts leak author identity.
- Supplementary naming and cross-references are wrong.
- Figure DPI, size and fonts fail the target format.
- Reference metadata errors accumulate in bulk.

### Peer review and rebuttal

- Reviewer comments and manuscript revisions have no one-to-one mapping.
- Multiple reviewers raise the same issue.
- Reviewer A and B demand conflicting changes.
- Line locators in the response letter go stale after revision.
- A claimed fix misses a second occurrence of the same text.
- A reviewer-suggested citation may itself be irrelevant.
- Second rounds cannot confirm whether old issues actually closed.

### Reviewing others' work

- Checking whether citations support claims is slow.
- Suspicious table values require hand calculation.
- Overlap with an author's earlier work is hard to batch-check.
- Data and code availability links are checked one by one.
- Methods omissions have no automatic checklist.
- Self-citation patterns across 350 references are inspected by eye.

### Grants

- Funding opportunity and agency instructions change.
- Template versions expire.
- Page, font, header, footer and URL rules are fragmented.
- Biosketches and current-and-pending are re-entered each time.
- Collaborators reuse outdated biosketches.
- Publications are re-selected per proposal.
- The data management plan does not match the actual workflow.
- One institutional datum is copied into several attachments.
- Format errors surface only at the submission portal.
- Resubmission cannot map reviewer criticism to changed proposal text.

### Thesis

- University templates conflict with Word and LaTeX defaults.
- Section breaks and page numbering consume mechanical hours.
- Published chapters and dissertation versions drift apart.
- Figure and table lists have omissions.
- Format checks are highly local per institution.

### Long-term maintenance

- Code and data stop being maintained after publication.
- DOIs stay alive while external links rot.
- Dependencies disappear.
- Corrections do not notify local citers.
- Systematic reviews go stale within two years.
- New dataset versions change conclusions while old analyses remain unaware.

### Learning material intake

- Lecture, notes and flashcards mean entering the same content three times.
- PDF, video, handouts and exercises are isolated.
- One concept's treatments across materials are not merged.
- Cards are detached from the context that produced them.
- Image-based knowledge is slow to turn into occlusion cards.

### Learning state

- Recognition is mistaken for recall.
- Recognition is mistaken for generation and application.
- Flashcard performance does not transfer to real problems.
- The final answer is known but the intermediate reasoning is not.
- Prerequisite holes are invisible.
- Wrong answers record the answer, not the error mechanism.
- Confusable concepts are reviewed separately.
- The review backlog grows without bound.
- All content receives the same spaced-repetition policy.

### Learning feedback

- A proof attempt cannot locate the failing step.
- Reading the solution immediately produces an illusion of mastery.
- Full solutions destroy productive struggle.
- No one judges proof rigor.
- The same error recurs without a misconception identity.
- There is no graduated hint that reveals only the next step.

### Transfer

- Textbook examples are solved, variants are not.
- Flashcard recall does not become language production.
- Isolated facts are trained without contextual retrieval.
- No progression from near transfer to far transfer.
- Method selection for a new problem is never trained.

### Metacognition

- Learners judge their own mastery poorly.
- Familiarity from easy repetition masquerades as learning.
- Time is spent reviewing what is already known.
- The true cause of failure, knowledge gap versus retrieval failure versus strategy choice, is unknown.

## 4. Method notes

The inventory inherits the verification state of its sources as recorded in section 2. Items without a quantitative source are compressed formulations of recurring community reports; they are treated as hypotheses for the factor decomposition matrix, not as measured facts. The next research step assigns each item to architectural primitives and measures which primitives cover the largest share of the atlas.

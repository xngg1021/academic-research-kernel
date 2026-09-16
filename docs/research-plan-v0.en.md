# Research Plan, Version 0: Primitive-Based Architecture

Status: proposal, compiled 2026-09-16. This plan follows the pain atlas (docs/pain-atlas-v0.en.md) and the 1.3 Execution & Evidence Hardening round merged on main. It records direction, not implementation status.

## 1. Motivation

Academic software has optimized objects for decades: readers, reference managers, statistical packages, notebooks. The frictions that persist are about state changes between objects: whether two records are the same work, where a number came from, what changed between protocol versions, whether a result was ever recomputed, which notes have expired. The pain atlas enumerates these frictions; this plan proposes the architectural layer that absorbs them.

The repository already contains embryonic forms of this layer. CanonicalWork (skills/literature-analysis/scripts/interop.py) is a normalization core; the watch skills implement state snapshots and diff reporting; AcademicEvidenceReceipt and ReproductionReceipt are two views of one evidence structure. The next rounds upgrade these forms instead of replacing them.

## 2. Fourteen primitives

Each primitive is defined by first principles. A primitive is a capability, not a product.

| # | Primitive | Definition | Example frictions absorbed |
| --- | --- | --- | --- |
| 1 | Canonical Identity Resolver | Decide whether several representations name the same object | DOI/arXiv versions, PDF duplicates, author variants, dataset versions, code releases |
| 2 | Provenance / Lineage | Record which inputs produced a result through which process | citations, data cleaning, figures, statistics, notes, code, experiments |
| 3 | State Ledger | Store state transitions of an object, not only its current snapshot | protocols, paper revisions, datasets, environments, learning mastery |
| 4 | Diff Engine | Compare two states and report what changed | corrections, review revisions, protocol drift, data versions, knowledge decay |
| 5 | Evidence Receipt | Attach source, time, coverage, failures and uncertainty to every conclusion | literature checks, quantitative audits, reproduction, review, grants |
| 6 | Normalization Layer | Convert many formats into one canonical object | BibTeX/RIS/CSL-JSON, CSV, units, statistics, metadata, learning materials |
| 7 | Constraint Compiler | Turn rules in natural language into executable checks | journal guidelines, PRISMA, NIH forms, thesis templates, lab SOPs |
| 8 | Coverage Map | Record what was checked, what was not, what is unknown | literature gaps, systematic reviews, reproduction, knowledge maps |
| 9 | Retrieval / Resurfacing | Bring old information back in the right context at the right time | reading notes, failed experiments, old analyses, flashcards |
| 10 | Cross-artifact Linker | Connect paper, claim, table, code, dataset, note and experiment | the full research chain |
| 11 | Deterministic Verifier | Compute or rule-check everything that can be decided without judgment | numbers, metadata, formats, hashes, schemas, statistics |
| 12 | Uncertainty Queue | Route what automation cannot decide into an explicit human queue | fuzzy dedup, citation support, qualitative coding, identity conflicts |
| 13 | Event Watcher | Diff an object's future states and report only real changes | retractions, new papers, dataset releases, guideline updates, dependency breaks |
| 14 | Adaptive Practice Engine | Choose the next learning action from failure type instead of uniform review | spaced repetition, proofs, computation, language, concept discrimination |

## 3. Research Object model

Skills operate on research objects as different views of one structure.

```
Research Object
  ├── Identity
  ├── State
  ├── Lineage
  ├── Evidence
  ├── Constraints
  ├── Coverage
  └── Events
```

Examples: a Paper carries identity (DOI, arXiv, PMID, OpenAlex), versions (preprint to accepted to version of record to correction), evidence (metadata, full text, computed), relations (cites, contradicts, replicates), artifacts (supplement, code, dataset) and events (retraction, correction, new citation). A Dataset carries identity, version, schema, units, cleaning lineage, exclusions and derived artifacts. The same skeleton covers a learning Concept: canonical meaning, prerequisites, confusable concepts, examples, evidence, learner state and error history.

## 4. Four planes

The repository's future capability space is organized into four planes sharing the primitives.

- A. Evidence plane: identity, provenance, citation verification, contradiction.
- B. Process plane: protocol, workflow, state, diff, reproduction, decision history.
- C. Production plane: computation, writing, review, grants, systematic review, submission.
- D. Learning plane: prerequisites, retrieval, error taxonomy, feedback, transfer, forgetting.

Decision recorded here: the learning plane is a separate project. It shares primitives with research production but has zero overlap with the existing skill set; folding it into this repository would dilute the tap's identity. A future hermes-learning-skills repository or a Family HF learning zone is the natural home.

## 5. Candidate directions

Six directions are candidates for the next rounds, ranked by breadth of pain coverage and fit with existing assets.

1. Claim-Evidence Graph: spans reading, writing, review, retraction and systematic review; consumes AcademicEvidenceReceipt directly.
2. Research Object Identity and Lineage: the root of nearly all version, duplicate and provenance problems; upgrades CanonicalWork and the receipt schemas.
3. Method and Supplement Miner: high-frequency, high-pain, weak existing tools; deterministic extraction of methods lineage and supplementary cross-references.
4. Constraint Compiler: one mechanism for journal, grant, thesis and reporting guidelines; fetch rule, compile constraints, audit artifact, cite the exact instruction.
5. Decision and Negative Result Ledger: long-tail records with outsized long-term value; smallest implementation among the candidates.
6. Learning Error Taxonomy and Adaptive Practice: deferred to the separate learning project.

## 6. Phase 1: factor decomposition matrix

Before any new skill is built, the candidate selection is grounded in measurement. Phase 1 is a deterministic task: map every pain-atlas item to the primitives it exercises, then compute coverage leverage per primitive and per direction.

- Input: pain atlas items (both language editions are kept in sync).
- Mapping: each item may map to one or more primitives; mappings are recorded with a one-line rationale.
- Output: a machine-readable matrix (docs/factor-matrix.json or equivalent), a coverage table, and a ranked direction recommendation.
- Acceptance: matrix committed; coverage table rendered in the research plan; the ranked recommendation is evidence for, not a substitute for, the human choice of the next round.

The matrix measures which primitives absorb the largest share of enumerated friction. It replaces intuition about which skill to build next with a recorded, revisable mapping.

### 6.1 Phase 1 result (2026-09-17)

The matrix maps all 235 pain-atlas items to the fourteen primitives, one to three primitives per item with a one-line rationale, programmatically verified as lossless against the atlas. Coverage leverage per candidate direction:

| Direction | Items covered | Share |
| --- | --- | --- |
| Research Object Identity and Lineage | 146 / 235 | 62.1% |
| Method and Supplement Miner | 138 / 235 | 58.7% |
| Claim-Evidence Graph | 136 / 235 | 57.9% |
| Decision and Negative Result Ledger | 83 / 235 | 35.3% |
| Learning Error Taxonomy and Adaptive Practice | 77 / 235 | 32.8% |
| Constraint Compiler | 57 / 235 | 24.3% |

Primitive-level coverage is led by State Ledger (36), Deterministic Verifier (36), Canonical Identity Resolver (34), Normalization Layer (32), Cross-artifact Linker (32) and Provenance / Lineage (30). The top three directions are close (62.1, 58.7, 57.9); there is a steep drop to the fourth (35.3). The recorded recommendation is to start the next round with Research Object Identity and Lineage; the final choice belongs to the maintainer, and the matrix remains revisable as the atlas evolves.

## 7. Design discipline

The repository continues the discipline established in the 1.3 round.

- Deterministic core first: anything computable or rule-checkable is implemented as plain functions with tests, never as model judgment.
- Explicit source evidence: every conclusion carries its source, query time and coverage.
- Bounded model judgment: model use is limited to tasks that genuinely require language understanding, and its output is recorded as a candidate, not a verdict.
- Uncertainty queue: undecidable items enter an explicit human queue; automation never silently resolves them.
- Receipts everywhere: downstream skills consume machine-readable receipts instead of re-paraphrasing prior conclusions.
- No subjective scoring: support judgments are categorical (supported, contradicted, unverifiable, out of scope); no numeric quality scores are synthesized.

This structure is the alternative to handing a PDF to a model and asking for analysis. The repository's quality difference comes from the deterministic core and the receipts, not from larger models.

## 8. Acceptance criteria for subsequent rounds

- One direction per pull request; no mega-merges.
- New code is deterministic-first; model-touching code is isolated and labeled.
- Tests cover the new code and its regression surface; full suite must pass locally and in CI.
- SLL credential files remain untouched; any schema or receipt change keeps the historical records intact.
- Documentation is updated in both language editions before merge; new quantitative claims are source-verified first.

## 9. Relation to other projects

The primitives deliberately overlap with the evidence and provenance thinking in THM and Family HF, but this repository keeps its own boundary: small deterministic skills over research objects, no runtime, no memory architecture, no world model. Nothing from those projects is imported or required here.

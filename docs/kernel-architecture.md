# Research-State Kernel Architecture & Ingestion Bridge

## Overview

The **Academic Research Kernel** provides an offline-first, deterministic, cryptographically verifiable research-state runtime for autonomous AI agents and scholars.

Rather than treating tools as disconnected utility scripts, the kernel unifies 13 specialized scholarly capabilities around three core state models and a centralized ingestion bridge:

```text
 13 Scholarly Skills / External Harvesters
                    │
                    ▼
     Research Artifact Envelope v1
                    │
        Deterministic Adapters
        (Tier 1 / Tier 2 / Tier 3)
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
ResearchObject     CEG     Decision Ledger
 (Identity &    (Empirical   (Append-only
  Lineage)       Graph)      Decisions &
                             Negative Results)
      │             │             │
      └─────────────┼─────────────┘
                    ▼
       Artifact Ingestion Receipt
                    │
                    ▼
       Public Kernel MCP Surface
       (12 stdio JSON-RPC Tools)
```

---

## The Three Core State Layers

1. **Research Object Identity & Lineage (`skills/research-object-identity`)**:
   - Discrete, rule-based equivalence judgments (EXACT, STRONG_MATCH, CANDIDATE, CONFLICT, UNRESOLVED) with zero opaque similarity scores;
   - Cryptographic `LineageReceipt` anchors tracking entity derivation and activity history.
2. **Claim-Evidence Graph (`skills/claim-evidence-graph`)**:
   - Directed tripartite graph connecting Claims, Evidence Anchors, and Support/Refutation Edges;
   - Physical payload SHA-256 verification via `ReceiptRef`.
3. **Decision & Negative Result Ledger (`skills/decision-ledger`)**:
   - Append-only event sourcing (`DecisionStateEvent`) driving active, pruned, and reopened route transitions;
   - Content-addressed outcome corrections and explicit failure recording without in-place updates.

---

## Research Artifact Ingestion Bridge v1

The Ingestion Bridge (`scripts/ingestion/`) is the universal translation layer that ingests structured outputs from tools into the kernel without side effects.

### Ingestion Adapters (3 Tiers)

- **Tier 1: Native Structured Receipts (Lossless)**
  - `academic-source-verification`: Ingests `AcademicEvidenceReceipt`, registers works, populates CEG claims and evidences with physical payload signatures.
  - `research-object-identity`: Pass-through ingestion for canonical research objects and lineage receipts.
  - `claim-evidence-graph`: Validates and merges CEG sub-graphs.
  - `decision-ledger`: Validates and replays Decision Ledger snapshots.
- **Tier 2: Structured Analytical Artifacts**
  - `quantitative-paper-audit`: Recomputes statistics; verified/discrepant calculations enter as CEG evidence anchors.
  - `research-reproducibility`: Ingests reproduction attempts; inconclusive results emit uncertainty findings.
  - `cross-review-five`: Ingests multi-agent review findings; dissenting opinions are strictly preserved as uncertainties (never squashed by majority vote).
  - `systematic-review-meta-analysis`: Ingests screening matrices and pooled effect sizes.
  - `literature-analysis`: Ingests canonical work matrices.
  - `literature-watch`: Ingests monitoring deltas without mutating decision states.
  - `retraction-watch`: Signals retraction alerts and marks affected evidence as requiring revalidation (never deletes history).
  - `math-computation`: Ingests symbolic/numerical evaluations.
- **Tier 3: Opaque Artifacts (Prose Stays Prose)**
  - `academic-writing`: Manuscripts, submission packages, and drafts are stored with cryptographic hashes. The kernel **strictly forbids** extracting speculative claims or making automated decisions from unannotated prose.

---

## Universal MCP Interface (12 Tools)

The stdio MCP server ([scripts/mcp_server.py](../scripts/mcp_server.py)) exposes the deterministic kernel directly to Claude Code, Cursor, Codex, Gemini CLI, and Hermes:

1. `research_artifact_validate`: Validates envelope structure and payload hash.
2. `research_artifact_ingest`: Ingests envelope into kernel state and emits an `ArtifactIngestionReceipt`.
3. `research_receipt_verify`: Verifies physical receipt payloads against `ReceiptRef`.
4. `research_object_resolve`: Resolves candidate records to canonical objects.
5. `research_lineage_trace`: Traces provenance ancestry.
6. `claim_evidence_validate`: Validates CEG integrity and cycles.
7. `claim_evidence_trace`: Traces evidence and receipts for a claim.
8. `decision_ledger_validate`: Executes four-gate verification on a decision ledger.
9. `decision_trace`: Traces causal ancestry and corrections for a decision.
10. `academic_recompute_statistics`: Recomputes statistical claims (t-tests, effect sizes).
11. `academic_check_percentage`: Checks count/percentage compatibility.
12. `academic_scfabric_hardware_probe`: Probes execution accelerators.

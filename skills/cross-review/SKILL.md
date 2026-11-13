---
name: cross-review
description: "Run multi-model blind review, challenge, and synthesis."
version: 3.0.0
author: Junfu Shi (SJF, xngg1021)
license: LicenseRef-Source-Lineage-1.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [research, cross-review, multi-model, deliberation, red-team]
    related_skills: [audit-paper, audit-peer-review, check-submission]
---

# Cross-Review Deliberation (`cross-review`)

Harness-neutral multi-model sparse deliberation and adversarial red-teaming engine via `academic-research-kernel` (`3.0.0`). Replaces legacy `cross-review-five` with an explicit, vendor-neutral participant roster (`ReviewPanelSpec`) and both CLI and inline MCP execution.

## When to Use

- Running blind multi-model or multi-subagent reviews over a paper, codebase, or technical specification without letting early seats anchor later seats (`--stage plan`).
- Clustering structured findings deterministically by `(canonical_target, assertion_key)` across distinct participants, computing complementarity weights, solving $O(N^3)$ Kuhn-Munkres `max_weight_derangement`, and generating anonymized `Proposal-N` challenge bundles (`--stage merge` or MCP `academic_cross_review`).
- Dispatching targeted cross-examination only on genuine contradictions and high-severity (`P0`/`P1`) singletons (`--stage challenge`), then reconciling verdicts with **minority-evidence protection** so unrefuted findings backed by verified file locators are preserved in `unresolved-ledger.json` rather than erased by majority vote (`--stage synthesize`).

## Four-Stage Sparse Deliberation Modes

- `economy`: `max_challenges=1`, minimal targeted adjudication.
- `standard` (default): `max_challenges=3` prioritizing `P0`/`P1` contradictions and singletons.
- `audit`: `max_challenges=5` plus maximum-weight derangement peer verification when budget remains.

## Quick CLI Commands

```bash
# 1. Define explicit participant roster in panel.json (command templates or offline mock seats)
#    [{"id": "seat-a", "executor": "command", "provider": "openai", "model": "codex", "cmd": ["codex", "exec", "-o", "{out_path}", "-"]},
#     {"id": "seat-b", "executor": "command", "provider": "google", "model": "gemini", "cmd": "gemini -p {prompt_path}"}]

# 2. Run step-by-step or end-to-end sparse deliberation
academic-research-kernel cross-review ./review-stream --models-file ./panel.json --task ./task.md --stage plan
academic-research-kernel cross-review ./review-stream --models-file ./panel.json --stage merge --mode standard
academic-research-kernel cross-review ./review-stream --models-file ./panel.json --task ./task.md --stage challenge
academic-research-kernel cross-review ./review-stream --stage synthesize
academic-research-kernel cross-review ./review-stream --stage status

# 3. Compute classic v1 ring-rotation pairings for a given participant list
academic-research-kernel cross-review --models "seat-a,seat-b,seat-c" --stage pairings
```

## MCP Tools

- `academic_cross_review` (alias `cross_review_deliberate`): accepts inline `findings_by_model` (and optional `challenge_replies`) from any host agent's subagents and returns schema-valid `CrossReviewIssueRegistry`, anonymized `challenge_plan`, `derangement_pairings`, and minority-protected `ReviewRunReceipt`.

## Deliberation Rules

1. Multi-model agreement is a prioritization signal, never proof; provenance locators and deterministic recomputation remain the ground truth.
2. Single-model duplicate findings on the same target stay `singleton` (`consensus` requires $\ge 2$ distinct participants).
3. Challenger selection excludes every participant involved in raising the disputed issue and shuffles proposals as `Proposal-1..N`.

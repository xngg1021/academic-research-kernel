# -*- coding: utf-8 -*-
"""Decision & Negative Result Ledger Kernel v1.

Deterministic, append-only ledger for research decisions, negative results,
prune causality, and outcome corrections. Pure standard library, no LLM, no
network. Consumes the same receipt contracts as the Claim-Evidence Graph
Kernel (LineageReceipt, AcademicEvidenceReceipt).
"""
from ledger import (  # noqa: F401
    PROTOCOL,
    DecisionBasisEdge,
    DecisionForkEdge,
    DecisionLedger,
    DecisionNode,
    FrozenDict,
    OutcomeCorrection,
    PruneState,
    ReceiptRef,
    UncertaintyItem,
    canonical_academic_receipt_payload_sha256,
    canonical_basis_tuple,
    canonical_evidence_claim_digest,
    canonical_fork_tuple,
    canonical_ledger_payload_sha256,
    canonical_receipt_ref_tuple,
    canonical_text,
    compute_decision_digest,
    compute_outcome_digest,
    validate_academic_receipt_contract,
    validate_lineage_receipt_contract,
)

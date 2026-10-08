"""Chain A: real recomputation, adaptation, receipts, CEG/Ledger and replay.

All paper inputs and identifiers here are explicitly synthetic test data.
The numerical oracle uses mpmath's incomplete-beta identity, independently of
the production SciPy t survival function. No numerical/state layer is mocked.
"""

import json
from pathlib import Path
import sys

import mpmath
import pytest


ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "scripts",
             ROOT / "skills/claim-evidence-graph/scripts",
             ROOT / "skills/decision-ledger/scripts"):
    sys.path.insert(0, str(path))

import graph as ceg_mod
import ledger as ledger_mod
import mcp_server
from ingestion import ArtifactEnvelope, IngestionEngine, IngestionKernelState
from ingestion.contracts import validate_schema


def call_tool(name, arguments, call_id=1):
    reply = mcp_server.process_message({
        "jsonrpc": "2.0", "id": call_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    assert reply["id"] == call_id
    assert reply["result"]["isError"] is False, reply
    return json.loads(reply["result"]["content"][0]["text"])


def test_chain_a_real_statistics_to_identity_receipts_graph_ledger_and_replay(tmp_path):
    raw = [
        {"t_stat": 1, "df": 30, "p_value": 0.00001, "p_value_literal": "0.00001",
         "locator": "synthetic-table-1:row-small-p", "expected": "contradicted"},
        {"t_stat": 1, "df": 30, "p_value": 0.3253, "p_value_literal": "0.3253",
         "locator": "synthetic-table-1:row-rounded-p", "expected": "supported"},
    ]
    with mpmath.workdps(60):
        df, t = mpmath.mpf(30), mpmath.mpf(1)
        reference = mpmath.betainc(df / 2, mpmath.mpf("0.5"), 0,
                                  df / (df + t * t), regularized=True)
        independent_p = float(reference)
    # Independent interval facts make the scientific verdict explicit.
    assert independent_p > 0.000015
    assert 0.32525 <= independent_p < 0.32535

    computed = []
    for index, item in enumerate(raw):
        args = {key: item[key] for key in ("t_stat", "df", "p_value", "p_value_literal")}
        result = call_tool("academic_recompute_statistics", args, index + 1)
        assert result["recomputed_p"] == pytest.approx(independent_p, abs=1e-14)
        assert result["p_match"]["consistent"] is (item["expected"] == "supported")
        # Adapt the actual production result, retaining its inputs/precision.
        computed.append({**result["p_match"], "statistic": "two-sided t-test",
                         "inputs": result["p_receipt"]["inputs"], "locator": item["locator"]})

    work_id = "work:doi:10.5555/ark-correctness-chain-a-test"
    source_payload = {
        "schema_version": "1.0", "query": "Synthetic test inputs for correctness chain A",
        "identifiers": {"doi": "10.5555/ark-correctness-chain-a-test"},
        "sources": [{"source": "test-fixture:chain-a", "queried_at": "2026-10-08T00:00:00Z",
                     "status": "ok", "coverage": "Synthetic offline test data; no online retrieval"}],
        "claims": [{"claim": f"Synthetic test report: t(30)=1 has two-sided p={item['p_value_literal']}",
                    "evidence_type": "computed", "source": "test-fixture:chain-a",
                    "locator": item["locator"], "support_status": "unverifiable"} for item in raw],
        "generated_at": "2026-10-08T00:00:00Z",
    }
    source_env = ArtifactEnvelope.create(
        payload=source_payload, producer_skill="academic-source-verification", producer_version="1.0.0",
        artifact_kind="evidence_receipt", payload_schema="evidence-receipt-1.0", subject_refs=[work_id],
    )
    engine = IngestionEngine()
    state = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph(), ledger=ledger_mod.DecisionLedger())
    source_receipt = engine.ingest(source_env, state=state)
    assert source_receipt.status == "accepted", source_receipt.failure_reason
    assert work_id in source_receipt.created_or_reused_objects
    assert state.objects[work_id]["kind"] == "work"
    assert source_env.payload_sha256 in state.receipts
    claims_by_locator = {claim.locator: claim for claim in state.ceg.claims.values()}
    assert len(claims_by_locator) == 2
    audit_receipts, audit_envelopes = [], []

    for index, (item, audit) in enumerate(zip(raw, computed)):
        claim = claims_by_locator[item["locator"]]
        assert claim.target_work_id == work_id
        assert validate_schema(audit, "quantitative-audit.schema.json") == []
        audit_env = ArtifactEnvelope.create(
            payload=audit, producer_skill="quantitative-paper-audit", producer_version="1.1.0",
            artifact_kind="computed_evidence", payload_schema="quantitative-audit-1.0",
            subject_refs=[work_id], locator=item["locator"],
        )
        receipt = engine.ingest(audit_env, state=state, bindings={"claim_id": claim.id})
        assert receipt.status == "accepted", receipt.failure_reason
        assert receipt.adapter_id == "adapter-quantitative-paper-audit"
        assert receipt.source_artifact_id == audit_env.artifact_id
        assert receipt.source_artifact_sha256 == audit_env.payload_sha256
        assert not receipt.ledger_bindings
        assert state.ledger.to_dict()["decisions"] == []
        anchor = state.ceg.evidence_anchors[receipt.ceg_nodes[0]]
        assert anchor.locator == item["locator"]
        assert anchor.metadata["audit_result"] == audit
        assert anchor.metadata["recomputed"] == pytest.approx(independent_p, abs=1e-14)
        linked = [edge for edge in state.ceg.support_edges if edge.evidence_id == anchor.id]
        assert len(linked) == 1
        assert linked[0].claim_id == claim.id
        assert linked[0].support_status == item["expected"]
        audit_receipts.append(receipt)
        audit_envelopes.append((audit_env, {"claim_id": claim.id}))

    # Explicit human-selected test decisions, after verifying that the adapter
    # created none. The basis receipt anchors provenance of the original input;
    # metadata links the actual quantitative artifact and its ingestion receipt.
    for index, (item, receipt, (audit_env, _)) in enumerate(zip(raw, audit_receipts, audit_envelopes)):
        claim = claims_by_locator[item["locator"]]
        source_anchor = next(anchor for anchor in state.ceg.evidence_anchors.values()
                             if anchor.locator == item["locator"] and anchor.receipt_ref is not None)
        state.ledger.add_decision(f"source-basis-{index}", "Human selected statistical input for review",
                                  decision_action="explore", context_work_id="chain-a-test-work", locator=claim.locator,
                                  metadata={"research_object_id": work_id})
        state.ledger.add_decision(f"human-review-{index}", "Human selected review of recomputation verdict",
                                  decision_action="revise", context_work_id="chain-a-test-work", locator=claim.locator,
                                  metadata={"selection": "explicit test researcher action",
                                            "research_object_id": work_id,
                                            "audit_artifact_id": audit_env.artifact_id,
                                            "ingestion_receipt_id": receipt.receipt_id,
                                            "verdict": item["expected"]})
        state.ledger.add_basis(f"human-review-{index}", "decision", f"source-basis-{index}",
                               receipt_ref=source_anchor.receipt_ref,
                               metadata={"claim_id": claim.id, "audit_artifact_id": audit_env.artifact_id})

    assert len(state.objects) == 1  # Both reports retain the same DOI identity.
    valid, errors = state.validate_invariants()
    assert valid, errors
    snapshot = state.to_dict()
    exported = tmp_path / "chain-a-kernel.json"
    exported.write_text(json.dumps(snapshot, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    replayed = IngestionKernelState.from_dict(json.loads(exported.read_text(encoding="utf-8")),
                                             ceg_cls=ceg_mod.ClaimEvidenceGraph,
                                             ledger_cls=ledger_mod.DecisionLedger)
    assert replayed.compute_digests() == state.compute_digests()
    assert replayed.to_dict() == snapshot
    assert replayed.objects[work_id] == state.objects[work_id]
    assert engine.ingest(source_env, state=replayed) == source_receipt
    for index, ((audit_env, bindings), receipt) in enumerate(zip(audit_envelopes, audit_receipts)):
        assert engine.ingest(audit_env, state=replayed, bindings=bindings) == receipt
        claim = claims_by_locator[raw[index]["locator"]]
        trace = call_tool("claim_evidence_trace", {"graph": replayed.ceg.to_dict(), "claim_id": claim.id,
                                                    "receipts": snapshot["receipts"]}, 10 + index)
        branch = "contradictions" if raw[index]["expected"] == "contradicted" else "support"
        assert trace[branch]
        decision = replayed.ledger.get_decision(f"human-review-{index}")
        assert decision.metadata["verdict"] == raw[index]["expected"]
        assert decision.metadata["research_object_id"] == work_id
        assert decision.locator == raw[index]["locator"]
        assert replayed.ledger.bases_of(decision.id)[0]["receipt_ref"]["payload_sha256"] == source_env.payload_sha256

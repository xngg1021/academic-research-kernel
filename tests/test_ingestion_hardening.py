"""Regression tests for the fail-closed ingestion and stateless MCP boundary."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parent.parent
for path in (
    ROOT / "scripts",
    ROOT / "skills" / "claim-evidence-graph" / "scripts",
    ROOT / "skills" / "decision-ledger" / "scripts",
):
    sys.path.insert(0, str(path))

import graph as ceg_mod
import ledger as ledger_mod
import mcp_server
from ingestion import ArtifactEnvelope, IngestionEngine, IngestionKernelState, IngestionReceipt
from shared_contracts.evidence import (
    ReceiptRef,
    canonical_evidence_claim_digest,
    canonical_json_bytes,
    compute_sha256,
)


def evidence_payload(claim: str = "A verified claim") -> dict:
    return {
        "schema_version": "1.0",
        "query": "doi:10.1000/example",
        "identifiers": {"doi": "10.1000/example"},
        "sources": [],
        "claims": [{
            "claim": claim,
            "evidence_type": "computed",
            "source": "doi:10.1000/example",
            "support_status": "supported",
        }],
        "generated_at": "2026-09-20T00:00:00Z",
    }


def envelope(payload: dict, producer: str, schema: str, **kwargs) -> ArtifactEnvelope:
    return ArtifactEnvelope.create(
        payload=payload,
        producer_skill=producer,
        producer_version=kwargs.pop("producer_version", "1.0.0"),
        artifact_kind=kwargs.pop("artifact_kind", "test_artifact"),
        payload_schema=schema,
        **kwargs,
    )


def kernel() -> IngestionKernelState:
    return IngestionKernelState(
        ceg=ceg_mod.ClaimEvidenceGraph(),
        ledger=ledger_mod.DecisionLedger(),
    )


def call_tool(name: str, arguments: dict, call_id: int = 1) -> tuple[dict, dict]:
    response = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": call_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    body = json.loads(response["result"]["content"][0]["text"])
    return response, body


def test_envelope_and_receipt_are_deeply_immutable():
    env = envelope(
        {"nested": {"values": [1, 2]}},
        "unknown-producer",
        "unknown-schema-1.0",
        caller_metadata={"run": {"tags": ["a"]}},
    )
    with pytest.raises(TypeError):
        env.payload["nested"]["new"] = True
    with pytest.raises(TypeError):
        env.payload._data["nested"] = {"changed": True}
    with pytest.raises(AttributeError):
        env.payload["nested"]["values"].append(3)
    with pytest.raises(TypeError):
        env.caller_metadata["run"]["tags"][0] = "changed"

    receipt = IngestionEngine().ingest(env, state=IngestionKernelState())
    assert receipt.status == "accepted"
    with pytest.raises(TypeError):
        receipt.output_digests["object_registry_digest"] = "0" * 64
    with pytest.raises(TypeError):
        receipt.caller_metadata["run"]["new"] = True


def test_caller_metadata_is_preserved_but_excluded_from_receipt_identity():
    payload = {"value": 1}
    first = envelope(
        payload,
        "unknown-producer",
        "unknown-schema-1.0",
        caller_metadata={"run_id": "one"},
    )
    second = envelope(
        payload,
        "unknown-producer",
        "unknown-schema-1.0",
        caller_metadata={"run_id": "two"},
    )
    state = IngestionKernelState()
    r1 = IngestionEngine().ingest(first, state=state)
    r2 = IngestionEngine().ingest(second, state=state)
    assert r1.caller_metadata["run_id"] == "one"
    assert r2.caller_metadata["run_id"] == "two"
    assert r1.receipt_id == r2.receipt_id


def test_caller_metadata_replay_does_not_reapply_outcome_correction():
    state = kernel()
    state.ledger.add_decision("dec-1", "Decision", decision_action="commit")
    engine = IngestionEngine()
    bindings_a = {
        "action": "add_outcome_correction",
        "decision_id": "dec-1",
        "verdict": "positive",
        "rationale": "result A",
    }
    first = envelope(
        evidence_payload("Evidence A"),
        "academic-source-verification",
        "evidence-receipt-1.0",
        caller_metadata={"run_id": "first"},
    )
    second = envelope(
        evidence_payload("Evidence B"),
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    r_a = engine.ingest(first, state=state, bindings=bindings_a)
    r_b = engine.ingest(
        second,
        state=state,
        bindings={
            "action": "add_outcome_correction",
            "decision_id": "dec-1",
            "verdict": "negative",
            "rationale": "result B",
        },
    )
    replay = envelope(
        evidence_payload("Evidence A"),
        "academic-source-verification",
        "evidence-receipt-1.0",
        caller_metadata={"run_id": "replay"},
    )
    r_replay = engine.ingest(replay, state=state, bindings=bindings_a)

    corrections = state.ledger.to_dict()["corrections"]
    assert len(corrections) == 2
    assert state.ledger.outcome_of("dec-1")["latest_correction_id"] == r_b.ledger_bindings[0]["basis_id"]
    assert r_a.ledger_bindings[0]["basis_id"] == corrections[0]["correction_id"]
    assert r_replay.receipt_id == r_a.receipt_id
    assert r_replay.caller_metadata["run_id"] == "replay"


def test_runtime_schema_rejects_documented_but_incomplete_receipt():
    env = envelope(
        {"schema_version": "1.0", "claims": []},
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    receipt = IngestionEngine().ingest(env, state=kernel())
    assert receipt.status == "rejected"
    assert "required property" in receipt.failure_reason


def test_known_producer_schema_mismatch_does_not_fall_back_to_opaque():
    env = envelope(
        {"text": "not an evidence receipt"},
        "academic-source-verification",
        "manuscript-opaque-1.0",
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "rejected"
    assert receipt.adapter_id == "adapter-academic-source-verification"
    assert not state.objects


def test_unsupported_producer_major_is_rejected():
    env = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
        producer_version="2.0.0",
    )
    receipt = IngestionEngine().ingest(env, state=kernel())
    assert receipt.status == "rejected"
    assert "unsupported" in receipt.failure_reason


def test_current_cross_review_v2_registry_is_accepted_and_preserved():
    payload = {
        "metadata": {"mode": "standard", "models": ["reviewer-a"]},
        "stats": {
            "consensus_count": 0,
            "singleton_count": 0,
            "contradiction_count": 0,
            "total_issues": 0,
        },
        "consensus": [],
        "contradictions": [],
        "singletons": [],
        "complementarity_weights": {},
    }
    env = envelope(
        payload,
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    object_id = receipt.created_or_reused_objects[0]
    assert state.objects[object_id]["registry"] == payload


def test_real_quantitative_unknown_result_is_unverifiable():
    payload = {
        "consistent": None,
        "implied_n": None,
        "reported_n": 20,
        "difference": None,
        "inputs": {"df": 7.5, "reported_n": 20, "kind": "ttest_2sample_welch"},
        "formula": "Welch df cannot determine N",
        "library": "pure python",
        "confidence": "medium",
        "note": "No deterministic sample-size verdict",
    }
    state = kernel()
    state.ceg.add_claim("claim-1", "The sample size is internally consistent")
    env = envelope(
        payload,
        "quantitative-paper-audit",
        "quantitative-audit-1.0",
        producer_version="1.1.0",
    )
    receipt = IngestionEngine().ingest(env, state=state, bindings={"claim_id": "claim-1"})
    assert receipt.status == "accepted"
    assert state.ceg.support_edges[-1].support_status == "unverifiable"
    assert receipt.uncertainties[0]["kind"] == "quantitative_verification_gap"


def test_direct_canonical_work_producer_shape_is_accepted():
    payload = {
        "work_type": "article",
        "title": "A Canonical Work",
        "authors": [{"family": "Example", "given": "Ada"}],
        "year": 2026,
        "container": "Journal",
        "doi": "10.1000/example",
        "url": "https://doi.org/10.1000/example",
        "volume": "1",
        "issue": "2",
        "pages": "1-10",
        "publisher": "Example Press",
        "extra": {},
    }
    env = envelope(
        payload,
        "literature-analysis",
        "canonical-work-1.0",
        producer_version="1.3.0",
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    assert state.objects["work:doi:10.1000/example"] == payload


def test_meta_analysis_only_artifact_creates_a_kernel_object():
    payload = {"meta_analysis": {"effect": 0.42, "model": "random"}, "protocol_id": "p-1"}
    env = envelope(
        payload,
        "systematic-review-meta-analysis",
        "meta-analysis-1.0",
        producer_version="1.0.1",
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    object_id = receipt.created_or_reused_objects[0]
    assert state.objects[object_id]["value"] == payload["meta_analysis"]


def test_current_reproduction_receipt_shape_is_accepted_and_preserved():
    payload = {
        "kind": "ReproductionReceipt",
        "schema_version": "1.0",
        "status": "blocked",
        "tier": "runs",
        "paper": {"title": "Example"},
        "repository": None,
        "stages": [{"id": "code", "status": "missing"}],
        "contradictions": [],
        "blocking": ["code"],
        "gaps": [],
        "generated_at": "2026-09-20T00:00:00Z",
    }
    env = envelope(
        payload,
        "research-reproducibility",
        "reproduction-receipt-1.0",
        producer_version="1.0.1",
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    evidence_id = receipt.ceg_nodes[0]
    assert state.ceg.evidence_anchors[evidence_id].metadata.to_dict()["receipt"] == payload


def test_dangling_claim_binding_rolls_back_every_mutation():
    env = envelope(
        {
            "paper_title": "Example",
            "assertions": [{
                "statistic": "t",
                "reported_value": 1.0,
                "recomputed_value": 2.0,
                "discrepancy_detected": True,
            }],
        },
        "quantitative-paper-audit",
        "quantitative-audit-1.0",
    )
    state = kernel()
    before = state.compute_digests()
    receipt = IngestionEngine().ingest(env, state=state, bindings={"claim_id": "ghost"})
    assert receipt.status == "rejected"
    assert "Dangling support edge" in receipt.failure_reason
    assert state.compute_digests() == before
    assert not state.ingested_artifacts


def test_quantitative_missing_verdict_is_unverifiable_not_supported():
    state = kernel()
    state.ceg.add_claim("claim-1", "A numerical claim")
    env = envelope(
        {
            "reported": 1.0,
            "recomputed": 1.0,
            "formula": "x",
            "library": "reference",
        },
        "quantitative-paper-audit",
        "quantitative-audit-1.0",
    )
    receipt = IngestionEngine().ingest(env, state=state, bindings={"claim_id": "claim-1"})
    assert receipt.status == "accepted"
    assert state.ceg.support_edges[-1].support_status == "unverifiable"
    assert receipt.uncertainties[0]["kind"] == "quantitative_verification_gap"


def test_math_missing_verification_is_unverifiable_not_contradicted():
    state = kernel()
    state.ceg.add_claim("claim-1", "A symbolic claim")
    env = envelope(
        {"expression": "x + x", "result": "2*x"},
        "math-computation",
        "computation-receipt-1.0",
    )
    receipt = IngestionEngine().ingest(env, state=state, bindings={"claim_id": "claim-1"})
    assert receipt.status == "accepted"
    assert state.ceg.support_edges[-1].support_status == "unverifiable"
    assert receipt.uncertainties[0]["kind"] == "computation_unverified"


def test_screening_only_and_citation_only_payloads_mutate_state():
    state = kernel()
    screening = envelope(
        {"screening_results": [{"record_id": "record-1", "decision": "include"}]},
        "systematic-review-meta-analysis",
        "screening-matrix-1.0",
    )
    citation = envelope(
        {"new_citations": [{"id": "citation-1", "title": "New citation"}]},
        "literature-watch",
        "literature-delta-1.0",
    )
    receipts, _ = IngestionEngine().batch_ingest([screening, citation], state=state)
    assert all(item.status == "accepted" for item in receipts)
    assert state.objects["screening:record-1"]["kind"] == "screening_result"
    assert state.objects["citation-1"]["kind"] == "citation_delta"


def test_screening_record_does_not_replace_included_study_with_same_id():
    state = kernel()
    env = envelope(
        {
            "included_studies": [{"study_id": "study-1", "effect": 0.42}],
            "screening_results": [{"study_id": "study-1", "decision": "include"}],
        },
        "systematic-review-meta-analysis",
        "screening-matrix-1.0",
    )
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    assert state.objects["study-1"]["effect"] == 0.42
    assert state.objects["screening:study-1"]["decision"] == "include"


@pytest.mark.parametrize(
    ("value", "expected_uncertainties"),
    [(False, 0), (None, 1), (True, 1)],
)
def test_retraction_three_state_contract(value, expected_uncertainties):
    state = kernel()
    env = envelope(
        {"is_retracted": value, "signals": []},
        "retraction-watch",
        "retraction-delta-1.0",
        subject_refs=["doi:10.1000/example"],
    )
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    assert len(receipt.uncertainties) == expected_uncertainties
    assert receipt.created_or_reused_objects


def test_ceg_declared_digest_and_evidence_content_are_strictly_replayed():
    source = ceg_mod.ClaimEvidenceGraph(graph_id="source")
    source.add_claim("claim-1", "Claim", metadata={"scope": "all"})
    source.add_evidence(
        "evidence-1",
        "direct_observation",
        content_sha256="a" * 64,
        excerpt="Exact excerpt",
        metadata={"page": 1},
    )
    source.add_support_edge("evidence-1", "claim-1", "supported")
    exported = source.to_dict()

    tampered = copy.deepcopy(exported)
    tampered["claims"][0]["text"] = "Tampered"
    with pytest.raises(ValueError, match="tampering|identity mismatch"):
        ceg_mod.ClaimEvidenceGraph.from_dict(tampered)

    state = kernel()
    env = envelope(
        exported,
        "claim-evidence-graph",
        "claim-evidence-graph-1.0",
        artifact_kind="ceg_snapshot",
    )
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted"
    replayed = state.ceg.evidence_anchors["evidence-1"]
    assert replayed.content_sha256 == "a" * 64
    assert replayed.excerpt == "Exact excerpt"


def test_mcp_artifact_validation_accepts_receipt_context_for_ceg_snapshot():
    physical = evidence_payload()
    payload_sha = compute_sha256(canonical_json_bytes(physical))
    claim_digest = canonical_evidence_claim_digest(physical["claims"][0])
    ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=claim_digest,
        payload_sha256=payload_sha,
    )
    source = ceg_mod.ClaimEvidenceGraph(graph_id="receipt-backed")
    source.register_receipt(payload_sha, physical)
    source.add_claim("claim-1", "A verified claim", target_work_id="work:A")
    source.add_evidence(
        "evidence-1",
        "evidence_receipt",
        source_work_id="work:A",
        receipt_ref=ref,
    )
    source.add_support_edge("evidence-1", "claim-1", "supported", receipt_ref=ref)
    env = envelope(
        source.to_dict(),
        "claim-evidence-graph",
        "claim-evidence-graph-1.0",
        artifact_kind="ceg_snapshot",
    )

    _, without_context = call_tool(
        "research_artifact_validate", {"envelope": env.to_dict()}
    )
    _, with_context = call_tool(
        "research_artifact_validate",
        {"envelope": env.to_dict(), "receipts": {payload_sha: physical}},
    )
    assert without_context["valid"] is False
    assert with_context["valid"] is True


def test_complete_kernel_snapshot_round_trip_and_tamper_rejection():
    state = kernel()
    env = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
        caller_metadata={"run_id": "snapshot"},
    )
    assert IngestionEngine().ingest(env, state=state).status == "accepted"
    snapshot = state.to_dict()
    replayed = IngestionKernelState.from_dict(
        snapshot,
        ceg_cls=ceg_mod.ClaimEvidenceGraph,
        ledger_cls=ledger_mod.DecisionLedger,
    )
    assert replayed.to_dict() == snapshot

    tampered = copy.deepcopy(snapshot)
    tampered["objects"][next(iter(tampered["objects"]))]["tampered"] = True
    with pytest.raises(ValueError, match="tampering"):
        IngestionKernelState.from_dict(
            tampered,
            ceg_cls=ceg_mod.ClaimEvidenceGraph,
            ledger_cls=ledger_mod.DecisionLedger,
        )


def test_mcp_returns_full_round_trippable_state_even_for_dry_run():
    env = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    response, body = call_tool(
        "research_artifact_ingest",
        {"envelope": env.to_dict(), "dry_run": True},
    )
    assert response["result"]["isError"] is False
    assert body["success"] is True
    assert set(body["output_state"]) == {
        "protocol", "snapshot_digest", "ceg", "ledger", "objects", "receipts",
        "uncertainties", "ingested_artifacts", "ingestion_receipts", "content_digests",
    }
    IngestionKernelState.from_dict(
        body["output_state"],
        ceg_cls=ceg_mod.ClaimEvidenceGraph,
        ledger_cls=ledger_mod.DecisionLedger,
    )


def test_mcp_rejects_undeclared_arguments_with_is_error():
    response, body = call_tool("academic_scfabric_hardware_probe", {"surprise": True})
    assert response["result"]["isError"] is True
    assert body["error"] == "Invalid tool arguments"


def test_mcp_lineage_trace_preserves_canonical_fields_and_direction():
    graph = {
        "entities": [
            {
                "id": "raw",
                "type": "data_snapshot",
                "sha256": "a" * 64,
                "metadata": {"version": 1},
            },
            {"id": "analysis.py", "type": "code_file"},
            {"id": "result", "type": "statistic_artifact"},
        ],
        "activities": [{
            "id": "run",
            "type": "statistical_analysis",
            "script_id": "analysis.py",
            "commit_sha": "abc123",
            "environment": {"python": "3.12"},
            "timestamp": "2026-09-20T00:00:00Z",
        }],
        "edges": [
            {"type": "used", "source_id": "run", "target_id": "raw"},
            {"type": "generated", "source_id": "run", "target_id": "result"},
        ],
    }
    _, body = call_tool(
        "research_lineage_trace",
        {"lineage_graph": graph, "target_entity_id": "result"},
    )
    receipt = body["receipt"]
    assert "raw" in receipt["root_ancestors"]
    raw = next(item for item in receipt["entities"] if item["id"] == "raw")
    run = receipt["activities"][0]
    assert raw["sha256"] == "a" * 64
    assert raw["metadata"] == {"version": 1}
    assert run["script_id"] == "analysis.py"
    assert run["environment"] == {"python": "3.12"}


def test_real_stdio_transport_handles_tools_list_and_tools_call():
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "academic_check_percentage",
                "arguments": {"count": 12, "percent": 24.0, "sample_size": 50},
            },
        },
    ]
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "mcp_server.py")],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    assert [item["id"] for item in responses] == [1, 2, 3]
    assert len(responses[1]["result"]["tools"]) == 12
    tool_result = json.loads(responses[2]["result"]["content"][0]["text"])
    assert tool_result["consistent"] is True
    assert responses[2]["result"]["isError"] is False


def test_decision_trace_reports_upstream_bases_not_reverse_dependents():
    ledger = ledger_mod.DecisionLedger()
    ledger.add_decision("root", "Root", decision_action="explore")
    ledger.add_decision("child", "Child", decision_action="commit")
    ledger.add_basis("child", "decision", "root")
    _, body = call_tool(
        "decision_trace",
        {"ledger": ledger.to_dict(), "decision_id": "child"},
    )
    assert body["bases"][0]["basis_id"] == "root"
    assert body["dependent_decisions"] == []


def test_object_registry_digest_is_insertion_order_invariant():
    first = IngestionKernelState(objects={"b": {"value": 2}, "a": {"value": 1}})
    second = IngestionKernelState(objects={"a": {"value": 1}, "b": {"value": 2}})
    assert first.compute_digests()["object_registry_digest"] == second.compute_digests()["object_registry_digest"]


def test_equal_claims_for_different_works_get_distinct_ceg_nodes():
    payload = evidence_payload()
    first = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:A"],
    )
    second = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:B"],
    )
    state = kernel()
    accepted_a = IngestionEngine().ingest(first, state=state)
    accepted_b = IngestionEngine().ingest(second, state=state)
    assert accepted_a.status == "accepted"
    assert accepted_b.status == "accepted"
    assert accepted_b.receipt_id != accepted_a.receipt_id
    assert accepted_a.ceg_nodes != accepted_b.ceg_nodes
    assert {claim.target_work_id for claim in state.ceg.claims.values()} == {
        "work:A",
        "work:B",
    }


def test_missing_input_lineage_receipt_verifies_and_ingests():
    receipt = mcp_server.prov_mod.trace_origin(
        mcp_server.prov_mod.LineageGraph(),
        "missing-target",
        check_on_disk_hashes=False,
    ).to_dict()
    ref = {
        "kind": "lineage",
        "schema_version": "lineage-receipt-1.0",
        "receipt_id": receipt["receipt_id"],
        "receipt_digest": receipt["receipt_digest"],
    }
    _, verified = call_tool(
        "research_receipt_verify",
        {"receipt_ref": ref, "receipt_payload": receipt},
    )
    env = envelope(
        receipt,
        "research-object-identity",
        "lineage-receipt-1.0",
        artifact_kind="lineage_receipt",
    )
    ingested = IngestionEngine().ingest(env, state=kernel())
    assert verified["valid"] is True
    assert ingested.status == "accepted"


def test_lineage_receipt_timestamp_variants_share_registry_identity():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    first_payload = mcp_server.prov_mod.trace_origin(
        graph, "entity-1", check_on_disk_hashes=False
    ).to_dict()
    first_payload["timestamp"] = "2026-09-20T00:00:00Z"
    second_payload = copy.deepcopy(first_payload)
    second_payload["timestamp"] = "2026-09-20T00:00:01Z"
    first = envelope(
        first_payload,
        "research-object-identity",
        "lineage-receipt-1.0",
        artifact_kind="lineage_receipt",
    )
    second = envelope(
        second_payload,
        "research-object-identity",
        "lineage-receipt-1.0",
        artifact_kind="lineage_receipt",
    )
    state = kernel()
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)
    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.receipts) == 1
    assert state.receipts[first_payload["receipt_id"]]["timestamp"] == first_payload["timestamp"]


def test_batch_bindings_length_must_match_exactly():
    env = envelope({"value": 1}, "unknown", "unknown-1.0")
    with pytest.raises(ValueError, match="exactly match"):
        IngestionEngine().batch_ingest([env], bindings_list=[])


def test_academic_retrieval_metadata_does_not_change_stable_work_identity():
    first_payload = evidence_payload()
    second_payload = copy.deepcopy(first_payload)
    second_payload["query"] = "title:A verified claim"
    second_payload["identifiers"] = {"openalex_id": "W123"}
    state = kernel()

    first = envelope(
        first_payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:stable"],
    )
    second = envelope(
        second_payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:stable"],
    )
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert dict(state.objects["work:stable"]) == {"id": "work:stable", "kind": "work"}
    assert len(state.ceg.claims) == 1
    assert len(state.ceg.evidence_anchors) == 2


def test_effective_envelope_locator_participates_in_academic_ceg_identity():
    payload = evidence_payload()
    state = kernel()
    first = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:stable"],
        locator="page:1",
    )
    second = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:stable"],
        locator="page:2",
    )
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert {claim.locator for claim in state.ceg.claims.values()} == {"page:1", "page:2"}
    assert len(state.ceg.evidence_anchors) == 2


def test_screening_record_id_prevents_same_study_reports_from_overwriting():
    env = envelope(
        {
            "screening_results": [
                {"record_id": "report-a", "study_id": "study-1", "decision": "include"},
                {"record_id": "report-b", "study_id": "study-1", "decision": "exclude"},
            ]
        },
        "systematic-review-meta-analysis",
        "screening-matrix-1.0",
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)

    assert receipt.status == "accepted"
    assert state.objects["screening:report-a"]["decision"] == "include"
    assert state.objects["screening:report-b"]["decision"] == "exclude"


def test_retraction_retained_prior_is_not_treated_as_current_negative():
    env = envelope(
        {
            "is_retracted": False,
            "signals": [],
            "current_observation": None,
            "verification_status": "retained_prior",
        },
        "retraction-watch",
        "retraction-delta-1.0",
        subject_refs=["doi:10.1000/example"],
    )
    receipt = IngestionEngine().ingest(env, state=kernel())

    assert receipt.status == "accepted"
    assert len(receipt.uncertainties) == 1
    assert receipt.uncertainties[0]["kind"] == "publication_status_change"


def test_artifact_preflight_rejects_forged_lineage_identity():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    receipt = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    receipt["lineage_digest"] = "f" * 64
    env = envelope(
        receipt,
        "research-object-identity",
        "lineage-receipt-1.0",
        artifact_kind="lineage_receipt",
    )

    _, body = call_tool("research_artifact_validate", {"envelope": env.to_dict()})

    assert body["valid"] is False
    assert any("digest mismatch" in error for error in body["errors"])


def test_mcp_lineage_trace_requires_explicit_activity_timestamp():
    response, body = call_tool(
        "research_lineage_trace",
        {
            "lineage_graph": {
                "entities": [],
                "activities": [{"id": "run", "type": "statistical_analysis"}],
                "edges": [],
            },
            "target_entity_id": "result",
        },
    )

    assert response["result"]["isError"] is True
    assert body["error"] == "Invalid tool arguments"
    assert any("timestamp" in error for error in body["details"])


def test_ledger_snapshot_replay_ignores_unrelated_kernel_receipts():
    snapshot_ledger = ledger_mod.DecisionLedger("snapshot-ledger")
    snapshot_ledger.add_decision("decision-1", "Snapshot decision", decision_action="commit")
    snapshot = snapshot_ledger.to_dict()
    assert snapshot["verification_manifest"] == {}

    state = kernel()
    state.register_receipt("unrelated", evidence_payload())
    env = envelope(
        snapshot,
        "decision-ledger",
        "decision-ledger-1.0",
        artifact_kind="decision_ledger_snapshot",
    )
    receipt = IngestionEngine().ingest(env, state=state)

    assert receipt.status == "accepted"
    assert state.ledger.ledger_id == "snapshot-ledger"
    assert state.ledger.to_dict()["decisions"][0]["id"] == "decision-1"
    assert "unrelated" in state.ledger.to_dict()["verification_manifest"]

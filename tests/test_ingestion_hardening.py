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

    receipt_state = kernel()
    evidence = evidence_payload()
    accepted = IngestionEngine().ingest(
        envelope(
            evidence,
            "academic-source-verification",
            "evidence-receipt-1.0",
        ),
        state=receipt_state,
    )
    assert accepted.status == "accepted"
    physical = receipt_state.receipts[compute_sha256(canonical_json_bytes(evidence))]
    with pytest.raises(TypeError):
        physical["claims"][0]["claim"] = "tampered"


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


def test_unknown_binding_cannot_reapply_an_old_outcome_correction():
    state = kernel()
    state.ledger.add_decision("dec-1", "Decision", decision_action="commit")
    engine = IngestionEngine()
    first = envelope(
        evidence_payload("Evidence A"),
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    second = envelope(
        evidence_payload("Evidence B"),
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    binding_a = {
        "action": "add_outcome_correction",
        "decision_id": "dec-1",
        "verdict": "positive",
        "rationale": "result A",
    }
    engine.ingest(first, state=state, bindings=binding_a)
    accepted_b = engine.ingest(
        second,
        state=state,
        bindings={
            "action": "add_outcome_correction",
            "decision_id": "dec-1",
            "verdict": "negative",
            "rationale": "result B",
        },
    )

    rejected = engine.ingest(
        first,
        state=state,
        bindings={**binding_a, "claim_id": "unused"},
    )

    assert rejected.status == "rejected"
    assert "Unsupported binding fields" in rejected.failure_reason
    assert len(state.ledger.to_dict()["corrections"]) == 2
    assert (
        state.ledger.outcome_of("dec-1")["latest_correction_id"]
        == accepted_b.ledger_bindings[0]["basis_id"]
    )


def test_runtime_schema_rejects_documented_but_incomplete_receipt():
    env = envelope(
        {"schema_version": "1.0", "claims": []},
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    receipt = IngestionEngine().ingest(env, state=kernel())
    assert receipt.status == "rejected"
    assert "required property" in receipt.failure_reason


def test_academic_receipt_rejects_empty_claim_text():
    for claim_text in ("", " \t "):
        payload = evidence_payload(claim_text)
        receipt = IngestionEngine().ingest(
            envelope(
                payload,
                "academic-source-verification",
                "evidence-receipt-1.0",
            ),
            state=kernel(),
        )
        assert receipt.status == "rejected"
        assert "claim" in receipt.failure_reason
        assert (
            "nonblank" in receipt.failure_reason
            or "non-empty" in receipt.failure_reason
        )


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


def test_wrapped_canonical_works_use_the_full_runtime_schema():
    for payload in ({"canonical_work": {}}, {"works": [{}]}):
        receipt = IngestionEngine().ingest(
            envelope(
                payload,
                "literature-analysis",
                "canonical-work-1.0",
            ),
            state=kernel(),
        )
        assert receipt.status == "rejected"
        assert "not valid under any" in receipt.failure_reason


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
    screening_object = next(
        value for value in state.objects.values()
        if value["kind"] == "screening_result"
    )
    assert screening_object["screening_source_id"] == "record-1"
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
    extraction = next(
        value
        for value in state.objects.values()
        if value["kind"] == "study_extraction"
    )
    assert extraction["study_id"] == "study-1"
    assert extraction["effect"] == 0.42
    screening = next(
        value for value in state.objects.values()
        if value["kind"] == "screening_result"
    )
    assert screening["screening_source_id"] == "study-1"
    assert screening["decision"] == "include"


def test_study_extractions_are_scoped_to_each_review_artifact():
    state = kernel()
    first = envelope(
        {
            "included_studies": [{"study_id": "study-1", "effect": 0.42}],
            "screening_results": [
                {"record_id": "record-1", "decision": "include"}
            ],
        },
        "systematic-review-meta-analysis",
        "screening-matrix-1.0",
    )
    second = envelope(
        {
            "included_studies": [{"study_id": "study-1", "effect": 0.73}],
            "screening_results": [
                {"record_id": "record-1", "decision": "exclude"}
            ],
        },
        "systematic-review-meta-analysis",
        "screening-matrix-1.0",
    )

    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)
    extractions = [
        value
        for value in state.objects.values()
        if value["kind"] == "study_extraction"
    ]
    screenings = [
        value
        for value in state.objects.values()
        if value["kind"] == "screening_result"
    ]

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(extractions) == 2
    assert {item["study_id"] for item in extractions} == {"study-1"}
    assert {item["effect"] for item in extractions} == {0.42, 0.73}
    assert len(screenings) == 2
    assert {item["screening_source_id"] for item in screenings} == {"record-1"}
    assert {item["decision"] for item in screenings} == {"include", "exclude"}


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

    missing_source = ceg_mod.ClaimEvidenceGraph(graph_id="receipt-missing-at-export")
    missing_source.add_claim("claim-1", "A verified claim", target_work_id="work:A")
    missing_source.add_evidence(
        "evidence-1",
        "evidence_receipt",
        source_work_id="work:A",
        receipt_ref=ref,
    )
    missing_source.add_support_edge(
        "evidence-1",
        "claim-1",
        "supported",
        receipt_ref=ref,
    )
    target = kernel()
    target.register_receipt(payload_sha, physical)
    snapshot_receipt = IngestionEngine().ingest(
        envelope(
            missing_source.to_dict(),
            "claim-evidence-graph",
            "claim-evidence-graph-1.0",
            artifact_kind="ceg_snapshot",
        ),
        state=target,
    )
    assert snapshot_receipt.status == "accepted"
    assert not [item for item in target.uncertainties if item["kind"] == "missing_receipt"]


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

    rekeyed = copy.deepcopy(snapshot)
    old_key, cached_receipt = rekeyed["ingestion_receipts"].popitem()
    other_context = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:other"],
    ).ingestion_context_digest()
    rekeyed["ingestion_receipts"][f"{env.artifact_id}:{other_context}"] = cached_receipt
    unsigned = {key: value for key, value in rekeyed.items() if key != "snapshot_digest"}
    rekeyed["snapshot_digest"] = compute_sha256(canonical_json_bytes(unsigned))
    with pytest.raises(ValueError, match="context"):
        IngestionKernelState.from_dict(
            rekeyed,
            ceg_cls=ceg_mod.ClaimEvidenceGraph,
            ledger_cls=ledger_mod.DecisionLedger,
        )

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
    response, verified = call_tool(
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
    assert "error" not in verified
    assert response["result"]["isError"] is False
    assert ingested.status == "accepted"


def test_envelope_lineage_reference_is_preserved_verified_and_resolved():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    physical = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id=physical["receipt_id"],
        receipt_digest=physical["receipt_digest"],
    )
    source = envelope(
        {"value": 1},
        "unknown-producer",
        "unknown-schema-1.0",
        lineage_ref=ref,
    )
    state = kernel()
    engine = IngestionEngine()

    unresolved = engine.ingest(source, state=state)
    assert unresolved.status == "accepted"
    assert unresolved.source_lineage_ref == ref
    assert [item["kind"] for item in state.uncertainties] == ["missing_receipt"]

    physical_receipt = engine.ingest(
        envelope(
            physical,
            "research-object-identity",
            "lineage-receipt-1.0",
            artifact_kind="lineage_receipt",
        ),
        state=state,
    )
    assert physical_receipt.status == "accepted"
    assert not [
        item
        for item in state.uncertainties
        if item.get("metadata", {}).get("kernel_origin") == "envelope_lineage"
    ]

    mismatched_ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id=physical["receipt_id"],
        receipt_digest="0" * 64,
    )
    mismatch_state = kernel()
    mismatch_state.register_receipt(physical["receipt_id"], physical)
    mismatch = engine.ingest(
        envelope(
            {"value": 2},
            "unknown-producer",
            "unknown-schema-1.0",
            lineage_ref=mismatched_ref,
        ),
        state=mismatch_state,
    )
    assert mismatch.status == "rejected"
    assert "lineage_ref verification failed" in mismatch.failure_reason


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
    screenings = {
        value["screening_source_id"]: value
        for value in state.objects.values()
        if value["kind"] == "screening_result"
    }
    assert screenings["report-a"]["decision"] == "include"
    assert screenings["report-b"]["decision"] == "exclude"


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


def test_lineage_evidence_identity_includes_envelope_locator():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    payload = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    first = envelope(
        payload,
        "research-object-identity",
        "lineage-receipt-1.0",
        artifact_kind="lineage_receipt",
        locator="store:a",
    )
    second = envelope(
        payload,
        "research-object-identity",
        "lineage-receipt-1.0",
        artifact_kind="lineage_receipt",
        locator="store:b",
    )
    state = kernel()
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.ceg.evidence_anchors) == 2
    assert {item.locator for item in state.ceg.evidence_anchors.values()} == {
        "store:a",
        "store:b",
    }


def test_retraction_event_identity_includes_resolved_target_work():
    payload = {"is_retracted": None, "signals": []}
    first = envelope(
        payload,
        "retraction-watch",
        "retraction-delta-1.0",
        subject_refs=["work:A"],
    )
    second = envelope(
        payload,
        "retraction-watch",
        "retraction-delta-1.0",
        subject_refs=["work:B"],
    )
    state = kernel()
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.objects) == 2
    assert {item["target_work_id"] for item in state.objects.values()} == {
        "work:A",
        "work:B",
    }
    assert {item["subject_id"] for item in state.uncertainties} == {"work:A", "work:B"}


def test_claim_evidence_validate_reports_integrity_failure_as_validation_result():
    graph = ceg_mod.ClaimEvidenceGraph("tampered")
    graph.add_claim("claim-1", "Claim")
    exported = graph.to_dict()
    exported["graph_digest"] = "f" * 64

    response, body = call_tool("claim_evidence_validate", {"graph": exported})

    assert response["result"]["isError"] is False
    assert body["valid"] is False
    assert any("tamper" in error.lower() or "digest" in error.lower() for error in body["errors"])


def test_claim_evidence_trace_returns_supporting_and_refuting_anchors():
    graph = ceg_mod.ClaimEvidenceGraph("complete-trace")
    graph.add_claim("claim-1", "Claim")
    graph.add_evidence("support-1", "direct_observation", locator="table:1")
    graph.add_evidence("refute-1", "direct_observation", locator="table:2")
    graph.add_support_edge("support-1", "claim-1", "supported")
    graph.add_support_edge("refute-1", "claim-1", "contradicted")

    _, body = call_tool(
        "claim_evidence_trace",
        {"graph": graph.to_dict(), "claim_id": "claim-1"},
    )

    assert [item["evidence_id"] for item in body["support"]] == ["support-1"]
    assert [item["evidence_id"] for item in body["contradictions"]] == ["refute-1"]


def test_truncated_retraction_check_creates_coverage_uncertainty():
    env = envelope(
        {
            "is_retracted": False,
            "signals": [],
            "current_observation": False,
            "verification_status": "verified_current",
            "truncated": True,
        },
        "retraction-watch",
        "retraction-delta-1.0",
        subject_refs=["doi:10.1000/example"],
    )
    receipt = IngestionEngine().ingest(env, state=kernel())

    assert receipt.status == "accepted"
    assert len(receipt.uncertainties) == 1
    assert "truncated" in receipt.uncertainties[0]["reason"]

    confirmed = IngestionEngine().ingest(
        envelope(
            {
                "is_retracted": True,
                "signals": ["retraction"],
                "current_observation": True,
                "verification_status": "verified_current",
                "truncated": True,
            },
            "retraction-watch",
            "retraction-delta-1.0",
            subject_refs=["doi:10.1000/confirmed"],
        ),
        state=kernel(),
    )
    assert confirmed.status == "accepted"
    assert {item["kind"] for item in confirmed.uncertainties} == {
        "publication_status_change",
        "retraction_alert",
    }


def test_unknown_screening_decision_is_rejected_fail_closed():
    env = envelope(
        {"screening_results": [{"record_id": "record-1", "decision": "incldue"}]},
        "systematic-review-meta-analysis",
        "screening-matrix-1.0",
    )
    receipt = IngestionEngine().ingest(env, state=kernel())

    assert receipt.status == "rejected"
    assert "include, exclude, or maybe" in receipt.failure_reason


def test_incremental_ceg_mutation_persists_derived_uncertainty():
    payload = evidence_payload()
    payload["claims"][0]["support_status"] = "unverifiable"
    env = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:uncertain"],
    )
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)

    assert receipt.status == "accepted"
    assert [item["kind"] for item in state.uncertainties] == ["unverifiable_claim"]
    assert [item["kind"] for item in receipt.uncertainties] == ["unverifiable_claim"]
    assert receipt.output_digests == state.compute_digests()


def test_resolved_domain_uncertainty_is_removed_from_kernel_queue():
    payload = evidence_payload("Receipt-backed claim")
    payload_sha = compute_sha256(canonical_json_bytes(payload))
    claim_digest = canonical_evidence_claim_digest(payload["claims"][0])
    graph = ceg_mod.ClaimEvidenceGraph("eventual-receipt")
    graph.add_claim("claim-1", "Receipt-backed claim")
    graph.add_evidence(
        "evidence-1",
        "evidence_receipt",
        receipt_ref=ReceiptRef(
            kind="academic_evidence",
            schema_version="1.0",
            claim_digest=claim_digest,
            payload_sha256=payload_sha,
        ),
    )
    graph.add_support_edge("evidence-1", "claim-1", "supported")
    snapshot = envelope(
        graph.to_dict(),
        "claim-evidence-graph",
        "claim-evidence-graph-1.0",
    )
    state = kernel()
    engine = IngestionEngine()

    first = engine.ingest(snapshot, state=state)
    missing_id = next(
        item["item_id"]
        for item in state.uncertainties
        if item["kind"] == "missing_receipt"
    )
    receipt_env = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    second = engine.ingest(receipt_env, state=state)

    assert first.status == "accepted"
    assert second.status == "accepted"
    assert missing_id not in {item["item_id"] for item in state.uncertainties}
    assert not [
        item for item in state.ceg.extract_uncertainties()
        if item.kind == "missing_receipt"
    ]

    state.add_uncertainty({
        "item_id": "manual-missing-receipt",
        "subject_id": "manual-audit",
        "kind": "missing_receipt",
        "reason": "Explicit manual audit finding",
        "needs_human": True,
    })
    opaque = engine.ingest(
        envelope(
            {"text": "unrelated"},
            "unknown-producer",
            "unknown-schema-1.0",
        ),
        state=state,
    )
    assert opaque.status == "accepted"
    assert "manual-missing-receipt" in {
        item["item_id"] for item in state.uncertainties
    }


def test_evidence_verdicts_share_one_semantic_claim_node():
    supported = evidence_payload("One proposition")
    contradicted = evidence_payload("One proposition")
    contradicted["claims"][0]["source"] = "doi:10.1000/independent"
    contradicted["claims"][0]["support_status"] = "contradicted"
    state = kernel()

    receipts, _ = IngestionEngine().batch_ingest(
        [
            envelope(
                supported,
                "academic-source-verification",
                "evidence-receipt-1.0",
                subject_refs=["work:shared"],
            ),
            envelope(
                contradicted,
                "academic-source-verification",
                "evidence-receipt-1.0",
                subject_refs=["work:shared"],
            ),
        ],
        state=state,
    )

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.ceg.claims) == 1
    assert len(state.ceg.evidence_anchors) == 2
    claim_ids = {edge.claim_id for edge in state.ceg.support_edges}
    assert len(claim_ids) == 1
    assert {edge.support_status for edge in state.ceg.support_edges} == {
        "supported",
        "contradicted",
    }


def test_quantitative_evidence_uses_contextual_128_bit_identity():
    payload = {
        "reported": 1.0,
        "recomputed": 1.0,
        "formula": "x",
        "library": "reference",
    }
    first = envelope(
        payload,
        "quantitative-paper-audit",
        "quantitative-audit-1.0",
        locator="table:1",
    )
    second = envelope(
        payload,
        "quantitative-paper-audit",
        "quantitative-audit-1.0",
        locator="table:2",
    )
    state = kernel()
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.ceg.evidence_anchors) == 2
    for evidence_id in state.ceg.evidence_anchors:
        assert evidence_id.startswith("ev-quant-")
        assert len(evidence_id.removeprefix("ev-quant-")) == 32


def test_academic_evidence_reuses_richer_existing_work_object():
    state = kernel()
    original = {"id": "work:stable", "kind": "work", "title": "Canonical title"}
    state.register_object("work:stable", original)
    env = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=["work:stable"],
    )
    receipt = IngestionEngine().ingest(env, state=state)

    assert receipt.status == "accepted"
    assert dict(state.objects["work:stable"]) == original


def test_reproduction_evidence_identity_includes_envelope_locator():
    payload = {
        "kind": "ReproductionReceipt",
        "schema_version": "1.0",
        "status": "blocked",
        "tier": "runs",
        "paper": {"title": "Example"},
        "repository": None,
        "stages": [],
        "contradictions": [],
        "blocking": ["data"],
        "gaps": [],
        "generated_at": "2026-09-20T00:00:00Z",
    }
    first = envelope(
        payload,
        "research-reproducibility",
        "reproduction-receipt-1.0",
        locator="run:a",
    )
    second = envelope(
        payload,
        "research-reproducibility",
        "reproduction-receipt-1.0",
        locator="run:b",
    )
    state = kernel()
    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.ceg.evidence_anchors) == 2


def test_ceg_snapshot_projects_missingness_per_receipt_reference():
    present_payload = evidence_payload("Present receipt")
    missing_payload = evidence_payload("Missing at export")
    present_sha = compute_sha256(canonical_json_bytes(present_payload))
    missing_sha = compute_sha256(canonical_json_bytes(missing_payload))
    present_ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=canonical_evidence_claim_digest(present_payload["claims"][0]),
        payload_sha256=present_sha,
    )
    missing_ref = ReceiptRef(
        kind="academic_evidence",
        schema_version="1.0",
        claim_digest=canonical_evidence_claim_digest(missing_payload["claims"][0]),
        payload_sha256=missing_sha,
    )
    source = ceg_mod.ClaimEvidenceGraph("per-reference-receipts")
    source.register_receipt(present_sha, present_payload)
    source.add_claim("claim-1", "Claim")
    source.add_evidence(
        "evidence-1",
        "evidence_receipt",
        receipt_ref=present_ref,
    )
    source.add_support_edge(
        "evidence-1",
        "claim-1",
        "supported",
        receipt_ref=missing_ref,
    )
    snapshot = source.to_dict()
    assert len([
        item for item in snapshot["uncertainties"]
        if item["kind"] == "missing_receipt"
    ]) == 1

    target = kernel()
    target.register_receipt(present_sha, present_payload)
    target.register_receipt(missing_sha, missing_payload)
    receipt = IngestionEngine().ingest(
        envelope(
            snapshot,
            "claim-evidence-graph",
            "claim-evidence-graph-1.0",
            artifact_kind="ceg_snapshot",
        ),
        state=target,
    )

    assert receipt.status == "accepted"
    assert not [
        item for item in target.uncertainties
        if item["kind"] == "missing_receipt"
    ]


def test_preflight_rejects_mismatched_envelope_lineage_reference():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    physical = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    mismatched_ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id=physical["receipt_id"],
        receipt_digest="0" * 64,
    )
    env = envelope(
        {"text": "lineage-bound artifact"},
        "unknown-producer",
        "unknown-schema-1.0",
        lineage_ref=mismatched_ref,
    )

    _, body = call_tool(
        "research_artifact_validate",
        {
            "envelope": env.to_dict(),
            "receipts": {physical["receipt_id"]: physical},
        },
    )

    assert body["valid"] is False
    assert any("lineage_ref verification failed" in error for error in body["errors"])


def test_retained_prior_positive_retraction_keeps_alert_and_coverage_gap():
    receipt = IngestionEngine().ingest(
        envelope(
            {
                "is_retracted": True,
                "signals": [],
                "current_observation": None,
                "verification_status": "retained_prior",
            },
            "retraction-watch",
            "retraction-delta-1.0",
            subject_refs=["doi:10.1000/prior-retraction"],
        ),
        state=kernel(),
    )

    assert receipt.status == "accepted"
    assert {item["kind"] for item in receipt.uncertainties} == {
        "publication_status_change",
        "retraction_alert",
    }


def test_manuscript_objects_are_scoped_to_envelope_context():
    payload = {"text": "Same immutable manuscript payload"}
    first = envelope(
        payload,
        "academic-writing",
        "manuscript-opaque-1.0",
        artifact_kind="opaque_manuscript",
        locator="section:one",
    )
    second = envelope(
        payload,
        "academic-writing",
        "manuscript-opaque-1.0",
        artifact_kind="opaque_manuscript",
        locator="section:two",
    )
    assert first.artifact_id == second.artifact_id
    state = kernel()

    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    manuscripts = [
        value for value in state.objects.values()
        if value["kind"] == "opaque_manuscript"
    ]
    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(manuscripts) == 2
    assert {item["locator"] for item in manuscripts} == {"section:one", "section:two"}


def test_math_evidence_preserves_and_binds_effective_locator():
    state = kernel()
    state.ceg.add_claim("claim-1", "Computed claim")
    payload = {"expression": "x + 1", "result": 2, "verified": True}
    first = envelope(
        payload,
        "math-computation",
        "computation-receipt-1.0",
        locator="equation:one",
    )
    second = envelope(
        payload,
        "math-computation",
        "computation-receipt-1.0",
        locator="equation:two",
    )
    payload_locator = envelope(
        {**payload, "locator": "equation:payload"},
        "math-computation",
        "computation-receipt-1.0",
        locator="equation:ignored-envelope",
    )

    receipts, _ = IngestionEngine().batch_ingest(
        [first, second, payload_locator],
        state=state,
        bindings_list=[{"claim_id": "claim-1"}] * 3,
    )

    assert [item.status for item in receipts] == ["accepted"] * 3
    assert {item.locator for item in state.ceg.evidence_anchors.values()} == {
        "equation:one",
        "equation:two",
        "equation:payload",
    }


def test_multi_claim_receipt_adds_one_explicitly_selected_correction():
    payload = evidence_payload("First claim")
    payload["claims"].append({
        "claim": "Second claim",
        "evidence_type": "computed",
        "source": "doi:10.1000/second",
        "support_status": "supported",
    })
    selected_digest = canonical_evidence_claim_digest(payload["claims"][1])
    env = envelope(
        payload,
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    state = kernel()
    state.ledger.add_decision("decision-1", "Decision", decision_action="commit")
    common_binding = {
        "action": "add_outcome_correction",
        "decision_id": "decision-1",
        "verdict": "positive",
        "rationale": "Explicit correction",
    }
    engine = IngestionEngine()

    ambiguous = engine.ingest(env, state=state, bindings=common_binding)
    selected = engine.ingest(
        env,
        state=state,
        bindings={**common_binding, "claim_digest": selected_digest},
    )
    corrections = state.ledger.to_dict()["corrections"]

    assert ambiguous.status == "rejected"
    assert "claim_digest" in ambiguous.failure_reason
    assert selected.status == "accepted"
    assert len(corrections) == 1
    assert corrections[0]["receipt_ref"]["claim_digest"] == selected_digest


def test_literature_artifact_rejects_conflicting_duplicate_work_ids():
    env = envelope(
        {
            "works": [
                {
                    "work_id": "work:duplicate",
                    "work_type": "article",
                    "title": "First metadata record",
                    "authors": [],
                },
                {
                    "work_id": "work:duplicate",
                    "work_type": "article",
                    "title": "Conflicting metadata record",
                    "authors": [],
                },
            ],
        },
        "literature-analysis",
        "corpus-matrix-1.0",
    )
    state = kernel()

    receipt = IngestionEngine().ingest(env, state=state)

    assert receipt.status == "rejected"
    assert "Conflicting canonical work entries" in receipt.failure_reason
    assert not state.objects


def test_mcp_lineage_trace_rejects_malformed_entities_and_edges():
    malformed_graphs = [
        {"entities": [{}], "activities": [], "edges": []},
        {
            "entities": [],
            "activities": [],
            "edges": [{"type": "used"}],
        },
    ]

    for graph in malformed_graphs:
        response, body = call_tool(
            "research_lineage_trace",
            {"lineage_graph": graph, "target_entity_id": "result"},
        )
        assert response["result"]["isError"] is True
        assert body["error"] == "Invalid tool arguments"
        assert any("required" in detail for detail in body["details"])


def test_literature_watch_rejects_conflicting_ids_before_plan_overwrite():
    payloads = [
        {
            "new_papers": [
                {"id": "record-1", "title": "First"},
                {"id": "record-1", "title": "Conflicting"},
            ],
        },
        {
            "new_papers": [{"id": "record-1", "title": "Paper"}],
            "new_citations": [{"id": "record-1", "citing": "Other"}],
        },
    ]

    for payload in payloads:
        receipt = IngestionEngine().ingest(
            envelope(
                payload,
                "literature-watch",
                "literature-delta-1.0",
            ),
            state=kernel(),
        )
        assert receipt.status == "rejected"
        assert "Conflicting planned ResearchObject" in receipt.failure_reason


def test_cross_review_evidence_is_scoped_to_envelope_locator():
    payload = {"contradictions": [{"summary": "Disputed point"}]}
    first = envelope(
        payload,
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
        locator="review:one",
    )
    second = envelope(
        payload,
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
        locator="review:two",
    )
    state = kernel()

    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(state.ceg.evidence_anchors) == 2
    assert {item.locator for item in state.ceg.evidence_anchors.values()} == {
        "review:one",
        "review:two",
    }


def test_mcp_lineage_trace_rejects_unknown_node_types_as_arguments():
    malformed_graphs = [
        {
            "entities": [{"id": "entity-1", "type": "bogus"}],
            "activities": [],
            "edges": [],
        },
        {
            "entities": [],
            "activities": [{
                "id": "activity-1",
                "type": "bogus",
                "timestamp": "2026-09-20T00:00:00Z",
            }],
            "edges": [],
        },
    ]

    for graph in malformed_graphs:
        response, body = call_tool(
            "research_lineage_trace",
            {"lineage_graph": graph, "target_entity_id": "result"},
        )
        assert response["result"]["isError"] is True
        assert body["error"] == "Invalid tool arguments"
        assert any("not one of" in detail for detail in body["details"])


def test_cross_review_fallback_reasons_are_canonical_json():
    first_item = {"zeta": 1, "alpha": {"right": 2, "left": 1}}
    second_item = {"alpha": {"left": 1, "right": 2}, "zeta": 1}
    first = envelope(
        {"contradictions": [first_item]},
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
    )
    second = envelope(
        {"contradictions": [second_item]},
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
    )
    assert first.artifact_id == second.artifact_id

    first_receipt = IngestionEngine().ingest(first, state=kernel())
    second_receipt = IngestionEngine().ingest(second, state=kernel())

    assert first_receipt.status == second_receipt.status == "accepted"
    assert first_receipt.receipt_id == second_receipt.receipt_id
    assert first_receipt.uncertainties[0]["reason"] == (
        '{"alpha":{"left":1,"right":2},"zeta":1}'
    )
    assert first_receipt.uncertainties == second_receipt.uncertainties


def test_receipt_verify_returns_invalid_for_incomplete_lineage_payload():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    physical = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    ref = {
        "kind": "lineage",
        "schema_version": "lineage-receipt-1.0",
        "receipt_id": physical["receipt_id"],
        "receipt_digest": physical["receipt_digest"],
    }
    incomplete = copy.deepcopy(physical)
    incomplete.pop("verification_status")

    response, body = call_tool(
        "research_receipt_verify",
        {"receipt_ref": ref, "receipt_payload": incomplete},
    )

    assert response["result"]["isError"] is True
    assert body["valid"] is False
    assert "verification_status" in body["error"]
    assert "Internal execution failure" not in body["error"]


def test_falsy_registered_lineage_receipt_is_rejected_not_treated_as_missing():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    physical = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    ref = ReceiptRef(
        kind="lineage",
        schema_version="lineage-receipt-1.0",
        receipt_id=physical["receipt_id"],
        receipt_digest=physical["receipt_digest"],
    )
    env = envelope(
        {"text": "artifact"},
        "unknown-producer",
        "unknown-schema-1.0",
        lineage_ref=ref,
    )
    state = kernel()
    state.register_receipt(physical["receipt_id"], {})

    receipt = IngestionEngine().ingest(env, state=state)
    _, preflight = call_tool(
        "research_artifact_validate",
        {
            "envelope": env.to_dict(),
            "receipts": {physical["receipt_id"]: {}},
        },
    )

    assert receipt.status == "rejected"
    assert "invalid protocol" in receipt.failure_reason
    assert preflight["valid"] is False
    assert any("invalid protocol" in error for error in preflight["errors"])


def test_canonical_work_upgrades_an_evidence_placeholder():
    work_id = "work:placeholder-upgrade"
    state = kernel()
    evidence = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
        subject_refs=[work_id],
    )
    canonical = {
        "work_id": work_id,
        "work_type": "article",
        "title": "Canonical metadata",
        "authors": [{"family": "Example"}],
    }
    canonical_env = envelope(
        canonical,
        "literature-analysis",
        "canonical-work-1.0",
        producer_version="1.3.0",
    )
    engine = IngestionEngine()

    first = engine.ingest(evidence, state=state)
    second = engine.ingest(canonical_env, state=state)

    assert first.status == "accepted"
    assert second.status == "accepted"
    assert state.to_dict()["objects"][work_id] == canonical


def test_opaque_fallback_objects_are_scoped_to_full_envelope_context():
    payload = {"value": "same bytes"}
    first = envelope(
        payload,
        "unknown-producer-a",
        "unknown-schema-1.0",
        artifact_kind="classification-a",
    )
    second = envelope(
        payload,
        "unknown-producer-b",
        "unknown-schema-1.0",
        artifact_kind="classification-b",
    )
    assert first.artifact_id == second.artifact_id
    state = kernel()

    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    opaque_objects = [
        value for value in state.objects.values()
        if value["kind"] == "opaque_artifact"
    ]
    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(opaque_objects) == 2
    assert {item["artifact_kind"] for item in opaque_objects} == {
        "classification-a",
        "classification-b",
    }


def test_dissenting_opinion_reasons_are_canonical_json():
    first = envelope(
        {
            "contradictions": [],
            "dissenting_opinions": [{"zeta": 1, "alpha": {"b": 2, "a": 1}}],
        },
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
    )
    second = envelope(
        {
            "dissenting_opinions": [{"alpha": {"a": 1, "b": 2}, "zeta": 1}],
            "contradictions": [],
        },
        "cross-review-five",
        "cross-review-2.0",
        producer_version="2.0.0",
    )
    assert first.artifact_id == second.artifact_id

    first_receipt = IngestionEngine().ingest(first, state=kernel())
    second_receipt = IngestionEngine().ingest(second, state=kernel())

    assert first_receipt.status == second_receipt.status == "accepted"
    assert first_receipt.receipt_id == second_receipt.receipt_id
    assert first_receipt.uncertainties[0]["reason"] == (
        '{"alpha":{"a":1,"b":2},"zeta":1}'
    )


def test_preflight_reports_planning_collisions_as_validation_errors():
    env = envelope(
        {
            "new_papers": [
                {"id": "duplicate", "title": "First"},
                {"id": "duplicate", "title": "Conflicting"},
            ],
        },
        "literature-watch",
        "literature-delta-1.0",
    )

    response, body = call_tool(
        "research_artifact_validate",
        {"envelope": env.to_dict()},
    )

    assert response["result"]["isError"] is False
    assert body["valid"] is False
    assert any("Conflicting planned ResearchObject" in error for error in body["errors"])


def test_manuscript_objects_include_producer_version_context():
    payload = {"text": "Same manuscript"}
    first = envelope(
        payload,
        "academic-writing",
        "manuscript-opaque-1.0",
        artifact_kind="opaque_manuscript",
        producer_version="1.0.0",
    )
    second = envelope(
        payload,
        "academic-writing",
        "manuscript-opaque-1.0",
        artifact_kind="opaque_manuscript",
        producer_version="1.1.0",
    )
    assert first.artifact_id == second.artifact_id
    state = kernel()

    receipts, _ = IngestionEngine().batch_ingest([first, second], state=state)

    manuscripts = [
        value for value in state.objects.values()
        if value["kind"] == "opaque_manuscript"
    ]
    assert [item.status for item in receipts] == ["accepted", "accepted"]
    assert len(manuscripts) == 2
    assert {item["producer"]["version"] for item in manuscripts} == {
        "1.0.0",
        "1.1.0",
    }


def test_doi_retraction_targets_the_canonical_work_identity():
    canonical = {
        "work_type": "article",
        "title": "Retracted work",
        "authors": [],
        "doi": "10.1000/example",
    }
    state = kernel()
    engine = IngestionEngine()
    work_receipt = engine.ingest(
        envelope(
            canonical,
            "literature-analysis",
            "canonical-work-1.0",
            producer_version="1.3.0",
        ),
        state=state,
    )
    retraction_receipt = engine.ingest(
        envelope(
            {
                "doi": " 10.1000/EXAMPLE ",
                "is_retracted": True,
                "signals": ["retraction"],
            },
            "retraction-watch",
            "retraction-delta-1.0",
        ),
        state=state,
    )
    status_object = next(
        value for value in state.objects.values()
        if value.get("kind") == "publication_status_observation"
    )

    assert work_receipt.status == "accepted"
    assert retraction_receipt.status == "accepted"
    assert status_object["target_work_id"] == "work:doi:10.1000/example"
    assert {item["subject_id"] for item in retraction_receipt.uncertainties} == {
        "work:doi:10.1000/example"
    }


def test_doi_resolver_forms_converge_across_all_scholarly_adapters():
    canonical = {
        "work_type": "article",
        "title": "Resolver-form work",
        "authors": [],
        "doi": "HTTPS://DOI.ORG/10.1000/EXAMPLE",
    }
    evidence = evidence_payload()
    evidence["identifiers"] = {"doi": "doi:10.1000/EXAMPLE"}
    state = kernel()
    engine = IngestionEngine()

    work_receipt = engine.ingest(
        envelope(
            canonical,
            "literature-analysis",
            "canonical-work-1.0",
            producer_version="1.3.0",
        ),
        state=state,
    )
    evidence_receipt = engine.ingest(
        envelope(
            evidence,
            "academic-source-verification",
            "evidence-receipt-1.0",
        ),
        state=state,
    )
    retraction_receipt = engine.ingest(
        envelope(
            {
                "doi": "http://dx.doi.org/10.1000/Example",
                "is_retracted": None,
                "signals": [],
            },
            "retraction-watch",
            "retraction-delta-1.0",
        ),
        state=state,
    )

    assert [work_receipt.status, evidence_receipt.status, retraction_receipt.status] == [
        "accepted",
        "accepted",
        "accepted",
    ]
    assert "work:doi:10.1000/example" in state.objects
    assert {claim.target_work_id for claim in state.ceg.claims.values()} == {
        "work:doi:10.1000/example"
    }
    status_object = next(
        value
        for value in state.objects.values()
        if value.get("kind") == "publication_status_observation"
    )
    assert status_object["target_work_id"] == "work:doi:10.1000/example"


def test_cross_artifact_object_collisions_distinguish_json_boolean_and_number():
    first = envelope(
        {"new_papers": [{"id": "same-paper", "value": 1}]},
        "literature-watch",
        "literature-delta-1.0",
    )
    second = envelope(
        {"new_papers": [{"id": "same-paper", "value": True}]},
        "literature-watch",
        "literature-delta-1.0",
    )
    state = kernel()
    engine = IngestionEngine()

    accepted = engine.ingest(first, state=state)
    rejected = engine.ingest(second, state=state)

    assert accepted.status == "accepted"
    assert rejected.status == "rejected"
    assert "ResearchObject ID collision" in rejected.failure_reason
    assert state.objects["same-paper"]["value"] == 1
    assert type(state.objects["same-paper"]["value"]) is int


def test_cached_receipt_rejects_missing_recorded_mutations_on_replay():
    state = kernel()
    state.ledger.add_decision("decision-1", "Decision", decision_action="commit")
    env = envelope(
        evidence_payload(),
        "academic-source-verification",
        "evidence-receipt-1.0",
    )
    receipt = IngestionEngine().ingest(
        env,
        state=state,
        bindings={
            "action": "add_outcome_correction",
            "decision_id": "decision-1",
            "verdict": "positive",
            "rationale": "verified",
        },
    )
    assert receipt.status == "accepted"

    object_missing = state.clone()
    object_missing.objects.pop(receipt.created_or_reused_objects[0])
    with pytest.raises(ValueError, match="missing ResearchObject"):
        IngestionKernelState.from_dict(
            object_missing.to_dict(),
            ceg_cls=ceg_mod.ClaimEvidenceGraph,
            ledger_cls=ledger_mod.DecisionLedger,
        )

    ceg_missing = state.clone()
    ceg_missing.ceg.claims.clear()
    ceg_missing.ceg.evidence_anchors.clear()
    ceg_missing.ceg.support_edges.clear()
    ceg_missing.ceg._all_node_ids.clear()
    ceg_missing.ceg._support_edge_keys.clear()
    with pytest.raises(ValueError, match="missing CEG node"):
        IngestionKernelState.from_dict(
            ceg_missing.to_dict(),
            ceg_cls=ceg_mod.ClaimEvidenceGraph,
            ledger_cls=ledger_mod.DecisionLedger,
        )

    ledger_missing = state.clone()
    ledger_missing.ledger._corrections.clear()
    ledger_missing.ledger._corrections_by_decision.clear()
    with pytest.raises(ValueError, match="missing Ledger binding"):
        IngestionKernelState.from_dict(
            ledger_missing.to_dict(),
            ceg_cls=ceg_mod.ClaimEvidenceGraph,
            ledger_cls=ledger_mod.DecisionLedger,
        )


def test_cached_ledger_snapshot_tracks_every_mutation_family():
    source = ledger_mod.DecisionLedger("snapshot-ledger")
    source.add_decision("decision-1", "Primary", decision_action="commit")
    source.add_decision("decision-2", "Alternative", decision_action="explore")
    source.add_fork("decision-1", "decision-2", "considered")
    source.add_state_event("decision-1", "active")
    source.add_outcome_correction("decision-1", "positive", "verified")
    state = kernel()

    receipt = IngestionEngine().ingest(
        envelope(
            source.to_dict(),
            "decision-ledger",
            "decision-ledger-1.0",
            artifact_kind="decision_ledger_snapshot",
        ),
        state=state,
    )

    assert receipt.status == "accepted"
    assert {binding["binding_kind"] for binding in receipt.ledger_bindings} == {
        "ledger_decision",
        "ledger_fork",
        "ledger_state_event",
        "outcome_correction",
    }

    fork_missing = state.clone()
    fork_missing.ledger._forks.clear()
    valid, errors = fork_missing.validate_invariants()
    assert valid is False
    assert any("missing Ledger binding" in error for error in errors)

    event_missing = state.clone()
    event_missing.ledger._state_events.clear()
    event_missing.ledger._state_events_by_decision.clear()
    valid, errors = event_missing.validate_invariants()
    assert valid is False
    assert any("missing Ledger binding" in error for error in errors)

    correction_missing = state.clone()
    correction_missing.ledger._corrections.clear()
    correction_missing.ledger._corrections_by_decision.clear()
    valid, errors = correction_missing.validate_invariants()
    assert valid is False
    assert any("missing Ledger binding" in error for error in errors)


def test_cached_decision_only_snapshot_cannot_suppress_restoration():
    source = ledger_mod.DecisionLedger("decision-only")
    source.add_decision("decision-1", "Only decision", decision_action="commit")
    state = kernel()
    receipt = IngestionEngine().ingest(
        envelope(
            source.to_dict(),
            "decision-ledger",
            "decision-ledger-1.0",
            artifact_kind="decision_ledger_snapshot",
        ),
        state=state,
    )
    assert receipt.status == "accepted"
    assert receipt.ledger_bindings[0]["binding_kind"] == "ledger_decision"

    state.ledger._decisions.clear()
    valid, errors = state.validate_invariants()

    assert valid is False
    assert any("missing Ledger binding" in error for error in errors)


def test_ledger_snapshot_replay_normalizes_lineage_timestamp_variants():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("entity-1", "data_snapshot")
    earlier = mcp_server.prov_mod.trace_origin(
        graph,
        "entity-1",
        check_on_disk_hashes=False,
    ).to_dict()
    earlier["timestamp"] = "2026-09-20T00:00:00Z"
    later = copy.deepcopy(earlier)
    later["timestamp"] = "2026-09-20T00:00:01Z"

    source = ledger_mod.DecisionLedger()
    source.add_decision("decision-1", "Snapshot decision", decision_action="commit")
    source.register_receipt(later["receipt_id"], later)
    state = kernel()
    state.register_receipt(earlier["receipt_id"], earlier)

    result = IngestionEngine().ingest(
        envelope(
            source.to_dict(),
            "decision-ledger",
            "decision-ledger-1.0",
            artifact_kind="decision_ledger_snapshot",
        ),
        state=state,
    )

    assert result.status == "accepted"
    assert state.ledger.to_dict()["verification_manifest"] == source.to_dict()["verification_manifest"]
    assert state.receipts[earlier["receipt_id"]]["timestamp"] == earlier["timestamp"]

    legacy_snapshot = source.to_dict()
    legacy_snapshot["verification_manifest"][later["receipt_id"]] = (
        ledger_mod._legacy_ledger_payload_sha256(later)
    )
    legacy_snapshot["verification_digest"] = compute_sha256(canonical_json_bytes({
        "ledger_digest": legacy_snapshot["ledger_digest"],
        "receipts": legacy_snapshot["verification_manifest"],
    }))
    legacy_state = kernel()
    legacy_state.register_receipt(later["receipt_id"], later)

    legacy_result = IngestionEngine().ingest(
        envelope(
            legacy_snapshot,
            "decision-ledger",
            "decision-ledger-1.0",
            artifact_kind="decision_ledger_snapshot",
        ),
        state=legacy_state,
    )

    assert legacy_result.status == "accepted"
    assert (
        legacy_state.ledger.to_dict()["verification_manifest"]
        == legacy_snapshot["verification_manifest"]
    )


@pytest.mark.parametrize(
    ("identifiers", "subject_refs", "expected_work_id"),
    [
        ({"doi": " HTTPS://DOI.ORG/10.1000/EXAMPLE "}, [], "work:doi:10.1000/example"),
        ({}, ["doi:10.1000/EXAMPLE"], "work:doi:10.1000/example"),
        ({"arxiv_id": "arXiv:2106.09624"}, [], "work:arxiv:2106.09624"),
        ({"pmid": "PMID:123456"}, [], "work:pmid:123456"),
        ({"openalex_id": "https://openalex.org/w123"}, [], "work:openalex:W123"),
    ],
)
def test_academic_evidence_resolves_canonical_identifier_work_ids(
    identifiers,
    subject_refs,
    expected_work_id,
):
    payload = evidence_payload()
    payload["identifiers"] = identifiers
    state = kernel()

    receipt = IngestionEngine().ingest(
        envelope(
            payload,
            "academic-source-verification",
            "evidence-receipt-1.0",
            subject_refs=subject_refs,
        ),
        state=state,
    )

    assert receipt.status == "accepted"
    assert expected_work_id in state.objects
    assert {claim.target_work_id for claim in state.ceg.claims.values()} == {
        expected_work_id
    }

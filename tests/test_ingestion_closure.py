"""Final-review contract families: identities, lossless sets and observations."""
import copy

import pytest

from test_ingestion_closeout import (
    IngestionEngine, IngestionKernelState, call_tool, ceg_mod, compute_sha256,
    envelope, graph_artifact, kernel, ledger_mod,
)
from ingestion.contracts import validate_adapter_contract, validate_schema
from shared_contracts.evidence import canonical_json_bytes


@pytest.mark.parametrize("collection", ["new_papers", "new_citations"])
@pytest.mark.parametrize("bad_id", [{"a": 1, "b": 2}, ["paper"], 1, False, None, ""])
def test_monitoring_ids_reject_non_string_identity_at_every_boundary(collection, bad_id):
    env = envelope({collection: [{"id": bad_id, "title": "Paper"}]}, "literature-watch", "literature-delta-1.0")
    engine = IngestionEngine()
    adapter = engine.registry.resolve(env)
    assert validate_adapter_contract(env, adapter)
    assert adapter.validate(env)[0] is False
    state = kernel()
    before = state.to_dict()
    assert engine.ingest(env, state=state).status == "rejected"
    assert state.to_dict() == before
    assert call_tool("research_artifact_validate", {"envelope": env.to_dict()})[1]["valid"] is False


@pytest.mark.parametrize("collection", ["new_papers", "new_citations"])
def test_monitoring_fallback_identity_is_order_invariant(collection):
    payloads = [{collection: [{"title": "Paper", "metadata": {"a": 1, "b": 2}}]},
                {collection: [{"metadata": {"b": 2, "a": 1}, "title": "Paper"}]}]
    states = [kernel(), kernel()]
    receipts = [IngestionEngine().ingest(envelope(p, "literature-watch", "literature-delta-1.0"), state=s)
                for p, s in zip(payloads, states)]
    assert all(r.status == "accepted" for r in receipts)
    assert receipts[0].receipt_id == receipts[1].receipt_id
    assert states[0].to_dict() == states[1].to_dict()


@pytest.mark.parametrize("field", ["claims", "evidence_anchors", "support_edges", "claim_relations", "uncertainties"])
def test_ceg_snapshot_duplicate_records_are_rejected_losslessly(field):
    raw = graph_artifact().to_dict()["payload"]
    if field == "uncertainties":
        graph = ceg_mod.ClaimEvidenceGraph()
        graph.add_claim("a", "Claim")
        graph.add_evidence("e", "direct_observation")
        graph.add_support_edge("e", "a", "unverifiable")
        raw = graph.to_dict()
    raw[field].append(copy.deepcopy(raw[field][0]))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        ceg_mod.ClaimEvidenceGraph.from_dict(raw)
    env = envelope(raw, "claim-evidence-graph", "claim-evidence-graph-1.0")
    assert IngestionEngine().registry.resolve(env).validate(env)[0] is False
    state = kernel()
    before = state.to_dict()
    assert IngestionEngine().ingest(env, state=state).status == "rejected"
    assert state.to_dict() == before
    assert call_tool("research_artifact_validate", {"envelope": env.to_dict()})[1]["valid"] is False


def test_kernel_snapshot_cannot_silently_deduplicate_uncertainties():
    state = kernel()
    state.add_uncertainty({"item_id": "warning", "subject_id": "work", "kind": "generic_uncertainty", "reason": "Missing", "needs_human": True})
    raw = state.to_dict()
    raw["uncertainties"].append(copy.deepcopy(raw["uncertainties"][0]))
    raw.pop("snapshot_digest")
    raw["snapshot_digest"] = compute_sha256(canonical_json_bytes(raw))
    with pytest.raises(ValueError):
        IngestionKernelState.from_dict(raw, ceg_cls=ceg_mod.ClaimEvidenceGraph, ledger_cls=ledger_mod.DecisionLedger)


@pytest.mark.parametrize("status", [None, "verified_current", "unverified"])
@pytest.mark.parametrize("retained,current", [(True, False), (False, True), (True, None), (False, None), (None, True), (None, False)])
def test_conflicting_retraction_observations_fail_closed(status, retained, current):
    payload = {"target_work_id": "work:test", "is_retracted": retained, "current_observation": current, "signals": []}
    if status is not None:
        payload["verification_status"] = status
    env = envelope(payload, "retraction-watch", "retraction-delta-1.0")
    engine = IngestionEngine()
    adapter = engine.registry.resolve(env)
    assert validate_adapter_contract(env, adapter)
    assert adapter.validate(env)[0] is False
    state = kernel()
    before = state.to_dict()
    assert engine.ingest(env, state=state).status == "rejected"
    assert state.to_dict() == before
    assert call_tool("research_artifact_validate", {"envelope": env.to_dict()})[1]["valid"] is False


@pytest.mark.parametrize("retained", [False, True])
def test_retained_prior_retraction_is_the_explicit_unknown_current_exception(retained):
    env = envelope({"target_work_id": "work:test", "is_retracted": retained, "current_observation": None,
                    "verification_status": "retained_prior", "signals": []}, "retraction-watch", "retraction-delta-1.0")
    result = IngestionEngine().ingest(env, state=kernel())
    assert result.status == "accepted"
    assert any(u["kind"] == "retraction_alert" for u in result.uncertainties) is retained
    assert any("could not be verified" in u["reason"] for u in result.uncertainties)


@pytest.mark.parametrize("field", ["decisions", "bases", "forks", "state_events", "corrections", "uncertainties"])
def test_ledger_snapshot_duplicate_records_fail_before_replay(field):
    ledger = ledger_mod.DecisionLedger()
    ledger.add_decision("a", "A")
    ledger.add_decision("b", "B")
    ledger.add_decision("negative", "Negative", decision_type="negative_result")
    ledger.add_basis("b", "decision", "a")
    ledger.add_fork("a", "b", "considered")
    ledger.add_state_event("a", "active")
    ledger.add_outcome_correction("a", "positive", "Outcome")
    raw = ledger.to_dict()
    raw[field].append(copy.deepcopy(raw[field][0]))
    with pytest.raises(ValueError, match="[Dd]uplicate"):
        ledger_mod.DecisionLedger.from_dict(raw)


@pytest.mark.parametrize("raw_key", [1, False, None, ""])
def test_all_kernel_and_plan_registries_reject_non_string_keys(raw_key):
    from ingestion.adapters import _PlanObjectRegistry
    for field in ("objects", "receipts", "ingested_artifacts", "ingestion_receipts"):
        with pytest.raises(ValueError, match="Registry key"):
            IngestionKernelState(**{field: {raw_key: {}}})
    with pytest.raises(ValueError, match="Registry key"):
        _PlanObjectRegistry()[raw_key] = {}
    state = kernel()
    for method in (state.register_object, state.register_receipt):
        with pytest.raises(ValueError, match="Registry key"):
            method(raw_key, {})


def test_canonical_bytes_accept_frozen_json_without_changing_numeric_identity():
    from shared_contracts.evidence import FrozenJSONMap
    raw = {"nested": [{"b": 2, "a": 1}], "float": 1.0}
    assert canonical_json_bytes(FrozenJSONMap(raw)) == canonical_json_bytes(raw)
    assert canonical_json_bytes({"x": 1}) != canonical_json_bytes({"x": 1.0})
    assert canonical_json_bytes({"x": 1}) != canonical_json_bytes({"x": True})


def test_distinct_canonical_edge_metadata_survives_producer_consumer_contract():
    graph = ceg_mod.ClaimEvidenceGraph()
    graph.add_claim("a", "A")
    graph.add_evidence("e", "direct_observation")
    for value in (1, 1.0, True):
        graph.add_support_edge("e", "a", "supported", metadata={"value": value})
    raw = graph.to_dict()
    assert len(raw["support_edges"]) == 3
    assert not validate_schema(raw, "claim-evidence-graph.schema.json")
    assert ceg_mod.ClaimEvidenceGraph.from_dict(raw).to_dict() == raw


@pytest.mark.parametrize("field", ["included_studies", "screening_results"])
def test_adjacent_systematic_review_fallback_hashes_frozen_records(field):
    item = {"metadata": {"a": 1, "b": 2}}
    if field == "screening_results":
        item["decision"] = "maybe"
    env = envelope({field: [item]}, "systematic-review-meta-analysis", "screening-matrix-1.0")
    state = kernel()
    engine = IngestionEngine()
    receipt = engine.ingest(env, state=state)
    assert receipt.status == "accepted", receipt.failure_reason
    assert engine.ingest(env, state=state) == receipt

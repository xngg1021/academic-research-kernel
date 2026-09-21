"""Cross-registry mutation and invocation-authority acceptance regressions."""

import base64
import copy
from dataclasses import replace

import pytest

from test_ingestion_hardening import (
    ArtifactEnvelope, IngestionEngine, IngestionKernelState, ReceiptRef,
    call_tool, ceg_mod, compute_sha256, envelope, evidence_payload, kernel,
    ledger_mod, mcp_server,
)
from shared_contracts.evidence import LineageVerificationContext, validate_lineage_receipt_integrity


def reload_state(state, context=None):
    return IngestionKernelState.from_dict(
        state.to_dict(), ceg_cls=ceg_mod.ClaimEvidenceGraph,
        ledger_cls=ledger_mod.DecisionLedger, verification_context=context,
    )


def graph_artifact():
    graph = ceg_mod.ClaimEvidenceGraph("committed-graph")
    graph.add_claim("claim-a", "Original claim", locator="table:1", metadata={"scope": "original"})
    graph.add_claim("claim-b", "Related claim")
    graph.add_evidence("evidence-a", "direct_observation", excerpt="Original evidence", locator="figure:1")
    graph.add_support_edge("evidence-a", "claim-a", "supported")
    graph.add_claim_relation("claim-a", "claim-b", "corroborates")
    return envelope(graph.to_dict(), "claim-evidence-graph", "claim-evidence-graph-1.0")


@pytest.mark.parametrize("mutation", [
    "claim_text", "claim_locator", "claim_metadata", "evidence_excerpt",
    "evidence_metadata", "edge_status", "edge_metadata", "relation_type",
    "relation_metadata", "relation_remove", "graph_identity",
])
def test_every_ceg_semantic_record_is_bound_after_transport_resigning(mutation):
    state = kernel()
    env = graph_artifact()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted", receipt.failure_reason
    assert {b["kind"] for b in receipt.mutation_bindings} >= {
        "ceg_claim", "ceg_evidence", "ceg_support", "ceg_relation", "ceg_container",
    }
    graph = state.ceg
    if mutation.startswith("claim_"):
        field = mutation.removeprefix("claim_")
        value = {"scope": "changed"} if field == "metadata" else "Changed"
        graph.claims["claim-a"] = replace(graph.claims["claim-a"], **{field: value})
    elif mutation.startswith("evidence_"):
        field = mutation.removeprefix("evidence_")
        value = {"changed": True} if field == "metadata" else "Changed"
        graph.evidence_anchors["evidence-a"] = replace(graph.evidence_anchors["evidence-a"], **{field: value})
    elif mutation.startswith("edge_"):
        change = {"support_status": "contradicted"} if mutation == "edge_status" else {"metadata": {"changed": True}}
        graph.support_edges[0] = replace(graph.support_edges[0], **change)
    elif mutation == "relation_remove":
        graph.claim_relations.clear()
    elif mutation.startswith("relation_"):
        change = {"relation_type": "refines"} if mutation == "relation_type" else {"metadata": {"changed": True}}
        graph.claim_relations[0] = replace(graph.claim_relations[0], **change)
    else:
        graph.graph_id = "substituted-graph"
    # to_dict recomputes all public graph/content/snapshot digests. Cache
    # commitments must still reject the replacement semantic record.
    with pytest.raises(ValueError, match="invariant|commitment"):
        reload_state(state)
    with pytest.raises(ValueError, match="invalid kernel"):
        IngestionEngine().ingest(env, state=state)


@pytest.mark.parametrize("field,value", [
    ("payload_sha256", "f" * 64), ("producer", {"skill": "changed", "version": "1"}),
    ("locator", "changed"), ("metadata", {"changed": True}),
    ("context", {"changed": True}), ("kind", "changed"),
])
def test_opaque_object_cannot_change_under_cached_identity(field, value):
    state = kernel()
    env = envelope({"text": "Opaque prose"}, "unknown", "opaque-1")
    receipt = IngestionEngine().ingest(env, state=state)
    object_id = receipt.created_or_reused_objects[0]
    state.objects[object_id] = {**dict(state.objects[object_id]), field: value}
    with pytest.raises(ValueError, match="commitment"):
        reload_state(state)


@pytest.mark.parametrize("mutation", ["delete", "reason", "metadata", "kind", "subject_id", "needs_human"])
def test_adapter_uncertainty_cannot_disappear_or_change(mutation):
    state = kernel()
    env = envelope({"is_retracted": True, "doi": "10.1000/example", "signals": []}, "retraction-watch", "retraction-alert-1.0")
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted", receipt.failure_reason
    if mutation == "delete":
        state.uncertainties.clear()
    else:
        value = dict(state.uncertainties[0])
        value[mutation] = {"metadata": {"changed": True}, "kind": "generic_uncertainty", "needs_human": False}.get(mutation, "changed")
        state.uncertainties[0] = value
    with pytest.raises(ValueError, match="commitment"):
        reload_state(state)


@pytest.mark.parametrize("mutation", ["delete", "replace"])
def test_zero_claim_receipt_only_mutation_is_committed(mutation):
    payload = evidence_payload()
    payload["claims"] = []
    payload["query"] = ""
    payload["identifiers"] = {}
    env = envelope(payload, "academic-source-verification", "evidence-receipt-1.0")
    state = kernel()
    receipt = IngestionEngine().ingest(env, state=state)
    assert receipt.status == "accepted", receipt.failure_reason
    assert not receipt.created_or_reused_objects and not receipt.ceg_nodes
    key = next(iter(state.receipts))
    if mutation == "delete":
        state.receipts.clear()
        state.ceg._receipt_registry.clear()
        state.ledger._receipts.clear()
    else:
        altered = {**payload, "query": "Changed lookup"}
        state.receipts[key] = altered
        state.ceg._receipt_registry[key] = altered
        state.ledger._receipts[key] = altered
    with pytest.raises(ValueError, match="commitment"):
        reload_state(state)


def test_empty_ledger_complete_lifecycle_and_first_append():
    state = kernel()
    source = ledger_mod.DecisionLedger("empty-but-real")
    env = envelope(source.to_dict(), "decision-ledger", "decision-ledger-1.0")
    engine = IngestionEngine()
    first = engine.ingest(env, state=state)
    assert first.status == "accepted", first.failure_reason
    assert first.ledger_bindings == ()
    assert any(b["kind"] == "ledger_container" for b in first.mutation_bindings)
    replayed = reload_state(state)
    assert engine.ingest(env, state=replayed) == first
    source.add_decision("first", "First decision", decision_action="explore")
    next_env = envelope(source.to_dict(), "decision-ledger", "decision-ledger-1.0")
    assert engine.ingest(next_env, state=replayed).status == "accepted"
    assert engine.ingest(env, state=reload_state(replayed)) == first


def content_receipt(tmp_path, size=32, budget=10 * 1024 * 1024):
    content = b"x" * size
    (tmp_path / "artifact.bin").write_bytes(content)
    graph = mcp_server.prov_mod.LineageGraph(root_dir=tmp_path)
    graph.add_entity("artifact", "data_snapshot", locator="artifact.bin", sha256=compute_sha256(content))
    context = LineageVerificationContext(content_root=tmp_path, max_content_bytes=budget)
    receipt = mcp_server.prov_mod.trace_origin(graph, "artifact", verification_context=context)
    return graph, context, receipt, content


def test_authority_survives_all_trusted_replay_apis_out_of_band(tmp_path):
    _, context, produced, _ = content_receipt(tmp_path)
    physical = produced.to_dict()
    assert "content_root" not in physical and "verification_context" not in physical
    assert validate_lineage_receipt_integrity(produced) == (True, None)
    assert validate_lineage_receipt_integrity(physical)[0] is False
    assert validate_lineage_receipt_integrity(physical, verification_context=context) == (True, None)
    state = IngestionKernelState(ceg=ceg_mod.ClaimEvidenceGraph(), ledger=ledger_mod.DecisionLedger(), verification_context=context)
    env = envelope(physical, "research-object-identity", "lineage-receipt-1.0")
    engine = IngestionEngine()
    receipt = engine.ingest(env, state=state)
    assert receipt.status == "accepted", receipt.failure_reason
    ref = ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id=produced.receipt_id, receipt_digest=produced.receipt_digest)
    state.ledger.add_decision("basis", "Basis")
    state.ledger.add_decision("decision", "Decision")
    state.ledger.add_basis("decision", "decision", "basis", receipt_ref=ref)
    replayed = reload_state(state, context)
    assert engine.ingest(env, state=replayed) == receipt
    assert replayed.ledger.validate_ledger()[0]
    with pytest.raises(ValueError):
        reload_state(state)
    exported = state.ceg.to_dict()
    assert ceg_mod.ClaimEvidenceGraph.from_dict(exported, receipt_registry=state.receipts, verification_context=context).validate_graph()[0]


def test_large_artifact_budget_is_explicit_and_shared_by_producer_and_verifier(tmp_path):
    size = 10 * 1024 * 1024 + 1
    graph, context, receipt, _ = content_receipt(tmp_path, size=size, budget=size)
    assert receipt.content_verification == "fully_verified"
    assert validate_lineage_receipt_integrity(receipt) == (True, None)
    assert validate_lineage_receipt_integrity(receipt.to_dict(), verification_context=context) == (True, None)
    bounded = LineageVerificationContext(content_root=tmp_path)
    assert validate_lineage_receipt_integrity(receipt.to_dict(), verification_context=bounded)[0] is False
    with pytest.raises(ValueError, match="read-size budget"):
        mcp_server.prov_mod.trace_origin(graph, "artifact", verification_context=bounded)


def test_content_context_contains_traversal_escape(tmp_path):
    root = tmp_path / "authorized"
    root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret")
    graph = mcp_server.prov_mod.LineageGraph(root_dir=root)
    graph.add_entity("outside", "data_snapshot", locator="../outside.bin", sha256=compute_sha256(b"secret"))
    context = LineageVerificationContext(content_root=root)
    receipt = mcp_server.prov_mod.trace_origin(graph, "outside", verification_context=context)
    assert receipt.content_verification == "unverified"
    assert validate_lineage_receipt_integrity(receipt.to_dict(), verification_context=context)[0]


def test_mcp_content_bytes_work_for_ingestion_and_snapshot_replay(tmp_path):
    _, _, physical, content = content_receipt(tmp_path)
    env = envelope(physical.to_dict(), "research-object-identity", "lineage-receipt-1.0")
    contents = {"artifact": base64.b64encode(content).decode()}
    _, preflight = call_tool("research_artifact_validate", {"envelope": env.to_dict(), "content_payloads": contents})
    assert preflight["valid"] is True, preflight
    _, body = call_tool("research_artifact_ingest", {"envelope": env.to_dict(), "content_payloads": contents})
    assert body["success"] is True, body
    _, replay = call_tool("research_artifact_ingest", {"envelope": env.to_dict(), "state": body["output_state"], "content_payloads": contents})
    assert replay["success"] is True
    assert replay["receipt"] == body["receipt"]
    _, denied = call_tool("research_artifact_ingest", {"envelope": env.to_dict(), "content_root": str(tmp_path)})
    assert "Invalid tool arguments" in denied["error"]


@pytest.mark.parametrize("bad", ["scalar", 1, [], None, {}, {"protocol": "lineage-receipt-1.0"}, {"schema_version": "1.0", "extra": True}])
def test_malformed_mcp_receipt_registry_is_a_validation_result(bad):
    env = envelope({"text": "opaque"}, "unknown", "opaque-1")
    _, result = call_tool("research_artifact_validate", {"envelope": env.to_dict(), "receipts": {"r": bad}})
    assert result["valid"] is False and result["errors"]
    assert "Internal execution failure" not in str(result)


def test_preflight_checks_apply_semantics_and_preserves_target_state():
    env = envelope({"paper_title": "Example", "assertions": [{"statistic": "t", "reported_value": 1, "recomputed_value": 2, "discrepancy_detected": True}]}, "quantitative-paper-audit", "quantitative-audit-1.0")
    _, result = call_tool("research_artifact_validate", {"envelope": env.to_dict(), "bindings": {"claim_id": "missing"}})
    assert result["valid"] is False
    assert any("Dangling" in item for item in result["errors"])


@pytest.mark.parametrize("changed", ["decision", "basis", "fork", "event", "correction", "container"])
def test_every_ledger_record_rejects_valid_resigned_substitution(changed):
    def build(change=None):
        ledger = ledger_mod.DecisionLedger("changed" if change == "container" else "bound")
        ledger.add_decision("a", "Changed" if change == "decision" else "Original")
        ledger.add_decision("b", "Alternative")
        ledger.add_basis("b", "decision", "a", metadata={"value": change == "basis"})
        ledger.add_fork("a", "b", "considered", metadata={"value": change == "fork"})
        ledger.add_state_event("a", "active", metadata={"changed": change == "event"})
        ledger.add_outcome_correction("a", "positive", "Changed" if change == "correction" else "Original")
        return ledger

    state = kernel()
    env = envelope(build().to_dict(), "decision-ledger", "decision-ledger-1.0")
    assert IngestionEngine().ingest(env, state=state).status == "accepted"
    state.ledger = build(changed)
    with pytest.raises(ValueError, match="invariant|commitment"):
        reload_state(state)


def test_active_domain_uncertainty_cannot_be_suppressed():
    state = kernel()
    payload = evidence_payload()
    payload["claims"][0]["support_status"] = "unverifiable"
    env = envelope(payload, "academic-source-verification", "evidence-receipt-1.0")
    assert IngestionEngine().ingest(env, state=state).status == "accepted"
    assert any(value.get("metadata", {}).get("kernel_origin") == "domain_derived" for value in state.uncertainties)
    state.uncertainties.clear()
    with pytest.raises(ValueError, match="derived uncertainty"):
        reload_state(state)


def test_placeholder_upgrade_remains_bound_to_the_canonical_adoption():
    state = kernel()
    env = envelope(evidence_payload(), "academic-source-verification", "evidence-receipt-1.0")
    engine = IngestionEngine()
    old_receipt = engine.ingest(env, state=state)
    work_id = old_receipt.created_or_reused_objects[0]
    canonical = {"work_id": work_id, "work_type": "article", "title": "Canonical", "authors": []}
    new_env = envelope(canonical, "literature-analysis", "canonical-work-1.0")
    assert engine.ingest(new_env, state=state).status == "accepted"
    assert engine.ingest(env, state=reload_state(state)) == old_receipt
    state.objects[work_id] = {**canonical, "title": "Arbitrary replacement"}
    with pytest.raises(ValueError, match="commitment"):
        reload_state(state)


def test_mcp_cannot_increase_its_content_budget(tmp_path):
    _, _, receipt, _ = content_receipt(tmp_path)
    ref = {"kind": "lineage", "schema_version": "lineage-receipt-1.0",
           "receipt_id": receipt.receipt_id, "receipt_digest": receipt.receipt_digest}
    _, result = call_tool("research_receipt_verify", {
        "receipt_ref": ref, "receipt_payload": receipt.to_dict(),
        "content_payloads": {"artifact": "A" * (4 * ((10 * 1024 * 1024 + 2) // 3) + 4)},
    })
    assert result["valid"] is False and "budget" in result["error"]
    _, result = call_tool("research_receipt_verify", {
        "receipt_ref": ref, "receipt_payload": receipt.to_dict(), "max_content_bytes": 1 << 40,
    })
    assert result["error"] == "Invalid tool arguments"


def test_producer_preserves_unverified_diagnostic_in_receipt_identity():
    graph = mcp_server.prov_mod.LineageGraph()
    graph.add_entity("unanchored", "data_snapshot", locator="relative.csv", sha256="a" * 64)
    receipt = mcp_server.prov_mod.trace_origin(graph, "unanchored")
    assert "explicit root_dir" in receipt.error_detail
    assert validate_lineage_receipt_integrity(receipt.to_dict()) == (True, None)


def test_uncertainty_boolean_integer_metadata_is_not_an_equal_record():
    state = kernel()
    record = {"item_id": "unc", "subject_id": "s", "kind": "generic_uncertainty",
              "reason": "r", "needs_human": True, "metadata": {"observed": True}}
    state.add_uncertainty(record)
    with pytest.raises(ValueError, match="collision"):
        state.add_uncertainty({**record, "metadata": {"observed": 1}})


def test_explicit_legacy_receipt_contract_agrees_across_adoption_and_mcp():
    from shared_contracts.evidence import canonical_evidence_claim_digest, canonical_academic_receipt_payload_sha256
    claim = evidence_payload()["claims"][0]
    digest = canonical_evidence_claim_digest(claim)
    physical = {"schema_version": "1.0", "receipt_id": "legacy-physical", "claims": [{**claim, "claim_digest": digest}]}
    ref = {"kind": "academic_evidence", "schema_version": "1.0", "claim_digest": digest,
           "payload_sha256": canonical_academic_receipt_payload_sha256(physical)}
    _, result = call_tool("research_receipt_verify", {"receipt_ref": ref, "receipt_payload": physical})
    assert result == {"valid": True}
    env = envelope(physical, "academic-source-verification", "academic-evidence-1.0")
    _, preflight = call_tool("research_artifact_validate", {"envelope": env.to_dict()})
    assert preflight["valid"] is True, preflight
    state = kernel()
    assert IngestionEngine().ingest(env, state=state).status == "accepted"
    assert reload_state(state).to_dict() == state.to_dict()


def test_shared_contract_rejects_unrecognized_lineage_fields(tmp_path):
    _, context, produced, _ = content_receipt(tmp_path)
    physical = produced.to_dict()
    physical["content_root"] = str(tmp_path)
    valid, error = validate_lineage_receipt_integrity(physical, verification_context=context)
    assert valid is False and "schema" in error

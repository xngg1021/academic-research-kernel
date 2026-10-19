"""Tests for the expanded universal MCP server surface."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "claim-evidence-graph" / "scripts"))
sys.path.insert(0, str(ROOT / "skills" / "decision-ledger" / "scripts"))

import mcp_server
from ingestion import ArtifactEnvelope
from shared_contracts.evidence import ReceiptRef, compute_sha256, canonical_json_bytes, canonical_evidence_claim_digest
import graph as ceg_mod
import ledger as ledger_mod


def _call_tool(name: str, arguments: dict, call_id: int = 1) -> dict:
    req = {
        "jsonrpc": "2.0",
        "id": call_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
        },
    }
    resp = mcp_server.process_message(req)
    assert resp.get("id") == call_id
    assert "result" in resp, f"Tool call failed: {resp}"
    return json.loads(resp["result"]["content"][0]["text"])


def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2026-07-28"},
    }
    resp = mcp_server.process_message(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "academic-research-kernel"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_tools_list():
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }
    resp = mcp_server.process_message(req)
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert len(tools) == 12
    assert "research_artifact_validate" in tool_names
    assert "research_artifact_ingest" in tool_names
    assert "research_receipt_verify" in tool_names
    assert "research_object_resolve" in tool_names
    assert "research_lineage_trace" in tool_names
    assert "claim_evidence_validate" in tool_names
    assert "claim_evidence_trace" in tool_names
    assert "decision_ledger_validate" in tool_names
    assert "decision_trace" in tool_names
    assert "academic_recompute_statistics" in tool_names
    assert "academic_check_percentage" in tool_names
    assert "academic_scfabric_hardware_probe" in tool_names


def test_mcp_call_research_artifact_validate():
    env = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "validation test",
            "identifiers": {},
            "sources": [],
            "claims": [],
            "generated_at": "2026-09-20T00:00:00Z",
        },
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )
    data = _call_tool("research_artifact_validate", {"envelope": env.to_dict()}, call_id=3)
    assert data["valid"] is True
    assert data["artifact_id"] == env.artifact_id


def test_mcp_call_research_artifact_ingest():
    env = ArtifactEnvelope.create(
        payload={
            "schema_version": "1.0",
            "query": "DOI:10.1000/1",
            "identifiers": {"doi": "10.1000/1"},
            "sources": [],
            "claims": [{
                "claim": "Ingest test claim",
                "evidence_type": "computed",
                "source": "DOI:10.1000/1",
                "support_status": "supported",
            }],
            "generated_at": "2026-09-20T00:00:00Z",
        },
        producer_skill="academic-source-verification",
        producer_version="1.0.0",
        artifact_kind="evidence_receipt",
        payload_schema="evidence-receipt-1.0",
    )
    data = _call_tool("research_artifact_ingest", {"envelope": env.to_dict()}, call_id=4)
    assert data["success"] is True
    assert "receipt" in data
    assert "output_state" in data
    assert "ceg" in data["output_state"]


def test_mcp_call_research_receipt_verify():
    payload = {
        "schema_version": "1.0",
        "query": "DOI:10.1037/bul0000209",
        "identifiers": {"doi": "10.1037/bul0000209"},
        "sources": [],
        "claims": [{
            "claim": "Interleaving enhances retention",
            "evidence_type": "computed",
            "locator": "p. 1042",
            "source": "DOI:10.1037/bul0000209",
            "support_status": "supported",
        }],
        "generated_at": "2026-09-20T00:00:00Z",
    }
    p_bytes = canonical_json_bytes(payload)
    p_sha = compute_sha256(p_bytes)
    c_digest = canonical_evidence_claim_digest(payload["claims"][0])

    ref_dict = {
        "kind": "academic_evidence",
        "schema_version": "1.0",
        "claim_digest": c_digest,
        "payload_sha256": p_sha,
        "locator": "p. 1042",
    }
    data = _call_tool("research_receipt_verify", {"receipt_ref": ref_dict, "receipt_payload": payload}, call_id=5)
    assert data["valid"] is True


def test_mcp_call_research_object_resolve():
    records = [
        {"doi": "10.1000/182", "title": "First Paper", "year": 2024},
        {"doi": "10.1000/182", "title": "First Paper (Preprint)", "year": 2023},
    ]
    data = _call_tool("research_object_resolve", {"records": records}, call_id=6)
    assert "resolved" in data


def test_mcp_call_research_lineage_trace():
    lineage_graph = {
        "entities": [
            {"id": "data-snapshot-1", "type": "data_snapshot"},
            {"id": "model-eval-1", "type": "statistic_artifact"},
        ],
        "activities": [
            {
                "id": "eval-run-1",
                "type": "statistical_analysis",
                "timestamp": "2026-09-20T00:00:00Z",
            },
        ],
        "edges": [
            {"source_id": "eval-run-1", "target_id": "data-snapshot-1", "type": "used"},
            {"source_id": "eval-run-1", "target_id": "model-eval-1", "type": "generated"},
        ],
    }
    data = _call_tool("research_lineage_trace", {"lineage_graph": lineage_graph, "target_entity_id": "model-eval-1"}, call_id=7)
    assert data["target_entity_id"] == "model-eval-1"
    assert "receipt" in data


def test_mcp_call_claim_evidence_validate_and_trace():
    cg = ceg_mod.ClaimEvidenceGraph(graph_id="g-1")
    cg.add_claim("c-1", "Test claim text", target_work_id="w-1")
    cg.add_evidence("ev-1", "direct_observation", locator="p. 1")
    cg.add_support_edge("ev-1", "c-1", "supported")
    graph_dict = cg.to_dict()

    # Validate
    val_data = _call_tool("claim_evidence_validate", {"graph": graph_dict}, call_id=8)
    assert val_data["valid"] is True
    assert val_data["node_count"] == 2

    # Trace
    trace_data = _call_tool("claim_evidence_trace", {"graph": graph_dict, "claim_id": "c-1"}, call_id=9)
    assert trace_data["claim_id"] == "c-1"
    assert "provenance_trace" in trace_data


def test_mcp_call_decision_ledger_validate_and_trace():
    ledger = ledger_mod.DecisionLedger(ledger_id="l-1")
    ledger.add_decision("dec-1", "Investigate Neural Scaling", decision_action="explore")
    ledger.add_decision("dec-2", "Refine Batch Size", decision_action="commit")
    ledger.add_basis("dec-2", "decision", "dec-1")
    ledger.add_state_event("dec-1", "active")
    ledger.add_outcome_correction("dec-1", "positive", "Scaling law holds")
    ledger_dict = ledger.to_dict()

    # Validate
    val_data = _call_tool("decision_ledger_validate", {"ledger": ledger_dict}, call_id=10)
    assert val_data["valid"] is True
    assert val_data["decision_count"] == 2

    # Trace
    trace_data = _call_tool("decision_trace", {"ledger": ledger_dict, "decision_id": "dec-1"}, call_id=11)
    assert trace_data["decision_id"] == "dec-1"
    assert len(trace_data["corrections"]) == 1
    assert len(trace_data["state_history"]) == 1


def test_mcp_call_math_and_statistics_tools():
    # 1. academic_check_percentage
    p_data = _call_tool("academic_check_percentage", {"count": 12, "percent": 24.0, "sample_size": 50}, call_id=12)
    assert p_data["consistent"] is True

    # 2. academic_recompute_statistics
    s_data = _call_tool("academic_recompute_statistics", {"t_stat": 2.10, "df": 48, "p_value": 0.041}, call_id=13)
    assert "recomputed_p" in s_data

    # 3. academic_scfabric_hardware_probe
    h_data = _call_tool("academic_scfabric_hardware_probe", {}, call_id=14)
    assert "os" in h_data


def test_mcp_unknown_method():
    req = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "unknown_custom_method",
    }
    resp = mcp_server.process_message(req)
    assert resp["error"]["code"] == -32601


def test_mcp_stdio_roundtrip():
    """Verify standard stdio process pipe communication."""
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "mcp_server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    req = {"jsonrpc": "2.0", "id": 100, "method": "initialize", "params": {}}
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()

    line = proc.stdout.readline()
    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=5)

    assert line.strip()
    resp = json.loads(line)
    assert resp["id"] == 100
    assert resp["result"]["serverInfo"]["name"] == "academic-research-kernel"


def test_mcp_server_discover_and_meta_protocol_version():
    disc = mcp_server.process_message({"jsonrpc": "2.0", "id": 101, "method": "server/discover", "params": {}})
    res = disc["result"]
    assert "protocolVersion" not in res
    assert res["supportedVersions"] == ["2024-11-05", "2026-07-28"]
    assert res["resultType"] == "complete"
    assert res["ttlMs"] == 3600000
    assert res["cacheScope"] == "public"
    assert res["_meta"]["io.modelcontextprotocol/serverInfo"]["name"] == "academic-research-kernel"
    assert len(res["tools"]) == 12

    bad_cap_meta = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": 1015,
        "method": "tools/list",
        "params": {"_meta": {"io.modelcontextprotocol/clientCapabilities": "not-an-object"}},
    })
    assert bad_cap_meta["error"]["code"] == -32602

    bad_official_meta = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/list",
        "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2099-01-01"}},
    })
    assert bad_official_meta["error"]["code"] == -32022
    assert bad_official_meta["error"]["data"] == {
        "requested": "2099-01-01",
        "supported": ["2024-11-05", "2026-07-28"],
    }

    ok_official_meta = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tools/list",
        "params": {"_meta": {"io.modelcontextprotocol/protocolVersion": "2026-07-28", "protocolVersion": "custom-1.0"}},
    })
    assert ok_official_meta["result"]["resultType"] == "complete"
    assert ok_official_meta["result"]["ttlMs"] == 3600000
    assert ok_official_meta["result"]["cacheScope"] == "public"
    assert len(ok_official_meta["result"]["tools"]) == 12

    call_resp = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": 104,
        "method": "tools/call",
        "params": {
            "name": "academic_check_percentage",
            "arguments": {"count": 10, "percent": 50.0, "sample_size": 20},
        },
    })
    assert call_resp["result"]["resultType"] == "complete"
    assert call_resp["result"]["isError"] is False


def test_mcp_startup_and_percentage_do_not_import_statistics_stack():
    code = (
        "import sys; sys.path.insert(0, 'scripts'); "
        "import mcp_server; "
        "r = mcp_server.handle_tool_call('academic_check_percentage', {'count': 10, 'percent': 50.0, 'sample_size': 20}); "
        "assert r['consistent'] is True; "
        "assert not any(m in sys.modules for m in ('numpy', 'scipy', 'statsmodels'))"
    )
    subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), check=True, timeout=30)


def test_recompute_requires_scipy_and_statsmodels_for_distributions_and_power():
    import pytest
    recompute_mod = mcp_server.recompute
    old_scipy, old_power = recompute_mod._SCIPY_STATS, recompute_mod._TTEST_POWER_CLS
    try:
        recompute_mod._SCIPY_STATS = None
        recompute_mod._TTEST_POWER_CLS = None
        assert recompute_mod.achieved_power_ttest(0.5, 5, 5, 0.05)["recomputed"] == pytest.approx(0.107686, abs=1e-5)
        assert recompute_mod.achieved_power_ttest(0.0, 2, 2, 0.05)["recomputed"] == pytest.approx(0.05, abs=1e-12)
        assert recompute_mod.required_n_ttest(2.0, 0.80, 0.05, 1.0)["recomputed"] == pytest.approx(5.089995, abs=1e-5)
        assert recompute_mod.p_from_chi2(10000, 10000)["recomputed"] == pytest.approx(0.498119365966183, abs=1e-12)
        assert recompute_mod.p_from_f(1.0, 200_000_000, 200_000_000)["recomputed"] == pytest.approx(0.5, abs=1e-6)

        recompute_mod._SCIPY_STATS = False
        recompute_mod._TTEST_POWER_CLS = False
        assert recompute_mod.cohens_d(5.0, 2.0, 30, 3.0, 2.0, 30)["recomputed"]["cohens_d"] == pytest.approx(1.0)
        assert recompute_mod.check_percentage(10, 50.0, 20)["consistent"] is True
        with pytest.raises(RuntimeError, match="scipy is required"):
            recompute_mod.p_from_t(2.0, 30)
        with pytest.raises(RuntimeError, match="scipy is required"):
            recompute_mod.p_from_chi2(10000, 10000)
        with pytest.raises(RuntimeError, match="statsmodels is required"):
            recompute_mod.achieved_power_ttest(0.5, 5, 5, 0.05)
        with pytest.raises(RuntimeError, match="statsmodels is required"):
            recompute_mod.required_n_ttest(2.0, 0.80, 0.05, 1.0)
    finally:
        recompute_mod._SCIPY_STATS = old_scipy
        recompute_mod._TTEST_POWER_CLS = old_power


def test_frozen_json_map_deep_nesting_memory_and_duck_typed_receipt_isolation():
    import tracemalloc
    from shared_contracts.evidence import FrozenJSONMap
    from ledger import DecisionLedger
    from graph import ClaimEvidenceGraph

    payload = "a" * (4 * 1024 * 1024)
    nested = {"leaf": payload}
    for _ in range(32):
        nested = {"content": nested}
    tracemalloc.start()
    before_cur, _ = tracemalloc.get_traced_memory()
    fmap = FrozenJSONMap(nested)
    after_cur, _ = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    retained_mib = (after_cur - before_cur) / (1024 * 1024)
    assert retained_mib < 1.0
    assert fmap["content"]["content"]["content"] is not None

    class FakeFrozen(dict):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self._canonical_bytes = b'{"score":1}'

        def sha256(self):
            return "0" * 64

    led = DecisionLedger()
    ceg = ClaimEvidenceGraph()
    fake = FakeFrozen(score=1)
    led.register_receipt("r1", fake)
    ceg.register_receipt("r1", fake)
    fake["score"] = 2
    assert led._receipts["r1"]["score"] == 1
    assert ceg._receipt_registry["r1"]["score"] == 1

    import ingestion.commitments as commitments_mod
    from shared_contracts.evidence import LineageVerificationContext
    import time
    assert not hasattr(commitments_mod, "_SOURCE_PROJECTION_CACHE")

    ctx_10m = LineageVerificationContext(content_by_entity_id={"e1": b"x" * (10 * 1024 * 1024)})
    ctx_10m_twin = LineageVerificationContext(content_by_entity_id={"e1": b"x" * (10 * 1024 * 1024)})
    assert ctx_10m == ctx_10m_twin
    t0 = time.perf_counter()
    for _ in range(500):
        fp = ctx_10m.fingerprint()
    elapsed = time.perf_counter() - t0
    assert elapsed < 0.25
    assert len(fp[1][0][1]) == 64
    assert ctx_10m == ctx_10m_twin

    import tempfile
    import pytest
    from ingestion.engine import IngestionEngine
    from ingestion.models import ArtifactEnvelope, IngestionKernelState
    from shared_contracts.evidence import compute_sha256

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        doc = td_path / "artifact.bin"
        doc.write_bytes(b"before")
        l_graph = mcp_server.prov_mod.LineageGraph(root_dir=td_path)
        l_graph.add_entity("artifact", "data_snapshot", locator="artifact.bin", sha256=compute_sha256(b"before"))
        disk_ctx = LineageVerificationContext(content_root=td_path)
        produced = mcp_server.prov_mod.trace_origin(l_graph, "artifact", verification_context=disk_ctx)
        state = IngestionKernelState(
            ceg=ClaimEvidenceGraph(),
            ledger=DecisionLedger(),
            verification_context=disk_ctx,
        )
        env = ArtifactEnvelope.create(
            payload=produced.to_dict(),
            producer_skill="research-object-identity",
            producer_version="1.0.0",
            artifact_kind="lineage_receipt",
            payload_schema="lineage-receipt-1.0",
        )
        eng = IngestionEngine()
        receipt = eng.ingest(env, state=state)
        assert receipt.status == "accepted"
        ck = next(iter(state.ingestion_sources))
        assert commitments_mod.expected_mutation_inventory(state, ck, receipt)
        doc.write_bytes(b"after!")
        with pytest.raises(ValueError, match="independent source planning failed"):
            commitments_mod.expected_mutation_inventory(state, ck, receipt)

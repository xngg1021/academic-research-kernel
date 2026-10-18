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
    assert disc["result"]["protocolVersion"] == "2026-07-28"
    assert len(disc["result"]["tools"]) == 12

    bad_meta = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": 102,
        "method": "tools/list",
        "params": {"_meta": {"protocolVersion": "2099-01-01"}},
    })
    assert bad_meta["error"]["code"] == -32022

    ok_meta = mcp_server.process_message({
        "jsonrpc": "2.0",
        "id": 103,
        "method": "tools/list",
        "params": {"_meta": {"protocolVersion": "2026-07-28"}},
    })
    assert len(ok_meta["result"]["tools"]) == 12


def test_mcp_startup_and_percentage_do_not_import_statistics_stack():
    code = (
        "import sys; sys.path.insert(0, 'scripts'); "
        "import mcp_server; "
        "r = mcp_server.handle_tool_call('academic_check_percentage', {'count': 10, 'percent': 50.0, 'sample_size': 20}); "
        "assert r['consistent'] is True; "
        "assert not any(m in sys.modules for m in ('numpy', 'scipy', 'statsmodels'))"
    )
    subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), check=True, timeout=30)


def test_recompute_stdlib_fallback_matches_scipy():
    import pytest
    recompute_mod = mcp_server.recompute
    old_scipy, old_power = recompute_mod._SCIPY_STATS, recompute_mod._TTEST_POWER_CLS
    try:
        recompute_mod._SCIPY_STATS = None
        recompute_mod._TTEST_POWER_CLS = None
        t_sci = recompute_mod.p_from_t(2.0, 30)["recomputed"]
        f_sci = recompute_mod.p_from_f(4.5, 2, 27)["recomputed"]
        chi_sci = recompute_mod.p_from_chi2(3.84, 1)["recomputed"]
        z_sci = recompute_mod.z_from_beta_se(1.96, 1.0)["recomputed"]["p"]
        ci_sci = recompute_mod.check_ci_consistency(2.0, 1.0, 3.0)["implied_se"]

        recompute_mod._SCIPY_STATS = False
        recompute_mod._TTEST_POWER_CLS = False
        assert recompute_mod.p_from_t(2.0, 30)["recomputed"] == pytest.approx(t_sci, abs=1e-14)
        assert recompute_mod.p_from_f(4.5, 2, 27)["recomputed"] == pytest.approx(f_sci, abs=1e-14)
        assert recompute_mod.p_from_chi2(3.84, 1)["recomputed"] == pytest.approx(chi_sci, abs=1e-14)
        assert recompute_mod.z_from_beta_se(1.96, 1.0)["recomputed"]["p"] == pytest.approx(z_sci, abs=1e-14)
        assert recompute_mod.check_ci_consistency(2.0, 1.0, 3.0)["implied_se"] == pytest.approx(ci_sci, abs=1e-14)
    finally:
        recompute_mod._SCIPY_STATS = old_scipy
        recompute_mod._TTEST_POWER_CLS = old_power

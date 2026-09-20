"""Tests for the expanded universal MCP server surface."""

import json
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server


def test_mcp_initialize():
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2026-07-28"}
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
    envelope = {
        "protocol": "artifact-envelope-1.0",
        "artifact_id": "art-" + "1" * 32,
        "artifact_kind": "evidence_receipt",
        "producer": {"skill": "academic-source-verification", "version": "1.0.0"},
        "payload_schema": "evidence-receipt-1.0",
        "payload_sha256": "d6d628c0b15a261ab4c71ab1d1198bf9a4bea9a21923e1dc7e8bb134a8e39ab3",
        "payload": {
            "schema_version": "1.0",
            "claims": []
        }
    }
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "research_artifact_validate",
            "arguments": {"envelope": envelope}
        }
    }
    resp = mcp_server.process_message(req)
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["valid"] is True
    assert data["artifact_id"] == envelope["artifact_id"]


def test_mcp_call_academic_check_percentage():
    req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "academic_check_percentage",
            "arguments": {"count": 12, "percent": 24.0, "sample_size": 50}
        }
    }
    resp = mcp_server.process_message(req)
    data = json.loads(resp["result"]["content"][0]["text"])
    assert data["consistent"] is True


def test_mcp_unknown_method():
    req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "unknown_custom_method",
    }
    resp = mcp_server.process_message(req)
    assert resp["error"]["code"] == -32601

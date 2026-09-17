# -*- coding: utf-8 -*-
"""Regression tests for Harness-Neutral Architecture:
- ReviewPanelSpec, Finding, ReviewResult, ReviewRunReceipt JSON Schemas
- ReviewerAdapter protocol and implementations (MockReviewerAdapter, CommandReviewerAdapter)
- Agent Plugins v1 portable manifest & MCP server
"""
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent

# 导入 contracts 与 adapters
sys.path.insert(0, str(ROOT / "skills/cross-review-five/scripts"))
import contracts as ct
from adapters import CommandReviewerAdapter, HermesCliReviewerAdapter, MockReviewerAdapter


# =========================================================================
# 1. JSON Schemas & Spec Contracts
# =========================================================================

def test_new_schemas_are_valid_json():
    """All newly introduced JSON schemas must be valid JSON and contain required metadata."""
    schema_dir = ROOT / "schemas"
    schemas = [
        "review-panel-spec.schema.json",
        "review-finding.schema.json",
        "review-result.schema.json",
        "review-run-receipt.schema.json",
    ]
    for name in schemas:
        path = schema_dir / name
        assert path.is_file(), f"Missing schema file: {name}"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert "$schema" in data
        assert "title" in data
        assert data.get("type") == "object"


def test_panel_spec_data_structure():
    """PanelSpec and ParticipantSpec must support arbitrary seats and roles."""
    p1 = ct.ParticipantSpec(id="claude-lead", executor="command", provider="anthropic", model="claude-3-7-sonnet", role="Architecture Lead")
    p2 = ct.ParticipantSpec(id="gemini-redteam", executor="command", provider="gemini", model="gemini-3.8-flash", role="Red Team")
    p3 = ct.ParticipantSpec(id="codex-auditor", executor="command", provider="openai", model="o3-mini", role="Code Auditor")

    panel = ct.PanelSpec(
        panel_id="cross-review-universal-1",
        participants=[p1, p2, p3],
        description="3-member heterogeneous deliberation panel",
        topology="sparse_deliberation"
    )

    assert len(panel.participants) == 3
    assert panel.get_participant("gemini-redteam").role == "Red Team"
    assert panel.get_participant("unknown") is None


def test_finding_conversion_and_schema_fields():
    """Finding dataclass must produce valid schema-compliant dictionary."""
    f = ct.Finding(
        id="F1",
        target="skills/literature-watch/scripts/watch.py",
        claim="404 error was retried 3 times causing delay",
        kind="bug",
        severity="P1",
        blocking=True,
        polarity="negative",
        evidence=["watch.py:105"]
    )
    d = f.to_dict()
    assert d["id"] == "F1"
    assert d["severity"] == "P1"
    assert d["blocking"] is True
    assert d["evidence"] == ["watch.py:105"]


# =========================================================================
# 2. Reviewer Adapters (Mock & Command)
# =========================================================================

def test_mock_reviewer_adapter_flow(tmp_path):
    """MockReviewerAdapter must execute review and challenge phases deterministically."""
    p = ct.ParticipantSpec(id="seat-a", executor="mock", model="mock-model")
    adapter = MockReviewerAdapter()

    caps = adapter.capabilities(p)
    assert caps.harness == "mock"
    assert caps.structured_output is True

    # Review
    req_review = ct.ReviewRequest(
        task_path=str(tmp_path / "task.md"),
        out_path=str(tmp_path / "review.md"),
        findings_path=str(tmp_path / "findings.json"),
        participant=p,
    )
    res_review = adapter.review(req_review)
    assert res_review.success is True
    assert len(res_review.findings) == 1
    assert Path(req_review.out_path).is_file()
    assert Path(req_review.findings_path).is_file()

    # Challenge
    req_challenge = ct.ChallengeRequest(
        task_path=str(tmp_path / "task.md"),
        bundle_path=str(tmp_path / "bundle.json"),
        out_path=str(tmp_path / "challenge_reply.md"),
        reviewer=p,
        target_participant_id="seat-b",
    )
    res_challenge = adapter.challenge(req_challenge)
    assert res_challenge.success is True
    assert "CONCEDE" in res_challenge.stances


def test_command_reviewer_adapter_formats_and_invokes_cli(tmp_path):
    """CommandReviewerAdapter must format CLI command template and invoke subprocess."""
    helper = tmp_path / "helper.py"
    helper.write_text(
        "import sys, pathlib\n"
        "pathlib.Path(sys.argv[1]).write_text('cli review done', encoding='utf-8')\n"
        "pathlib.Path(sys.argv[2]).write_text('{\"findings\": []}', encoding='utf-8')\n",
        encoding="utf-8"
    )
    p = ct.ParticipantSpec(
        id="cli-agent",
        executor="command",
        provider="custom",
        model="my-subagent",
        cmd=f"python {helper} {{out_path}} {{findings_path}}"
    )
    adapter = CommandReviewerAdapter()

    out_file = tmp_path / "out.md"
    findings_file = tmp_path / "findings.json"
    req = ct.ReviewRequest(
        task_path=str(tmp_path / "task.md"),
        out_path=str(out_file),
        findings_path=str(findings_file),
        participant=p,
    )

    res = adapter.review(req)
    assert res.success is True
    assert out_file.read_text(encoding="utf-8") == "cli review done"


# =========================================================================
# 3. Agent Plugins v1 & Portable MCP Server
# =========================================================================

def test_agent_plugins_v1_manifests_exist():
    """plugin.json and mcp.json must exist and be valid JSON referencing repository skills."""
    p_json = ROOT / "plugin.json"
    m_json = ROOT / "mcp.json"
    assert p_json.is_file()
    assert m_json.is_file()

    p_data = json.loads(p_json.read_text(encoding="utf-8"))
    assert p_data["name"] == "academic-skills"
    assert len(p_data["skills"]) == 11
    for s_rel in p_data["skills"]:
        assert (ROOT / s_rel).is_dir(), f"Referenced skill dir missing: {s_rel}"

    m_data = json.loads(m_json.read_text(encoding="utf-8"))
    assert "mcpServers" in m_data
    assert "academic-skills" in m_data["mcpServers"]


def test_mcp_server_protocol_messages():
    """mcp_server.py must handle initialize, tools/list and tools/call over JSON-RPC 2.0."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import mcp_server

    # 1. initialize
    init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
    init_resp = mcp_server.process_message(init_req)
    assert init_resp["id"] == 1
    assert init_resp["result"]["serverInfo"]["name"] == "hermes-academic-skills"

    # 2. tools/list
    list_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    list_resp = mcp_server.process_message(list_req)
    assert list_resp["id"] == 2
    tool_names = [t["name"] for t in list_resp["result"]["tools"]]
    assert "academic_recompute_statistics" in tool_names
    assert "academic_check_percentage" in tool_names

    # 3. tools/call
    call_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "academic_check_percentage",
            "arguments": {"count": 10, "percent": 50.0, "sample_size": 20}
        }
    }
    call_resp = mcp_server.process_message(call_req)
    assert call_resp["id"] == 3
    content_text = call_resp["result"]["content"][0]["text"]
    result_data = json.loads(content_text)
    assert result_data["consistent"] is True

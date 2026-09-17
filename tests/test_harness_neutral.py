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
    assert p_data["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    allowed_plugin_fields = {
        "$schema", "name", "version", "description", "author",
        "homepage", "repository", "license", "keywords", "extensions"
    }
    assert set(p_data).issubset(allowed_plugin_fields), f"Unexpected plugin fields: {set(p_data) - allowed_plugin_fields}"

    skill_files = list((ROOT / "skills").glob("*/SKILL.md"))
    assert len(skill_files) == 11, f"Expected 11 skills, found {len(skill_files)}"

    m_data = json.loads(m_json.read_text(encoding="utf-8"))
    assert m_data["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    assert set(m_data) == {"$schema", "mcpServers"}
    assert "academic-skills" in m_data["mcpServers"]
    srv = m_data["mcpServers"]["academic-skills"]
    assert srv.get("type") == "stdio"
    assert set(srv).issubset({"type", "command", "args", "env", "cwd"})


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


def test_agent_plugins_v1_skills_and_manifest_compatibility():
    """Verify all 11 skills have strictly portable metadata and pass Agent Plugins v1 checks."""
    import yaml
    skill_files = sorted(list((ROOT / "skills").glob("*/SKILL.md")))
    assert len(skill_files) == 11

    for sf in skill_files:
        text = sf.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        assert len(parts) >= 3, f"{sf.name} missing YAML frontmatter"
        fm = yaml.safe_load(parts[1])
        assert isinstance(fm, dict), f"{sf.name} invalid frontmatter"
        assert "name" in fm
        assert "description" in fm

        # Agent Plugins v1 metadata check: must be flat string -> string map
        if "metadata" in fm:
            meta = fm["metadata"]
            assert isinstance(meta, dict), f"{sf.name}: metadata must be a dictionary"
            for k, v in meta.items():
                assert isinstance(k, str), f"{sf.name}: metadata key {k!r} not string"
                assert isinstance(v, str), f"{sf.name}: metadata value {v!r} not string"


def test_command_adapter_challenge_receives_prompt_not_just_bundle(tmp_path):
    """CommandReviewerAdapter.challenge must pass task_path as prompt_path so instructions are retained."""
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("FULL_CHALLENGE_INSTRUCTIONS", encoding="utf-8")
    bundle_file = tmp_path / "bundle.json"
    bundle_file.write_text('{"target": "dummy"}', encoding="utf-8")
    out_file = tmp_path / "reply.md"

    helper = tmp_path / "agent.py"
    helper.write_text(
        "import sys, pathlib\n"
        "p_content = pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')\n"
        "assert 'FULL_CHALLENGE_INSTRUCTIONS' in p_content\n"
        "pathlib.Path(sys.argv[2]).write_text('CONCEDE: verified', encoding='utf-8')\n"
    )

    p = ct.ParticipantSpec(
        id="cmd_reviewer",
        executor="command",
        provider="custom",
        cmd=f"python {helper} {{prompt_path}} {{out_path}}"
    )
    adapter = CommandReviewerAdapter()
    req = ct.ChallengeRequest(
        task_path=str(prompt_file),
        bundle_path=str(bundle_file),
        out_path=str(out_file),
        reviewer=p,
        target_participant_id="target_x"
    )
    res = adapter.challenge(req)
    assert res.success is True
    assert "CONCEDE" in res.stances


def test_command_adapter_environment_isolation(tmp_path, monkeypatch):
    """CommandReviewerAdapter must not leak unrelated secrets to child subagent CLI processes."""
    monkeypatch.setenv("SUPER_SECRET_TOKEN", "leak_me_if_you_can")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-valid-sample-key-12345")

    helper = tmp_path / "env_check.py"
    helper.write_text(
        "# -*- coding: utf-8 -*-\n"
        "import os, sys, pathlib\n"
        "assert 'SUPER_SECRET_TOKEN' not in os.environ, 'Secret token leaked!'\n"
        "assert os.environ.get('ANTHROPIC_API_KEY') == 'sk-ant-valid-sample-key-12345'\n"
        "pathlib.Path(sys.argv[1]).write_text('ok', encoding='utf-8')\n",
        encoding="utf-8"
    )

    out_file = tmp_path / "out.md"
    p = ct.ParticipantSpec(
        id="anthropic_agent",
        executor="command",
        provider="anthropic",
        cmd=f"python {helper} {{out_path}}"
    )
    adapter = CommandReviewerAdapter()
    req = ct.ReviewRequest(
        task_path=str(tmp_path / "task.txt"),
        out_path=str(out_file),
        findings_path=str(tmp_path / "f.json"),
        participant=p
    )
    res = adapter.review(req)
    assert res.success is True


def test_participant_id_slug_validation_and_path_containment(tmp_path):
    """Participant IDs must be validated slugs, rejecting path traversal attempts."""
    for bad_id in ("../evil", "foo/bar", "-flag", "has space", "evil;rm -rf", "a" * 65):
        with pytest.raises(ValueError):
            ct.validate_participant_id(bad_id)

        with pytest.raises(ValueError):
            ct.ParticipantSpec(id=bad_id, executor="command")


def test_review_result_matches_json_schema(tmp_path):
    """ReviewResult dataclass must strictly validate against review-result.schema.json."""
    import jsonschema

    schema_file = ROOT / "schemas/review-result.schema.json"
    finding_file = ROOT / "schemas/review-finding.schema.json"
    schema = json.loads(schema_file.read_text(encoding="utf-8"))
    finding_schema = json.loads(finding_file.read_text(encoding="utf-8"))

    finding = ct.Finding(id="F01", target="foo.py", claim="broken logic", severity="P0", blocking=True)
    res = ct.ReviewResult(
        participant_id="sonnet",
        phase="plan",
        success=True,
        text="Review done",
        findings=[finding],
        wall_time_seconds=1.2345
    )

    payload = res.to_dict()
    # 本地离线 Schema 解析，阻断外部网络请求
    schema_store = {
        schema.get("$id", "review-result.schema.json"): schema,
        finding_schema.get("$id", "review-finding.schema.json"): finding_schema,
        "review-finding.schema.json": finding_schema,
    }
    resolver = jsonschema.RefResolver.from_schema(schema, store=schema_store)
    jsonschema.validate(instance=payload, schema=schema, resolver=resolver)


def test_panel_spec_matches_json_schema():
    """PanelSpec dataclass must strictly validate against review-panel-spec.schema.json."""
    import jsonschema

    schema_file = ROOT / "schemas/review-panel-spec.schema.json"
    schema = json.loads(schema_file.read_text(encoding="utf-8"))

    p1 = ct.ParticipantSpec(id="p1", executor="command", model="claude-3-7-sonnet")
    p2 = ct.ParticipantSpec(id="p2", executor="hermes.cli", model="gpt-4o")
    panel = ct.PanelSpec(
        panel_id="panel_test",
        participants=[p1, p2],
        budget_max_calls=15,
        budget_max_cost_usd=5.0,
        budget_max_seconds=1800
    )

    payload = panel.to_dict()
    resolver = jsonschema.RefResolver.from_schema(schema)
    jsonschema.validate(instance=payload, schema=schema, resolver=resolver)


def test_mcp_recompute_scientific_integrity():
    """academic_recompute_statistics must refuse to forge Cohen's d and correctly check p value."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import mcp_server

    # 1. t_stat, df, p_value 计算真实接通，不报 AttributeError
    req = {
        "jsonrpc": "2.0", "id": 10, "method": "tools/call",
        "params": {
            "name": "academic_recompute_statistics",
            "arguments": {"t_stat": 2.101, "df": 18.5, "p_value": 0.05}
        }
    }
    resp = mcp_server.process_message(req)
    data = json.loads(resp["result"]["content"][0]["text"])
    assert "recomputed_p" in data
    assert "p_match" in data
    assert "t_test_error" not in data

    # 2. 缺失参数时拒绝伪造 Cohen's d
    req_missing_d = {
        "jsonrpc": "2.0", "id": 11, "method": "tools/call",
        "params": {
            "name": "academic_recompute_statistics",
            "arguments": {"mean1": 10.0, "mean2": 8.0}  # missing sd1, n1, sd2, n2
        }
    }
    resp_missing = mcp_server.process_message(req_missing_d)
    data_missing = json.loads(resp_missing["result"]["content"][0]["text"])
    assert "cohens_d" not in data_missing
    assert "cohens_d_error" in data_missing
    assert "Missing required parameters" in data_missing["cohens_d_error"]

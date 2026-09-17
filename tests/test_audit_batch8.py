# -*- coding: utf-8 -*-
"""Batch 8 regression tests for dynamic multi-model and custom subagent orchestration:
- Arbitrary number and arbitrary specifications of models via CLI or JSON config
- Custom CLI subagent runner execution template
- Large model count (> 8) derangement fallback
- Dynamic API key whitelist matching for non-default providers (Anthropic, OpenAI, etc.)
"""
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_module(name, rel_path):
    p = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


orch_v2 = _load_module("orch_v2_b8", "skills/cross-review-five/scripts/orchestrate_v2.py")


def test_dynamic_model_registration_via_cli_spec():
    """User can supply arbitrary 3-part or 4-part specs like sonnet:anthropic:claude-3-7-sonnet."""
    models_arg = "sonnet:anthropic:claude-3-7-sonnet,gpt4:openai:gpt-4o:cli"
    keys = orch_v2.parse_and_register_models(models_arg=models_arg)
    assert keys == ["sonnet", "gpt4"]
    assert orch_v2.MODELS["sonnet"] == ("anthropic", "claude-3-7-sonnet")
    assert orch_v2.CUSTOM_SPECS["gpt4"]["runner"] == "cli"


def test_dynamic_model_registration_via_json_file(tmp_path):
    """User can define an arbitrary number of models and subagents in a JSON file."""
    cfg = tmp_path / "models.json"
    cfg.write_text(json.dumps([
        {"key": "claude", "provider": "anthropic", "model": "claude-3-7-sonnet"},
        {"key": "gemini-agent", "runner": "cli", "cmd": "gemini -p {prompt_path}"},
        {"key": "custom-llm", "provider": "local", "model": "qwen-2.5-72b"},
    ]), encoding="utf-8")

    keys = orch_v2.parse_and_register_models(models_file=str(cfg))
    assert keys == ["claude", "gemini-agent", "custom-llm"]
    assert orch_v2.CUSTOM_SPECS["gemini-agent"]["cmd"] == "gemini -p {prompt_path}"


def test_derangement_fallback_for_large_model_counts():
    """When N > 8, max_weight_derangement safely falls back to circular shift without O(N!) factorial search."""
    large_panel = [f"m_{i}" for i in range(12)]
    weights = {(f"m_{i}", f"m_{j}"): 1.0 for i in range(12) for j in range(12)}
    pairs = orch_v2.max_weight_derangement(large_panel, weights)
    assert len(pairs) == 12
    for r, t in pairs:
        assert r != t
    # 验证循环位移性
    for i in range(12):
        assert pairs[i] == (large_panel[i], large_panel[(i + 1) % 12])


def test_minimal_child_env_matches_dynamic_providers():
    """_minimal_child_env dynamically whitelists API keys for new providers like Anthropic and OpenAI."""
    orch_v2.register_model_spec("sonnet", "anthropic", "claude-3-7-sonnet")
    orch_v2.register_model_spec("o3mini", "openai", "o3-mini")

    mock_env = {
        "PATH": "/usr/bin",
        "ANTHROPIC_API_KEY": "sk-ant-test-123",
        "OPENAI_API_KEY": "sk-oai-test-456",
        "UNRELATED_KEY": "leak_prevention",
    }

    with patch.dict(os.environ, mock_env, clear=True):
        env_sonnet = orch_v2._minimal_child_env("sonnet")
        assert env_sonnet.get("ANTHROPIC_API_KEY") == "sk-ant-test-123"
        assert "OPENAI_API_KEY" not in env_sonnet
        assert "UNRELATED_KEY" not in env_sonnet

        env_o3 = orch_v2._minimal_child_env("o3mini")
        assert env_o3.get("OPENAI_API_KEY") == "sk-oai-test-456"
        assert "ANTHROPIC_API_KEY" not in env_o3


def test_spawn_with_custom_cli_runner():
    """spawn executes custom CLI command template when runner is cli/cmd."""
    orch_v2.register_model_spec(
        "custom-agent", "custom", "agent-x", runner="cli",
        cmd="python -m myagent --query {prompt_path}"
    )

    spawned_cmds = []

    def fake_popen(cmd, stdout=None, stderr=None, cwd=None, env=None):
        spawned_cmds.append(cmd)
        mock = MagicMock()
        mock.poll.return_value = 0
        mock.returncode = 0
        return mock

    with patch.object(orch_v2.subprocess, "Popen", side_effect=fake_popen):
        orch_v2.spawn("custom-agent", "fake_prompt.md", os.devnull)

    assert len(spawned_cmds) == 1
    executed_cmd = spawned_cmds[0]
    assert executed_cmd[0] == "python"
    assert executed_cmd[1] == "-m"
    assert executed_cmd[2] == "myagent"
    assert executed_cmd[4] == "fake_prompt.md"

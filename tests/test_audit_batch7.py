# -*- coding: utf-8 -*-
"""Batch 7 regression tests for critical P1 audit items:
- Literature/Retraction watch 404 handling & Crossref fallback bypass (no retry on 404)
- OpenAlex credential authority boundary (urlsplit vs startswith)
- Crossref /v1/ explicit endpoint
- RFC 9110 Retry-After header parsing (delta-seconds & HTTP-date)
- Cross-review child process isolation: --ignore-rules & minimal env allowlist
- Cross-review streaming task digest
- Scfabric AMD ROCm vs CUDA runtime identity separation
- Scfabric Intel XPU backend registration & probe
"""
import importlib.util
import io
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_module(name, rel_path):
    p = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


lit_watch = _load_module("lit_watch_b7", "skills/literature-watch/scripts/watch.py")
ret_watch = _load_module("ret_watch_b7", "skills/retraction-watch/scripts/watch.py")
orch_v2 = _load_module("orch_v2_b7", "skills/cross-review-five/scripts/orchestrate_v2.py")
sc_backends = _load_module("sc_backends_b7", "scripts/scfabric/backends.py")
sc_probe = _load_module("sc_probe_b7", "scripts/scfabric/hardware_probe.py")


def _make_mock_response(content_bytes):
    resp = MagicMock()
    resp.__enter__.return_value.read.return_value = content_bytes
    resp.read.return_value = content_bytes
    return resp


# =========================================================================
# 1. Literature & Retraction watch: 404 non-retriable fallback
# =========================================================================

def test_p1_literature_watch_404_routes_to_crossref_fallback_without_retry():
    """404 on OpenAlex DOI query must return None immediately without retry and trigger Crossref."""
    calls = []

    def fake_urlopen(req, timeout=20):
        url = req.full_url
        calls.append(url)
        if "api.openalex.org" in url:
            # 模拟 OpenAlex 404 Not Found
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b"{}"))
        if "api.crossref.org" in url:
            return _make_mock_response(b'{"message": {"title": ["Test Crossref Paper"], "issued": {"date-parts": [[2025]]}}}')
        raise RuntimeError(f"Unexpected URL: {url}")

    with patch.object(lit_watch, "urlopen", side_effect=fake_urlopen):
        items, truncated = lit_watch.fetch_citing_works("10.1234/test404", date(2026, 1, 1))

    # 验证：OpenAlex 只请求了 1 次（没有被重试 3 次！），且成功走入 Crossref 兜底
    openalex_calls = [u for u in calls if "api.openalex.org" in u]
    crossref_calls = [u for u in calls if "api.crossref.org" in u]
    assert len(openalex_calls) == 1
    assert len(crossref_calls) == 1
    assert len(items) == 1
    assert items[0]["source"] == "crossref-fallback"
    assert items[0]["title"] == "Test Crossref Paper"
    assert items[0]["publication_year"] == 2025


def test_p1_retraction_watch_404_does_not_retry_and_sets_none():
    """Retraction watch check_doi handles 404 by returning None for is_retracted without retry."""
    calls = []

    def fake_urlopen(req, timeout=20):
        url = req.full_url
        calls.append(url)
        if "api.openalex.org" in url:
            raise HTTPError(url, 404, "Not Found", hdrs=None, fp=io.BytesIO(b"{}"))
        if "api.crossref.org" in url:
            return _make_mock_response(b'{"message": {"items": [], "total-results": 0}}')
        raise RuntimeError(f"Unexpected URL: {url}")

    with patch.object(ret_watch, "urlopen", side_effect=fake_urlopen):
        snap = ret_watch.check_doi("10.1234/unknown")

    openalex_calls = [u for u in calls if "api.openalex.org" in u]
    assert len(openalex_calls) == 1
    assert snap["is_retracted"] is None
    assert snap["signals"] == []


# =========================================================================
# 2. OpenAlex Credential Injection & Crossref /v1/ Endpoint
# =========================================================================

def test_p1_openalex_token_authority_check_guards_against_prefix_spoofing():
    """Token must NOT be sent to spoofed domains like https://api.openalex.org.evil.com."""
    sent_headers = {}

    def fake_urlopen(req, timeout=20):
        sent_headers["auth"] = req.headers.get("Authorization")
        return _make_mock_response(b"{}")

    with patch.dict(os.environ, {"OPENALEX_API_KEY": "secret_key_xyz"}):
        with patch.object(lit_watch, "urlopen", side_effect=fake_urlopen):
            # 1. 正常官方域名 -> 附加 Bearer key
            lit_watch.get("https://api.openalex.org/works")
            assert sent_headers.get("auth") == "Bearer secret_key_xyz"

            # 2. 伪造前缀域名 -> 严禁附加 Bearer key
            sent_headers.clear()
            lit_watch.get("https://api.openalex.org.attacker.com/works")
            assert sent_headers.get("auth") is None

            # 3. HTTP 非加密协议 -> 严禁附加 Bearer key
            sent_headers.clear()
            lit_watch.get("http://api.openalex.org/works")
            assert sent_headers.get("auth") is None


def test_p1_crossref_endpoint_is_explicit_v1():
    """Crossref API endpoint must explicitly specify /v1."""
    assert lit_watch.CROSSREF == "https://api.crossref.org/v1"
    assert ret_watch.CROSSREF == "https://api.crossref.org/v1"


def test_p2_retry_after_supports_delta_seconds_and_http_date():
    """_parse_retry_after must parse both integer seconds and RFC 9110 HTTP-date."""
    # 秒数字符串
    assert lit_watch._parse_retry_after("12", default_delay=2.0) == 12.0
    assert lit_watch._parse_retry_after("0", default_delay=2.0) == 0.0

    # HTTP-date 格式 (未来时间)
    future_date_str = "Wed, 21 Oct 2099 07:28:00 GMT"
    parsed = lit_watch._parse_retry_after(future_date_str, default_delay=2.0)
    # 应被 min(..., 30.0) 截断为上限 30 秒
    assert parsed == 30.0

    # 无法解析时降级到 default_delay
    assert lit_watch._parse_retry_after("invalid-format", default_delay=5.0) == 5.0
    assert lit_watch._parse_retry_after(None, default_delay=5.0) == 5.0


# =========================================================================
# 3. Cross-review child process isolation & optimization
# =========================================================================

def test_p1_cross_review_spawn_includes_ignore_rules_and_minimal_env():
    """Spawn must pass --ignore-rules and filter environment to safe minimal allowlist."""
    spawned_cmds = []
    spawned_envs = []

    def fake_popen(cmd, stdout=None, stderr=None, cwd=None, env=None):
        spawned_cmds.append(cmd)
        spawned_envs.append(env)
        mock_proc = MagicMock()
        mock_proc.poll.return_value = 0
        mock_proc.returncode = 0
        return mock_proc

    mock_environ = {
        "PATH": "/usr/bin",
        "HOME": "/home/user",
        "UNRELATED_SECRET_TOKEN": "should_never_leak_to_child",
        "AWS_SECRET_ACCESS_KEY": "sensitive_cloud_key",
        "KIMI_API_KEY": "kimi_secret_val",
        "DEEPSEEK_API_KEY": "ds_secret_val",
        "GEMINI_API_KEY": "gemini_secret_val",
    }

    with patch.dict(os.environ, mock_environ, clear=True):
        with patch.object(orch_v2.subprocess, "Popen", side_effect=fake_popen):
            # 启动 kimi-k3
            orch_v2.spawn("kimi-k3", "prompt.md", os.devnull)

    assert len(spawned_cmds) == 1
    cmd = spawned_cmds[0]
    child_env = spawned_envs[0]

    # 校验必须带 --ignore-rules
    assert "--ignore-rules" in cmd
    assert "-m" in cmd and "kimi-k3" in cmd

    # 校验不相关密钥被完全隔离
    assert "UNRELATED_SECRET_TOKEN" not in child_env
    assert "AWS_SECRET_ACCESS_KEY" not in child_env
    # 校验其他模型提供商的密钥不被泄露给 kimi-k3
    assert "DEEPSEEK_API_KEY" not in child_env
    assert "GEMINI_API_KEY" not in child_env
    # 校验 kimi 自身所需密钥被保全
    assert child_env.get("KIMI_API_KEY") == "kimi_secret_val"
    assert child_env.get("PATH") == "/usr/bin"


def test_p1_streaming_task_digest(tmp_path):
    """_task_digest must stream files in chunks without full-file read memory spikes."""
    f = tmp_path / "big_task.md"
    f.write_text("# Review Task\n" * 1000, encoding="utf-8")
    digest = orch_v2._task_digest(str(f))
    assert digest is not None
    assert len(digest) == 16


# =========================================================================
# 4. Scfabric: ROCm runtime identity & Intel XPU backend
# =========================================================================

def test_p1_scfabric_rocm_runtime_distinction():
    """PyTorch on ROCm (hip is not None) must be identified with runtime='rocm'."""
    mock_torch = MagicMock()
    mock_torch.cuda.is_available.return_value = True
    mock_torch.cuda.get_device_name.return_value = "AMD Radeon RX 7900 XTX"
    mock_torch.cuda.device_count.return_value = 1
    mock_torch.__version__ = "2.6.0+rocm6.2"
    mock_torch.version.hip = "6.2.41133"

    with patch.dict("sys.modules", {"torch": mock_torch}):
        res = sc_backends._probe_torch_cuda()
        assert res["executable"] is True
        assert res["runtime"] == "rocm"
        assert res["hip_version"] == "6.2.41133"

        # 普通 NVIDIA CUDA (hip 为 None)
        mock_torch.version.hip = None
        mock_torch.cuda.get_device_name.return_value = "NVIDIA GeForce RTX 4090"
        res_cuda = sc_backends._probe_torch_cuda()
        assert res_cuda["executable"] is True
        assert res_cuda["runtime"] == "cuda"
        assert res_cuda["hip_version"] is None


def test_p1_scfabric_torch_xpu_backend_registered():
    """torch_xpu must be registered in BACKENDS with accelerator kind and float16/bfloat16 dtypes."""
    assert "torch_xpu" in sc_backends.BACKENDS
    spec = sc_backends.BACKENDS["torch_xpu"]
    assert spec.kind == "accelerator"
    assert spec.supports_dtype("float32")
    assert spec.supports_dtype("float16")
    assert spec.supports_dtype("bfloat16")
    assert not spec.supports_dtype("float64")

    # 模拟 XPU 可用
    mock_torch = MagicMock()
    mock_torch.xpu.is_available.return_value = True
    mock_torch.xpu.get_device_name.return_value = "Intel Data Center GPU Max 1550"
    mock_torch.__version__ = "2.6.0"

    with patch.dict("sys.modules", {"torch": mock_torch}):
        probe_res = sc_backends._probe_torch_xpu()
        assert probe_res["executable"] is True
        assert probe_res["runtime"] == "xpu"
        assert probe_res["device_name"] == "Intel Data Center GPU Max 1550"

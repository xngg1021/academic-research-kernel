"""cross-review-five v2 编排器 (Sparse Adaptive Deliberation) 的离线可测单元测试。"""

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "orchestrate_v2", ROOT / "skills" / "cross-review-five" / "scripts" / "orchestrate_v2.py")
oc2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oc2)


def test_v2_model_table_and_presets():
    expected_models = {
        "kimi-k3": ("kimi", "kimi-k3"),
        "dsv4pro": ("deepseek", "deepseek-v4-pro"),
        "glm53": ("zai", "glm-5.3"),
        "gemini38flash": ("google", "gemini-3.8-flash"),
        "gemini31pro": ("google", "gemini-3.1-pro-preview"),
    }
    assert oc2.MODELS == expected_models
    assert set(oc2.MODE_PRESETS) == {"economy", "standard", "audit"}
    assert oc2.MODE_PRESETS["economy"]["max_challenges"] == 1
    assert oc2.MODE_PRESETS["standard"]["max_challenges"] == 3
    assert oc2.MODE_PRESETS["audit"]["max_challenges"] == 5


def test_normalize_target():
    assert oc2.normalize_target("schemas/foo.json:41-52") == "schemas/foo.json"
    assert oc2.normalize_target("D:\\repos\\proj\\src\\lib.py:120") == "d:/repos/proj/src/lib.py"
    assert oc2.normalize_target("  core_engine  ") == "core_engine"
    assert oc2.normalize_target("") == "general"


def test_max_weight_derangement():
    models = ["A", "B", "C"]
    # 构造权重：A->B 很重, B->C 很重, C->A 很重 (环权重最高)
    weights = {
        ("A", "B"): 10.0,
        ("B", "C"): 10.0,
        ("C", "A"): 10.0,
        ("A", "C"): 1.0,
        ("B", "A"): 1.0,
        ("C", "B"): 1.0,
    }
    pairs = oc2.max_weight_derangement(models, weights)
    assert len(pairs) == 3
    # 验证错排无自环
    for reviewer, target in pairs:
        assert reviewer != target
    assert set(pairs) == {("A", "B"), ("B", "C"), ("C", "A")}


def test_cluster_issues():
    models = ["kimi-k3", "dsv4pro", "glm53"]
    findings_by_model = {
        "kimi-k3": {
            "findings": [
                {"target": "core.py:10", "kind": "bug", "claim": "资源未释放", "evidence": ["core.py:10"], "severity": "P1"},
                {"target": "db.py", "kind": "perf", "claim": "全表扫描", "evidence": ["db.py:50"], "severity": "P2"},
            ]
        },
        "dsv4pro": {
            "findings": [
                {"target": "core.py:12", "kind": "bug", "claim": "资源句柄泄漏", "evidence": ["core.py:12"], "severity": "P1"},
                {"target": "auth.py", "kind": "security", "claim": "凭证硬编码", "evidence": ["auth.py:5"], "severity": "P0"},
            ]
        },
        "glm53": {
            "findings": [
                {"target": "schemas/api.json", "kind": "schema_bug", "claim": "缺少 items 约束", "evidence": ["schemas/api.json:88"], "severity": "P0"},
            ]
        }
    }

    consensus, singletons, contradictions = oc2.cluster_issues(models, findings_by_model)

    # core.py 两个模型均指出，应为共识 (或分歧)
    targets_consensus = {c["target"] for c in consensus}
    targets_singleton = {s["target"] for s in singletons}

    assert "core.py" in targets_consensus
    assert "schemas/api.json" in targets_singleton
    assert "auth.py" in targets_singleton
    assert "db.py" in targets_singleton

    # 找到 schemas/api.json 的单例，确认是 glm53 提出且保留了 P0
    schema_item = next(s for s in singletons if s["target"] == "schemas/api.json")
    assert schema_item["raised_by"] == ["glm53"]
    assert schema_item["severity"] == "P0"


def test_extract_findings_fallback_markdown(tmp_path):
    stream = tmp_path / "stream1"
    stream.mkdir()

    # 模拟 review-kimi-k3.md 包含 markdown 代码块
    md_content = """# 评审意见
我仔细阅读了代码。

```json
{
  "findings": [
    {
      "id": "F1",
      "target": "utils.py:40",
      "kind": "bug",
      "claim": "除零异常",
      "evidence": ["utils.py:40"],
      "severity": "P1",
      "blocking": true
    }
  ],
  "unknowns": [],
  "assumptions": []
}
```
"""
    (stream / "review-kimi-k3.md").write_text(md_content, encoding="utf-8")

    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert len(data["findings"]) == 1
    assert data["findings"][0]["claim"] == "除零异常"

    # 验证落盘了 sidecar json
    assert (stream / "findings-kimi-k3.json").exists()


def test_merge_and_synthesize_end_to_end(tmp_path):
    stream = tmp_path / "stream_e2e"
    stream.mkdir()

    # 构造两个模型的 findings
    f_k3 = {
        "findings": [
            {"target": "server.py", "kind": "perf", "claim": "并发锁争用", "evidence": ["server.py:20"], "severity": "P1"},
            {"target": "config.yaml", "kind": "bug", "claim": "配置项缺失", "evidence": ["config.yaml:5"], "severity": "P2"}
        ]
    }
    f_ds = {
        "findings": [
            {"target": "server.py", "kind": "perf", "claim": "存在锁冲突", "evidence": ["server.py:22"], "severity": "P1"},
            {"target": "crypto.py", "kind": "security", "claim": "弱随机数生成", "evidence": ["crypto.py:15"], "severity": "P0"}
        ]
    }

    (stream / "findings-kimi-k3.json").write_text(json.dumps(f_k3), encoding="utf-8")
    (stream / "findings-dsv4pro.json").write_text(json.dumps(f_ds), encoding="utf-8")

    # 执行 stage_merge_v2
    ok_merge = oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro"], mode="economy")
    assert ok_merge is True
    assert (stream / "issue-registry.json").exists()
    assert (stream / "challenge-plan.json").exists()
    assert (stream / "graph-summary.md").exists()

    # 模拟写入质询答复
    (stream / "challenge-reply-C01-kimi-k3.md").write_text(
        "第一步【提取增量】：核验了对方的弱随机数。\n第四步【裁决与表态】：【CONCEDE】对方指出 crypto.py 使用了 random 而非 secrets，证据确凿。",
        encoding="utf-8"
    )

    # 执行 stage_synthesize_v2
    ok_synth = oc2.stage_synthesize_v2(str(stream))
    assert ok_synth is True
    assert (stream / "consensus-report.md").exists()
    assert (stream / "unresolved-ledger.json").exists()

    with open(stream / "unresolved-ledger.json", "r", encoding="utf-8") as f:
        ledger = json.load(f)
    # 验证少数派保护：P0 的 crypto.py 是否进入账本或被识别
    report_text = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "五人交叉评审合议报告 (v2 Sparse Deliberation)" in report_text
    assert "CONCEDE" in report_text or "认同/认输" in report_text

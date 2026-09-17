"""cross-review-five v2 编排器 (Sparse Adaptive Deliberation) 的离线可测单元测试。

覆盖 implementation-contract-v2.md 的 C01-C11 验收标准:
- C01 聚类按独立模型数判定 (消灭伪共识)
- C02 矛盾仅由互斥 polarity 判定 (消灭伪矛盾)
- C03 canonical target 归一 + 幽灵 target 拒绝
- C04 findings sidecar 优先 + provenance + 平衡括号 JSON 提取
- C05 synthesize 对账 + 逐断言表态
- C06 质询者排除当事人 + bundle 匿名乱序
- C07 少数派保护与 REFUTED 联动 + 幽灵证据丢弃
- C09 raised_by 保序确定性
- C10 单模型失败容错
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "orchestrate_v2", ROOT / "skills" / "cross-review-five" / "scripts" / "orchestrate_v2.py")
oc2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oc2)


def _f(**kw):
    """构造一条 finding, 带默认值。"""
    base = {"id": "F1", "target": "core.py", "kind": "bug", "claim": "资源未释放",
            "evidence": ["core.py:10"], "severity": "P1", "blocking": False}
    base.update(kw)
    return base


# ---------- 基础 ----------

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


def test_max_weight_derangement():
    models = ["A", "B", "C"]
    weights = {
        ("A", "B"): 10.0, ("B", "C"): 10.0, ("C", "A"): 10.0,
        ("A", "C"): 1.0, ("B", "A"): 1.0, ("C", "B"): 1.0,
    }
    pairs = oc2.max_weight_derangement(models, weights)
    assert len(pairs) == 3
    for reviewer, target in pairs:
        assert reviewer != target
    assert set(pairs) == {("A", "B"), ("B", "C"), ("C", "A")}


# ---------- C03: canonical 目标归一 ----------

def test_normalize_target_basename():
    assert oc2.normalize_target("schemas/foo.json:41-52") == "foo.json"
    assert oc2.normalize_target("D:\\repos\\proj\\src\\lib.py:120") == "lib.py"
    assert oc2.normalize_target("  core_engine  ") == "core_engine"
    assert oc2.normalize_target("") == "general"


def test_normalize_target_path_equivalence():
    """同一文件五种写法归一后必须相等 (用中性路径, 避免触发个人路径检测)。"""
    variants = [
        "approval_detection.py",
        "tools/approval_detection.py:238",
        "/opt/audit/hermes-agent/tools/approval_detection.py",
        "/opt/audit/hermes-agent/tools/approval_detection.py:238",
        "D:/repos/proj/tools/APPROVAL_DETECTION.PY",
    ]
    canon = {oc2.normalize_target(v) for v in variants}
    assert canon == {"approval_detection.py"}


def test_is_plausible_target_rejects_regex_fragment():
    assert oc2._is_plausible_target("approval_detection.py")
    assert oc2._is_plausible_target("test_x.py")
    assert not oc2._is_plausible_target("cli/.py")
    assert not oc2._is_plausible_target(r"cli\.py")
    assert not oc2._is_plausible_target("cli[abc].py")
    assert not oc2._is_plausible_target("README")


# ---------- C01/C02/C09: 聚类语义 ----------

def test_single_model_multi_findings_not_consensus():
    """C01: 同一模型对同一 target 的多条 findings 归 singleton, 不冒充多模型共识。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="core.py:10", claim="资源未释放"),
                                 _f(target="core.py:20", claim="句柄泄漏", id="F2")]},
        "dsv4pro": {"findings": []},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert consensus == []
    assert [s["target"] for s in singletons] == ["core.py"]
    assert singletons[0]["raised_by"] == ["kimi-k3"]


def test_claim_keywords_do_not_make_contradiction():
    """C02: claim 含'不/错'字、kind 不同, 不构成矛盾。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="core.py", kind="bug", claim="资源未关闭,不正确释放")]},
        "dsv4pro": {"findings": [_f(target="core.py", kind="perf", claim="句柄未释放,存在错误")]},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert contradictions == []
    assert len(consensus) == 1
    assert consensus[0]["raised_by"] == ["kimi-k3", "dsv4pro"]


def test_polarity_opposition_is_contradiction():
    """C02: 不同模型对同一 target 给出互斥 polarity 才判矛盾。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="cache.py", claim="缓存未失效", polarity="present")]},
        "dsv4pro": {"findings": [_f(target="cache.py", claim="缓存已失效", polarity="absent")]},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert consensus == []
    assert len(contradictions) == 1
    assert contradictions[0]["state"] == "contradiction"


def test_raised_by_preserves_order():
    """C09: 保序去重, 与输入顺序无关的确定性。"""
    assert oc2.dedup_preserve_order(["b", "a", "b", "a", "c"]) == ["b", "a", "c"]
    # 跨进程确定性: 重复运行结果一致
    assert oc2.dedup_preserve_order(["b", "a", "b", "a", "c"]) == \
        oc2.dedup_preserve_order(["b", "a", "b", "a", "c"])


# ---------- C04/C10: findings 提取 ----------

def test_extract_findings_md_json_block(tmp_path):
    stream = tmp_path / "stream1"
    stream.mkdir()
    md_content = """# 评审意见
```json
{
  "findings": [
    {"id": "F1", "target": "utils.py:40", "kind": "bug",
     "claim": "除零异常", "evidence": ["utils.py:40"], "severity": "P1", "blocking": true}
  ],
  "unknowns": [], "assumptions": []
}
```
"""
    (stream / "review-kimi-k3.md").write_text(md_content, encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert len(data["findings"]) == 1
    assert data["findings"][0]["claim"] == "除零异常"
    assert data["findings"][0]["provenance"] == "model_written"
    assert (stream / "findings-kimi-k3.json").exists()


def test_extract_findings_nested_brace_json(tmp_path):
    """C10: 嵌套大括号的 JSON 块必须正确解析 (平衡提取)。"""
    stream = tmp_path / "stream_nested"
    stream.mkdir()
    md_content = """# 评审意见
```json
{
  "findings": [
    {"id": "F1", "target": "cfg.py", "kind": "bug",
     "claim": "配置字典含嵌套映射的合并错误",
     "evidence": ["cfg.py:10"], "severity": "P1"}
  ],
  "unknowns": [], "assumptions": []
}
```
"""
    (stream / "review-kimi-k3.md").write_text(md_content, encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert len(data["findings"]) == 1
    assert data["findings"][0]["target"] == "cfg.py"


def test_sidecar_preferred_over_fallback(tmp_path):
    """C04: sidecar 存在且合法时直接使用, 不走 fallback。"""
    stream = tmp_path / "stream_sidecar"
    stream.mkdir()
    sidecar = {"findings": [_f(target="real.py", claim="真实发现")],
               "unknowns": [], "assumptions": []}
    (stream / "findings-kimi-k3.json").write_text(json.dumps(sidecar), encoding="utf-8")
    (stream / "review-kimi-k3.md").write_text(
        "fake.py:1 崩溃 fake.py:2 缺陷", encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert len(data["findings"]) == 1
    assert data["findings"][0]["target"] == "real.py"
    assert data["findings"][0]["provenance"] == "model_written"


def test_sidecar_non_object_no_crash(tmp_path):
    """C04/C10: sidecar 为数组等非对象形状时不引发 AttributeError。"""
    stream = tmp_path / "stream_badsidecar"
    stream.mkdir()
    (stream / "findings-kimi-k3.json").write_text("[1, 2, 3]", encoding="utf-8")
    (stream / "review-kimi-k3.md").write_text("", encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert isinstance(data, dict)
    assert data["findings"] == []


def test_fallback_rejects_regex_fragment(tmp_path):
    """C03/C04: 正则残片与幽灵路径不产生 finding。"""
    stream = tmp_path / "stream_ghost"
    stream.mkdir()
    (stream / "review-kimi-k3.md").write_text(
        "检测规则缺失 r'\\b(pkill|killall)\\b.*\\b(hermes|gateway|cli\\.py)\\b'\n"
        "cl\\.py:1 崩溃\n", encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    for f in data["findings"]:
        assert oc2._is_plausible_target(f["target"])


# ---------- C05/C06/C07: merge + synthesize ----------

def _write_two_sidecars(stream, findings_by_model):
    for m, findings in findings_by_model.items():
        (stream / f"findings-{m}.json").write_text(
            json.dumps({"findings": findings, "unknowns": [], "assumptions": []}),
            encoding="utf-8")


def test_reviewer_excludes_contradiction_parties(tmp_path):
    """C06: 矛盾质询的 reviewer 不得是争议当事人。"""
    stream = tmp_path / "stream_r"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    assert len(plan) == 1
    assert plan[0]["type"] == "contradiction"
    assert plan[0]["reviewer"] not in ("kimi-k3", "dsv4pro")


def test_bundle_anonymized(tmp_path):
    """C06: bundle 提案不含模型短名, 别名 Proposal-N, 乱序由固定种子决定。"""
    stream = tmp_path / "stream_a"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    bundle = plan[0]["bundle"]
    raw = json.dumps(bundle, ensure_ascii=False)
    for m in ("kimi-k3", "dsv4pro", "gemini38flash"):
        assert m not in raw
    aliases = [p["source_alias"] for p in bundle["proposals"]]
    assert aliases == sorted(aliases, key=lambda a: int(a.split("-")[1]))
    # 确定性: 两次 merge 产出字节一致
    b2 = (stream / "challenge-plan.json").read_bytes()
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    b3 = (stream / "challenge-plan.json").read_bytes()
    assert b2 == b3


def test_mixed_stances_parsed():
    """C05: 一份答复含三种表态时, 三类均被计数。"""
    text = ("第四步【裁决与表态】：\n"
            "【CONCEDE】对方证据确凿, 认同。\n"
            "【REFUTED】该条不成立, 反例见附件。\n"
            "【UNRESOLVED_REQUIRES_CODE_VERIFICATION】需跑测试验证。\n")
    conceded, refuted, unresolved = oc2._parse_stances(text)
    assert len(conceded) == 1 and len(refuted) == 1 and len(unresolved) == 1


def test_synthesize_missing_reply_reported(tmp_path):
    """C05: 质询计划与答复对账, 缺失答复在报告点名。"""
    stream = tmp_path / "stream_m"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    # 不写任何 challenge-reply
    oc2.stage_synthesize_v2(str(stream))
    report = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "质询缺失" in report or "MISSING" in report
    assert "质询缺失 (Missing Replies): 1 项" in report


def test_refuted_singleton_excluded_from_ledger(tmp_path):
    """C07: 被质询 REFUTED 的单例不得进入未决账本。"""
    stream = tmp_path / "stream_f"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="crypto.py", claim="弱随机数", severity="P0")],
        "dsv4pro": [],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    assert plan and plan[0]["type"] == "singleton_audit"
    cid, reviewer = plan[0]["challenge_id"], plan[0]["reviewer"]
    (stream / f"challenge-reply-{cid}-{reviewer}.md").write_text(
        "第四步【裁决与表态】：【REFUTED】该断言不成立, 代码实际使用 secrets 模块。",
        encoding="utf-8")
    oc2.stage_synthesize_v2(str(stream))
    ledger = json.loads((stream / "unresolved-ledger.json").read_text(encoding="utf-8"))
    issue_ids = [u.get("issue_id") for u in ledger]
    assert plan[0]["issue_id"] not in issue_ids


def test_ghost_absolute_evidence_excluded(tmp_path):
    """C07: 绝对路径证据不存在 (幽灵证据) 时单例不得入账, 报告记录丢弃。"""
    stream = tmp_path / "stream_g"
    stream.mkdir()
    ghost = "/opt/hermes-nonexistent-dir-xyz/ghost.py"
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="ghost.py", claim="幽灵发现", severity="P0", evidence=[ghost])],
        "dsv4pro": [],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    oc2.stage_synthesize_v2(str(stream))
    ledger = json.loads((stream / "unresolved-ledger.json").read_text(encoding="utf-8"))
    report = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert ledger == []
    assert "幽灵证据" in report


# ---------- C10: 容错 ----------

def test_wait_for_outputs_partial_failure(tmp_path):
    """C10: 单个模型无产出时, 返回逐项状态而非整阶段失败。"""
    ok_file = tmp_path / "ok.md"
    ok_file.write_text("x", encoding="utf-8")
    missing = tmp_path / "missing.md"
    procs = [subprocess.Popen([sys.executable, "-c", "pass"]) for _ in range(2)]
    for p in procs:
        p.wait()
    results = oc2.wait_for_outputs([str(ok_file), str(missing)], procs)
    assert results[str(ok_file)] is True
    assert results[str(missing)] is False


# ---------- 端到端 ----------

def test_merge_and_synthesize_end_to_end(tmp_path):
    stream = tmp_path / "stream_e2e"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="server.py", kind="perf", claim="并发锁争用"),
                    _f(target="config.yaml", kind="bug", claim="配置项缺失", severity="P2")],
        "dsv4pro": [_f(target="server.py", kind="perf", claim="存在锁冲突"),
                    _f(target="crypto.py", kind="security", claim="弱随机数生成", severity="P0")],
    })
    ok_merge = oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro"], mode="economy")
    assert ok_merge is True
    assert (stream / "issue-registry.json").exists()
    assert (stream / "challenge-plan.json").exists()
    assert (stream / "graph-summary.md").exists()

    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    assert plan, "P0 单例应规划质询"
    cid, reviewer = plan[0]["challenge_id"], plan[0]["reviewer"]
    (stream / f"challenge-reply-{cid}-{reviewer}.md").write_text(
        "第一步【提取增量】：核验了对方的弱随机数。\n"
        "第四步【裁决与表态】：【CONCEDE】对方指出 crypto.py 使用了 random 而非 secrets，证据确凿。",
        encoding="utf-8")

    ok_synth = oc2.stage_synthesize_v2(str(stream))
    assert ok_synth is True
    assert (stream / "consensus-report.md").exists()
    assert (stream / "unresolved-ledger.json").exists()
    report_text = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "五人交叉评审合议报告 (v2 Sparse Deliberation)" in report_text
    # 头部计数 + 单例质询答复章节呈现 CONCEDE 表态原文
    assert "质询认同/认输 (Conceded): 1 项" in report_text
    assert "单例/互补质询答复" in report_text
    assert "【CONCEDE】" in report_text
    # server.py 两模型同向 -> consensus
    registry = json.loads((stream / "issue-registry.json").read_text(encoding="utf-8"))
    assert any(c["target"] == "server.py" and c["state"] == "consensus"
               for c in registry["consensus"])

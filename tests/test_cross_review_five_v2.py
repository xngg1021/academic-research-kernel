"""cross-review-five v2 编排器 (Sparse Adaptive Deliberation) 的离线可测单元测试。

覆盖 implementation-contract-v2.md 与第二轮 PR 裁决的全部验收标准:
- 断言级 Issue identity (issue_key 对齐 + claim 哈希兜底 + 宁拆不并)
- 单模型多条 findings 全部保留, severity 不错嫁接
- 同 basename 不同父目录不合并
- 无 polarity 的相反 claim 不默认共识
- run lineage (陈旧产物清理 + manifest 谱系 + 缺失模型进报告)
- 相对幽灵证据标注 unverified
- schema 校验丢弃非法条目
- 全员当事人时质询跳过而非退回当事人
- P0 单例优先于 P2 矛盾占用配额
- merge 幂等 (除 timestamp 外字节一致)
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
    base = {"id": "F1", "target": "core.py", "kind": "bug", "claim": "资源未释放",
            "evidence": ["core.py:10"], "severity": "P1", "blocking": False}
    base.update(kw)
    return base


def _write_two_sidecars(stream, findings_by_model):
    for m, findings in findings_by_model.items():
        (stream / f"findings-{m}.json").write_text(
            json.dumps({"findings": findings, "unknowns": [], "assumptions": []}),
            encoding="utf-8")


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


# ---------- C03: canonical 目标归一 (basename + 关键父目录段) ----------

def test_normalize_target_basename_and_parent():
    assert oc2.normalize_target("schemas/foo.json:41-52") == "schemas/foo.json"
    assert oc2.normalize_target("D:\\repos\\proj\\src\\lib.py:120") == "src/lib.py"
    assert oc2.normalize_target("  core_engine  ") == "core_engine"
    assert oc2.normalize_target("") == "general"


def test_normalize_target_path_equivalence():
    """带相同父目录的写法归一后相等; 裸文件名与带路径写法不再强行等价 (宁拆不并)。"""
    assert oc2.normalize_target("/opt/audit/hermes-agent/tools/approval_detection.py") == "tools/approval_detection.py"
    assert oc2.normalize_target("/opt/audit/hermes-agent/tools/approval_detection.py:238") == "tools/approval_detection.py"
    assert oc2.normalize_target("D:/repos/proj/tools/APPROVAL_DETECTION.PY") == "tools/approval_detection.py"
    assert oc2.normalize_target("approval_detection.py") == "approval_detection.py"
    assert oc2.normalize_target("approval_detection.py") != oc2.normalize_target("tools/approval_detection.py")


def test_normalize_target_distinguishes_same_basename():
    """同 basename 不同父目录不得合并 (src/config.py vs tests/config.py)。"""
    assert oc2.normalize_target("src/config.py") == "src/config.py"
    assert oc2.normalize_target("tests/config.py") == "tests/config.py"
    assert oc2.normalize_target("src/config.py") != oc2.normalize_target("tests/config.py")


def test_normalize_target_extracts_file_from_composite():
    """复合描述式 target (文件名+函数+行号) 归一后按文件聚合。"""
    assert oc2.normalize_target("orchestrate_v2.py cluster_issues (388-430行), 对应契约C01") == "orchestrate_v2.py"
    assert oc2.normalize_target("orchestrate_v2.py normalize_target (295-308行)") == "orchestrate_v2.py"
    assert oc2.normalize_target("skills/cross-review-five/scripts/orchestrate_v2.py:661-670") == "scripts/orchestrate_v2.py"
    a = oc2.normalize_target("orchestrate_v2.py cluster_issues (388-430行)")
    b = oc2.normalize_target("orchestrate_v2.py cluster_issues L382-430")
    assert a == b == "orchestrate_v2.py"


def test_is_plausible_target_rejects_regex_fragment():
    assert oc2._is_plausible_target("approval_detection.py")
    assert not oc2._is_plausible_target("cli/.py")
    assert not oc2._is_plausible_target(r"cli\.py")
    assert not oc2._is_plausible_target("cli[abc].py")
    assert not oc2._is_plausible_target("README")


# ---------- C01/C02: 断言级聚类 ----------

def test_single_model_multi_findings_all_preserved():
    """单模型同 target 多条 findings 全部保留 (身份=target+claim 哈希, 宁拆不并), severity 不错嫁接。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="core.py:10", claim="轻微风格问题", severity="P2"),
                                 _f(target="core.py:20", claim="数据丢失缺陷", severity="P0", id="F2")]},
        "dsv4pro": {"findings": []},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert consensus == []
    assert len(singletons) == 2
    by_claim = {s["claims"][0]["claim"]: s for s in singletons}
    p2 = by_claim["轻微风格问题"]
    p0 = by_claim["数据丢失缺陷"]
    assert p2["claims"][0]["severity"] == "P2" and p2["severity"] == "P2"
    assert p0["claims"][0]["severity"] == "P0" and p0["severity"] == "P0"
    for s in singletons:
        assert s["raised_by"] == ["kimi-k3"]


def test_opposite_claims_without_polarity_not_consensus():
    """两模型同 target 语义相反且都无 polarity: 不得默认共识 (宁拆不并)。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="core.py", claim="validation exists")]},
        "dsv4pro": {"findings": [_f(target="core.py", claim="validation is absent")]},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert consensus == []
    assert contradictions == []
    assert len(singletons) == 2


def test_issue_key_aligns_assertions():
    """同 target 同 issue_key 的不同措辞 claim 聚合为 consensus。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="core.py", claim="锁未释放,不正确",
                                    issue_key="lock-leak", kind="bug")]},
        "dsv4pro": {"findings": [_f(target="core.py", claim="存在锁竞争错误",
                                    issue_key="lock-leak", kind="perf")]},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert contradictions == []
    assert len(consensus) == 1
    assert consensus[0]["raised_by"] == ["kimi-k3", "dsv4pro"]


def test_polarity_opposition_is_contradiction():
    """同 issue_key 下互斥 polarity 判矛盾 (claim 措辞不同也可)。"""
    models = ["kimi-k3", "dsv4pro"]
    findings = {
        "kimi-k3": {"findings": [_f(target="cache.py", claim="缓存未失效",
                                    issue_key="cache-stale", polarity="present")]},
        "dsv4pro": {"findings": [_f(target="cache.py", claim="缓存失效问题不存在",
                                    issue_key="cache-stale", polarity="absent")]},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert consensus == []
    assert len(contradictions) == 1
    assert contradictions[0]["state"] == "contradiction"


def test_raised_by_preserves_order():
    assert oc2.dedup_preserve_order(["b", "a", "b", "a", "c"]) == ["b", "a", "c"]
    assert oc2.dedup_preserve_order(["b", "a", "b", "a", "c"]) == \
        oc2.dedup_preserve_order(["b", "a", "b", "a", "c"])


# ---------- C04/C10: findings 提取与 schema 校验 ----------

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
    stream = tmp_path / "stream_badsidecar"
    stream.mkdir()
    (stream / "findings-kimi-k3.json").write_text("[1, 2, 3]", encoding="utf-8")
    (stream / "review-kimi-k3.md").write_text("", encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert isinstance(data, dict)
    assert data["findings"] == []


def test_schema_validation_drops_invalid(tmp_path):
    """非法条目 (severity 越界/非对象/polarity 非法) 丢弃, 合法条目保留, 不崩。"""
    stream = tmp_path / "stream_schema"
    stream.mkdir()
    sidecar = {"findings": [
        {"id": "F1", "target": "ok.py", "kind": "bug", "claim": "合法发现",
         "evidence": ["ok.py:1"], "severity": "P1"},
        {"id": "F2", "target": "bad.py", "kind": "bug", "claim": "severity 越界",
         "evidence": ["bad.py:1"], "severity": "P9"},
        "not-an-object",
        {"id": "F4", "target": "bad2.py", "kind": "bug", "claim": "polarity 非法",
         "evidence": ["bad2.py:1"], "severity": "P2", "polarity": "maybe"},
    ], "unknowns": [], "assumptions": []}
    (stream / "findings-kimi-k3.json").write_text(json.dumps(sidecar), encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    assert len(data["findings"]) == 1
    assert data["findings"][0]["target"] == "ok.py"
    dropped = data.get("_meta", {}).get("dropped", [])
    assert len(dropped) == 3


def test_fallback_rejects_regex_fragment(tmp_path):
    stream = tmp_path / "stream_ghost"
    stream.mkdir()
    (stream / "review-kimi-k3.md").write_text(
        "检测规则缺失 r'\\b(pkill|killall)\\b.*\\b(hermes|gateway|cli\\.py)\\b'\n"
        "cl\\.py:1 崩溃\n", encoding="utf-8")
    data = oc2.extract_findings_json(str(stream), "kimi-k3")
    for f in data["findings"]:
        assert oc2._is_plausible_target(f["target"])


# ---------- run lineage: 陈旧产物清理与 manifest ----------

def test_plan_cleans_stale_outputs(tmp_path):
    stream = tmp_path / "stream_clean"
    stream.mkdir()
    (stream / "review-kimi-k3.md").write_text("旧评审", encoding="utf-8")
    (stream / "findings-kimi-k3.json").write_text("{}", encoding="utf-8")
    (stream / "log-kimi-k3.txt").write_text("旧日志", encoding="utf-8")
    oc2._clean_stale_plan_outputs(str(stream), ["kimi-k3", "dsv4pro"])
    assert not (stream / "review-kimi-k3.md").exists()
    assert not (stream / "findings-kimi-k3.json").exists()
    assert not (stream / "log-kimi-k3.txt").exists()


def test_challenge_cleans_stale_replies(tmp_path):
    stream = tmp_path / "stream_clean_c"
    stream.mkdir()
    (stream / "challenge-reply-C01-kimi-k3.md").write_text("旧答复", encoding="utf-8")
    (stream / "bundle-C01.json").write_text("{}", encoding="utf-8")
    oc2._clean_stale_challenge_outputs(str(stream))
    assert not (stream / "challenge-reply-C01-kimi-k3.md").exists()
    assert not (stream / "bundle-C01.json").exists()


def test_manifest_roundtrip(tmp_path):
    stream = tmp_path / "stream_manifest"
    stream.mkdir()
    (stream / "task.md").write_text("任务书内容", encoding="utf-8")
    m = oc2._write_manifest(str(stream), str(stream / "task.md"), ["a", "b"], "economy",
                            missing_models=["b"])
    assert m["run_id"]
    assert m["task_sha256"] and len(m["task_sha256"]) == 16
    assert m["missing_models"] == ["b"]
    m2 = oc2._read_manifest(str(stream))
    assert m2["run_id"] == m["run_id"]


def test_plan_failed_model_reported_missing(tmp_path, monkeypatch):
    """plan 阶段: 旧产物被清理, 失败模型的旧文件不得冒充本轮结果, missing 进 manifest。"""
    stream = tmp_path / "stream_fail"
    stream.mkdir()
    (stream / "task.md").write_text("任务", encoding="utf-8")
    (stream / "review-kimi-k3.md").write_text("旧评审", encoding="utf-8")
    (stream / "findings-kimi-k3.json").write_text("{}", encoding="utf-8")

    class _FakeProc:
        pid = 0

        def poll(self):
            return 0

    def fake_spawn(model_key, prompt_path, log_path):
        if model_key == "dsv4pro":
            out = stream / "review-dsv4pro.md"
            out.write_text("新评审", encoding="utf-8")
        return _FakeProc()

    monkeypatch.setattr(oc2, "spawn", fake_spawn)
    ok = oc2.stage_plan_v2(str(stream), str(stream / "task.md"), ["kimi-k3", "dsv4pro"])
    assert ok is True
    assert (stream / "review-dsv4pro.md").exists()
    assert not (stream / "review-kimi-k3.md").exists()
    manifest = oc2._read_manifest(str(stream))
    assert "kimi-k3" in manifest["missing_models"]


# ---------- C05/C06/C07: merge + challenge + synthesize ----------

def test_reviewer_excludes_contradiction_parties(tmp_path):
    stream = tmp_path / "stream_r"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", issue_key="ck", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", issue_key="ck", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    assert len(plan) == 1
    assert plan[0]["type"] == "contradiction"
    assert plan[0]["reviewer"] not in ("kimi-k3", "dsv4pro")


def test_bundle_anonymized(tmp_path):
    stream = tmp_path / "stream_a"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", issue_key="ck", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", issue_key="ck", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    bundle = plan[0]["bundle"]
    raw = json.dumps(bundle, ensure_ascii=False)
    for m in ("kimi-k3", "dsv4pro", "gemini38flash"):
        assert m not in raw
    aliases = [p["source_alias"] for p in bundle["proposals"]]
    assert aliases == sorted(aliases, key=lambda a: int(a.split("-")[1]))


def test_all_parties_no_anonymous_candidate_skipped(tmp_path):
    """两模型全员当事人: 质询跳过并记录, 不退回当事人。"""
    stream = tmp_path / "stream_skip"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", issue_key="ck", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", issue_key="ck", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    assert plan == []
    skipped = json.loads((stream / "challenge-skipped.json").read_text(encoding="utf-8"))
    assert len(skipped) == 1
    assert "无匿名候选" in skipped[0]["reason"] or "无可用非当事人" in skipped[0]["reason"]


def test_p0_singleton_beats_p2_contradiction(tmp_path):
    """配额 1: P2 矛盾与 P0 单例并存时, P0 单例优先。"""
    stream = tmp_path / "stream_quota"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", issue_key="ck", polarity="present",
                       severity="P2"),
                    _f(target="crypto.py", claim="弱随机数", severity="P0")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", issue_key="ck", polarity="absent",
                       severity="P2")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    plan = json.loads((stream / "challenge-plan.json").read_text(encoding="utf-8"))
    assert len(plan) == 1
    assert plan[0]["type"] == "singleton_audit"
    assert plan[0]["target"] == "crypto.py"


def test_merge_idempotent_modulo_timestamp(tmp_path):
    """两次 merge: registry 除 timestamp 外一致, challenge-plan 字节一致。"""
    stream = tmp_path / "stream_idem"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", issue_key="ck", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", issue_key="ck", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    r1 = json.loads((stream / "issue-registry.json").read_text(encoding="utf-8"))
    p1 = (stream / "challenge-plan.json").read_bytes()
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    r2 = json.loads((stream / "issue-registry.json").read_text(encoding="utf-8"))
    p2 = (stream / "challenge-plan.json").read_bytes()
    r1["metadata"].pop("timestamp", None)
    r2["metadata"].pop("timestamp", None)
    assert r1 == r2
    assert p1 == p2


def test_mixed_stances_parsed():
    text = ("第四步【裁决与表态】：\n"
            "【CONCEDE】对方证据确凿, 认同。\n"
            "【REFUTED】该条不成立, 反例见附件。\n"
            "【UNRESOLVED_REQUIRES_CODE_VERIFICATION】需跑测试验证。\n")
    conceded, refuted, unresolved = oc2._parse_stances(text)
    assert len(conceded) == 1 and len(refuted) == 1 and len(unresolved) == 1


def test_synthesize_missing_reply_reported(tmp_path):
    stream = tmp_path / "stream_m"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="cache.py", claim="缓存未失效", issue_key="ck", polarity="present")],
        "dsv4pro": [_f(target="cache.py", claim="缓存已失效", issue_key="ck", polarity="absent")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    oc2.stage_synthesize_v2(str(stream))
    report = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "质询缺失 (Missing Replies): 1 项" in report
    assert "MISSING" in report


def test_refuted_singleton_excluded_from_ledger(tmp_path):
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
        "第四步【裁决与表态】：【REFUTED】该断言不成立, 代码实际使用加密安全随机源。",
        encoding="utf-8")
    oc2.stage_synthesize_v2(str(stream))
    ledger = json.loads((stream / "unresolved-ledger.json").read_text(encoding="utf-8"))
    issue_ids = [u.get("issue_id") for u in ledger]
    assert plan[0]["issue_id"] not in issue_ids


def test_ghost_absolute_evidence_excluded(tmp_path):
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


def test_relative_ghost_evidence_marked_unverified(tmp_path):
    """相对路径样式证据未命中任何 base 目录: 入账但标注 unverified, 不冒充已验证。"""
    stream = tmp_path / "stream_rg"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="config.py", claim="配置缺陷", severity="P0",
                       evidence=["ghost_dir/ghost.py:10"])],
        "dsv4pro": [],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    oc2.stage_synthesize_v2(str(stream))
    ledger = json.loads((stream / "unresolved-ledger.json").read_text(encoding="utf-8"))
    report = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert len(ledger) == 1
    assert ledger[0]["evidence_unverified"] == ["ghost_dir/ghost.py:10"]
    assert "证据未验证" in report


def test_consensus_report_uses_corroborated_naming(tmp_path):
    """报告不得使用 Verified Consensus 命名 (与'模型共识不是证据'纪律一致)。"""
    stream = tmp_path / "stream_name"
    stream.mkdir()
    _write_two_sidecars(stream, {
        "kimi-k3": [_f(target="core.py", claim="锁泄漏", issue_key="lock-leak")],
        "dsv4pro": [_f(target="core.py", claim="锁未释放", issue_key="lock-leak")],
    })
    oc2.stage_merge_v2(str(stream), ["kimi-k3", "dsv4pro", "gemini38flash"], mode="economy")
    oc2.stage_synthesize_v2(str(stream))
    report = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "Verified Consensus" not in report
    assert "多模型互证" in report
    assert "Corroborated" in report


def test_wait_for_outputs_partial_failure(tmp_path):
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
        "kimi-k3": [_f(target="server.py", kind="perf", claim="并发锁争用", issue_key="lock"),
                    _f(target="config.yaml", kind="bug", claim="配置项缺失", severity="P2")],
        "dsv4pro": [_f(target="server.py", kind="perf", claim="存在锁冲突", issue_key="lock"),
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
        "第四步【裁决与表态】：【CONCEDE】对方指出 crypto.py 使用了伪随机源而非加密安全随机源。",
        encoding="utf-8")

    ok_synth = oc2.stage_synthesize_v2(str(stream))
    assert ok_synth is True
    assert (stream / "consensus-report.md").exists()
    assert (stream / "unresolved-ledger.json").exists()
    report_text = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "五人交叉评审合议报告 (v2 Sparse Deliberation)" in report_text
    assert "质询认同/认输 (Conceded): 1 项" in report_text
    assert "【CONCEDE】" in report_text
    registry = json.loads((stream / "issue-registry.json").read_text(encoding="utf-8"))
    assert any(c["target"] == "server.py" and c["state"] == "consensus"
               for c in registry["consensus"])

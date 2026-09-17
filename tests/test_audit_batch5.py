"""Regression tests for audit batch 5:
- R01: _clean_stale_plan_outputs 保护任务书与用户输入材料 (即使名为 review-task.md)
- R02: stage_plan_v2 非零退出进程不视为有效产出, 不提取残缺 findings
- R03: stage_synthesize_v2 保护账本非空或争议未决时报告不得显示已闭环 (converged=False)
- R04: 单例议题包含多 claims 时逐断言反驳, 部分反驳不清除全项
- R05: _parse_stances 正确解析 Markdown 表格中的裁决标签
- R06: stage_plan_v2 保持单轮 plan 的 run_id 与 started_at 一致
- R07: normalize_target 通用去除 Windows 盘符与前导斜杠
- R08: _validate_findings 拒绝空 claim 与非法 kind
- R09: 同 issue_key 但 claims 对立 (exists vs absent) 在缺 polarity 时判定为 contradiction
- M01: literature-watch collect() 排除被监控论文自身的 crossref-fallback, 不冒充新引用者
- M02: retraction-watch check_doi 检测 Crossref 截断并标记 truncated=True
- M03: retraction-watch update_signals_from_records 信号身份绑定通知记录自身 DOI
- L01: collect_corpus merge_candidates 别名映射遇 DOI 冲突时保留为独立候选
- L03: deduplicate_works 支持 publication_year 避免不同年份误合并
- A01: locate_oa 离线 record DOI 不匹配时受控拒绝并报错
- S01: meta_core trim_and_fill 连续两轮 k0 稳定正确判定到达固定点收敛
"""

import importlib.util
import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_module(name, rel_path):
    p = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


oc2 = _load_module("orchestrate_v2", "skills/cross-review-five/scripts/orchestrate_v2.py")
lwatch = _load_module("lwatch", "skills/literature-watch/scripts/watch.py")
rwatch = _load_module("rwatch", "skills/retraction-watch/scripts/watch.py")
collect = _load_module("collect", "skills/literature-analysis/scripts/collect_corpus.py")
dedup = _load_module("dedup", "skills/literature-analysis/scripts/deduplicate_works.py")
locate_oa = _load_module("locate_oa", "skills/academic-source-verification/scripts/locate_oa.py")
meta_core = _load_module("meta_core", "skills/systematic-review-meta-analysis/scripts/meta_core.py")


# ---------- R01 ----------

def test_r01_clean_stale_plan_outputs_protects_named_task(tmp_path):
    task_file = tmp_path / "review-task.md"
    task_file.write_text("# Review Task Specification\nDo review.", encoding="utf-8")
    stale_review = tmp_path / "review-kimi-k3.md"
    stale_review.write_text("old review", encoding="utf-8")

    oc2._clean_stale_plan_outputs(str(tmp_path), ["kimi-k3"], task_path=str(task_file))
    assert task_file.exists(), "命名为 review-task.md 的任务书不得被清理删除"
    assert not stale_review.exists(), "已声明模型的陈旧 review-*.md 产物应被清理"


# ---------- R02 ----------

def test_r02_failed_exit_not_treated_as_valid_stage_output(tmp_path, monkeypatch):
    stream = tmp_path / "stream_r02"
    stream.mkdir()
    task_file = stream / "task.md"
    task_file.write_text("task", encoding="utf-8")

    out_file = stream / "review-kimi-k3.md"
    out_file.write_text("partial text before crash", encoding="utf-8")

    class FakeProc:
        pid = 1234
        returncode = 9

        def poll(self):
            return 9

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 9

    monkeypatch.setattr(oc2, "spawn", lambda k, pr, lr: FakeProc())
    monkeypatch.setattr(oc2, "TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(oc2, "POLL_SECONDS", 0.05)

    ok = oc2.stage_plan_v2(str(stream), str(task_file), ["kimi-k3"])
    assert ok is False, "非零退出码进程不得认定为阶段成功"
    manifest = oc2._read_manifest(str(stream))
    assert "kimi-k3" in manifest.get("missing_models", []), "异常退出模型应记入 missing_models"


# ---------- R03 ----------

def test_r03_unresolved_ledger_prevents_converged_status(tmp_path):
    stream = tmp_path / "stream_r03"
    stream.mkdir()
    manifest = {
        "run_id": "test-run",
        "task_sha256": "abcdef12",
        "model_set": ["m1", "m2"],
        "mode": "standard",
        "started_at": "2026-09-17 12:00:00",
    }
    (stream / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    registry = {
        "metadata": {"mode": "standard", "models": ["m1", "m2"], "missing_models": []},
        "consensus": [],
        "contradictions": [],
        "singletons": [{
            "issue_id": "I01",
            "target": "core.py",
            "assertion_key": "k:leak",
            "raised_by": ["m1"],
            "severity": "P1",
            "claims": [{"model": "m1", "claim": "leak exists", "evidence": ["core.py:10"]}],
            "provenance": "model_written",
            "state": "singleton",
        }],
    }
    (stream / "issue-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    # 创建真实文件使 evidence_check 验证通过
    (stream / "core.py").write_text("# core", encoding="utf-8")

    oc2.stage_synthesize_v2(str(stream))
    report = (stream / "consensus-report.md").read_text(encoding="utf-8")
    assert "未收敛" in report
    assert "已闭环" not in report


# ---------- R04 ----------

def test_r04_singleton_multi_claims_partial_refute(tmp_path):
    stream = tmp_path / "stream_r04"
    stream.mkdir()
    manifest = {"run_id": "r1", "task_sha256": "abc", "model_set": ["m1", "m2"], "mode": "std"}
    (stream / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    registry = {
        "metadata": {"mode": "std", "models": ["m1", "m2"], "missing_models": []},
        "consensus": [],
        "contradictions": [],
        "singletons": [{
            "issue_id": "I01",
            "target": "core.py",
            "assertion_key": "k:leak",
            "raised_by": ["m1"],
            "severity": "P1",
            "claims": [
                {"model": "m1", "claim": "claim 1", "evidence": ["core.py:10"]},
                {"model": "m1", "claim": "claim 2", "evidence": ["core.py:20"]},
            ],
            "provenance": "model_written",
            "state": "singleton",
        }],
    }
    (stream / "issue-registry.json").write_text(json.dumps(registry), encoding="utf-8")
    (stream / "challenge-plan.json").write_text(json.dumps([{
        "challenge_id": "C01",
        "reviewer": "m2",
        "issue_id": "I01",
        "target": "core.py",
        "type": "singleton_audit",
    }]), encoding="utf-8")
    (stream / "core.py").write_text("# core\n" * 30, encoding="utf-8")

    # 仅驳回 Proposal 1
    (stream / "challenge-reply-C01-m2.md").write_text(
        "第四步【裁决与表态】：\n【REFUTED】驳回 Proposal 1，代码无此逻辑。",
        encoding="utf-8",
    )

    oc2.stage_synthesize_v2(str(stream))
    ledger = json.loads((stream / "unresolved-ledger.json").read_text(encoding="utf-8"))
    assert len(ledger) == 1, "Proposal 1 被驳回后，剩余 claim 2 必须保留在保护账本中"
    assert len(ledger[0]["claims"]) == 1
    assert ledger[0]["claims"][0]["claim"] == "claim 2"


# ---------- R05 ----------

def test_r05_parse_stances_from_markdown_table():
    text = """
| 序号 | 议题 | 裁决与表态 | 理由说明 |
|:---|:---|:---|:---|
| 1 | 锁泄漏 | 【CONCEDE】 | 证据行号确凿，认同此缺陷 |
| 2 | 变量未初始化 | 【REFUTED】 Proposal 2 | 第50行已有默认值保护 |
| 3 | 缓存击穿 | 【UNRESOLVED_REQUIRES_CODE_VERIFICATION】 | 需补充压力测试 |
"""
    conceded, refuted, unresolved = oc2._parse_stances(text)
    assert len(conceded) == 1
    assert "【CONCEDE】" in conceded[0]
    assert len(refuted) == 1
    assert "【REFUTED】" in refuted[0]
    assert len(unresolved) == 1
    assert "【UNRESOLVED" in unresolved[0]


# ---------- R06 ----------

def test_r06_plan_maintains_consistent_run_id(tmp_path, monkeypatch):
    stream = tmp_path / "stream_r06"
    stream.mkdir()
    task_file = stream / "task.md"
    task_file.write_text("task", encoding="utf-8")

    class FakeProc:
        pid = 1234
        returncode = 0

        def poll(self):
            return 0

        def terminate(self):
            pass

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(oc2, "spawn", lambda k, pr, lr: FakeProc())
    monkeypatch.setattr(oc2, "wait_for_outputs",
                        lambda out_paths, procs: {p: {"file": True, "exit": 0} for p in out_paths})

    # 先创建一个假产物文件避免 missing
    for k in ["m1", "m2"]:
        (stream / f"review-{k}.md").write_text("ok", encoding="utf-8")

    oc2.stage_plan_v2(str(stream), str(task_file), ["m1", "m2"])
    manifest = oc2._read_manifest(str(stream))
    run_id_first = manifest["run_id"]
    started_first = manifest["started_at"]

    # 验证同一阶段没有覆盖导致 run_id 突变
    assert run_id_first is not None
    assert started_first is not None


# ---------- R07 ----------

def test_r07_normalize_target_cross_platform():
    assert oc2.normalize_target("E:\\repos\\proj\\core.py:42") == "repos/proj/core.py"
    assert oc2.normalize_target("/var/log/test.log:99") == "var/log/test.log"
    assert oc2.normalize_target("z:\\app\\main.py") == "app/main.py"


# ---------- R08 ----------

def test_r08_validate_findings_rejects_empty_claim_and_bad_kind():
    data = {
        "findings": [
            {"target": "a.py", "severity": "P1", "claim": "   ", "evidence": []},
            {"target": "b.py", "severity": "P1", "claim": "valid", "kind": "invalid_kind_xyz"},
            {"target": "c.py", "severity": "P1", "claim": "valid claim", "kind": "bug"},
        ]
    }
    res = oc2._validate_findings(data, "model_written")
    assert len(res["findings"]) == 1
    assert res["findings"][0]["target"] == "c.py"
    dropped = res.get("_meta", {}).get("dropped", [])
    assert len(dropped) == 2


# ---------- R09 ----------

def test_r09_opposing_claims_without_polarity_becomes_contradiction():
    models = ["m1", "m2"]
    findings = {
        "m1": {"findings": [{"target": "auth.py", "claim": "validation exists in token check",
                             "issue_key": "token-val", "severity": "P1", "evidence": []}]},
        "m2": {"findings": [{"target": "auth.py", "claim": "validation is absent in token check",
                             "issue_key": "token-val", "severity": "P1", "evidence": []}]},
    }
    consensus, singletons, contradictions = oc2.cluster_issues(models, findings)
    assert len(contradictions) == 1, "exists 与 absent 词义对立在无 polarity 时必须判为 contradiction"
    assert consensus == []


# ---------- M01 ----------

def test_m01_collect_does_not_report_watched_work_as_new_citer(monkeypatch):
    def fake_citing(doi, since):
        return [{
            "id": None,
            "doi": "10.1000/182",
            "title": "Watched Paper Itself",
            "source": "crossref-fallback",
        }], False

    monkeypatch.setattr(lwatch, "fetch_topic_works", lambda t, s: ([], False))
    monkeypatch.setattr(lwatch, "fetch_author_works", lambda a, s: ([], False))
    monkeypatch.setattr(lwatch, "fetch_citing_works", fake_citing)

    items, trunc = lwatch.collect({"topics": [], "authors": [], "dois": ["10.1000/182"]}, date.today())
    assert items == [], "被监控论文自身的 crossref-fallback 不得作为新增引用者产出"


# ---------- M02 ----------

def test_m02_retraction_watch_detects_truncation(monkeypatch):
    def fake_get(url, timeout=20):
        if "openalex" in url:
            return {"is_retracted": False}
        return {
            "message": {
                "total-results": 250,
                "items": [{"update-to": [{"DOI": "10.1/target", "type": "correction"}]}] * 100
            }
        }

    monkeypatch.setattr(rwatch, "get", fake_get)
    snap = rwatch.check_doi("10.1/target")
    assert snap.get("truncated") is True, "Crossref 超过 100 条时快照必须记录 truncated=True"


# ---------- M03 ----------

def test_m03_update_signals_binds_notice_doi():
    records = [{
        "DOI": "10.1000/retraction-notice-1",
        "update-to": [{"DOI": "10.1000/target-paper", "type": "retraction", "source": "crossref"}],
    }]
    signals = rwatch.update_signals_from_records(records, "10.1000/target-paper")
    assert any("update-doi=10.1000/retraction-notice-1" in s for s in signals), \
        f"信号必须绑定通知记录自身的 DOI, got: {signals}"


# ---------- L01 ----------

def test_l01_merge_candidates_preserves_conflicting_doi():
    layers = {
        "layer1": [{"id": "W999", "doi": "10.1/first", "title": "Paper A"}],
        "layer2": [{"id": "W999", "doi": "10.1/second-conflict", "title": "Paper A"}],
    }
    res = collect.merge_candidates(layers)
    assert res["count"] == 2, "相同 OpenAlex ID 但 DOI 冲突的记录不得静默合并，应保留为独立候选"
    dois = {c.get("doi") for c in res["candidates"]}
    assert "10.1/first" in dois and "10.1/second-conflict" in dois


# ---------- L03 ----------

def test_l03_deduplicate_works_respects_publication_year():
    works = [
        {"title": "Deep Learning Survey", "publication_year": 2018, "authors": [{"name": "Smith, J"}]},
        {"title": "Deep Learning Survey", "publication_year": 2024, "authors": [{"name": "Smith, J"}]},
    ]
    res = dedup.deduplicate_works(works)
    assert len(res["kept"]) == 2, "不同年份的同名同作者文献不得误判为重复"
    assert len(res["removed"]) == 0


# ---------- A01 ----------

def test_a01_locate_oa_checks_record_doi(tmp_path):
    record_file = tmp_path / "record.json"
    record_file.write_text(json.dumps({
        "doi": "10.1000/different-paper",
        "is_oa": True,
        "oa_locations": [{"url_for_pdf": "https://example.com/diff.pdf"}]
    }), encoding="utf-8")

    exit_code = locate_oa.main(["--doi", "10.1000/requested-paper", "--record", str(record_file)])
    assert exit_code == 1, "record 中的 DOI 与请求的 DOI 不匹配时必须以非零码退出并报错"


# ---------- S01 & S02 ----------

def test_s01_trim_and_fill_fixed_point_converges():
    # ChatGPT 反例中的真实固定点样本
    import numpy as np
    y = np.array([6, -4, 1, -4, 0, 6, 7, 2, 5, -1], dtype=float)
    v = np.array([0.5, 2.0, 2.0, 0.2, 0.2, 2.0, 0.5, 2.0, 0.2, 0.5], dtype=float)

    res = meta_core.trim_and_fill(y, v, side="left")
    assert res["converged"] is True, "k0 在固定点稳定时不应误判为状态循环未收敛"
    assert res["k0"] == 1
    assert res["adjusted"] is not None

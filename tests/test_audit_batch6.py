"""Regression tests for audit batch 6:
- M04: watch.py _atomic_write_json 重读合并保证状态增量不丢失
- M05: watch.py 遗留锁过期自动受控回收
- M06: retraction-watch run() 区分 current_observation 与 retained_prior
- L02: collect_corpus merge_candidates 并查集消除别名桥接输入顺序依赖
- L04: export_bibtex _load_works 适配 Crossref items 列表响应
- L05: interop to_bibtex / from_bibtex 对称编解码保持转义幂等
- L06: interop from_bibtex 保护双花括号单一机构作者不被拆分
- L07: collect_corpus merge_candidates 保留 authors, abstract, referenced_works
- A02: verify_pdf_identity 支持西里尔切词并拒绝子串假阳性 (AI vs training)
- Q01: recompute check_percentage 0% 且 count>0 判定为分母欠定而不算不可能
- Q02: recompute check_sample_size_from_df 支持 Welch 容错与显式声明
- Q03: recompute _decimals 支持字符串输入保留尾随零 (0.050 -> 3)
- F01: generated-scenarios.json 记录当前观测声明并标明 repair_executed=False
"""

import importlib.util
import json
import os
import sys
import time
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


rwatch = _load_module("rwatch_b6", "skills/retraction-watch/scripts/watch.py")
lwatch = _load_module("lwatch_b6", "skills/literature-watch/scripts/watch.py")
collect = _load_module("collect_b6", "skills/literature-analysis/scripts/collect_corpus.py")
exp_bib = _load_module("exp_bib_b6", "skills/literature-analysis/scripts/export_bibtex.py")
interop = _load_module("interop_b6", "skills/literature-analysis/scripts/interop.py")
verify_pdf = _load_module("verify_pdf_b6", "skills/academic-source-verification/scripts/verify_pdf_identity.py")
recompute = _load_module("recompute_b6", "skills/quantitative-paper-audit/scripts/recompute.py")


# ---------- M04 & M05 ----------

def test_m05_stale_lock_auto_reclaimed(tmp_path):
    state_file = tmp_path / "state.json"
    lock_file = tmp_path / "state.json.lock"
    # 模拟 100 秒前崩溃遗留的锁
    lock_file.write_text(f"99999:{time.time() - 100.0}", encoding="utf-8")

    rwatch._atomic_write_json(state_file, {"10.1/a": {"is_retracted": True}})
    assert state_file.exists()
    assert not lock_file.exists(), "超时遗留锁必须被自动回收清除"


def test_m04_reread_merge_preserves_incremental_keys(tmp_path):
    state_file = tmp_path / "state.json"
    # 磁盘上已存在其他进程写入的数据
    state_file.write_text(json.dumps({"10.1/prior": {"is_retracted": False}}), encoding="utf-8")

    rwatch._atomic_write_json(state_file, {"10.1/new": {"is_retracted": True}})
    res = json.loads(state_file.read_text(encoding="utf-8"))
    assert "10.1/prior" in res, "写锁期间必须重读合并既有状态，防止覆盖丢失"
    assert "10.1/new" in res


# ---------- M06 ----------

def test_m06_retained_prior_exposes_current_observation(monkeypatch, tmp_path):
    watchlist = tmp_path / "watchlist.json"
    watchlist.write_text(json.dumps({"dois": ["10.1/target"]}), encoding="utf-8")
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"10.1/target": {"is_retracted": True, "signals": []}}), encoding="utf-8")

    # 模拟本轮 OpenAlex 404 返回 None
    def fake_check(doi):
        return {"is_retracted": None, "signals": []}

    monkeypatch.setattr(rwatch, "check_doi", fake_check)
    rwatch.run(str(watchlist), str(state_file))

    saved = json.loads(state_file.read_text(encoding="utf-8"))
    target_data = saved["10.1/target"]
    assert target_data["is_retracted"] is True, "保留历史确认值"
    assert target_data["current_observation"] is None, "必须如实记录本轮未获响应"
    assert target_data["verification_status"] == "retained_prior"


# ---------- L02 & L07 ----------

def test_l02_merge_candidates_order_independence():
    rec_doi_only = {"doi": "10.1/xyz", "title": "Paper XYZ"}
    rec_oa_only = {"id": "W555", "title": "Paper XYZ"}
    rec_bridge = {"doi": "10.1/xyz", "id": "W555", "title": "Paper XYZ", "publication_year": 2021}

    # 顺序 A: 先分立后桥接
    layers_a = {"layer1": [rec_doi_only], "layer2": [rec_oa_only], "layer3": [rec_bridge]}
    res_a = collect.merge_candidates(layers_a)

    # 顺序 B: 桥接先来
    layers_b = {"layer1": [rec_bridge], "layer2": [rec_doi_only], "layer3": [rec_oa_only]}
    res_b = collect.merge_candidates(layers_b)

    assert res_a["count"] == 1, "顺序 A 下三条记录应完全合并为 1 条"
    assert res_b["count"] == 1, "顺序 B 下三条记录应完全合并为 1 条"
    assert res_a["candidates"][0]["doi"] == "10.1/xyz"
    assert res_a["candidates"][0]["openalex_id"] == "W555"


def test_l07_merge_candidates_preserves_downstream_metadata():
    work = {
        "doi": "10.1/complete",
        "title": "Full Paper",
        "authors": [{"name": "Alice"}, {"name": "Bob"}],
        "abstract": "This is a full abstract.",
        "referenced_works": ["https://openalex.org/W1", "https://openalex.org/W2"],
    }
    res = collect.merge_candidates({"main": [work]})
    cand = res["candidates"][0]
    assert cand["authors"] == [{"name": "Alice"}, {"name": "Bob"}]
    assert cand["abstract"] == "This is a full abstract."
    assert cand["referenced_works"] == ["https://openalex.org/W1", "https://openalex.org/W2"]


# ---------- L04 ----------

def test_l04_export_bibtex_crossref_list_response(tmp_path):
    cr_file = tmp_path / "crossref.json"
    cr_file.write_text(json.dumps({
        "message": {
            "items": [
                {"DOI": "10.1/a", "title": ["Paper A"]},
                {"DOI": "10.1/b", "title": ["Paper B"]},
            ]
        }
    }), encoding="utf-8")

    works = exp_bib._load_works(str(cr_file), "crossref")
    assert len(works) == 2, "Crossref message.items 列表必须被解包为多条 works"
    assert works[0]["DOI"] == "10.1/a"
    assert works[1]["DOI"] == "10.1/b"


# ---------- L05 & L06 ----------

def test_l05_bibtex_roundtrip_idempotence():
    original_title = "Analysis & Synthesis: 100% of $O(N)$ Algorithms & Models"
    escaped = interop.tex_escape(original_title)
    unescaped = interop.tex_unescape(escaped)
    assert unescaped == original_title, "tex_unescape 必须精确还原被 tex_escape 转义的字符"
    re_escaped = interop.tex_escape(unescaped)
    assert re_escaped == escaped, "再次转义必须与初次转义完全一致，不得逐轮膨胀"


def test_l06_bibtex_institutional_author_not_split():
    bib = """
@article{cite1,
  author = {{Harvard University and Massachusetts Institute of Technology}},
  title = {Joint Research},
  year = {2023}
}
"""
    works = interop.from_bibtex(bib)
    assert len(works) == 1
    assert works[0].authors == ["Harvard University and Massachusetts Institute of Technology"], \
        f"双花括号机构作者不得被 ' and ' 拆解, got {works[0].authors}"


# ---------- A02 ----------

def test_a02_verify_pdf_identity_unicode_and_no_substring_false_positives():
    cyrillic = "Глубокое обучение в науке"
    tokens = verify_pdf.title_tokens(cyrillic)
    assert tokens == ["глубокое", "обучение", "в", "науке"], "西里尔标题切词不应丢失"

    # 子串假阳性反例: expected_title="AI", 页面仅有 "training"
    page = "This paper presents model training procedures without shortcuts."
    res = verify_pdf.compare_title("AI", page)
    assert res["match"] is False, "完整词匹配机制下 'ai' 不得误匹配 'training' 中的子串"
    assert "ai" in res["missing_tokens"]


# ---------- Q01, Q02, Q03 ----------

def test_q01_check_percentage_zero_percent_with_count_underdetermined():
    res = recompute.check_percentage(count=1, percent=0, denominator=None, decimals=0)
    assert res["consistent"] is None, "未声明分母时，0% 且 count=1 属于分母欠定，不应判不可能"
    assert res["min_possible_denominator"] == 200


def test_q02_check_sample_size_welch_support():
    # 显式声明 Welch 时不推定 N = df + 2
    res_welch = recompute.check_sample_size_from_df(df=15, reported_n=22, kind="ttest_2sample_welch")
    assert res_welch["consistent"] is None
    assert "Welch" in res_welch["formula"]


def test_q03_decimals_preserves_string_trailing_zeros():
    assert recompute._decimals("0.050") == 3, "字符串 '0.050' 必须准确识别出 3 位有效小数"
    assert recompute._decimals("0.0") == 1
    res = recompute.check_percentage(count=5, percent="5.00", denominator=100)
    assert res["tolerance"] < 0.01, "根据 '5.00' 字符串自动推断容差"


# ---------- F01 ----------

def test_f01_generated_scenarios_metadata_clean():
    scenario_file = ROOT / "tools" / "longtail" / "generated-scenarios.json"
    assert scenario_file.exists()
    data = json.loads(scenario_file.read_text(encoding="utf-8"))
    meta = data["generation_metadata"]
    assert meta["repair_executed"] is False
    assert "no monotone-improving swap path" not in meta.get("coverage_note", ""), \
        "不得包含被撤销的不可满足/最优/单调修复声称"

"""第四批裁决回归测试: 其余 P2 全量 (23 项)。

AV-03 标题归一保留 Unicode 文字系统; AV-04 arXiv URL 大小写统一解析;
ID-03 coverage 缺项不写 None; MW-03 更新事件独立身份; MW-04 原子写;
MW-05 Crossref 兜底接通; LA-02 DOI/OpenAlex 别名; LA-03 CLI 形状适配;
LA-04 简单图去重; LA-05 章节容器; LA-06 列表响应受控拒绝; LA-07 转义;
LA-08 机构作者; LA-09 created 不冒充发表年; SR-03 非有限拒绝;
SR-08 Hedges 阈值; SR-09 PubMed 邻近; QA-03 合法 0%; QA-04 尾随零;
RP-02 回执证据完整; FW-01 撤销重算; FW-02 缺席技能; FW-03 报告事实。
"""

import importlib.util
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
TOOLS = ROOT / "tools"


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


verify_work = _load(SKILLS / "academic-source-verification/scripts/verify_work.py", "b4_verify_work")
norm_id = _load(SKILLS / "academic-source-verification/scripts/normalize_identifier.py", "b4_norm_id")
identity = _load(SKILLS / "research-object-identity/scripts/identity.py", "b4_identity")
rwatch = _load(SKILLS / "retraction-watch/scripts/watch.py", "b4_rwatch")
lwatch = _load(SKILLS / "literature-watch/scripts/watch.py", "b4_lwatch")
collect = _load(SKILLS / "literature-analysis/scripts/collect_corpus.py", "b4_collect")
dedup = _load(SKILLS / "literature-analysis/scripts/deduplicate_works.py", "b4_dedup")
graph = _load(SKILLS / "literature-analysis/scripts/build_citation_graph.py", "b4_graph")
bibtex = _load(SKILLS / "literature-analysis/scripts/export_bibtex.py", "b4_export")
interop = _load(SKILLS / "literature-analysis/scripts/interop.py", "b4_interop")
meta_core = _load(SKILLS / "systematic-review-meta-analysis/scripts/meta_core.py", "b4_meta_core")
recompute = _load(SKILLS / "quantitative-paper-audit/scripts/recompute.py", "b4_recompute")
repro = _load(SKILLS / "research-reproducibility/scripts/repro_checklist.py", "b4_repro")
longtail = _load(TOOLS / "longtail/generate.py", "b4_longtail")


# ---------- AV-03 ----------

def test_av03_title_norm_preserves_scripts():
    assert verify_work._norm_title('Исследование Привет') == 'исследование привет'
    assert dedup.normalize_title('日本語の論文') == '日本語の論文'
    assert dedup.normalize_title('Café étude naïve') == 'café étude naïve'
    assert identity.normalize_title('Язык и речь') == 'язык и речь'


def test_av03_title_norm_discriminates_scripts():
    assert dedup.normalize_title('Русский') != dedup.normalize_title('русски')


# ---------- AV-04 ----------

def test_av04_arxiv_uppercase_pdf_path():
    """大写 /PDF/ 路径不再 IndexError, 受控解析或拒绝。"""
    res = norm_id.normalize_identifier('https://arxiv.org/PDF/2310.15264.pdf')
    assert res['type'] == 'arxiv'
    assert res['value'] == '2310.15264'
    res2 = norm_id.normalize_identifier('https://arxiv.org/pdf/')
    assert res2['type'] == 'unknown'


# ---------- ID-03 ----------

def test_id03_coverage_absent_omitted():
    out = identity.consume_receipt({
        'schema_version': '1.0',
        'sources': [{'source': 'OpenAlex', 'queried_at': 't', 'status': 'ok'}],
        'claims': [], 'conflicts': [], 'failures': []})
    obs = out['source_observations'][0]
    assert 'coverage' not in obs
    assert 'raw_identifier' not in obs


def test_id03_coverage_string_preserved():
    out = identity.consume_receipt({
        'schema_version': '1.0',
        'sources': [{'source': 'OpenAlex', 'queried_at': 't', 'status': 'ok',
                     'coverage': 'full', 'raw_identifier': '10.1/a'}],
        'claims': [], 'conflicts': [], 'failures': []})
    obs = out['source_observations'][0]
    assert obs['coverage'] == 'full'
    assert obs['raw_identifier'] == '10.1/a'


# ---------- MW-03 ----------

def test_mw03_distinct_corrections_distinct_signals():
    records = [
        {'update-to': [{'DOI': '10.1/a', 'type': 'correction', 'source': 'publisher',
                        'date': '2026-01-01'}]},
        {'update-to': [{'DOI': '10.1/a', 'type': 'correction', 'source': 'publisher',
                        'date': '2026-02-01'}]},
    ]
    sigs = rwatch.update_signals_from_records(records, '10.1/a')
    assert len(sigs) == 2, '第二次同类型更正必须是独立事件'


# ---------- MW-04 ----------

def test_mw04_atomic_write_no_temp_left(tmp_path):
    target = tmp_path / 'state.json'
    rwatch._atomic_write_json(target, {'10.1/a': {'is_retracted': False, 'signals': []}})
    assert json.loads(target.read_text(encoding='utf-8'))['10.1/a']['is_retracted'] is False
    assert not list(tmp_path.glob('*.tmp'))
    assert not list(tmp_path.glob('*.lock'))


# ---------- MW-05 ----------

def test_mw05_crossref_fallback_wired(monkeypatch):
    def fake_get(url, timeout=20):
        if url.startswith(lwatch.OPENALEX):
            return {}  # OpenAlex 无 id
        raise AssertionError('unexpected url')

    monkeypatch.setattr(lwatch, 'get', fake_get)
    monkeypatch.setattr(lwatch, 'fetch_crossref_record',
                        lambda doi: {'title': ['Fallback Paper'],
                                     'published-print': {'date-parts': [[2020]]}})
    items, truncated = lwatch.fetch_citing_works('10.1/x', None)
    assert len(items) == 1
    assert items[0]['source'] == 'crossref-fallback'
    assert items[0]['title'] == 'Fallback Paper'
    assert items[0]['publication_year'] == 2020
    assert truncated is False


# ---------- LA-02 ----------

def test_la02_doi_openalex_alias_merged():
    layers = {
        'openalex-search': [{'id': 'W123', 'title': 'Paper X', 'publication_year': 2020}],
        'openalex-work': [{'doi': '10.1/x', 'title': 'Paper X',
                           'id': 'W123', 'publication_year': 2020,
                           'cited_by_count': 7}],
    }
    res = collect.merge_candidates(layers)
    assert res['count'] == 1
    cand = res['candidates'][0]
    assert cand['doi'] == '10.1/x'
    assert cand['openalex_id'] == 'W123'
    assert cand['cited_by_count'] == 7
    assert set(cand['source_layers']) == {'openalex-search', 'openalex-work'}


# ---------- LA-03 ----------

def test_la03_dedup_main_accepts_candidates_shape(capsys):
    payload = json.dumps({'candidates': [{'doi': '10.1/x'}, {'doi': '10.1/x'}]})
    stdin = sys.stdin
    sys.stdin = io.StringIO(payload)
    try:
        assert dedup.main(['--input', '-']) == 0
    finally:
        sys.stdin = stdin
    report = json.loads(capsys.readouterr().out)
    assert report['summary']['input'] == 2
    assert report['summary']['kept'] == 1


def test_la03_graph_main_accepts_kept_shape(tmp_path, capsys):
    f = tmp_path / 'in.json'
    f.write_text(json.dumps({'kept': [{'id': 'W1', 'referenced_works': []}]}), encoding='utf-8')
    assert graph.main(['--input', str(f)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'ok'
    assert report['graph']['summary']['node_count'] == 1


# ---------- LA-04 ----------

def test_la04_duplicate_references_not_amplified():
    works = [
        {'id': 'W1', 'referenced_works': ['https://openalex.org/W2', 'W2']},
        {'id': 'W2', 'referenced_works': []},
    ]
    g = graph.build_graph(works)
    assert g['summary']['internal_edge_count'] == 1
    assert g['summary']['duplicate_edge_count'] == 1


# ---------- LA-05 ----------

def test_la05_book_chapter_container():
    msg = {
        'type': 'book-chapter',
        'title': ['A Chapter'],
        'container-title': ['The Big Book'],
        'publisher': 'Example Press',
        'author': [{'family': 'Li', 'given': 'Lei'}],
        'issued': {'date-parts': [[2021]]},
    }
    entry = bibtex.crossref_to_entry(msg)
    assert entry['type'] == 'incollection'
    assert entry['fields']['booktitle'] == 'The Big Book'
    assert entry['fields']['publisher'] == 'Example Press'


# ---------- LA-06 ----------

def test_la06_list_response_rejected():
    with pytest.raises(ValueError):
        interop.from_crossref_json({'message': {'items': [{'DOI': '10.1/a'}]}})


def test_la06_search_results_parsed():
    works = interop.from_crossref_search_results(
        {'message': {'items': [{'DOI': '10.1/a', 'title': ['A']},
                               {'DOI': '10.1/b', 'title': ['B']}]}})
    assert [w.doi for w in works] == ['10.1/a', '10.1/b']


# ---------- LA-07 ----------

def test_la07_interop_to_bibtex_escapes():
    work = interop.CanonicalWork(title='100% & pure', authors=['Zhang, San'], year=2020)
    out = interop.to_bibtex(work)
    assert r'100\% \& pure' in out


def test_la07_escape_tables_identical():
    for ch in '\\{}&%$#_~^':
        assert interop.tex_escape(ch) == bibtex.tex_escape(ch), ch


# ---------- LA-08 ----------

def test_la08_institutional_author_not_split():
    authors = interop._bibtex_authors('{Harvard and MIT} and Zhang, San')
    assert authors == ['Harvard and MIT', 'Zhang, San']


def test_la08_name_only_author_kept():
    work = interop.from_crossref_json({'DOI': '10.1/a', 'title': ['A'],
                                       'author': [{'name': 'WHO Collaborating Centre'}]})
    assert work.authors == ['WHO Collaborating Centre']


# ---------- LA-09 ----------

def test_la09_created_not_year():
    work = interop.from_crossref_json({'DOI': '10.1/a', 'title': ['A'],
                                       'created': {'date-parts': [[2023]]}})
    assert work.year is None
    assert work.extra.get('registered_at') == '2023'


# ---------- SR-03 ----------

def test_sr03_nonfinite_rejected():
    with pytest.raises(ValueError):
        meta_core.heterogeneity([0.0, float('nan')], [1.0, 1.0])
    with pytest.raises(ValueError):
        meta_core.heterogeneity([0.0, 1.0], [1.0, float('inf')])


# ---------- SR-08 ----------

def test_sr08_hedges_threshold_documented():
    ref = (SKILLS / "systematic-review-meta-analysis"
           / "references/effect-size-conversions.md").read_text(encoding='utf-8')
    assert 'df=10 时 J≈0.923' in ref
    assert 'df ≥ 40 时 J > 0.98' in ref
    assert meta_core.hedges_j(10) == pytest.approx(1 - 3 / 39)


# ---------- SR-09 ----------

def test_sr09_pubmed_proximity_documented():
    ref = (SKILLS / "systematic-review-meta-analysis"
           / "references/search-strategy-guide.md").read_text(encoding='utf-8')
    assert '[tiab:~N]' in ref


# ---------- QA-03 ----------

def test_qa03_legit_zero_percent():
    res = recompute.check_percentage(0, 0, denominator=10)
    assert res['consistent'] is True
    assert res['recomputed_percent'] == 0.0


def test_qa03_zero_percent_without_denominator():
    res = recompute.check_percentage(0, 0)
    assert res['consistent'] is None
    assert '无法确定分母' in res['note']
    res2 = recompute.check_percentage(1, 0, denominator=10)
    assert res2['consistent'] is False


# ---------- QA-04 ----------

def test_qa04_explicit_decimals_restores_precision():
    res = recompute.check_percentage(50, 0.050, decimals=3)
    assert res['tolerance'] == pytest.approx(0.0005 + 1e-12)
    res2 = recompute.check_percentage(50, 0.05)
    assert res2['tolerance'] == pytest.approx(0.005 + 1e-12)


# ---------- RP-02 ----------

def test_rp02_receipt_keeps_evidence_fields():
    cl = {'paper': {'title': 'T'},
          'stages': [{'id': 'measured-metrics', 'status': 'pass',
                      'claimed_value': 0.91, 'measured_value': 0.90,
                      'tolerance': 0.02, 'evidence': 'table 3',
                      'artifacts': ['log.txt'], 'checked_at': '2026-09-17'}]}
    receipt = repro.adjudicate(cl)
    stage = {s['id']: s for s in receipt['stages']}['measured-metrics']
    assert stage['claimed_value'] == 0.91
    assert stage['measured_value'] == 0.90
    assert stage['tolerance'] == 0.02
    assert stage['evidence'] == 'table 3'
    assert stage['artifacts'] == ['log.txt']
    assert stage['checked_at'] == '2026-09-17'


# ---------- FW-01 ----------

MINI_CATALOG = {
    'axes': {
        'A': {'levels': ['a1', 'a2', 'a3']},
        'E01_primary_capability': {'levels': ['cap1', 'cap2'], 'multi': True, 'min_choice': 1, 'max_choice': 3},
        'E02_skill_under_test': {'levels': ['s1', 's2']},
        'E03_task_goal': {'levels': ['g1', 'g2']},
        'E04_correct_terminal_state': {'levels': ['ok']},
    },
    'seed': 20260917,
    'hard_coverage_axes': [],
    'coverage_quotas': {'min_skill_usage': 2, 'min_skill_task_goals': 2, 'min_capability_usage': 1},
    'skill_semantics': {
        's1': {'coverage_anchor_goal': 'g1', 'task_goals': {'g1': ['cap1']}, 'event_categories': ['ev1', 'ev2']},
        's2': {'coverage_anchor_goal': 'g2', 'task_goals': {'g2': ['cap2']}, 'event_categories': ['ev1', 'ev2']},
    },
    'pairwise_axes': [],
    'critical_tuple': ['A'],
    'events': {'ev1': {}, 'ev2': {}},
}


def test_fw01_inverse_keeps_shared_levels():
    combo1 = {'A': 'a1', 'E01_primary_capability': ['cap1'],
              'E02_skill_under_test': 's1', 'E03_task_goal': 'g1',
              'E04_correct_terminal_state': 'ok', '_ci': 1}
    combo2 = {'A': 'a1', 'E01_primary_capability': ['cap2'],
              'E02_skill_under_test': 's2', 'E03_task_goal': 'g2',
              'E04_correct_terminal_state': 'ok', '_ci': 2}
    state = longtail.coverage_state(MINI_CATALOG)
    longtail.apply_combo(MINI_CATALOG, combo1, state)
    longtail.apply_combo(MINI_CATALOG, combo2, state)
    assert 'a1' in state['levels']['A']
    longtail.apply_combo_inverse(MINI_CATALOG, combo1, state, [combo2])
    assert 'a1' in state['levels']['A'], '共享 level 被其他场景覆盖时不得误删'
    assert state['skills']['s2'] == 1
    assert state['capabilities']['cap2'] == 1
    assert state['task_goals']['g2'] == 1


# ---------- FW-02 ----------

def test_fw02_absent_skill_flagged():
    state = longtail.coverage_state(MINI_CATALOG)
    problems = longtail.verify_quotas(state, [], MINI_CATALOG)
    assert any(p.startswith('skill s1:') and '0 < 2' in p for p in problems)
    assert any(p.startswith('skill s2:') for p in problems)


# ---------- FW-03 ----------

def test_fw03_report_claims_are_factual():
    src = (TOOLS / "longtail/generate.py").read_text(encoding='utf-8')
    assert '"repair_executed": False' in src
    assert 'not proven' in src
    assert 'best attainable' not in src

"""第二批裁决回归测试: 身份、撤稿与复现结论的 P1 (七项)。

- AV-01 来源互证前校验目标 DOI 绑定
- AV-02 PDF DOI 完整提取后精确匹配 (子串命中不再算)
- ID-01 部分记录共享标识符不得整批判 EXACT
- ID-02 human_confirmed 严格 JSON 布尔
- MW-01 OpenAlex 404 三态 (unknown 不冒充阴性, 保留最后成功核验)
- MW-02 首批分页截断完整性标记
- RP-01 豁免契约: 严格布尔 + 允许阶段 + 非空理由
"""

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"


def _load(rel_path, name):
    spec = importlib.util.spec_from_file_location(name, SKILLS / rel_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify_work = _load("academic-source-verification/scripts/verify_work.py", "av_verify_work")
verify_pdf = _load("academic-source-verification/scripts/verify_pdf_identity.py", "av_verify_pdf")
identity = _load("research-object-identity/scripts/identity.py", "id_identity")
retraction_watch = _load("retraction-watch/scripts/watch.py", "mw_retraction")
literature_watch = _load("literature-watch/scripts/watch.py", "mw_literature")
repro = _load("research-reproducibility/scripts/repro_checklist.py", "rp_repro")


# ---------- AV-01: 目标 DOI 绑定 ----------

def test_av01_compare_works_flags_binding_mismatch():
    """请求 A 而两份记录都是 B: 来源间比较可以通过, 但绑定冲突必须被拦住。"""
    works = [
        {'source': 'openalex', 'doi': '10.9999/b', 'title': 'Paper B', 'year': 2020},
        {'source': 'crossref', 'doi': '10.9999/B', 'title': 'Paper B', 'year': 2020},
    ]
    cmp = verify_work.compare_works(works, target_doi='10.1234/a')
    assert len(cmp['identity_binding_mismatch']) == 2
    assert cmp['fields']['doi']['match'] is True, '来源间一致, 但绑定冲突必须显式列出'
    # 不传 target 时向后兼容, 无绑定校验
    cmp2 = verify_work.compare_works(works)
    assert cmp2['identity_binding_mismatch'] == []


def test_av01_compare_works_binding_ok():
    works = [
        {'source': 'openalex', 'doi': 'https://doi.org/10.1234/A', 'title': 'A'},
        {'source': 'crossref', 'doi': '10.1234/a', 'title': 'A'},
    ]
    cmp = verify_work.compare_works(works, target_doi='10.1234/A')
    assert cmp['identity_binding_mismatch'] == []


# ---------- AV-02: DOI 精确匹配 ----------

def test_av02_find_doi_no_substring_match():
    """目标 10.1234/abc 不得命中仅含 10.1234/abcd 的文本。"""
    assert verify_pdf.find_doi('10.1234/abc', '本文 DOI 为 10.1234/abcd') is False
    assert verify_pdf.find_doi('10.1234/abc', '10.1234/abc') is True
    assert verify_pdf.find_doi('10.1234/ABC', 'doi: 10.1234/abc.') is True


def test_av02_extract_dois():
    found = verify_pdf.extract_dois('doi 10.1000/a and 10.1000/B, cited.')
    assert found == ['10.1000/a', '10.1000/b']


# ---------- ID-01: 部分共享不判 EXACT ----------

def test_id01_partial_shared_not_exact():
    """A、B 同 DOI, C 与它们无关: 不得整批判为 EXACT。"""
    a = {'identifiers': [{'type': 'doi', 'value': '10.1/x'}], 'title': 'Paper X',
         'source': 's1', 'queried_at': 't'}
    b = {'identifiers': [{'type': 'doi', 'value': '10.1/x'}], 'title': 'Paper X',
         'source': 's2', 'queried_at': 't'}
    c = {'identifiers': [{'type': 'doi', 'value': '10.2/y'}], 'title': 'Paper Y',
         'source': 's3', 'queried_at': 't'}
    agg = identity.resolve([a, b, c])
    assert agg['verdict'] != 'EXACT'
    assert any(u['kind'] == 'partial_shared_identifier' for u in agg['uncertainty'])


def test_id01_all_connected_exact_preserved():
    """全部记录共享同一标识符时 EXACT 行为保持。"""
    a = {'identifiers': [{'type': 'doi', 'value': '10.1/x'}], 'title': 'Paper X',
         'source': 's1', 'queried_at': 't'}
    b = {'identifiers': [{'type': 'doi', 'value': '10.1/x'}], 'title': 'Paper X',
         'source': 's2', 'queried_at': 't'}
    agg = identity.resolve([a, b])
    assert agg['verdict'] == 'EXACT'


# ---------- ID-02: 严格布尔 ----------

def test_id02_strict_bool_rejects_string_false():
    obj_a = identity.from_canonical_work({'doi': '10.1/a', 'title': 'A'})
    obj_b = identity.from_canonical_work({'doi': '10.1/b', 'title': 'B'})
    try:
        identity.link(obj_a, obj_b, 'cites', {
            'source': 'x', 'queried_at': 't', 'match_fields': [],
            'conflict_fields': [], 'human_confirmed': 'false'})
        raise AssertionError('string "false" must be rejected')
    except ValueError:
        pass
    # JSON 布尔正常
    edge = identity.link(obj_a, obj_b, 'cites', {
        'source': 'x', 'queried_at': 't', 'match_fields': [],
        'conflict_fields': [], 'human_confirmed': False})
    assert edge['evidence']['human_confirmed'] is False


# ---------- MW-01: 撤稿三态 ----------

def test_mw01_unknown_not_folded_to_false():
    snap = retraction_watch.snapshot_from_signals(None, [])
    assert snap['is_retracted'] is None
    snap2 = retraction_watch.snapshot_from_signals(False, [])
    assert snap2['is_retracted'] is False
    try:
        retraction_watch.snapshot_from_signals('false', [])
        raise AssertionError('string "false" must be rejected')
    except ValueError:
        pass


def test_mw01_diff_preserves_last_verified():
    old = {'is_retracted': True, 'signals': []}
    new = {'is_retracted': None, 'signals': []}
    changes = retraction_watch.diff_snapshots(old, new)
    assert any('保留上次成功核验结果' in c for c in changes)


def test_mw01_check_doi_404_returns_unknown(monkeypatch):
    """OpenAlex 404 时 is_retracted=None, 不得折叠成 False。"""
    class _FakeHTTPError(Exception):
        def __init__(self, code):
            self.code = code

    def fake_get(url, timeout=20):
        if url.startswith(retraction_watch.OPENALEX):
            raise _FakeHTTPError(404)
        return {'message': {'items': []}}

    monkeypatch.setattr(retraction_watch, 'get', fake_get)
    monkeypatch.setattr(retraction_watch, 'HTTPError', _FakeHTTPError)
    snap = retraction_watch.check_doi('10.1/a')
    assert snap['is_retracted'] is None


def test_mw01_run_keeps_last_verified(monkeypatch, tmp_path):
    """本轮 unknown 且有历史阳性: 状态文件保留阳性, 不覆盖。"""
    wl = tmp_path / 'wl.json'
    wl.write_text(json.dumps({'dois': ['10.1/a']}), encoding='utf-8')
    state = tmp_path / 'state.json'
    state.write_text(json.dumps({'10.1/a': {'is_retracted': True, 'signals': []}}),
                     encoding='utf-8')
    monkeypatch.setattr(retraction_watch, 'check_doi',
                        lambda doi: {'is_retracted': None, 'signals': []})
    retraction_watch.run(str(wl), str(state))
    saved = json.loads(state.read_text(encoding='utf-8'))
    assert saved['10.1/a']['is_retracted'] is True


# ---------- MW-02: 分页截断 ----------

def test_mw02_truncated_flag():
    assert literature_watch._truncated({'meta': {'count': 150},
                                        'results': list(range(100))}) is True
    assert literature_watch._truncated({'meta': {'count': 50},
                                        'results': list(range(50))}) is False
    assert literature_watch._truncated({'results': []}) is False


def test_mw02_collect_reports_truncation(monkeypatch):
    wl = {'topics': ['t'], 'authors': [], 'dois': []}
    monkeypatch.setattr(literature_watch, 'fetch_topic_works',
                        lambda topic, since: ([{'id': 'W1'}], True))
    items, truncations = literature_watch.collect(wl, None)
    assert items == [{'id': 'W1'}]
    assert truncations and 'topic' in truncations[0]


# ---------- RP-01: 豁免契约 ----------

def _checklist(extra_stages):
    stages = [{'id': sid, 'status': 'pass'} for sid in repro.STAGE_IDS]
    stages.extend(extra_stages)
    # 去重: 后加的覆盖前加的
    by_id = {}
    for s in stages:
        by_id[s['id']] = s
    return {'paper': {'title': 'T'}, 'stages': list(by_id.values())}


def test_rp01_waived_string_false_is_not_waiver():
    try:
        repro.normalize(_checklist([{'id': 'dataset', 'status': 'skipped',
                                     'waived': 'false'}]))
        raise AssertionError('string "false" must be rejected')
    except repro.ChecklistError:
        pass


def test_rp01_waived_requires_reason_and_waivable_stage():
    try:
        repro.normalize(_checklist([{'id': 'dataset', 'status': 'skipped',
                                     'waived': True}]))
        raise AssertionError('waived without reason must be rejected')
    except repro.ChecklistError:
        pass
    try:
        repro.normalize(_checklist([{'id': 'identity', 'status': 'skipped',
                                     'waived': True, 'reason': 'x'}]))
        raise AssertionError('hard stage must not be waivable')
    except repro.ChecklistError:
        pass


def test_rp01_legitimate_waiver_ok():
    cl = _checklist([{'id': 'dataset', 'status': 'skipped', 'waived': True,
                      'reason': '无数据集'}])
    receipt = repro.adjudicate(cl)
    assert 'dataset' not in receipt['gaps']

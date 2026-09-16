"""research-object-identity 测试：normalize/resolve/link 三核心、五态判定、
CanonicalWork 兼容、Evidence Receipt 消费与 schema 合法性。"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / 'schemas' / 'research-object.schema.json'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclass 延迟注解要求模块已注册
    spec.loader.exec_module(module)
    return module


identity = _load('identity', ROOT / 'skills' / 'research-object-identity' / 'scripts' / 'identity.py')
interop = _load('interop', ROOT / 'skills' / 'literature-analysis' / 'scripts' / 'interop.py')

EVIDENCE = {'source': 'OpenAlex', 'queried_at': '2026-09-17T00:00:00Z',
            'match_fields': ['doi'], 'conflict_fields': [], 'human_confirmed': False}


def _draft(object_id='ro:work:10.1/a'):
    return {'object_id': object_id, 'object_type': 'Work', 'identifiers': [],
            'manifestations': [], 'relations': [], 'lineage': [],
            'source_observations': [], 'uncertainty': []}


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('kind,value,expected', [
    ('doi', 'https://doi.org/10.1038/Nature12373', '10.1038/nature12373'),
    ('doi', 'doi: 10.1126/Science.1234567', '10.1126/science.1234567'),
    ('doi', 'http://dx.doi.org/10.1000/XYZ', '10.1000/xyz'),
    ('arxiv_id', '2310.15264v2', '2310.15264'),
    ('arxiv_id', 'arXiv:1706.03762v5', '1706.03762'),
    ('arxiv_id', 'https://arxiv.org/abs/2310.15264', '2310.15264'),
    ('arxiv_id', 'https://arxiv.org/pdf/hep-th/9901001v1', 'hep-th/9901001'),
    ('pmid', 'PMID: 38123654', '38123654'),
    ('pmid', 'pmid38123654.', '38123654'),
    ('openalex_id', 'https://openalex.org/W2123456789', 'W2123456789'),
    ('openalex_id', 'w2123456789', 'W2123456789'),
    ('orcid', 'https://orcid.org/0000-0002-1825-0097', '0000000218250097'),
    ('orcid', '0000-0002-1825-009x', '000000021825009X'),
    ('isbn', ' 978-7-04-000000-0 ', '9787040000000'),
])
def test_normalize(kind, value, expected):
    assert identity.normalize(kind, value) == expected


def test_normalize_empty_and_none():
    assert identity.normalize('doi', '') == ''
    assert identity.normalize('doi', None) == ''


# ---------------------------------------------------------------------------
# resolve：五态判定
# ---------------------------------------------------------------------------

def test_resolve_exact_shared_identifiers():
    """同一论文的 DOI+arXiv+PMID 三条记录：规范 DOI 全一致 -> EXACT。"""
    records = [
        {'identifiers': [{'type': 'doi', 'value': 'https://doi.org/10.1038/nature12373'}],
         'title': 'Attention Is All You Need', 'authors': ['Vaswani, Ashish'], 'year': 2017,
         'source': 'Crossref', 'queried_at': '2026-09-17T00:00:00Z'},
        {'identifiers': [{'type': 'doi', 'value': 'doi:10.1038/Nature12373'},
                         {'type': 'arxiv_id', 'value': '1706.03762v5'}],
         'title': 'Attention Is All You Need', 'authors': ['Vaswani, Ashish'], 'year': 2017,
         'source': 'arXiv', 'queried_at': '2026-09-17T00:01:00Z'},
        {'identifiers': [{'type': 'doi', 'value': '10.1038/nature12373'},
                         {'type': 'pmid', 'value': 'PMID:38123654'}],
         'title': 'Attention Is All You Need', 'authors': ['Vaswani, Ashish'], 'year': 2017,
         'source': 'PubMed', 'queried_at': '2026-09-17T00:02:00Z'},
    ]
    out = identity.resolve(records)
    assert out['verdict'] == 'EXACT'
    assert out['object_type'] == 'Work'
    assert 'doi' in out['match_fields'] and 'title' in out['match_fields']
    assert out['conflict_fields'] == []
    assert out['human_confirmed'] is False
    assert [s['source'] for s in out['sources']] == ['Crossref', 'arXiv', 'PubMed']
    merged = {(i['type'], i['normalized']) for i in out['merged_identifiers']}
    assert ('doi', '10.1038/nature12373') in merged
    assert ('arxiv_id', '1706.03762') in merged
    assert ('pmid', '38123654') in merged


def test_resolve_conflict_two_dois():
    """两个不同 DOI 且标题不同 -> CONFLICT，冲突字段含 doi。"""
    out = identity.resolve([
        {'identifiers': [{'type': 'doi', 'value': '10.1/aaa'}], 'title': 'First paper', 'year': 2020},
        {'identifiers': [{'type': 'doi', 'value': '10.1/bbb'}], 'title': 'Second paper', 'year': 2021},
    ])
    assert out['verdict'] == 'CONFLICT'
    assert 'doi' in out['conflict_fields']
    assert 'title' in out['conflict_fields']
    assert out['match_fields'] == []


def test_resolve_conflict_same_pmid_type_two_values():
    """同一 PMID 类型出现两个不同值即 CONFLICT，优先于共享 DOI。"""
    out = identity.resolve([
        {'identifiers': [{'type': 'doi', 'value': '10.1/a'}, {'type': 'pmid', 'value': '111'}]},
        {'identifiers': [{'type': 'doi', 'value': '10.1/a'}, {'type': 'pmid', 'value': '222'}]},
    ])
    assert out['verdict'] == 'CONFLICT'
    assert 'pmid' in out['conflict_fields']


def test_resolve_strong_match_title_authors_equal():
    """无共享标识符、标题与作者规范后全部一致 -> STRONG_MATCH。"""
    out = identity.resolve([
        {'title': 'Deep Residual Learning for Image Recognition',
         'authors': ['He, Kaiming', 'Zhang, Xiangyu'], 'year': 2016},
        {'title': 'deep residual learning for image recognition!',
         'authors': ['He, Kaiming', 'Zhang, Xiangyu'], 'year': 2016},
    ])
    assert out['verdict'] == 'STRONG_MATCH'
    assert 'title' in out['match_fields'] and 'authors' in out['match_fields']


def test_resolve_candidate_author_overlap():
    """姓名变体与标题部分一致 -> CANDIDATE。"""
    out = identity.resolve([
        {'title': 'Deep learning for graphs', 'authors': ['Zhang, Wei']},
        {'title': 'Deep learning for graphs: a survey', 'authors': ['Zhang, W.']},
    ])
    assert out['verdict'] == 'CANDIDATE'


def test_resolve_candidate_shared_author_only():
    """标题不相干但作者有重叠 -> CANDIDATE（作者重叠触发）。"""
    out = identity.resolve([
        {'title': 'Alpha beta gamma', 'authors': ['Li, Na', 'Wang, Gang']},
        {'title': 'Delta epsilon zeta', 'authors': ['Li, Na']},
    ])
    assert out['verdict'] == 'CANDIDATE'


def test_resolve_unresolved_empty():
    assert identity.resolve([])['verdict'] == 'UNRESOLVED'
    assert identity.resolve(None)['verdict'] == 'UNRESOLVED'


def test_resolve_unresolved_insufficient_info():
    """无标识符、标题不相干、作者无重叠 -> UNRESOLVED。"""
    out = identity.resolve([
        {'title': 'Alpha beta gamma', 'authors': ['Li, Na']},
        {'title': 'Delta epsilon zeta', 'authors': ['Wang, Gang']},
    ])
    assert out['verdict'] == 'UNRESOLVED'


def test_resolve_single_record():
    with_id = identity.resolve([{'identifiers': [{'type': 'doi', 'value': '10.1/a'}]}])
    assert with_id['verdict'] == 'EXACT'
    bare = identity.resolve([{'title': 'only a title'}])
    assert bare['verdict'] == 'UNRESOLVED'


def test_judge_is_pure_facts():
    """judge 直接接受离散事实，五态各一条。"""
    base = dict(id_conflicts=False, shared_identifier=False, single_record=False,
                has_identifier=False, title_all_equal=False, authors_all_equal=False,
                title_similar=False, author_overlap=False)
    assert identity.judge({**base, 'id_conflicts': True, 'shared_identifier': True}) == 'CONFLICT'
    assert identity.judge({**base, 'shared_identifier': True}) == 'EXACT'
    assert identity.judge({**base, 'single_record': True, 'has_identifier': True}) == 'EXACT'
    assert identity.judge({**base, 'title_all_equal': True, 'authors_all_equal': True}) == 'STRONG_MATCH'
    assert identity.judge({**base, 'title_similar': True}) == 'CANDIDATE'
    assert identity.judge(base) == 'UNRESOLVED'


def test_title_similarity_threshold():
    assert identity.title_similarity('Deep learning for graphs',
                                     'Deep learning for graphs: a survey') >= 0.5
    assert identity.title_similarity('Alpha beta gamma', 'Delta epsilon zeta') == 0.0


# ---------------------------------------------------------------------------
# link
# ---------------------------------------------------------------------------

def test_link_relation_directional_no_reverse_backfill():
    """cites 是有向边:只在 a 侧建边,b 侧不得出现反向断言。"""
    a, b = _draft('ro:work:a'), _draft('ro:work:b')
    edge = identity.link(a, b, 'cites', EVIDENCE)
    assert edge['target_object_id'] == 'ro:work:b'
    assert a['relations'][0]['target_object_id'] == 'ro:work:b'
    assert a['relations'][0]['kind'] == 'cites'
    for key in identity.EVIDENCE_KEYS:
        assert key in a['relations'][0]['evidence']
    assert b['relations'] == [], 'b 侧不得伪造反向 cites 断言'
    # 需要反向关系时调用者显式 link(b, a)
    identity.link(b, a, 'cites', EVIDENCE)
    assert b['relations'][0]['target_object_id'] == 'ro:work:a'


def test_link_rejects_self_loop():
    a = _draft('ro:work:a')
    with pytest.raises(ValueError):
        identity.link(a, a, 'cites', EVIDENCE)


def test_link_lineage_backfill_both_objects():
    a, b = _draft('ro:work:pre'), _draft('ro:work:vor')
    edge = identity.link(a, b, 'preprint_to_vor', EVIDENCE)
    assert edge['from_object_id'] == 'ro:work:pre' and edge['to_object_id'] == 'ro:work:vor'
    assert a['lineage'][0] == edge and b['lineage'][0] == edge


def test_link_evidence_required_keys():
    a, b = _draft(), _draft('ro:work:b')
    incomplete = {k: v for k, v in EVIDENCE.items() if k != 'human_confirmed'}
    with pytest.raises(ValueError):
        identity.link(a, b, 'cites', incomplete)
    with pytest.raises(ValueError):
        identity.link(a, b, 'cites', None)


def test_link_rejects_unknown_kind():
    a, b = _draft(), _draft('ro:work:b')
    with pytest.raises(ValueError):
        identity.link(a, b, 'similar_to', EVIDENCE)
    assert a['relations'] == [] and a['lineage'] == []


# ---------------------------------------------------------------------------
# from_canonical_work
# ---------------------------------------------------------------------------

CANONICAL = interop.CanonicalWork(
    work_type='article', title='Attention Is All You Need',
    authors=['Vaswani, Ashish', 'Shazeer, Noam'], year=2017,
    container='Advances in Neural Information Processing Systems',
    doi='10.5555/3295222.3295349', url='https://arxiv.org/abs/1706.03762')


def test_from_canonical_work_preserves_fields():
    draft = identity.from_canonical_work(CANONICAL)
    assert draft['object_type'] == 'Work'
    assert draft['object_id'] == 'ro:work:10.5555/3295222.3295349'
    assert draft['title'] == CANONICAL.title
    assert draft['authors'] == CANONICAL.authors
    assert draft['year'] == CANONICAL.year
    assert draft['container'] == CANONICAL.container
    assert draft['identifiers'] == [{'type': 'doi', 'value': CANONICAL.doi,
                                     'normalized': CANONICAL.doi}]
    for key in ('manifestations', 'relations', 'lineage', 'source_observations', 'uncertainty'):
        assert draft[key] == []


def test_from_canonical_work_dict_and_roundtrip_resolve():
    """dict 输入等价；两条 CanonicalWork 转换后再聚合回到 EXACT。"""
    from_dict = identity.from_canonical_work(CANONICAL.to_dict())
    from_obj = identity.from_canonical_work(CANONICAL)
    assert from_dict == from_obj
    out = identity.resolve([from_obj, dict(from_dict)])
    assert out['verdict'] == 'EXACT'
    assert 'doi' in out['match_fields']


def test_from_canonical_work_without_doi_uses_title_slug():
    draft = identity.from_canonical_work({'title': 'Attention Is All You Need', 'authors': [], 'year': 2017})
    assert draft['object_id'] == 'ro:work:attention-is-all-you-need'
    assert draft['identifiers'] == []


# ---------------------------------------------------------------------------
# consume_receipt
# ---------------------------------------------------------------------------

RECEIPT = json.loads((ROOT / 'examples' / 'evidence-receipt.example.json').read_text(encoding='utf-8'))


def test_consume_receipt_sources_become_observations():
    out = identity.consume_receipt(RECEIPT)
    assert len(out['source_observations']) == len(RECEIPT['sources'])
    first = out['source_observations'][0]
    assert first['source'] == 'OpenAlex' and first['status'] == 'ok'
    assert 'queried_at' in first and 'raw_identifier' in first
    assert out['uncertainty'] == []  # 示例回执无冲突


def test_consume_receipt_conflicts_need_human():
    receipt = dict(RECEIPT, conflicts=['citation count differs between sources'],
                   failures=['Unpaywall timeout'])
    out = identity.consume_receipt(receipt)
    kinds = {u['kind'] for u in out['uncertainty']}
    assert 'receipt_conflict' in kinds and 'query_failure' in kinds
    conflict = next(u for u in out['uncertainty'] if u['kind'] == 'receipt_conflict')
    assert conflict['needs_human'] is True
    failure = next(u for u in out['uncertainty'] if u['kind'] == 'query_failure')
    assert failure['needs_human'] is False


def test_consume_receipt_claim_status_mapping():
    receipt = dict(RECEIPT, claims=[
        {'claim': 'A', 'evidence_type': 'metadata', 'source': 'OpenAlex',
         'support_status': 'contradicted'},
        {'claim': 'B', 'evidence_type': 'metadata', 'source': 'OpenAlex',
         'support_status': 'unverifiable'},
        {'claim': 'C', 'evidence_type': 'metadata', 'source': 'OpenAlex',
         'support_status': 'supported'},
    ])
    out = identity.consume_receipt(receipt)
    by_item = {u['item']: u for u in out['uncertainty']}
    assert by_item['A'] == {'item': 'A', 'kind': 'contradicted_claim', 'needs_human': True}
    assert by_item['B'] == {'item': 'B', 'kind': 'unverifiable_claim', 'needs_human': False}
    assert 'C' not in by_item


# ---------------------------------------------------------------------------
# schema 合法性
# ---------------------------------------------------------------------------

def test_schema_parseable_and_required_keys():
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    assert schema['$schema'] == 'https://json-schema.org/draft/2020-12/schema'
    assert schema['type'] == 'object'
    assert schema['required'] == ['object_id', 'object_type', 'identifiers', 'manifestations',
                                  'relations', 'lineage', 'source_observations', 'uncertainty']


def test_schema_enums():
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    assert set(schema['properties']['object_type']['enum']) == {
        'Work', 'Person', 'Dataset', 'CodeRepository', 'Artifact'}
    items = schema['properties']
    assert set(items['relations']['items']['properties']['kind']['enum']) == {
        'cites', 'contradicts', 'replicates', 'derived_from'}
    assert set(items['lineage']['items']['properties']['kind']['enum']) == {
        'preprint_to_vor', 'correction', 'retraction', 'version_chain'}
    assert set(items['source_observations']['items']['properties']['status']['enum']) == {
        'ok', 'failed', 'skipped'}
    assert set(items['manifestations']['items']['properties']['kind']['enum']) == {
        'preprint', 'version_of_record', 'author_manuscript', 'publisher_pdf',
        'dataset_release', 'commit'}
    id_types = set(items['identifiers']['items']['properties']['type']['enum'])
    assert {'doi', 'arxiv_id', 'pmid', 'openalex_id', 'orcid'} <= id_types


def test_draft_conforms_to_schema_structure():
    """from_canonical_work 草案满足 schema 的必需键与枚举约束（手工校验）。"""
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    draft = identity.from_canonical_work(CANONICAL)
    for key in schema['required']:
        assert key in draft
    assert draft['object_type'] in schema['properties']['object_type']['enum']
    for ident in draft['identifiers']:
        assert ident['type'] in schema['properties']['identifiers']['items']['properties']['type']['enum']
    # 建边后的边结构符合 edgeEvidence 必需键
    other = identity.from_canonical_work({'doi': '10.1/b', 'title': 'T', 'authors': ['A'], 'year': 2020})
    identity.link(draft, other, 'cites', EVIDENCE)
    edge = draft['relations'][0]
    for key in schema['$defs']['edgeEvidence']['required']:
        assert key in edge['evidence']


# ---------------------------------------------------------------------------
# 交叉评审补强:jsonschema 真校验、版本拒绝、out_of_scope、顺序不敏感等
# ---------------------------------------------------------------------------

def _schema_obj():
    import json
    from pathlib import Path
    return json.loads((Path(__file__).resolve().parent.parent
                       / 'schemas' / 'research-object.schema.json').read_text(encoding='utf-8'))


def test_drafts_validate_against_real_jsonschema():
    """from_canonical_work 草案必须通过真实 jsonschema 校验(非手工键检查)。"""
    import jsonschema
    schema = _schema_obj()
    draft = identity.from_canonical_work({'doi': '10.1038/nature12373',
                                          'title': 'Attention Is All You Need',
                                          'authors': ['Vaswani, Ashish'],
                                          'year': 2017, 'container': 'NeurIPS'})
    jsonschema.validate(draft, schema)
    resolved = identity.resolve([{'identifiers': [{'type': 'doi', 'value': '10.1038/nature12373'}],
                                  'title': 'Attention Is All You Need'}])
    assert resolved['verdict'] == 'EXACT'


def test_consume_receipt_rejects_unknown_schema_version():
    out = identity.consume_receipt({'schema_version': '9.9', 'sources': [], 'claims': [],
                                    'conflicts': [], 'failures': []})
    assert out['uncertainty'][0]['kind'] == 'unsupported_schema_version'
    assert out['uncertainty'][0]['needs_human'] is True


def test_consume_receipt_keeps_out_of_scope_claims():
    out = identity.consume_receipt({'schema_version': '1.0',
                                    'sources': [],
                                    'claims': [{'claim': 'x', 'evidence_type': 'metadata',
                                                'source': 'OpenAlex', 'support_status': 'out_of_scope'}],
                                    'conflicts': [], 'failures': []})
    assert out['uncertainty'][0]['kind'] == 'out_of_scope_claim'
    assert out['uncertainty'][0]['needs_human'] is False


def test_consume_receipt_keeps_coverage():
    out = identity.consume_receipt({'schema_version': '1.0',
                                    'sources': [{'source': 'OpenAlex',
                                                 'queried_at': '2026-09-17T00:00:00Z',
                                                 'status': 'ok', 'coverage': 'identity, retraction flag',
                                                 'raw_identifier': None}],
                                    'claims': [], 'conflicts': [], 'failures': []})
    assert out['source_observations'][0]['coverage'] == 'identity, retraction flag'


def test_resolve_authors_order_insensitive():
    a = {'identifiers': [], 'title': 'Same Title',
         'authors': ['Vaswani, Ashish', 'Shazeer, Noam']}
    b = {'identifiers': [], 'title': 'Same Title',
         'authors': ['Shazeer, Noam', 'Vaswani, Ashish']}
    out = identity.resolve([a, b])
    assert out['verdict'] == 'STRONG_MATCH', out
    assert 'authors' in out['match_fields']


def test_resolve_object_type_disagreement_recorded():
    a = {'identifiers': [{'type': 'doi', 'value': '10.1/a'}], 'object_type': 'Work'}
    b = {'identifiers': [{'type': 'doi', 'value': '10.1/a'}], 'object_type': 'Dataset'}
    out = identity.resolve([a, b])
    assert 'object_type' in out['conflict_fields']
    assert any(u['kind'] == 'object_type_conflict' for u in out['uncertainty'])


def test_from_canonical_work_extracts_arxiv_id():
    draft = identity.from_canonical_work({'doi': '', 'title': 'T', 'authors': [],
                                          'extra': {'arxiv_id': 'arXiv:1706.03762v5'}})
    kinds = [i['type'] for i in draft['identifiers']]
    assert 'arxiv_id' in kinds
    assert draft['identifiers'][0]['normalized'] == '1706.03762'


def test_resolve_transitive_merge_stable():
    """合并输出与输入顺序无关:同一组记录任意排列,merged_identifiers 一致。"""
    records = [
        {'identifiers': [{'type': 'doi', 'value': '10.1/a'}], 'title': 'T'},
        {'identifiers': [{'type': 'arxiv_id', 'value': '1706.03762'}], 'title': 'T'},
    ]
    one = identity.resolve(records)['merged_identifiers']
    two = identity.resolve(list(reversed(records)))['merged_identifiers']
    assert one == two

"""Tests for the per-skill helper scripts extracted from SKILL.md embedded logic.

Covers, for every script: argparse --help, one minimal-input correct-output case,
and graceful degradation without network/keys. Only offline paths are exercised;
functions named live_* perform network access and are not called here.
"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ASV = ROOT / 'skills' / 'academic-source-verification' / 'scripts'
LA = ROOT / 'skills' / 'literature-analysis' / 'scripts'

ASV_SCRIPTS = ['normalize_identifier.py', 'verify_work.py', 'check_updates.py',
               'locate_oa.py', 'verify_pdf_identity.py']
LA_SCRIPTS = ['collect_corpus.py', 'deduplicate_works.py', 'build_citation_graph.py',
              'build_review_matrix.py', 'export_bibtex.py']
ALL_SCRIPTS = [(ASV, name) for name in ASV_SCRIPTS] + [(LA, name) for name in LA_SCRIPTS]


def load(script_dir, name):
    spec = importlib.util.spec_from_file_location(name[:-3].replace('-', '_'), script_dir / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(script_dir, name, *args, stdin=None):
    return subprocess.run([sys.executable, str(script_dir / name), *args],
                          input=stdin, capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=60)


@pytest.mark.parametrize('script_dir,name', ALL_SCRIPTS, ids=[n for _, n in ALL_SCRIPTS])
def test_argparse_help(script_dir, name):
    result = run(script_dir, name, '--help')
    assert result.returncode == 0
    assert 'usage' in result.stdout.lower()


# --- academic-source-verification: normalize_identifier.py ---

def test_normalize_identifier_forms():
    mod = load(ASV, 'normalize_identifier.py')
    cases = {
        'https://doi.org/10.1038/Nature14539': ('doi', '10.1038/nature14539'),
        'doi:10.48550/arXiv.2106.09624': ('doi', '10.48550/arxiv.2106.09624'),
        'arXiv:2106.09624v2': ('arxiv', '2106.09624v2'),
        'hep-th/9901001': ('arxiv', 'hep-th/9901001'),
        'PMID:38289500': ('pmid', '38289500'),
        'https://pubmed.ncbi.nlm.nih.gov/38289500/': ('pmid', '38289500'),
        'https://openalex.org/W2741809807': ('openalex', 'W2741809807'),
        'W2741809807': ('openalex', 'W2741809807'),
    }
    for raw, (kind, value) in cases.items():
        result = mod.normalize_identifier(raw)
        assert result['type'] == kind, raw
        assert result['value'] == value, raw
        assert result['canonical']
    assert mod.normalize_identifier('not an identifier')['type'] == 'unknown'
    assert mod.main(['10.1038/nature14539']) == 0
    assert mod.main(['nonsense']) == 1


# --- academic-source-verification: verify_work.py ---

OPENALEX_FIXTURE = {
    'doi': 'https://doi.org/10.1038/nature14539',
    'title': 'Deep learning', 'publication_year': 2015,
    'primary_location': {'source': {'display_name': 'Nature'}},
    'authorships': [{'author': {'display_name': 'Yann LeCun'}}],
    'cited_by_count': 50000, 'is_retracted': False,
    'open_access': {'oa_status': 'closed'},
}
CROSSREF_FIXTURE = {
    'DOI': '10.1038/nature14539', 'title': ['Deep learning'],
    'issued': {'date-parts': [[2015, 5, 28]]},
    'container-title': ['Nature'],
    'author': [{'given': 'Yann', 'family': 'LeCun'}],
    'is-referenced-by-count': 48000,
}


def test_verify_work_parse_and_compare():
    mod = load(ASV, 'verify_work.py')
    oa = mod.parse_openalex_work(OPENALEX_FIXTURE)
    cr = mod.parse_crossref_work(CROSSREF_FIXTURE)
    assert oa['doi'] == '10.1038/nature14539' and oa['venue'] == 'Nature'
    assert cr['year'] == 2015 and cr['authors'] == ['Yann LeCun']
    comparison = mod.compare_works([oa, cr])
    assert comparison['fields']['doi']['match'] is True
    assert comparison['fields']['title']['match'] is True
    assert comparison['fields']['year']['match'] is True
    assert comparison['citation_counts'] == {'openalex': 50000, 'crossref': 48000}


def test_verify_work_offline_files_and_degradation(tmp_path, capsys):
    mod = load(ASV, 'verify_work.py')
    oa_file = tmp_path / 'oa.json'
    cr_file = tmp_path / 'cr.json'
    oa_file.write_text(json.dumps(OPENALEX_FIXTURE), encoding='utf-8')
    cr_file.write_text(json.dumps(CROSSREF_FIXTURE), encoding='utf-8')
    rc = mod.main(['--doi', '10.1038/nature14539', '--offline',
                   '--openalex-json', str(oa_file), '--crossref-json', str(cr_file)])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report['comparison']['fields']['doi']['match'] is True
    capsys.readouterr()
    rc = mod.main(['--doi', '10.1038/nature14539', '--offline'])
    assert rc == 1
    report = json.loads(capsys.readouterr().out)
    assert all(s['status'] == 'skipped' for s in report['sources'].values())
    assert report['comparison'] is None


# --- academic-source-verification: check_updates.py ---

def test_check_updates_signals_fixture():
    mod = load(ASV, 'check_updates.py')
    fixture = {'DOI': '10.1234/notice', 'update-to': [
        {'DOI': '10.1234/original', 'type': 'retraction', 'source': 'publisher'}]}
    assert mod.update_signals('10.1234/original', [fixture])[0]['type'] == 'retraction'
    assert mod.update_signals('10.1234/notice', [fixture]) == []
    assert mod.update_signals('10.1234/original', [{'DOI': '10.1234/original'}]) == []
    counts = mod.summarize_signals(mod.update_signals('10.1234/original', [fixture]))
    assert counts == {'retraction': 1}


def test_check_updates_offline_records(tmp_path, capsys):
    mod = load(ASV, 'check_updates.py')
    records = [{'DOI': '10.1234/notice', 'update-to': [
        {'DOI': '10.1234/original', 'type': 'correction', 'source': 'publisher'}]}]
    path = tmp_path / 'records.json'
    path.write_text(json.dumps({'message': {'items': records}}), encoding='utf-8')
    assert mod.main(['--doi', '10.1234/original', '--records', str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['signal_counts'] == {'correction': 1}
    assert report['mode'] == 'offline-file'
    assert mod.main(['--doi', '10.1234/other', '--records', str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['signals'] == [] and '未发现' in report['note']


# --- academic-source-verification: locate_oa.py ---

def test_locate_oa_pick_location():
    mod = load(ASV, 'locate_oa.py')
    assert mod.pick_oa_location({'is_oa': False}) is None
    assert mod.pick_oa_location({'is_oa': True, 'best_oa_location': None}) is None
    record = {'is_oa': True, 'best_oa_location': {
        'url_for_pdf': 'https://example.org/paper.pdf', 'url': 'https://example.org/paper',
        'version': 'publishedVersion', 'host_type': 'repository', 'license': 'cc-by'}}
    location = mod.pick_oa_location(record)
    assert location['url_for_pdf'] == 'https://example.org/paper.pdf'
    assert location['version'] == 'publishedVersion'


def test_locate_oa_skip_without_email(monkeypatch, capsys):
    mod = load(ASV, 'locate_oa.py')
    monkeypatch.delenv('UNPAYWALL_EMAIL', raising=False)
    rc = mod.main(['--doi', '10.1038/nature14539'])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'skipped'
    assert 'SKIP' in report['reason'] and 'no result inferred' in report['reason']


def test_locate_oa_offline_record(tmp_path, capsys):
    mod = load(ASV, 'locate_oa.py')
    path = tmp_path / 'up.json'
    path.write_text(json.dumps({'is_oa': False, 'doi': '10.1/x'}), encoding='utf-8')
    assert mod.main(['--doi', '10.1/x', '--record', str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['is_oa'] is False and report['location'] is None
    assert '不证明不存在' in report['note']


# --- academic-source-verification: verify_pdf_identity.py ---

def test_verify_pdf_identity_text_logic():
    mod = load(ASV, 'verify_pdf_identity.py')
    page = 'Deep learning\nYann LeCun, Yoshua Bengio, Geoffrey Hinton\nNature 521, 436-444. doi: 10.1038/nature14539'
    result = mod.compare_title('Deep learning', page)
    assert result['match'] is True and result['token_coverage'] == 1.0
    result = mod.compare_title('Some Completely Different Title About Graphs', page)
    assert result['match'] is False and result['missing_tokens']
    assert mod.find_doi('10.1038/nature14539', page) is True
    assert mod.find_doi('10.9999/absent', page) is False
    assert mod.title_tokens('中文标题 test') == ['中', '文', '标', '题', 'test']


def test_verify_pdf_identity_requires_check_target():
    mod = load(ASV, 'verify_pdf_identity.py')
    with pytest.raises(SystemExit):
        mod.main(['--pdf', 'whatever.pdf'])  # 既无 --title 也无 --doi：argparse error


# --- literature-analysis: collect_corpus.py ---

def test_collect_corpus_merge_layers():
    mod = load(LA, 'collect_corpus.py')
    layers = {
        'text-search': [
            {'title': 'Attention Is All You Need', 'publication_year': 2017,
             'doi': '10.48550/arxiv.1706.03762', 'relevance_score': 0.99},
            {'title': 'Some other paper', 'publication_year': 2020, 'cited_by_count': 5},
        ],
        'algorithmic-related': [
            {'title': 'Attention Is All You Need', 'publication_year': 2017,
             'doi': 'https://doi.org/10.48550/arxiv.1706.03762', 'cited_by_count': 90000},
        ],
    }
    result = mod.merge_candidates(layers)
    assert result['count'] == 2
    merged = result['candidates'][0]
    assert merged['title'] == 'Attention Is All You Need'
    assert merged['source_layers'] == ['text-search', 'algorithmic-related']
    assert merged['cited_by_count'] == 90000  # 第二层补齐缺失字段
    assert result['candidates'][0]['relevance_score'] == 0.99  # 有 relevance 的排前


# --- literature-analysis: deduplicate_works.py ---

def test_deduplicate_works_by_doi_and_title():
    mod = load(LA, 'deduplicate_works.py')
    works = [
        {'title': 'Paper A', 'doi': 'https://doi.org/10.1/A'},
        {'title': 'Paper A duplicate', 'doi': '10.1/a'},
        {'title': 'Attention Is All You Need'},
        {'title': 'attention  is all you need'},
        {'title': 'Paper B', 'doi': '10.1/b'},
    ]
    result = mod.deduplicate_works(works)
    assert result['summary']['input'] == 5
    # 无作者无年份的同标题不再直接判重 (LA-01), 降级为候选关系
    assert result['summary']['kept'] == 4
    assert result['summary']['removed'] == 1
    assert result['summary']['title_candidates'] == 1
    reasons = {r['reason'] for r in result['removed']}
    assert reasons == {'same-doi'}


def test_deduplicate_works_main_stdin(capsys):
    mod = load(LA, 'deduplicate_works.py')
    import io
    stdin = sys.stdin
    sys.stdin = io.StringIO(json.dumps([{'title': 'X', 'doi': '10.1/x'}] * 2))
    try:
        assert mod.main(['--input', '-']) == 0
    finally:
        sys.stdin = stdin
    report = json.loads(capsys.readouterr().out)
    assert report['summary'] == {'input': 2, 'kept': 1, 'removed': 1,
                                 'unidentifiable_kept': 0, 'title_candidates': 0}


# --- literature-analysis: build_citation_graph.py ---

def test_build_citation_graph_offline():
    mod = load(LA, 'build_citation_graph.py')
    works = [
        {'id': 'https://openalex.org/W1', 'title': 'One',
         'referenced_works': ['https://openalex.org/W2', 'https://openalex.org/W9']},
        {'id': 'https://openalex.org/W2', 'title': 'Two', 'referenced_works': []},
        {'id': 'https://openalex.org/W3', 'title': 'Three',
         'referenced_works': ['https://openalex.org/W2']},
    ]
    graph = mod.build_graph(works)
    assert graph['summary'] == {'node_count': 3, 'internal_edge_count': 2,
                                'duplicate_edge_count': 0}
    assert {tuple(sorted(e.values())) for e in graph['edges']} == {('W1', 'W2'), ('W2', 'W3')}
    assert graph['external_reference_counts'] == {'W1': 1}
    assert mod.in_degrees(graph) == {'W1': 0, 'W2': 2, 'W3': 0}


# --- literature-analysis: build_review_matrix.py ---

def test_build_review_matrix_abstract_and_render():
    mod = load(LA, 'build_review_matrix.py')
    index = {'deep': [0], 'learning': [1, 3], 'methods': [2]}
    assert mod.rebuild_abstract(index) == 'deep learning methods learning'
    assert mod.rebuild_abstract(None) is None
    works = [
        {'title': 'Paper | with pipe', 'publication_year': 2021, 'doi': '10.1/a',
         'abstract_inverted_index': index},
        {'title': 'No abstract paper', 'publication_year': 2022},
    ]
    rows = mod.matrix_rows(works)
    assert rows[0]['abstract'] == 'deep learning methods learning'
    assert rows[1]['abstract'] == mod.NEEDS_FULLTEXT
    markdown = mod.render_markdown(rows, coverage={'query': 'deep learning', 'date': '2026-09-16'})
    assert '| 论文(年份) | 方法 | 样本/数据 | 核心结论 | 局限/适用边界 |' in markdown
    assert 'Paper \\| with pipe (2021)' in markdown
    assert '本次矩阵覆盖 2 篇' in markdown and '2026-09-16' in markdown


# --- literature-analysis: export_bibtex.py ---

def test_export_bibtex_name_and_escape_rules():
    mod = load(LA, 'export_bibtex.py')
    authors = [{'family': 'LeCun', 'given': 'Yann'},
               {'family': 'de la Cruz', 'given': 'María'}, {'name': 'Research & Co.'}]
    assert mod.bibtex_name(authors[0]) == 'LeCun, Yann'
    assert mod.bibtex_name(authors[1]) == 'de la Cruz, María'
    assert mod.bibtex_name({'display_name': '王小明'}) == '{王小明}'
    assert mod.tex_escape('A_{B} & 5%') == 'A\\_\\{B\\} \\& 5\\%'
    with pytest.raises(ValueError):
        mod.bibtex_name({})
    assert mod.entry_key([{'family': 'Vaswani'}], 2017, 'Attention is all you need') == 'vaswani2017attention'


def test_export_bibtex_crossref_entry():
    mod = load(LA, 'export_bibtex.py')
    message = {
        'type': 'journal-article', 'DOI': '10.5555/XYZ',
        'title': ['A Survey on RAG Systems'],
        'author': [{'family': 'Smith', 'given': 'Jane'}],
        'container-title': ['Journal of Tests & Measures'],
        'issued': {'date-parts': [[2024]]}, 'volume': '12', 'issue': '3', 'page': '1-20',
    }
    entry = mod.crossref_to_entry(message)
    assert entry['type'] == 'article'
    assert entry['key'] == 'smith2024a'
    assert entry['fields']['title'] == 'A Survey on {RAG} Systems'
    assert entry['fields']['journal'] == 'Journal of Tests \\& Measures'
    assert entry['fields']['doi'] == '10.5555/xyz'
    text = mod.format_entry(entry)
    assert text.startswith('@article{smith2024a,')
    assert 'doi = {10.5555/xyz}' in text


def test_export_bibtex_main_offline(tmp_path, capsys):
    mod = load(LA, 'export_bibtex.py')
    works = [{'type': 'journal-article', 'DOI': '10.1/a', 'title': ['T One'],
              'author': [{'family': 'Lee', 'given': 'Ann'}],
              'container-title': ['J'], 'issued': {'date-parts': [[2020]]}},
             {'type': 'journal-article', 'DOI': '10.1/b', 'title': ['T Two'],
              'author': [{'family': 'Lee', 'given': 'Bob'}],
              'container-title': ['J'], 'issued': {'date-parts': [[2020]]}}]
    path = tmp_path / 'works.json'
    path.write_text(json.dumps(works), encoding='utf-8')
    assert mod.main(['--input', str(path), '--source', 'crossref']) == 0
    out = capsys.readouterr().out
    assert out.count('@article{') == 2
    assert 'lee2020t' in out and 'lee2020t2' in out  # 同 bib 内 key 去重
    assert 'TODO' in out  # 去重说明写入 TODO 注释


def test_export_bibtex_openalex_literal_names():
    mod = load(LA, 'export_bibtex.py')
    work = {'type': 'article', 'type_crossref': 'journal-article',
            'title': 'Test', 'publication_year': 2023,
            'authorships': [{'author': {'display_name': '王小明'}}],
            'primary_location': {'source': {'display_name': '测试期刊'}},
            'biblio': {'volume': '1', 'issue': '2', 'first_page': '10', 'last_page': '19'},
            'doi': 'https://doi.org/10.1/c'}
    entry = mod.openalex_to_entry(work)
    assert entry['fields']['author'] == '{王小明}'
    assert entry['fields']['pages'] == '10--19'
    assert entry['fields']['doi'] == '10.1/c'
    assert any('display_name' in todo for todo in entry['todo'])


if __name__ == '__main__':
    raise SystemExit(pytest.main([__file__, '-q']))

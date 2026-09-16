"""interop.py 六向互转测试：每种格式一条样本做往返，断言关键字段保持。"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'interop', ROOT / 'skills' / 'literature-analysis' / 'scripts' / 'interop.py')
interop = importlib.util.module_from_spec(spec)
sys.modules['interop'] = interop  # dataclass 解析延迟注解要求模块已注册
spec.loader.exec_module(interop)

CanonicalWork = interop.CanonicalWork

BIBTEX_SAMPLE = """@article{vaswani2017attention,
  title = {Attention Is All You Need},
  author = {Vaswani, Ashish and Shazeer, Noam},
  year = {2017},
  journal = {Advances in Neural Information Processing Systems},
  volume = {30},
  doi = {10.5555/3295222.3295349},
  url = {https://arxiv.org/abs/1706.03762}
}"""

RIS_SAMPLE = """TY  - JOUR
TI  - Attention Is All You Need
AU  - Vaswani, Ashish
AU  - Shazeer, Noam
PY  - 2017
JO  - Advances in Neural Information Processing Systems
VL  - 30
DO  - 10.5555/3295222.3295349
UR  - https://arxiv.org/abs/1706.03762
ER  - """

CSL_SAMPLE = {
    'type': 'article-journal',
    'title': 'Attention Is All You Need',
    'author': [{'family': 'Vaswani', 'given': 'Ashish'},
               {'family': 'Shazeer', 'given': 'Noam'}],
    'issued': {'date-parts': [[2017]]},
    'container-title': 'Advances in Neural Information Processing Systems',
    'volume': '30',
    'DOI': '10.5555/3295222.3295349',
    'URL': 'https://arxiv.org/abs/1706.03762',
}

CROSSREF_SAMPLE = {
    'status': 'ok',
    'message': {
        'type': 'journal-article',
        'title': ['Attention Is All You Need'],
        'author': [{'family': 'Vaswani', 'given': 'Ashish'},
                   {'family': 'Shazeer', 'given': 'Noam'}],
        'issued': {'date-parts': [[2017, 6, 12]]},
        'container-title': ['Advances in Neural Information Processing Systems'],
        'volume': '30',
        'DOI': '10.5555/3295222.3295349',
        'URL': 'https://arxiv.org/abs/1706.03762',
        'publisher': 'Curran Associates',
    },
}

OPENALEX_SAMPLE = {
    'id': 'https://openalex.org/W2963403868',
    'type': 'article',
    'title': 'Attention Is All You Need',
    'publication_year': 2017,
    'authorships': [{'author': {'display_name': 'Ashish Vaswani'}},
                    {'author': {'display_name': 'Noam Shazeer'}}],
    'primary_location': {
        'source': {'display_name': 'Advances in Neural Information Processing Systems'},
        'landing_page_url': 'https://arxiv.org/abs/1706.03762',
    },
    'biblio': {'volume': '30', 'issue': None, 'first_page': None, 'last_page': None},
    'doi': 'https://doi.org/10.5555/3295222.3295349',
}

EXPECTED_KEYS = {
    'work_type': 'article',
    'title': 'Attention Is All You Need',
    'year': 2017,
    'container': 'Advances in Neural Information Processing Systems',
    'doi': '10.5555/3295222.3295349',
    'url': 'https://arxiv.org/abs/1706.03762',
}


def assert_round_trip(work, emit, parse):
    """原文 → CanonicalWork → 原文格式 → CanonicalWork，关键字段一致。"""
    again = parse(emit(work))
    if isinstance(again, list):
        again = again[0]
    assert again.key_fields() == work.key_fields()


def test_bibtex_round_trip():
    work = interop.from_bibtex(BIBTEX_SAMPLE)[0]
    for key, value in EXPECTED_KEYS.items():
        assert work.key_fields()[key] == value, key
    assert work.authors == ['Vaswani, Ashish', 'Shazeer, Noam']
    assert_round_trip(work, interop.to_bibtex, interop.from_bibtex)


def test_ris_round_trip():
    work = interop.from_ris(RIS_SAMPLE)[0]
    for key, value in EXPECTED_KEYS.items():
        assert work.key_fields()[key] == value, key
    assert work.authors == ['Vaswani, Ashish', 'Shazeer, Noam']
    assert_round_trip(work, interop.to_ris, interop.from_ris)


def test_csl_json_round_trip():
    work = interop.from_csl_json(CSL_SAMPLE)
    for key, value in EXPECTED_KEYS.items():
        assert work.key_fields()[key] == value, key
    assert work.authors == ['Vaswani, Ashish', 'Shazeer, Noam']
    out = interop.to_csl_json(work)
    assert out['type'] == 'article-journal'
    assert out['DOI'] == EXPECTED_KEYS['doi']
    assert out['author'] == CSL_SAMPLE['author']
    assert out['issued'] == {'date-parts': [[2017]]}
    assert_round_trip(work, interop.to_csl_json, interop.from_csl_json)


def test_crossref_round_trip():
    work = interop.from_crossref_json(CROSSREF_SAMPLE)
    for key, value in EXPECTED_KEYS.items():
        assert work.key_fields()[key] == value, key
    assert work.authors == ['Vaswani, Ashish', 'Shazeer, Noam']
    assert work.publisher == 'Curran Associates'
    # Crossref 只进不出：经 BibTeX 与 CSL-JSON 双向各走一次，关键字段保持
    assert_round_trip(work, interop.to_bibtex, interop.from_bibtex)
    assert_round_trip(work, interop.to_csl_json, interop.from_csl_json)


def test_openalex_round_trip():
    work = interop.from_openalex_json(OPENALEX_SAMPLE)
    for key, value in EXPECTED_KEYS.items():
        assert work.key_fields()[key] == value, key
    # OpenAlex 只有 display_name，无法可靠拆姓名，原样保留
    assert work.authors == ['Ashish Vaswani', 'Noam Shazeer']
    assert_round_trip(work, interop.to_ris, interop.from_ris)
    assert_round_trip(work, interop.to_csl_json, interop.from_csl_json)


def test_cross_format_chain():
    """BibTeX → Canonical → RIS → Canonical → CSL-JSON → Canonical 字段不漂。"""
    work = interop.from_bibtex(BIBTEX_SAMPLE)[0]
    via_ris = interop.from_ris(interop.to_ris(work))[0]
    via_csl = interop.from_csl_json(interop.to_csl_json(via_ris))
    assert via_csl.key_fields() == work.key_fields()


def test_doi_normalization():
    assert interop.normalize_doi('HTTPS://DOI.ORG/10.1/ABC') == '10.1/abc'
    assert interop.normalize_doi('doi: 10.1/ABC ') == '10.1/abc'
    assert interop.normalize_doi('') == ''
    assert interop.normalize_doi(None) == ''


def test_type_mapping_is_consistent():
    work = CanonicalWork(work_type='paper-conference', title='T', year=2020,
                         container='Proceedings of X')
    bib = interop.to_bibtex(work)
    assert bib.startswith('@inproceedings{')
    assert 'booktitle = {Proceedings of X}' in bib
    assert interop.from_bibtex(bib)[0].work_type == 'paper-conference'
    ris = interop.to_ris(work)
    assert ris.splitlines()[0] == 'TY  - CONF'
    assert interop.from_ris(ris)[0].work_type == 'paper-conference'


def test_multi_record_inputs():
    two = BIBTEX_SAMPLE + '\n\n' + BIBTEX_SAMPLE.replace('vaswani2017attention', 'x2017b')
    assert len(interop.from_bibtex(two)) == 2
    assert len(interop.from_ris(RIS_SAMPLE + '\n' + RIS_SAMPLE)) == 2


def test_make_citekey_shape():
    work = interop.from_bibtex(BIBTEX_SAMPLE)[0]
    assert interop.make_citekey(work) == 'vaswani2017attention'
    anon = CanonicalWork(title='Deep Work', year=None)
    assert interop.make_citekey(anon) == 'anonnddeep'


def test_no_third_party_imports():
    """interop.py 必须纯标准库：解析其 import 并逐个核对。"""
    import ast
    import sys
    tree = ast.parse((ROOT / 'skills' / 'literature-analysis' / 'scripts' / 'interop.py')
                     .read_text(encoding='utf-8'))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split('.')[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split('.')[0])
    names.discard('__future__')
    for name in names:
        assert name in sys.stdlib_module_names, f'非标准库依赖: {name}'

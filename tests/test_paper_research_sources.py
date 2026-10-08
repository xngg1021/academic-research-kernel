"""Offline acquisition controls; live publisher access is a separate acceptance."""
from __future__ import annotations

import json
from pathlib import Path
import zipfile
from urllib.error import HTTPError

import pytest

from test_paper_research_analysis import sources


def article_html(extra=""):
    return '<html><head><meta name="citation_title" content="Source controls"></head><body><h1>Source controls</h1><h2>Methods</h2><p>' + ("Randomized participants underwent the specified experiment and complete case analysis. " * 9) + '</p><h2>Results</h2><p>' + ("The reported results retained group labels and appropriate units. " * 9) + '</p>' + extra + '</body></html>'


def docx(path, table=False):
    body = '<w:p><w:r><w:t>Supplementary method description.</w:t></w:r></w:p>'
    if table:
        body += '<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Group</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Mean (ms)</w:t></w:r></w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>Treatment</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>12.5</w:t></w:r></w:p></w:tc></w:tr></w:tbl>'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' + body + '</w:body></w:document>')


def test_long_abstract_and_login_are_rejected(tmp_path):
    abstract = tmp_path / 'abstract.html'
    abstract.write_text('<h1>Abstract only</h1><h2>Abstract</h2><p>' + 'A search summary of findings without complete methods. '*30 + '</p>', 'utf-8')
    with pytest.raises(ValueError):
        sources.parse(abstract)
    login = tmp_path / 'login.html'
    login.write_text('<h1>Login</h1><p>Sign in to access</p>' + article_html(), 'utf-8')
    with pytest.raises(ValueError):
        sources.parse(login)


@pytest.mark.parametrize('text', ['<error><p>Access denied: cannot retrieve the requested article.</p></error>', '<article><front><abstract><p>Abstract only.</p></abstract></front></article>', '<article><body/></article>'])
def test_xml_error_and_abstract_are_not_fulltext(tmp_path, text):
    path = tmp_path / 'response.xml'
    path.write_text(text, 'utf-8')
    with pytest.raises(ValueError, match='no full text parsed'):
        sources.prepare(str(path), tmp_path / 'project')
    docs = json.loads((tmp_path / 'project' / 'documents.json').read_text('utf-8'))
    assert docs['documents'][0]['status'] == 'parse_failed'
    assert 'full-text body' in docs['documents'][0]['error']
    assert not docs['documents'][0]['segments']


def test_structured_body_and_html_table_headers(tmp_path):
    paper = tmp_path / 'body.html'
    paper.write_text(article_html('<table id="table-1"><tr><th>Group</th><th>Mean (ms)</th></tr><tr><td>Treatment</td><td>12.5</td></tr></table>'), 'utf-8')
    segments, title = sources.parse(paper)
    table = next(s for s in segments if s['table_id'] == 'table-1')
    assert title == 'Source controls'
    assert 'Group' in table['text'] and 'Mean (ms)' in table['text'] and '12.5' in table['text']
    assert '|' in table['text'] and ';' in table['text']


def test_xml_and_docx_table_relationships_retained(tmp_path):
    xml = tmp_path / 'article.xml'
    xml.write_text('<article><article-title>JATS source</article-title><body><sec><title>Results</title><table-wrap id="T1"><label>Table 1</label><table><thead><tr><th>Group</th><th>Mean (ms)</th></tr></thead><tbody><tr><td>Treatment</td><td>12.5</td></tr></tbody></table><table-wrap-foot><p>Values are means, not standard errors.</p></table-wrap-foot></table-wrap></sec></body></article>', 'utf-8')
    segments, _ = sources.parse(xml)
    table = next(s for s in segments if s['table_id'] == 'T1')
    assert '|' in table['text'] and ';' in table['text']
    assert 'Group' in table['text'] and 'Mean (ms)' in table['text'] and 'not standard errors' in table['text']
    office = tmp_path / 'table.docx'
    docx(office, table=True)
    segments, _ = sources.parse(office)
    table = next(s for s in segments if s['table_id'])
    assert 'Group' in table['text'] and 'Treatment' in table['text'] and 'Mean (ms)' in table['text']
    assert '|' in table['text'] and ';' in table['text']


def test_xlsx_preserves_header_cell_addresses_and_cached_formula(tmp_path):
    path = tmp_path / 'data.xlsx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('xl/workbook.xml', '<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Trial A" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', '<worksheet><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Group</t></is></c><c r="B1" t="inlineStr"><is><t>Mean (ms)</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>Treatment</t></is></c><c r="B2"><f>25/2</f><v>12.5</v></c></row></sheetData></worksheet>')
    segments, _ = sources.parse(path)
    assert 'A1=Group' in segments[0]['text'] and 'B1=Mean (ms)' in segments[0]['text']
    assert 'B2=12.5' in segments[1]['text'] and 'cached value only' in segments[1]['text']
    assert segments[1]['table_id'] == 'Trial A'


@pytest.mark.parametrize('name', ['../escape.xml', '/absolute.xml', 'C:/absolute.xml', '..\\escape.xml'])
def test_zip_escape_is_rejected(tmp_path, name):
    path = tmp_path / 'evil.docx'
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr(name, '<ignored/>')
    with pytest.raises(ValueError, match='escapes'):
        sources.safe_zip(path)


def test_zip_expansion_and_xml_entities_are_rejected(tmp_path, monkeypatch):
    path = tmp_path / 'big.docx'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('word/document.xml', 'a'*100)
    monkeypatch.setattr(sources, 'MAX_ZIP', 50)
    with pytest.raises(ValueError, match='expansion'):
        sources.safe_zip(path)
    with pytest.raises(ValueError, match='entity'):
        sources.xml_read(b'<!DOCTYPE article [<!ENTITY x "boom">]><article>&x;</article>')


def test_manifest_escape_and_missing_attachment_partial_success(tmp_path):
    package = tmp_path / 'input'
    package.mkdir()
    (package / 'body.txt').write_text('Methods and results source. '*25, 'utf-8')
    manifest = package / 'manifest.json'
    manifest.write_text(json.dumps({'files': [{'path': '../escape.txt'}]}), 'utf-8')
    with pytest.raises(ValueError, match='escapes'):
        sources.prepare(str(package), tmp_path / 'project-bad')
    manifest.write_text(json.dumps({'files': [{'path': 'body.txt', 'role': 'main'}, {'path': 'missing.pdf', 'role': 'supplement'}]}), 'utf-8')
    receipt = sources.prepare(str(package), tmp_path / 'project-good')
    assert receipt['parsed'] == 1 and receipt['failures']
    assert 'missing' in receipt['failures'][0]['reason']


def test_repeated_prepare_source_parser_and_snapshot_invalidation(tmp_path, monkeypatch):
    raw = tmp_path / 'paper.txt'
    raw.write_text('Methods and results source. '*25, 'utf-8')
    project = tmp_path / 'project'
    first = sources.prepare(str(raw), project)
    again = sources.prepare(str(raw), project)
    assert again['reused'] is True and first['fingerprint'] == again['fingerprint']
    saved = json.loads((project / 'documents.json').read_text('utf-8'))
    saved['documents'][0]['segments'][0]['text'] = 'fabricated snapshot text'
    (project / 'documents.json').write_text(json.dumps(saved), 'utf-8')
    with pytest.raises(ValueError, match='changed'):
        sources.verify(project)
    sources.prepare(str(raw), project)
    monkeypatch.setattr(sources, 'PARSER_VERSION', 'test-changed-parser')
    with pytest.raises(ValueError, match='changed'):
        sources.verify(project)
    changed = sources.prepare(str(raw), project)
    assert changed['changed'] is True
    raw.write_text(raw.read_text('utf-8') + ' Additional original result.', 'utf-8')
    changed = sources.prepare(str(raw), project)
    assert changed['changed'] is True


def test_bounded_fetch_respects_retry_after(tmp_path, monkeypatch):
    monkeypatch.setattr(sources, 'public_url', lambda url: url)
    sleeps, calls = [], []
    monkeypatch.setattr(sources.time, 'sleep', sleeps.append)
    class Response:
        url = 'https://publisher.example/paper.txt'
        headers = {'Content-Type': 'text/plain'}
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, limit): return b'paper source'
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                raise HTTPError(request.full_url, 429, 'backoff', {'Retry-After': '2'}, None)
            return Response()
    monkeypatch.setattr(sources, 'build_opener', lambda *args: Opener())
    final, _ = sources.fetch('https://publisher.example/paper.txt', tmp_path / 'download.txt')
    assert len(calls) == 2 and sleeps == [2] and final.endswith('paper.txt')


def test_extensionless_office_supplement_cache_and_failed_source_retry(tmp_path, monkeypatch):
    project = tmp_path / 'remote'
    project.mkdir()
    office = tmp_path / 'original.docx'
    docx(office)
    supplement_url = 'https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.test.s001&type=supplementary'
    counts = {}
    real_parse = sources.parse
    def fake_parse(path):
        if Path(path).suffix == '.pdf':
            return [sources.segment('pdf:page=1', 'Digital source controls. '*20, page_index=0)], ''
        return real_parse(path)
    monkeypatch.setattr(sources, 'parse', fake_parse)
    def fake_fetch(url, path):
        counts[url] = counts.get(url, 0) + 1
        if url == supplement_url:
            Path(path).write_bytes(office.read_bytes())
            return url, 'application/octet-stream'
        if 'type=printable' in url:
            if counts[url] == 1:
                raise OSError('synthetic temporary publisher failure')
            Path(path).write_bytes(b'%PDF-synthetic acquisition fixture')
            return url, 'application/pdf'
        if 'type=manuscript' in url:
            Path(path).write_text('<article><article-title>Source controls</article-title><body><p>Methods and full results are reported here.</p></body></article>', 'utf-8')
            return url, 'application/xml'
        Path(path).write_text(article_html(f'<a href="{supplement_url}">Supporting information</a>'), 'utf-8')
        return url, 'text/html'
    monkeypatch.setattr(sources, 'fetch', fake_fetch)
    first = sources.acquire('10.1371/journal.pone.test', project)
    assert first['failures'] and any(f['path'].endswith('.docx') for f in first['files'])
    second = sources.acquire('10.1371/journal.pone.test', project)
    assert counts[supplement_url] == 1
    assert any(f['path'].endswith('article.pdf') for f in second['files'])
    assert len({f['requested_url'] for f in second['files']}) == len(second['files'])


def test_generic_doi_full_html_without_pdf_metadata_is_body(tmp_path, monkeypatch):
    def fake_fetch(url, path):
        Path(path).write_text(article_html(), 'utf-8')
        return url, 'text/html'
    monkeypatch.setattr(sources, 'fetch', fake_fetch)
    receipt = sources.prepare('10.1000/synthetic-fulltext', tmp_path / 'generic-doi')
    assert receipt['parsed'] == 1
    docs = sources.verify(tmp_path / 'generic-doi')
    assert docs['documents'][0]['role'] == 'main'


def test_corrupt_supplement_is_parse_failed_while_main_survives(tmp_path):
    package = tmp_path / 'originals'
    package.mkdir()
    (package / 'body.txt').write_text('Explicit synthetic body control; methods and results are available. '*20, 'utf-8')
    (package / 'damaged-supplement.pdf').write_bytes(b'<html><p>Deliberately damaged supplementary file control.</p></html>')
    (package / 'manifest.json').write_text(json.dumps({'files': [{'path': 'body.txt', 'role': 'main'}, {'path': 'damaged-supplement.pdf', 'role': 'supplement'}]}), 'utf-8')
    project = tmp_path / 'corrupt-project'
    receipt = sources.prepare(str(package), project)
    assert receipt['parsed'] == 1
    docs = sources.verify(project)
    failed = next(d for d in docs['documents'] if d['role'] == 'supplement')
    assert failed['status'] == 'parse_failed' and 'signature' in failed['error']
    assert (project / failed['relative_path']).read_bytes().startswith(b'<html>')


def test_doi_redirect_full_html_is_not_discarded_as_metadata(tmp_path, monkeypatch):
    calls = []
    def fake_fetch(url, path):
        calls.append(url)
        Path(path).write_text(article_html(), 'utf-8')
        return 'https://publisher.example/articles/full', 'text/html'
    monkeypatch.setattr(sources, 'fetch', fake_fetch)
    first = sources.prepare('10.1234/full-html', tmp_path / 'project')
    assert first['parsed'] == 1
    again = sources.prepare('10.1234/full-html', tmp_path / 'project')
    assert again['reused'] and len(calls) == 1
    manifest = json.loads((tmp_path / 'project' / 'manifest.json').read_text('utf-8'))
    assert manifest['files'][0]['role'] == 'main'


def test_doi_relative_pdf_uses_final_publisher_url(tmp_path, monkeypatch):
    calls = []
    def fake_fetch(url, path):
        calls.append(url)
        if str(path).endswith('.pdf'):
            Path(path).write_bytes(b'%PDF-synthetic')
            return url, 'application/pdf'
        Path(path).write_text(article_html().replace('</head>', '<meta name="citation_pdf_url" content="paper.pdf"></head>'), 'utf-8')
        return 'https://publisher.example/articles/full', 'text/html'
    real_parse = sources.parse
    monkeypatch.setattr(sources, 'fetch', fake_fetch)
    monkeypatch.setattr(sources, 'parse', lambda p: ([sources.segment('pdf:page=1', 'Synthetic PDF text', page_index=0)], '') if Path(p).suffix == '.pdf' else real_parse(p))
    sources.prepare('10.1234/relative-pdf', tmp_path / 'project')
    assert calls == ['https://doi.org/10.1234/relative-pdf', 'https://publisher.example/articles/paper.pdf']


def test_pdf_optional_font_decoder_identity_invalidates_snapshot(tmp_path, monkeypatch):
    raw = tmp_path / 'paper.pdf'
    raw.write_bytes(b'%PDF-explicit synthetic parser-configuration fixture')
    monkeypatch.setattr(sources, 'parse', lambda path: ([sources.segment('pdf:page=1', 'Methods and results synthetic PDF fixture', page_index=0)], ''))
    original_version = sources.metadata.version
    def versions(name):
        if name == 'pypdf': return '6.19.0'
        if name == 'fonttools': return '4.66.1'
        return original_version(name)
    monkeypatch.setattr(sources.metadata, 'version', versions)
    project = tmp_path / 'project'
    sources.prepare(str(raw), project)
    assert sources.verify(project)['parser']['fonttools_version'] == '4.66.1'
    def missing_fonttools(name):
        if name == 'fonttools': raise sources.metadata.PackageNotFoundError(name)
        return versions(name)
    monkeypatch.setattr(sources.metadata, 'version', missing_fonttools)
    with pytest.raises(ValueError, match='changed'):
        sources.verify(project)
    changed = sources.prepare(str(raw), project)
    assert changed['changed'] is True
    assert sources.verify(project)['parser']['fonttools_version'] is None

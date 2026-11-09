"""Installed-artifact acceptance. Invoke using the fresh environment's Python -I.

No imports from the checkout. A different command may follow -- (e.g. uvx --from
an absolute wheel path academic-research-kernel). Every child uses an empty cwd.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

BASE_EXPECTED_TOOLS = {
    'research_artifact_validate', 'research_artifact_ingest', 'research_receipt_verify',
    'research_object_resolve', 'research_lineage_trace', 'claim_evidence_validate',
    'claim_evidence_trace', 'decision_ledger_validate', 'decision_trace',
    'academic_recompute_statistics', 'academic_check_percentage', 'academic_scfabric_hardware_probe',
}
EXTENDED_TOOLS_240 = {
    'academic_pre_submission_lint', 'academic_double_blind_sanitize', 'academic_table_forensics',
    'academic_meta_analyze', 'academic_verify_source', 'academic_openreview_audit',
}
EXPECTED_TOOLS = BASE_EXPECTED_TOOLS | EXTENDED_TOOLS_240


def _make_minimal_pdf(text_line: str) -> bytes:
    stream = f'BT /F1 11 Tf 36 720 Td ({text_line}) Tj ET'.encode('ascii')
    objs = [
        b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n',
        b'2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n',
        b'3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n',
        b'4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n',
        f'5 0 obj\n<< /Length {len(stream)} >>\nstream\n'.encode('ascii') + stream + b'\nendstream\nendobj\n',
    ]
    out = bytearray(b'%PDF-1.4\n')
    offsets = []
    for obj in objs:
        offsets.append(len(out))
        out.extend(obj)
    xref_pos = len(out)
    out.extend(f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode('ascii'))
    for off in offsets:
        out.extend(f'{off:010d} 00000 n \n'.encode('ascii'))
    out.extend(f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n'.encode('ascii'))
    return bytes(out)


def research_smoke(execute, directory, pdf_ready=False, expected_version='2.4.0'):
    """Exercise installed workflow on explicitly synthetic raw source material."""
    from importlib.resources import files
    root = Path(directory)
    skill = root / 'exported-skill'
    exported = json.loads(execute(['research', 'skill', '--output', str(skill)]))
    require(Path(exported['skill']).is_file(), 'installed skill export missing')
    package = files('academic_research_kernel')
    require((skill / 'SKILL.md').read_bytes() == package.joinpath('skills/paper-research/SKILL.md').read_bytes(),
            'exported skill differs from installed resource')
    for name in ('paper-extraction', 'paper-comparison', 'research-documents'):
        filename = name + '.schema.json'
        require((skill / 'references' / filename).read_bytes() == package.joinpath('schemas/' + filename).read_bytes(),
                'exported schema differs from installed resource: ' + filename)
    source = root / '材料 包'
    source.mkdir()
    numbers = {'count': 12, 'percent': 60.0, 'sample_size': 20, 't_stat': 2.0, 'df': 20,
               'mean1': 5.0, 'sd1': 2.0, 'n1': 30, 'mean2': 3.0, 'sd2': 2.0, 'n2': 30}
    text = ('<html><head><title>Explicit synthetic installation fixture</title>'
            '<meta name="citation_title" content="Explicit synthetic installation fixture">'
            '</head><body><h1>Installation fixture</h1>')
    text += ('<h2>Methods</h2><p>This explicitly synthetic document checks software installation. '
             'It describes a two-group fixture with integer sample sizes, sample means and sample standard deviations. '
             'The numeric values are deliberately small and independently interpretable. '
             'No human study was performed and these values are not attributed to a real paper. '
             'The local workflow must prepare stable source addresses, preserve original literals, call the existing '
             'statistical tools, validate and reload research state, render both report formats and reuse the saved '
             'snapshot on a repeated offline run.</p><h2>Results</h2>')
    text += ''.join(f'<p id="{name}">{name} = {value}</p>' for name, value in numbers.items()) + '</body></html>'
    (source / 'main.html').write_text(text, encoding='utf-8')
    project = root / '研究 project'
    prepared = json.loads(execute(['research', 'prepare', str(source), '--project', str(project)]))
    require(prepared['semantic_producer_required'] is True, 'CLI must disclose semantic producer requirement')
    documents = json.loads((project / 'documents.json').read_text(encoding='utf-8'))
    document = documents['documents'][0]
    context = dict.fromkeys(('group', 'timepoint', 'dataset', 'analysis_set', 'condition'))
    fields = []
    for name, value in numbers.items():
        segment = next(item for item in document['segments'] if item['locator'] == 'html:id=' + name)
        fields.append({'id': name, 'name': name, 'type': 'integer' if isinstance(value, int) else 'number',
                       'status': 'extracted', 'literal': str(value), 'value': value, 'unit': None,
                       'context': context.copy(), 'reason': None,
                       'sources': [{'document_id': document['document_id'], 'locator': segment['locator'], 'quote': segment['text']}]})
    statement = {'text': '明确标记的人工安装夹具；仅验证程序执行及资源分发。', 'field_ids': ['count']}
    candidate = {'schema_version': '1.0', 'project_fingerprint': documents['fingerprint'],
                 'paper': {'title': 'Explicit synthetic installation fixture', 'identifier': 'fixture:installation', 'version': '1'},
                 'producer': {'kind': 'agent', 'name': 'explicit synthetic installation test', 'model': None},
                 'search_scope': [document['document_id']], 'fields': fields,
                 'summary': {name: statement.copy() for name in ('objective', 'design', 'main_results', 'attention')},
                 'checks': [{'id': kind, 'kind': kind, 'inputs': {name: name for name in names},
                             'reported': 'percent' if kind == 'percentage' else None, 'tail': 'two' if kind == 't_p' else None, 'note': 'Synthetic installation fixture'}
                            for kind, names in [('percentage', ('count', 'percent', 'sample_size')),
                                                ('t_p', ('t_stat', 'df')),
                                                ('effect_size', ('mean1', 'sd1', 'n1', 'mean2', 'sd2', 'n2'))]]}
    candidate_path = root / 'fixture-candidate.json'
    candidate_path.write_text(json.dumps(candidate, ensure_ascii=False), encoding='utf-8')
    receipt = json.loads(execute(['research', 'finish', '--project', str(project), '--candidate', str(candidate_path)]))
    require(receipt['status'] == 'complete' and receipt['computed_checks'] == 3, 'installed research did not finish three numeric chains')
    require(receipt['ingestion']['round_trip'] == 'passed', 'installed research kernel reload failed')
    results = json.loads(Path(receipt['results']).read_text(encoding='utf-8'))
    require(results[0]['consistent'] is True and results[0]['recomputed'] == 60.0, 'installed percentage chain failed')
    require(0.05 < results[1]['recomputed'] < 0.07, 'installed t/p chain failed')
    require(results[2]['recomputed']['cohens_d'] == 1.0, 'installed effect-size chain failed')
    require(all(Path(receipt[key]).is_file() for key in ('report_markdown', 'report_html', 'extraction', 'results')),
            'installed research deliverables missing')
    replay = json.loads(execute(['research', 'replay', '--project', str(project)]))
    require(replay['reused'] is True and replay['analysis_fingerprint'] == receipt['analysis_fingerprint'],
            'identical installed snapshot replay did not reuse deterministic state')
    wf_state = json.loads((project / 'workflow-state.json').read_text(encoding='utf-8'))
    require(wf_state.get('stage') == 'complete' and wf_state.get('semantic_producer_required') is False,
            'workflow-state.json did not transition to complete')
    vs_out = json.loads(execute(['verify-source', 'https://doi.org/10.1038/nature14539', '--normalize-only']))
    require(vs_out.get('value') == '10.1038/nature14539', 'installed verify-source CLI failed')
    bib_file = root / 'fixture.bib'
    bib_file.write_text('@misc{ark2026,\n  title = {Synthetic Fixture},\n  author = {Doe, Jane},\n  year = {2026}\n}\n', encoding='utf-8')
    csl_out = json.loads(execute(['bibliography', '--from', 'bibtex', '--to', 'csl', '--input', str(bib_file)]))
    require(isinstance(csl_out, list) and csl_out[0].get('type') == 'document', 'installed bibliography CLI failed')
    meta_file = root / 'meta-studies.json'
    meta_file.write_text(json.dumps({'studies': [{'yi': 0.4, 'vi': 0.04}, {'yi': 0.5, 'vi': 0.05}, {'yi': 0.3, 'vi': 0.03}]}), encoding='utf-8')
    meta_out = json.loads(execute(['meta-analyze', '--input', str(meta_file)]))
    require(meta_out.get('study_count') == 3 and 'random_effects_dl' in meta_out, 'installed meta-analyze CLI failed')
    if tuple(map(int, expected_version.split('.'))) >= (2, 3, 0):
        require(package.joinpath('venue-specs.json').is_file(), 'installed venue-specs.json missing for >=2.3.0')
        vspecs = json.loads(package.joinpath('venue-specs.json').read_text(encoding='utf-8'))
        require('iclr' in vspecs.get('venues', {}), 'installed venue-specs.json missing iclr')
        vt_out = json.loads(execute(['venue-template', '--action', 'list-venues']))
        require('iclr' in vt_out.get('venues', {}), 'installed venue-template list-venues CLI failed')
        scaf_parent = root / 'scaffold-workspace'
        scaf_out = json.loads(execute([
            'venue-template', '--action', 'scaffold',
            '--workspace-dir', str(scaf_parent), '--slug', 'my-paper',
            '--venue', 'iclr', '--contribution-type', 'systems_architecture',
        ]))
        tex_dir = Path(scaf_out['manuscript_dir'])
        tex_file = tex_dir / 'main.tex'
        require(scaf_out.get('status') == 'scaffolded' and tex_file.is_file(), 'installed venue-template scaffold CLI failed')
        dbs_out = json.loads(execute(['sanitize-blind', '--target', str(tex_dir)]))
        require(dbs_out.get('status') == 'clean', 'installed sanitize-blind CLI failed')
        psl_out = json.loads(execute(['pre-submission-lint', '--tex', str(tex_file), '--venue', 'iclr', '--contribution-type', 'systems_architecture']))
        require(psl_out.get('passed') is True, 'installed pre-submission-lint CLI failed')
        rf_out = json.loads(execute(['repo-forensics', '--local-repo', str(tex_dir)]))
        require('first_party_core' in rf_out, 'installed repo-forensics CLI failed')
        tf_in = root / 'table-forensics.json'
        tf_in.write_text(json.dumps({'partition': {'total': 100, 'parts': [60, 40]}}), encoding='utf-8')
        tf_out = json.loads(execute(['table-forensics', '--input', str(tf_in)]))
        require(tf_out.get('consistent') is True, 'installed table-forensics CLI failed')
        r2l_in = root / 'table-receipt.json'
        r2l_in.write_text(json.dumps({
            'columns': ['Method', 'Score'],
            'rows': [['SynthA', 91.2], ['SynthB', 88.4]]
        }), encoding='utf-8')
        r2l_out = json.loads(execute(['receipt-to-latex', '--input', str(r2l_in), '--caption', 'Main Results', '--label', 'tab:main']))
        require('\\toprule' in r2l_out.get('latex', '') and 'Main Results' in r2l_out.get('latex', '') and 'tab:main' in r2l_out.get('latex', ''),
                'installed receipt-to-latex CLI failed')
        or_mirror = root / 'venue-mirror.json'
        or_mirror.write_text(json.dumps([
            {'forum_id': 'F1', 'title': 'Memory Agent Study', 'decision': 'Accept (Poster)', 'ratings': [8, 6, 8]},
            {'forum_id': 'F2', 'title': 'Vision Study', 'decision': 'Reject', 'ratings': [3, 5, 4]},
        ]), encoding='utf-8')
        or_out = json.loads(execute(['openreview-audit', '--venue-stats', str(or_mirror), '--topic-regex', 'memory|agent']))
        require(or_out.get('mode') == 'venue-stats' and or_out.get('total_submissions') == 2, 'installed openreview-audit venue-stats CLI failed')
        require('locate-oa' in execute(['locate-oa', '--help']), 'installed locate-oa CLI help failed')
    if tuple(map(int, expected_version.split('.'))) >= (2, 4, 0):
        # Verify newly wired 2.4.0+ CLI subcommands and bridges inside isolated installed environment
        ext_r2l = json.loads(execute(['receipt-to-latex', '--input', str(receipt['extraction']), '--from-research', 'extraction']))
        require('\\toprule' in ext_r2l.get('latex', '') and 'Field ID' in ext_r2l.get('latex', ''), 'installed receipt-to-latex --from-research extraction failed')
        res_r2l = json.loads(execute(['receipt-to-latex', '--input', str(receipt['results']), '--from-research', 'results']))
        require('\\toprule' in res_r2l.get('latex', '') and 'Check ID' in res_r2l.get('latex', ''), 'installed receipt-to-latex --from-research results failed')
        ks_path = Path(receipt['run_directory']) / 'kernel-state.json'
        ceg_anc = json.loads(execute(['venue-template', '--action', 'export-ceg-anchors', '--ceg', str(ks_path)]))
        require(ceg_anc.get('total_claims', 0) >= 1 and 'ceg_sha256' in ceg_anc, 'installed venue-template export-ceg-anchors failed')
        psl_style = json.loads(execute(['pre-submission-lint', '--tex', str(tex_file), '--venue', 'iclr', '--contribution-type', 'systems_architecture', '--check-academic-style']))
        require(psl_style.get('passed') is True and psl_style.get('style_check', {}).get('enabled') is True, 'installed pre-submission-lint --check-academic-style failed')
        lw_self = execute(['literature-watch', '--self-test'])
        require('self-test PASS' in lw_self, 'installed literature-watch --self-test failed')
        rw_self = execute(['retraction-watch', '--self-test'])
        require('self-test PASS' in rw_self, 'installed retraction-watch --self-test failed')
        rc_in = root / 'repro-checklist.json'
        rc_in.write_text(json.dumps({'paper': {'title': 'Synth Paper', 'doi': '10.1000/synth'}, 'stages': [{'id': 'identity', 'status': 'pass'}]}), encoding='utf-8')
        rc_out = json.loads(execute(['repro-checklist', str(rc_in)]))
        require(rc_out.get('kind') == 'ReproductionReceipt' and rc_out.get('status') == 'blocked', 'installed repro-checklist CLI failed')
        dd_in = root / 'dedup-works.json'
        dd_in.write_text(json.dumps([{'title': 'Work 1', 'doi': '10.1000/w1'}, {'title': 'Work 1 dup', 'doi': 'https://doi.org/10.1000/W1'}]), encoding='utf-8')
        dd_out = json.loads(execute(['bibliography', '--action', 'deduplicate', '--input', str(dd_in)]))
        require(dd_out.get('summary', {}).get('kept') == 1 and dd_out.get('summary', {}).get('removed') == 1, 'installed bibliography --action deduplicate failed')
    pdf_smoke = 'skipped_no_extra'
    if pdf_ready:
        pdf_file = root / 'synthetic-fixture.pdf'
        pdf_file.write_bytes(_make_minimal_pdf('Explicit synthetic PDF installation fixture for digital text extraction verification. ' * 4))
        pdf_project = root / 'pdf-project'
        pdf_prep = json.loads(execute(['research', 'prepare', str(pdf_file), '--project', str(pdf_project)]))
        require(pdf_prep['parsed'] == 1, 'installed PDF research prepare failed')
        pdf_docs = json.loads((pdf_project / 'documents.json').read_text(encoding='utf-8'))
        require(pdf_docs['documents'][0]['segments'][0]['locator'] == 'pdf:page=1', 'installed PDF page locator mismatch')
        pdf_smoke = 'passed'
    return {'skill_export': 'passed', 'source_path': 'Chinese and spaces', 'computed_checks': 3,
            'kernel_round_trip': 'passed', 'offline_snapshot_replay': 'passed', 'pdf_smoke': pdf_smoke,
            'fixture': 'explicitly synthetic'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command=None, expected_version=None, require_pdf=False):
    from academic_research_kernel import __version__, __file__ as package_file
    from academic_research_kernel.ingestion import ArtifactEnvelope
    expected_version = expected_version or __version__
    require(__version__ == expected_version, ('installed version mismatch', __version__, expected_version))
    checkout = Path(__file__).resolve().parents[1]
    require(Path(package_file).resolve().is_relative_to(Path(sys.prefix).resolve()), 'package must come from installed environment')
    require('site-packages' in Path(package_file).parts, 'installed import must use site-packages')
    require(str(checkout) not in sys.path, 'checkout must not be on the import path')
    executable = Path(sys.executable).parent / ('academic-research-kernel.exe' if os.name == 'nt' else 'academic-research-kernel')
    command = command or [str(executable)]
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    # A set credential should only be reported as configured, never echoed.
    env['OPENALEX_API_KEY'] = 'test-doctor-private-value'
    research = None
    with tempfile.TemporaryDirectory(prefix='ark-installed-') as directory:
        def execute(args, input=None):
            result = subprocess.run(command + args, input=input, cwd=directory, env=env,
                                    text=True, encoding='utf-8', capture_output=True, timeout=180)
            require(result.returncode == 0, result.stderr)
            require('test-doctor-private-value' not in result.stdout + result.stderr, 'doctor exposed a configured credential')
            return result.stdout
        ver_tuple = tuple(map(int, expected_version.split('.')))
        expected_tools = BASE_EXPECTED_TOOLS | (EXTENDED_TOOLS_240 if ver_tuple >= (2, 4, 0) else set())
        expected_tool_count = len(expected_tools)
        require(execute(['--version']).strip() == expected_version, 'command version mismatch')
        doctor = json.loads(execute(['doctor', '--json']))
        require(doctor['status'] == 'ok', doctor)
        require('site-packages' in Path(doctor['package_location']).parts, 'command must use an installed package')
        require(doctor['mcp']['tool_count'] == expected_tool_count, 'doctor tool inventory mismatch')
        require(doctor['external_services']['OPENALEX_API_KEY'] == 'configured', 'doctor configuration status mismatch')
        envelope = ArtifactEnvelope.create(payload={
            'schema_version': '1.0', 'query': 'distribution smoke', 'identifiers': {},
            'sources': [], 'claims': [], 'generated_at': '2026-09-21T00:00:00Z',
        }, producer_skill='academic-source-verification', producer_version='1.2.0',
            artifact_kind='evidence_receipt', payload_schema='evidence-receipt-1.0').to_dict()
        calls = [
            ('research_object_resolve', {'records': [{'doi': '10.1000/smoke'}, {'doi': 'https://doi.org/10.1000/smoke'}]}),
            ('academic_scfabric_hardware_probe', {}),
            ('academic_check_percentage', {'count': 10, 'percent': 50.0, 'sample_size': 20}),
            ('academic_recompute_statistics', {'t_stat': 2.0, 'df': 20, 'mean1': 5, 'sd1': 2, 'n1': 30, 'mean2': 3, 'sd2': 2, 'n2': 30}),
            ('research_artifact_validate', {'envelope': envelope}),
            ('research_artifact_ingest', {'envelope': envelope}),
            ('academic_recompute_statistics', {'t_stat': 1, 'df': 30, 'p_value': .00001, 'p_value_literal': '1.0e-5'}),
            ('academic_recompute_statistics', {'t_stat': 1, 'df': 30, 'p_value': .3253}),
        ]
        if tuple(map(int, expected_version.split('.'))) >= (2, 3, 0):
            calls.append(('academic_recompute_statistics', {
                'partition_total': 100, 'partition_parts': [40, 60],
                'ablation_matrix': [[0.80, 0.72], [0.85, 0.79], [0.90, 0.81]],
                'bandwidth_item_count': 10000, 'bandwidth_vector_dim': 128,
                'bandwidth_reported_size_mb': 12.0, 'bandwidth_reported_latency_us': 500.0,
            }))
        if tuple(map(int, expected_version.split('.'))) >= (2, 4, 0):
            calls.extend([
                ('academic_table_forensics', {'partition': {'total': 100, 'parts': [60, 40]}}),
                ('academic_meta_analyze', {'studies': [{'yi': 0.4, 'vi': 0.04}, {'yi': 0.5, 'vi': 0.05}, {'yi': 0.3, 'vi': 0.03}]}),
                ('academic_verify_source', {'identifier': 'https://doi.org/10.1038/nature14539', 'normalize_only': True}),
                ('academic_openreview_audit', {'venue_records': [{'forum_id': 'F1', 'title': 'Agent Study', 'decision': 'Accept (Poster)', 'ratings': [8, 6]}]}),
            ])
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        for i, (name, arguments) in enumerate(calls, 3):
            messages.append({'jsonrpc': '2.0', 'id': i, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})
        messages.append({'jsonrpc': '2.0', 'id': 99, 'method': 'tools/call', 'params': {'name': 'academic_check_percentage', 'arguments': {'count': 'bad'}}})
        messages.append({'jsonrpc': '2.0', 'id': 100, 'method': 'tools/call', 'params': {'name': 'academic_recompute_statistics', 'arguments': {'t_stat': 1}}})
        messages.extend([{'jsonrpc': '2.0', 'method': 'notifications/cancelled', 'params': {'requestId': 99}},
                         {'jsonrpc': '2.0', 'id': 'installed-ping', 'method': 'ping'}])
        output = execute(['mcp'], '\n'.join(json.dumps(m) for m in messages) + '\n')
        replies = [json.loads(line) for line in output.splitlines()]
        require(len(replies) == len(messages) - 2, 'missing replies or non-silent notifications')
        require(replies[0]['result']['serverInfo'] == {'name': 'academic-research-kernel', 'version': expected_version}, 'MCP server version mismatch')
        require(replies[0]['result']['protocolVersion'] == '2024-11-05', 'MCP protocol mismatch')
        require({t['name'] for t in replies[1]['result']['tools']} == expected_tools, 'MCP tool inventory mismatch')
        data = {}
        successful_replies = replies[2:2 + len(calls)]
        for response, (name, _) in zip(successful_replies, calls):
            require(not response['result']['isError'], response)
            value = json.loads(response['result']['content'][0]['text'])
            require('error' not in value, value)
            data.setdefault(name, value)
        p_idx = 6
        require(json.loads(successful_replies[p_idx]['result']['content'][0]['text'])['p_match']['consistent'] is False, 'small reported p must be inconsistent')
        require(json.loads(successful_replies[p_idx + 1]['result']['content'][0]['text'])['p_match']['consistent'] is True, 'ordinary reported p must be consistent')
        if tuple(map(int, expected_version.split('.'))) >= (2, 3, 0):
            v230_mcp = json.loads(successful_replies[p_idx + 2]['result']['content'][0]['text'])
            require(v230_mcp.get('partition_conservation', {}).get('consistent') is True, 'MCP partition_conservation failed')
            require(v230_mcp.get('ablation_delta_regularity', {}).get('consistent') is True, 'MCP ablation_delta_regularity failed')
            require(v230_mcp.get('storage_bandwidth_bounds', {}).get('consistent') is True, 'MCP storage_bandwidth_bounds failed')
        require(data['academic_check_percentage']['consistent'] is True, 'percentage positive control failed')
        require(0.05 < data['academic_recompute_statistics']['recomputed_p'] < 0.07, 't recomputation failed')
        require(data['academic_recompute_statistics']['cohens_d'] == 1.0, 'effect size control failed')
        require(data['research_artifact_validate']['valid'] is True, 'artifact validation failed')
        require(data['research_artifact_ingest']['success'] is True, 'artifact ingestion failed')
        require(data['academic_scfabric_hardware_probe']['python'], 'hardware probe missing interpreter')
        by_id = {reply['id']: reply for reply in replies}
        require(by_id[99]['result']['isError'] is True, 'invalid percentage must be a tool error')
        require(json.loads(by_id[99]['result']['content'][0]['text'])['details'], 'invalid input missing details')
        require(by_id[100]['result']['isError'] is True, 'incomplete statistics must be a tool error')
        require(json.loads(by_id[100]['result']['content'][0]['text'])['status'] == 'failed', 'incomplete statistics failure state missing')
        require(replies[-1] == {'jsonrpc': '2.0', 'id': 'installed-ping', 'result': {}}, 'ping response mismatch')
        if tuple(map(int, expected_version.split('.'))) >= (2, 1, 0):
            pdf_ready = bool(doctor.get('research', {}).get('pdf_ready'))
            if require_pdf:
                require(pdf_ready, 'require-pdf set but doctor reported pdf_ready=false')
            research = research_smoke(execute, directory, pdf_ready=pdf_ready, expected_version=expected_version)
            if require_pdf:
                require(research.get('pdf_smoke') == 'passed', 'require-pdf set but pdf_smoke did not pass')
    print(json.dumps({'installed_e2e': 'PASS', 'version': __version__, 'tools': expected_tool_count,
                      'calls': [name for name, _ in calls], 'clean_shutdown': True,
                      'arbitrary_cwd': True, 'source_independent': True, 'import_path': str(package_file),
                      'command_package_location': doctor['package_location'],
                      'command_python': doctor['python']['executable'], 'research': research}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-version', help='Independently expected release version')
    parser.add_argument('--require-pdf', action='store_true', help='Require [research] PDF extraction smoke to execute and pass')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == '--' else args.command
    run(command or None, expected_version=args.expected_version, require_pdf=args.require_pdf)

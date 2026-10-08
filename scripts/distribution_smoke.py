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

EXPECTED_TOOLS = {
    'research_artifact_validate', 'research_artifact_ingest', 'research_receipt_verify',
    'research_object_resolve', 'research_lineage_trace', 'claim_evidence_validate',
    'claim_evidence_trace', 'decision_ledger_validate', 'decision_trace',
    'academic_recompute_statistics', 'academic_check_percentage', 'academic_scfabric_hardware_probe',
}


def research_smoke(execute, directory):
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
    return {'skill_export': 'passed', 'source_path': 'Chinese and spaces', 'computed_checks': 3,
            'kernel_round_trip': 'passed', 'offline_snapshot_replay': 'passed', 'fixture': 'explicitly synthetic'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(command=None, expected_version=None):
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
        require(execute(['--version']).strip() == expected_version, 'command version mismatch')
        doctor = json.loads(execute(['doctor', '--json']))
        require(doctor['status'] == 'ok', doctor)
        require('site-packages' in Path(doctor['package_location']).parts, 'command must use an installed package')
        require(doctor['mcp']['tool_count'] == 12, 'doctor tool inventory mismatch')
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
        require({t['name'] for t in replies[1]['result']['tools']} == EXPECTED_TOOLS, 'MCP tool inventory mismatch')
        data = {}
        successful_replies = replies[2:2 + len(calls)]
        for response, (name, _) in zip(successful_replies, calls):
            require(not response['result']['isError'], response)
            value = json.loads(response['result']['content'][0]['text'])
            require('error' not in value, value)
            data.setdefault(name, value)
        require(json.loads(successful_replies[-2]['result']['content'][0]['text'])['p_match']['consistent'] is False, 'small reported p must be inconsistent')
        require(json.loads(successful_replies[-1]['result']['content'][0]['text'])['p_match']['consistent'] is True, 'ordinary reported p must be consistent')
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
            research = research_smoke(execute, directory)
    print(json.dumps({'installed_e2e': 'PASS', 'version': __version__, 'tools': 12,
                      'calls': [name for name, _ in calls], 'clean_shutdown': True,
                      'arbitrary_cwd': True, 'source_independent': True, 'import_path': str(package_file),
                      'command_package_location': doctor['package_location'],
                      'command_python': doctor['python']['executable'], 'research': research}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-version', help='Independently expected release version')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == '--' else args.command
    run(command or None, expected_version=args.expected_version)

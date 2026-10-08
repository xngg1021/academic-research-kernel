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
    print(json.dumps({'installed_e2e': 'PASS', 'version': __version__, 'tools': 12,
                      'calls': [name for name, _ in calls], 'clean_shutdown': True,
                      'arbitrary_cwd': True, 'source_independent': True, 'import_path': str(package_file),
                      'command_package_location': doctor['package_location'],
                      'command_python': doctor['python']['executable']}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-version', help='Independently expected release version')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command and args.command[0] == '--' else args.command
    run(command or None, expected_version=args.expected_version)

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


def run(command=None):
    from academic_research_kernel import __version__, __file__ as package_file
    from academic_research_kernel.ingestion import ArtifactEnvelope
    assert __version__ == '2.0.0'
    checkout = Path(__file__).resolve().parents[1]
    assert Path(package_file).resolve().is_relative_to(Path(sys.prefix).resolve()), 'package must come from installed environment'
    assert 'site-packages' in Path(package_file).parts
    assert str(checkout) not in sys.path
    executable = Path(sys.executable).parent / ('academic-research-kernel.exe' if os.name == 'nt' else 'academic-research-kernel')
    command = command or [str(executable)]
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    # A set credential should only be reported as configured, never echoed.
    env['OPENALEX_API_KEY'] = 'test-doctor-private-value'
    with tempfile.TemporaryDirectory(prefix='ark-installed-') as directory:
        def execute(args, input=None):
            result = subprocess.run(command + args, input=input, cwd=directory, env=env,
                                    text=True, encoding='utf-8', capture_output=True, timeout=180)
            assert result.returncode == 0, result.stderr
            assert 'test-doctor-private-value' not in result.stdout + result.stderr
            return result.stdout
        assert execute(['--version']).strip() == '2.0.0'
        doctor = json.loads(execute(['doctor', '--json']))
        assert doctor['status'] == 'ok', doctor
        assert doctor['mcp']['tool_count'] == 12
        assert doctor['external_services']['OPENALEX_API_KEY'] == 'configured'
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
        ]
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}]
        for i, (name, arguments) in enumerate(calls, 3):
            messages.append({'jsonrpc': '2.0', 'id': i, 'method': 'tools/call', 'params': {'name': name, 'arguments': arguments}})
        messages.append({'jsonrpc': '2.0', 'id': 99, 'method': 'tools/call', 'params': {'name': 'academic_check_percentage', 'arguments': {'count': 'bad'}}})
        output = execute(['mcp'], '\n'.join(json.dumps(m) for m in messages) + '\n')
        replies = [json.loads(line) for line in output.splitlines()]
        assert len(replies) == len(messages) - 1
        assert replies[0]['result']['serverInfo'] == {'name': 'academic-research-kernel', 'version': '2.0.0'}
        assert replies[0]['result']['protocolVersion'] == '2024-11-05'
        assert {t['name'] for t in replies[1]['result']['tools']} == EXPECTED_TOOLS
        data = {}
        for response, (name, _) in zip(replies[2:-1], calls):
            assert not response['result']['isError'], response
            data[name] = json.loads(response['result']['content'][0]['text'])
            assert 'error' not in data[name], data[name]
        assert data['academic_check_percentage']['consistent'] is True
        assert 0.05 < data['academic_recompute_statistics']['recomputed_p'] < 0.07
        assert data['academic_recompute_statistics']['cohens_d'] == 1.0
        assert data['research_artifact_validate']['valid'] is True
        assert data['research_artifact_ingest']['success'] is True
        assert data['academic_scfabric_hardware_probe']['python']
        assert replies[-1]['result']['isError'] is True
        assert json.loads(replies[-1]['result']['content'][0]['text'])['details']
    print(json.dumps({'installed_e2e': 'PASS', 'version': __version__, 'tools': 12,
                      'calls': [name for name, _ in calls], 'clean_shutdown': True,
                      'arbitrary_cwd': True, 'source_independent': True}))


if __name__ == '__main__':
    args = sys.argv[1:]
    run(args[1:] if args and args[0] == '--' else args or None)

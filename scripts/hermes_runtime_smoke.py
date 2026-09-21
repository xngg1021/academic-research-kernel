"""Exercise the real Hermes Agent Plugins loader and translated MCP command.

Run with the pinned or current Hermes installed. No LLM or scholarly APIs used.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile


def main():
    from hermes_cli import agent_plugins
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='ark-hermes-') as directory:
        data = Path(directory)
        diagnostics = []
        manifest, errors = agent_plugins._validate_manifest(root)
        assert manifest and not errors, errors
        assert len(agent_plugins._discover_skills(root, diagnostics)) == 13
        config = agent_plugins._discover_mcp(root, data, diagnostics, create_data=True)['academic-skills']
        assert not diagnostics, diagnostics
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
        env.update(config['env'])
        command = [config['command'], *config['args']]
        assert command[-1] == 'mcp'
        doctor = subprocess.run(command[:-1] + ['doctor', '--json'], cwd=config['cwd'], env=env,
                                text=True, encoding='utf-8', capture_output=True, timeout=240)
        assert doctor.returncode == 0, doctor.stderr
        report = json.loads(doctor.stdout)
        assert report['status'] == 'ok' and report['mcp']['tool_count'] == 12, report
        assert Path(report['python']['executable']).is_relative_to(data)
        assert report['python']['version'].startswith('3.12.')
        messages = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
                        'name': 'academic_check_percentage', 'arguments': {'count': 10, 'percent': 50, 'sample_size': 20}}}]
        result = subprocess.run(command, cwd=config['cwd'], env=env, input='\n'.join(json.dumps(m) for m in messages)+'\n',
                                text=True, encoding='utf-8', capture_output=True, timeout=180)
        assert result.returncode == 0, result.stderr
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        assert replies[0]['result']['serverInfo']['version'] == '2.0.0'
        assert len(replies[1]['result']['tools']) == 12
        assert not replies[2]['result']['isError']
        assert json.loads(replies[2]['result']['content'][0]['text'])['consistent'] is True
    print('PASS Hermes loader -> locked isolated Python 3.12 -> 12 MCP tools -> deterministic dispatch')


if __name__ == '__main__':
    main()

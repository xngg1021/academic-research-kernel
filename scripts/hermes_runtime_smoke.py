"""Exercise the real Hermes Agent Plugins loader and translated MCP command.

Run with the pinned or current Hermes installed. No LLM or scholarly APIs used.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from _version import __version__
from distribution_smoke import EXPECTED_TOOLS


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Persist structured runtime smoke receipt')
    args = parser.parse_args(argv)
    from hermes_cli import agent_plugins
    root = Path(__file__).resolve().parents[1]
    out_payload = {'status': 'failed', 'version': __version__}
    try:
        expected_skills = {p.parent.name for p in (root / 'skills').glob('*/SKILL.md')}
        require(len(expected_skills) == 14, f'expected 14 skills, found {len(expected_skills)}')
        with tempfile.TemporaryDirectory(prefix='ark-hermes-') as directory:
            data = Path(directory)
            diagnostics = []
            manifest, errors = agent_plugins._validate_manifest(root)
            require(manifest and not errors, f'manifest validation failed: {errors}')
            discovered_skills = agent_plugins._discover_skills(root, diagnostics)
            require({s.name for s in discovered_skills} == expected_skills, 'discovered skill names mismatch')
            config = agent_plugins._discover_mcp(root, data, diagnostics, create_data=True)['academic-skills']
            require(not diagnostics, f'plugin diagnostics not empty: {diagnostics}')
            env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
            env.update(config['env'])
            command = [config['command'], *config['args']]
            require(command[-1] == 'mcp', f'unexpected MCP entrypoint: {command}')
            doctor = subprocess.run(command[:-1] + ['doctor', '--json'], cwd=config['cwd'], env=env,
                                    text=True, encoding='utf-8', capture_output=True, timeout=240)
            require(doctor.returncode == 0, doctor.stderr)
            report = json.loads(doctor.stdout)
            require(report['status'] == 'ok' and report['mcp']['tool_count'] == 18, report)
            require(Path(report['python']['executable']).is_relative_to(data), 'runtime python outside plugin data root')
            require(report['python']['version'].startswith('3.12.'), f'expected Python 3.12, got {report["python"]["version"]}')
            messages = [
                {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'},
                {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {
                    'name': 'academic_check_percentage', 'arguments': {'count': 10, 'percent': 50, 'sample_size': 20}}},
                {'jsonrpc': '2.0', 'id': 4, 'method': 'tools/call', 'params': {
                    'name': 'academic_table_forensics', 'arguments': {'partition': {'total': 100, 'parts': [60, 40]}}}},
            ]
            result = subprocess.run(command, cwd=config['cwd'], env=env, input='\n'.join(json.dumps(m) for m in messages) + '\n',
                                    text=True, encoding='utf-8', capture_output=True, timeout=180)
            require(result.returncode == 0, result.stderr)
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            require(replies[0]['result']['serverInfo']['version'] == __version__, 'MCP server version mismatch')
            tool_names = {t['name'] for t in replies[1]['result']['tools']}
            require(tool_names == EXPECTED_TOOLS, f'MCP tool inventory mismatch: {sorted(tool_names ^ EXPECTED_TOOLS)}')
            require(not replies[2]['result']['isError'], replies[2])
            require(json.loads(replies[2]['result']['content'][0]['text'])['consistent'] is True, 'percentage check failed')
            require(not replies[3]['result']['isError'], replies[3])
            require(json.loads(replies[3]['result']['content'][0]['text'])['consistent'] is True, 'table forensics check failed')
            out_payload = {
                'status': 'passed',
                'version': __version__,
                'skills_count': len(discovered_skills),
                'mcp_tool_count': len(tool_names),
                'python_version': report['python']['version'],
            }
    except Exception as exc:
        out_payload['error'] = str(exc)
        raise
    finally:
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(out_payload, indent=2) + '\n', encoding='utf-8')
    print('PASS Hermes loader -> locked isolated Python 3.12 -> 18 MCP tools -> deterministic dispatch')


if __name__ == '__main__':
    main()

"""Offline regressions for live monitoring, including real subprocess paths."""
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'


def load_script(name):
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.pop(0)


external = load_script('verify_external_apis')
status = load_script('monitoring_status')


def skill_fence(root, name, code):
    path = root / 'skills' / name / 'SKILL.md'
    path.parent.mkdir(parents=True)
    path.write_text(f'```python\n# external-test: true\n{code}\n```\n', encoding='utf-8')
    return path


@pytest.mark.parametrize(('exception', 'expected'), [
    ("from urllib.error import HTTPError; raise HTTPError('https://test.invalid', 429, 'quota', {}, None)", 'degraded'),
    ("from urllib.error import URLError; raise URLError('transport')", 'degraded'),
    ("raise TimeoutError('external timeout')", 'degraded'),
    ("from http.client import RemoteDisconnected; raise RemoteDisconnected('closed')", 'degraded'),
    ("from ssl import SSLCertVerificationError; raise SSLCertVerificationError('certificate unavailable')", 'degraded'),
    ("from http.client import IncompleteRead; raise IncompleteRead(b'')", 'degraded'),
    ("from urllib.error import HTTPError; raise HTTPError('https://test.invalid', 400, 'bad request', {}, None)", 'failed'),
    ("assert False, 'URLError and HTTP Error 429 appear in an assertion'", 'failed'),
    ("raise KeyError('missing schema field')", 'failed'),
    ("print('completed')", 'healthy'),
    ("print('SKIP Unpaywall: configuration absent')", 'degraded'),
])
def test_external_real_fence_execution_and_terminal_classification(tmp_path, exception, expected):
    # These raise local external-boundary fixtures; no network is contacted.
    skill_fence(tmp_path, 'test-external', exception)
    report = external.check_external_apis(tmp_path)
    assert report['status'] == expected
    assert report['results'][0]['status'] == expected
    assert 'test.invalid' not in json.dumps(report)


def test_external_timeout_start_failure_and_invalid_repository_fence(tmp_path, monkeypatch):
    path = skill_fence(tmp_path, 'test-external', 'print(1)')
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired('external-fixture', 180)
    monkeypatch.setattr(external, 'run_fence', timeout)
    assert external.check_external_apis(tmp_path)['status'] == 'degraded'
    def cannot_start(*args, **kwargs):
        raise OSError('cannot start python')
    monkeypatch.setattr(external, 'run_fence', cannot_start)
    assert external.check_external_apis(tmp_path)['status'] == 'failed'
    path.write_text('```python\nprint(1)\n```\n', encoding='utf-8')
    assert external.check_external_apis(tmp_path)['status'] == 'failed'


def test_external_failure_wins_over_degraded_and_empty_is_failed(tmp_path):
    assert external.check_external_apis(tmp_path)['status'] == 'failed'
    skill_fence(tmp_path, 'a-transport', "raise TimeoutError('timeout')")
    skill_fence(tmp_path, 'b-contract', 'assert False')
    report = external.check_external_apis(tmp_path)
    assert report['status'] == 'failed'
    assert {item['status'] for item in report['results']} == {'degraded', 'failed'}


@pytest.mark.parametrize(('state', 'code'), [('healthy', 0), ('degraded', 2), ('failed', 1)])
def test_report_persistence_summary_and_exit_codes(tmp_path, monkeypatch, capsys, state, code):
    summary = tmp_path / 'summary.md'
    output = tmp_path / 'monitoring' / 'status.json'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    report = status.make_report('hermes-latest-upstream', [{'name': 'loader', 'status': state}], hermes_sha='a' * 40)
    assert status.emit_report(report, output) == code
    assert json.loads(output.read_text(encoding='utf-8')) == report
    assert json.loads(capsys.readouterr().out) == report
    assert f'hermes-latest-upstream: {state}' in summary.read_text(encoding='utf-8')
    assert 'a' * 40 in summary.read_text(encoding='utf-8')


def test_external_main_persists_aggregate_state(tmp_path, monkeypatch):
    skill_fence(tmp_path, 'external-fixture', 'print(1)')
    check = external.check_external_apis
    monkeypatch.setattr(external, 'check_external_apis', lambda: check(tmp_path))
    output = tmp_path / 'status.json'
    summary = tmp_path / 'summary.md'
    assert external.main(['--output', str(output), '--summary', str(summary)]) == 0
    assert json.loads(output.read_text(encoding='utf-8'))['status'] == 'healthy'
    assert 'external-apis: healthy' in summary.read_text(encoding='utf-8')


def upstream_fixture(root, broken=False):
    package = root / 'hermes_cli'
    package.mkdir(parents=True)
    (package / '__init__.py').write_text('', encoding='utf-8')
    (package / 'agent_plugins.py').write_text(
        'from types import SimpleNamespace\n'
        'def _validate_manifest(root): return ({"name": "test-fixture"}, [])\n'
        'def _discover_skills(root, diagnostics):\n'
        + ('    return []\n' if broken else
           '    return tuple(SimpleNamespace(name=p.parent.name) for p in (root / "skills").glob("*/SKILL.md"))\n')
        + 'def _discover_mcp(root, data, diagnostics, create_data=False):\n'
        '    return {"academic-skills": {"args": ["mcp"]}}\n', encoding='utf-8')
    subprocess.run(['git', 'init', str(root)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test Fixture', '-c',
                    'user.email=test@example.invalid', 'commit', '-m', 'external loader fixture'],
                   check=True, capture_output=True)
    return subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()


@pytest.mark.parametrize(('broken', 'expected', 'code'), [(False, 'healthy', 0), (True, 'failed', 1)])
def test_canary_real_cli_records_actual_checkout_sha(tmp_path, broken, expected, code):
    # The external Hermes surface is fixture code. The canary, git revision
    # lookup, import origin check, validation and report writer run unchanged.
    upstream = tmp_path / 'upstream'
    sha = upstream_fixture(upstream, broken)
    output = tmp_path / 'hermes.json'
    summary = tmp_path / 'summary.md'
    process = subprocess.run([sys.executable, str(SCRIPTS / 'hermes_compatibility_canary.py'),
                              '--upstream', str(upstream), '--channel', 'pinned', '--expected-sha', sha,
                              '--output', str(output)], capture_output=True, text=True,
                             env={**os.environ, 'GITHUB_STEP_SUMMARY': str(summary)}, timeout=30)
    assert process.returncode == code, process.stderr
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['status'] == expected and report['hermes_sha'] == sha
    assert report['channel'] == 'pinned'
    assert sha in summary.read_text(encoding='utf-8')


@pytest.mark.parametrize('outcome', ['failure', 'skipped', 'cancelled'])
def test_canary_checkout_unavailable_never_claims_success(tmp_path, outcome):
    output = tmp_path / 'hermes.json'
    process = subprocess.run([sys.executable, str(SCRIPTS / 'hermes_compatibility_canary.py'),
                              '--upstream', str(tmp_path / 'absent'), '--channel', 'latest-upstream',
                              '--checkout-outcome', outcome, '--output', str(output)],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 2, process.stderr
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['status'] == 'degraded' and report['hermes_sha'] is None
    assert 'not tested' in report['results'][0]['reason']


def test_canary_rejects_wrong_pin(tmp_path):
    upstream = tmp_path / 'upstream'
    sha = upstream_fixture(upstream)
    output = tmp_path / 'hermes.json'
    process = subprocess.run([sys.executable, str(SCRIPTS / 'hermes_compatibility_canary.py'),
                              '--upstream', str(upstream), '--channel', 'pinned',
                              '--expected-sha', '0' * 40, '--output', str(output)],
                             capture_output=True, text=True, timeout=30)
    assert process.returncode == 1
    report = json.loads(output.read_text(encoding='utf-8'))
    assert report['status'] == 'failed' and report['hermes_sha'] == sha


def evaluate_condition(expression, event, action='', draft=True, labels=(), ref='refs/heads/main'):
    """Evaluate the actual workflow's limited boolean trigger expression."""
    values = {'github.event_name': event, 'github.event.action': action,
              'github.event.pull_request.draft': draft,
              'github.event.pull_request.labels.*.name': list(labels), 'github.ref': ref}
    for name in sorted(values, key=len, reverse=True):
        expression = expression.replace(name, repr(values[name]))
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    expression = re.sub(r'\bfalse\b', 'False', expression)
    expression = re.sub(r'\btrue\b', 'True', expression)
    return eval(expression, {'__builtins__': {}, 'contains': lambda values, item: item in values})


@pytest.mark.parametrize(('event', 'action', 'draft', 'labels', 'expected'), [
    ('schedule', '', True, [], True),
    ('workflow_dispatch', '', True, [], True),
    ('push', '', True, [], True),
    ('pull_request', 'opened', True, [], False),
    ('pull_request', 'labeled', True, ['full-ci'], True),
    ('pull_request', 'synchronize', True, ['full-ci'], True),
    ('pull_request', 'ready_for_review', False, ['full-ci'], False),
    ('pull_request', 'opened', False, [], True),
])
def test_actual_workflow_canary_trigger_conditions(event, action, draft, labels, expected):
    workflow = yaml.load((ROOT / '.github/workflows/qa.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    assert 'schedule' in workflow['on']
    assert evaluate_condition(workflow['jobs']['upstream-canary']['if'], event, action, draft, labels) is expected
    if event == 'schedule':
        for job in ('checks', 'tap-lifecycle', 'upstream-runtime', 'distribution-build'):
            assert not evaluate_condition(workflow['jobs'][job]['if'], event)


def test_workflows_run_canary_and_persist_separate_reports_with_verified_action_pins():
    qa = yaml.load((ROOT / '.github/workflows/qa.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    job = qa['jobs']['upstream-canary']
    channels = {item['channel']: item for item in job['strategy']['matrix']['include']}
    assert channels['latest-upstream']['ref'] == 'main'
    assert channels['pinned']['ref'] == channels['pinned']['expected-sha']
    assert re.fullmatch('[0-9a-f]{40}', channels['pinned']['ref'])
    run = next(step for step in job['steps'] if 'hermes_compatibility_canary.py' in step.get('run', ''))
    assert run['if'] == 'always()' and '--checkout-outcome' in run['run']
    assert '--expected-sha' in run['run'] and '"$code" -eq 2' in run['run']
    # Preserve candidate runtime/CLI coverage separately from the light schedule.
    runtime = qa['jobs']['upstream-runtime']
    setup = next(step for step in runtime['steps'] if step.get('uses', '').startswith('actions/setup-python@'))
    assert setup['with']['python-version'] == '3.14'
    assert any('hermes_runtime_smoke.py' in step.get('run', '') for step in runtime['steps'])
    assert any('--query-file' in step.get('run', '') and '--ignore-rules' in step['run'] for step in runtime['steps'])
    for definition in qa['jobs'].values():
        for step in definition['steps']:
            if step.get('uses', '').startswith('actions/checkout@') and 'repository' not in step.get('with', {}):
                assert step['with']['ref'] == '${{ github.event.pull_request.head.sha || github.sha }}'
    for filename in ('qa.yml', 'live-contract.yml'):
        workflow = yaml.load((ROOT / '.github/workflows' / filename).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
        for definition in workflow['jobs'].values():
            for step in definition['steps']:
                action = step.get('uses', '')
                if action.startswith('actions/checkout@'):
                    assert action == 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1'
                elif action.startswith('actions/setup-python@'):
                    assert action == 'actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97'
    for definition, artifact_name in ((job, 'hermes-${{ matrix.channel }}-status'),
                                    (workflow['jobs']['external-apis'], 'external-api-status')):
        artifact = next(step for step in definition['steps'] if step.get('with', {}).get('name') == artifact_name)
        assert artifact['if'] == 'always()'
        assert artifact['with']['if-no-files-found'] == 'error'

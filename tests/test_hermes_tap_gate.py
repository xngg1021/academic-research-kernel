"""Offline fail-closed checks for the live tap gate; installs run in main CI."""
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hermes_tap_gate', ROOT / 'scripts/hermes_tap_smoke.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


@pytest.fixture
def installed_state(tmp_path):
    home = tmp_path / 'profile'
    root = tmp_path / 'source'
    revision = 'a' * 40
    state = {'hermes_sha': gate.HERMES_SHA, 'skills_dir': str(home / 'skills'),
             'taps': [{'repo': gate.REPO, 'path': 'skills/'}],
             'installed': [], 'enabled_names': list(gate.SKILLS), 'disabled_names': []}
    for name in gate.SKILLS:
        for directory in (root / 'skills' / name, home / 'skills' / name):
            (directory / 'scripts').mkdir(parents=True)
            (directory / 'SKILL.md').write_text(f'name: {name}', encoding='utf-8')
            (directory / 'scripts/helper.py').write_text('# complete supporting file', encoding='utf-8')
        url = f'https://github.com/{gate.REPO}/tree/{revision}/skills/{name}'
        state['installed'].append({'name': name, 'source': 'github',
                                   'identifier': f'{gate.REPO}/skills/{name}', 'install_path': name,
                                   'files': ['SKILL.md', 'scripts/helper.py'], 'scan_verdict': 'safe',
                                   'metadata': {'source_revision': revision, 'source_url': url},
                                   'scan_provenance': {'source_url': url}})
    return state, home, revision, root


def test_accepts_four_complete_enabled_exact_source_bundles(installed_state):
    state, home, revision, root = installed_state
    state['installed'][0]['scan_verdict'] = 'caution'
    assert set(gate.check_installed(state, home, revision, root)) == set(gate.SKILLS)


def test_accepts_actual_cli_registry_relabel_with_exact_github_provenance(installed_state):
    state, home, revision, root = installed_state
    for entry in state['installed']:
        entry['source'] = 'skills.sh'
        entry['identifier'] = 'skills-sh/' + entry['identifier']
    assert set(gate.check_installed(state, home, revision, root)) == set(gate.SKILLS)


@pytest.mark.parametrize('failure', [
    'zero-installed', 'missing-install', 'disabled', 'not-discovered', 'different-source',
    'different-identifier', 'different-revision', 'different-scan-source', 'missing-support-file',
    'changed-file', 'dangerous', 'unexpected-caution', 'different-hermes', 'different-profile',
    'missing-tap', 'escaping-install-path',
])
def test_refuses_false_green_installations(installed_state, failure):
    state, home, revision, root = installed_state
    first = state['installed'][0]
    if failure == 'zero-installed':
        state['installed'] = []
    elif failure == 'missing-install':
        state['installed'].pop()
    elif failure == 'disabled':
        state['disabled_names'] = [gate.SKILLS[0]]
    elif failure == 'not-discovered':
        state['enabled_names'].pop()
    elif failure == 'different-source':
        first['source'] = 'clawhub'
    elif failure == 'different-identifier':
        first['identifier'] = 'another-owner/repo/skills/' + first['name']
    elif failure == 'different-revision':
        first['metadata']['source_revision'] = 'b' * 40
    elif failure == 'different-scan-source':
        first['scan_provenance']['source_url'] = 'https://example.org/other'
    elif failure == 'missing-support-file':
        (home / 'skills' / gate.SKILLS[0] / 'scripts/helper.py').unlink()
    elif failure == 'changed-file':
        (home / 'skills' / gate.SKILLS[0] / 'SKILL.md').write_text('different bytes')
    elif failure == 'dangerous':
        first['scan_verdict'] = 'dangerous'
    elif failure == 'unexpected-caution':
        state['installed'][1]['scan_verdict'] = 'caution'
    elif failure == 'different-hermes':
        state['hermes_sha'] = 'b' * 40
    elif failure == 'different-profile':
        state['skills_dir'] = str(home / 'other')
    elif failure == 'missing-tap':
        state['taps'] = []
    elif failure == 'escaping-install-path':
        first['install_path'] = '../outside'
    with pytest.raises(RuntimeError):
        gate.check_installed(state, home, revision, root)


@pytest.mark.parametrize('rows', [[], [{'identifier': 'wrong', 'source': 'github'}],
                                [{'identifier': f'{gate.REPO}/skills/{gate.SKILLS[0]}', 'source': 'skills-sh'}]])
def test_empty_or_wrong_source_search_fails_even_when_cli_exits_zero(rows):
    with pytest.raises(RuntimeError, match='did not discover'):
        gate.check_search(rows, gate.SKILLS[0])


def test_accepts_exact_github_search_identifier():
    gate.check_search([{'identifier': f'{gate.REPO}/skills/{gate.SKILLS[0]}', 'source': 'github'}], gate.SKILLS[0])


@pytest.mark.parametrize('identity', ['commit', 'tree'])
def test_source_revision_maps_to_exact_checked_out_commit_or_tree(identity):
    commit, tree = 'a' * 40, 'b' * 40
    revision = {'commit': commit, 'tree': tree}[identity]
    remote = {'source_revision': revision, 'default_branch': 'main', 'commit': commit, 'tree': tree}
    assert gate.select_source_revision(remote, commit, tree) == revision


@pytest.mark.parametrize('field', ['source_revision', 'commit', 'tree'])
def test_unrelated_source_revision_or_mapping_is_rejected(field):
    remote = {'source_revision': 'a' * 40, 'default_branch': 'main', 'commit': 'a' * 40, 'tree': 'b' * 40}
    remote[field] = 'c' * 40
    with pytest.raises(RuntimeError, match='differs from reviewed checkout'):
        gate.select_source_revision(remote, 'a' * 40, 'b' * 40)


def test_tap_job_executes_real_gate_and_keeps_failure_evidence():
    workflow = yaml.load((ROOT / '.github/workflows/qa.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    steps = workflow['jobs']['tap-lifecycle']['steps']
    step = next(step for step in steps if 'hermes_tap_smoke.py' in step.get('run', ''))
    assert step['env']['GITHUB_TOKEN'] == '${{ github.token }}'
    assert '--output tap-lifecycle.json' in step['run']
    upload = next(step for step in steps if step.get('with', {}).get('name') == 'tap-lifecycle-status')
    assert upload['if'] == 'always()'
    assert upload['with']['path'] == 'tap-lifecycle.json'


def test_quantitative_external_receipt_links_survive_standalone_installation():
    text = (ROOT / 'skills/quantitative-paper-audit/SKILL.md').read_text(encoding='utf-8')
    for path in ('schemas/evidence-receipt.schema.json', 'examples/evidence-receipt.example.json'):
        assert f'](https://github.com/{gate.REPO}/blob/main/{path})' in text
        assert f'](../../{path})' not in text

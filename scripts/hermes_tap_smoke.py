"""Real pinned Hermes tap acceptance; CLI exit zero alone is not acceptance.

Run with the pinned Hermes installed. Uses a disposable profile, live GitHub
discovery/downloads, and the actual quarantine/scanner/installer/skill loader.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
REPO = 'xngg1021/academic-research-kernel'
HERMES_SHA = '245e48008fa814b3251f50755eb656bd9fb86cb1'
SKILLS = ('academic-source-verification', 'quantitative-paper-audit',
          'retraction-watch', 'cross-review-five')
# These two reviewed skills are CAUTION under skills-guard-v2 (API bearer/env
# examples and the explicit reviewer subprocess adapter). Upstream --force is
# per-install, still scans/quarantines, and cannot override community DANGEROUS.
CAUTION_OVERRIDES = {'academic-source-verification', 'cross-review-five'}

PROBE = r'''
import json
from pathlib import Path
import subprocess
import hermes_cli
from hermes_constants import get_skills_dir
from tools.skills_hub import HubLockFile, TapsManager
from tools.skills_tool import _find_all_skills
from agent.skill_utils import get_disabled_skill_names
upstream = Path(hermes_cli.__file__).resolve().parents[1]
print(json.dumps({
    'hermes_sha': subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip(),
    'skills_dir': str(get_skills_dir()),
    'taps': TapsManager().list_taps(),
    'installed': HubLockFile().list_installed(),
    'enabled_names': [skill['name'] for skill in _find_all_skills()],
    'disabled_names': sorted(get_disabled_skill_names()),
}))
'''

REMOTE_TREE = r'''
import json
from tools.skills_hub_github import GitHubAuth, GitHubSource
source = GitHubSource(GitHubAuth())
tree = source._get_repo_tree('xngg1021/academic-research-kernel')
commit = source._github_json('https://api.github.com/repos/xngg1021/academic-research-kernel/commits/main') or {}
print(json.dumps({'source_revision': source._tree_revisions.get('xngg1021/academic-research-kernel'),
                  'commit': commit.get('sha'), 'tree': commit.get('commit', {}).get('tree', {}).get('sha'),
                  'default_branch': tree[0] if tree else None}))
'''

TAP_SEARCH = r'''
import json
import sys
from tools.skills_hub import TapsManager
from tools.skills_hub_github import GitHubAuth, GitHubSource
from tools.skills_hub_search import unified_search
source = GitHubSource(GitHubAuth())
# Scope this adapter instance to the registered tap. Do not change upstream
# DEFAULT_TAPS or global configuration. Every row still comes from live GitHub.
source.taps = [tap for tap in TapsManager().list_taps()
               if tap['repo'] == 'xngg1021/academic-research-kernel']
rows = unified_search(sys.argv[1], [source], source_filter='github', limit=25)
print(json.dumps([{'name': row.name, 'identifier': row.identifier, 'source': row.source}
                  for row in rows]))
'''


def run(command, env, cwd, *, show=True):
    result = subprocess.run(command, env=env, cwd=cwd, stdin=subprocess.DEVNULL,
                            text=True, encoding='utf-8', capture_output=True, timeout=240)
    if show or result.returncode:
        print(result.stdout, end='', flush=True)
        print(result.stderr, end='', file=sys.stderr, flush=True)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {command}')
    return result.stdout


def check_search(rows, name):
    expected = f'{REPO}/skills/{name}'
    if not any(row.get('identifier') == expected and row.get('source') == 'github'
               for row in rows):
        raise RuntimeError(f'GitHub tap search did not discover {expected}: {rows}')


def select_source_revision(remote, expected_commit, expected_tree):
    # The pinned adapter stores /git/trees/main's returned sha verbatim. Real
    # responses observed here identify the commit; standard tree responses can
    # identify its tree. Accept only either identity of this exact checkout.
    revision = remote.get('source_revision')
    if (remote.get('default_branch') != 'main'
            or remote.get('commit') != expected_commit or remote.get('tree') != expected_tree
            or revision not in {expected_commit, expected_tree}):
        raise RuntimeError(f'Tap default branch differs from reviewed checkout: {remote}')
    return revision


def bundle_files(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()
            and not any(part.startswith('.') or part == '__pycache__'
                        for part in path.relative_to(directory).parts)
            and path.suffix != '.pyc'}


def check_installed(state, home, expected_revision, root=ROOT):
    if state['hermes_sha'] != HERMES_SHA:
        raise RuntimeError(f'Wrong Hermes revision: {state["hermes_sha"]}')
    skills_dir = (home / 'skills').resolve()
    if Path(state['skills_dir']).resolve() != skills_dir:
        raise RuntimeError('Hermes used a different profile')
    if {'repo': REPO, 'path': 'skills/'} not in state['taps']:
        raise RuntimeError('The real GitHub tap was not registered')
    installed = {entry['name']: entry for entry in state['installed']}
    if set(installed) != set(SKILLS):
        raise RuntimeError(f'Expected four hub installations; found {sorted(installed)}')
    disabled = set(SKILLS) & set(state['disabled_names'])
    missing = set(SKILLS) - set(state['enabled_names'])
    if disabled or missing:
        raise RuntimeError(f'Skills not enabled in Hermes discovery: disabled={disabled}, missing={missing}')
    for name in SKILLS:
        entry = installed[name]
        identifier = f'{REPO}/skills/{name}'
        source_url = f'https://github.com/{REPO}/tree/{expected_revision}/skills/{name}'
        # The actual CLI probes SkillsShSource before GitHubSource. That
        # production adapter downloads this same GitHub bundle and records its
        # own registry label; require its exact wrapped identifier as well.
        sources = {'github': identifier, 'skills.sh': f'skills-sh/{identifier}'}
        if entry['identifier'] != sources.get(entry['source']):
            raise RuntimeError(f'Wrong installation source for {name}: {entry}')
        if (entry['metadata'].get('source_revision') != expected_revision
                or entry['metadata'].get('source_url') != source_url
                or entry['scan_provenance'].get('source_url') != source_url):
            raise RuntimeError(f'Wrong downloaded/scanned revision for {name}: {entry}')
        allowed = {'safe', 'caution'} if name in CAUTION_OVERRIDES else {'safe'}
        if entry['scan_verdict'] not in allowed:
            raise RuntimeError(f'Unexpected scan verdict for {name}: {entry["scan_verdict"]}')
        target = (skills_dir / entry['install_path']).resolve()
        if not target.is_relative_to(skills_dir) or target == skills_dir:
            raise RuntimeError(f'Invalid installation location for {name}')
        expected = bundle_files(root / 'skills' / name)
        actual = bundle_files(target)
        if actual != expected or set(entry['files']) != set(expected):
            raise RuntimeError(f'Installed bundle is incomplete or differs from checkout: {name}')
    return installed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    expected_commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
                                              text=True).strip()
    expected_tree = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD^{tree}'],
                                            text=True).strip()
    report = {'status': 'failed', 'expected_commit': expected_commit,
              'expected_tree': expected_tree, 'hermes_sha': HERMES_SHA}
    try:
        with tempfile.TemporaryDirectory(prefix='ark-tap-') as directory:
            home = Path(directory) / 'profile'
            env = dict(os.environ, HERMES_HOME=str(home), PYTHONUTF8='1', NO_COLOR='1')
            cli = [sys.executable, '-m', 'hermes_cli.main', 'skills']
            remote = json.loads(run([sys.executable, '-c', REMOTE_TREE], env, directory, show=False))
            revision = select_source_revision(remote, expected_commit, expected_tree)
            report['source_revision'] = revision
            report['remote_identity'] = remote
            run(cli + ['tap', 'add', REPO], env, directory)
            # Pinned Hermes can silently return [] for ordinary CLI search:
            # all-source search skips custom GitHub taps when its index exists;
            # github search traverses unrelated default taps before ours and
            # can hit unified_search's 30-second deadline (confirmed in the
            # release investigation). Assert real discovery using the production
            # adapter scoped to this registered repository, without fake rows
            # or transport mocks; do not claim ordinary CLI search passed.
            print('Discovery uses production GitHubSource targeted search, not ordinary all-tap CLI search', flush=True)
            report['targeted_search'] = {}
            for name in SKILLS:
                print(f'Production GitHubSource targeted search: {name}', flush=True)
                output = run([sys.executable, '-c', TAP_SEARCH, name], env, directory)
                rows = json.loads(output)
                check_search(rows, name)
                report['targeted_search'][name] = rows
                # --yes skips only the interactive confirmation. --force below
                # is scoped to two reviewed CAUTION bundles in this empty home.
                flags = ['--yes'] + (['--force'] if name in CAUTION_OVERRIDES else [])
                run(cli + ['install', f'{REPO}/skills/{name}', *flags], env, directory)
            run(cli + ['list', '--source', 'hub', '--enabled-only'], env, directory)
            state = json.loads(run([sys.executable, '-c', PROBE], env, directory, show=False))
            report['observed_state'] = state
            report['installed'] = check_installed(state, home, revision)
            report['enabled_names'] = sorted(set(SKILLS) & set(state['enabled_names']))
            report['status'] = 'passed'
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('PASS real GitHub tap -> four exact-source bundles installed -> four enabled Hermes skills')


if __name__ == '__main__':
    main()

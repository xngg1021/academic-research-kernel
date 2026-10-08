"""Offline release gates and interrupted-publication recovery regressions."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from urllib.error import HTTPError, URLError
import zipfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
try:
    import release_manifest as manifests
    import verify_release_assets as releases
finally:
    sys.path.pop(0)

VERSION, TAG = '2.0.1', 'v2.0.1'


def metadata(version=VERSION):
    return (f'Name: academic-research-kernel\nVersion: {version}\n'
            'Requires-Python: <3.15,>=3.10\nLicense-Expression: LicenseRef-Source-Lineage-1.0\n\n'
            'mcp-name: io.github.xngg1021/academic-research-kernel\n').encode()


def packages(directory, internal_version=VERSION, runtime_version=None, version=VERSION):
    runtime_version = internal_version if runtime_version is None else runtime_version
    directory.mkdir()
    wheel = directory / f'academic_research_kernel-{version}-py3-none-any.whl'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr(f'academic_research_kernel-{version}.dist-info/METADATA', metadata(internal_version))
        archive.writestr('academic_research_kernel/_version.py', f'__version__ = "{runtime_version}"\n')
        for name in ('cli.py', 'mcp_server.py', 'recompute.py', 'ingestion/engine.py'):
            archive.writestr('academic_research_kernel/' + name, '# source fixture\n')
        archive.writestr('academic_research_kernel/artifact-adapter-matrix.json', '{}')
        for number in range(23):
            archive.writestr(f'academic_research_kernel/schemas/{number}.json', '{}')
        if tuple(map(int, version.split('.'))) >= (2, 1, 0):
            for name in manifests.RESEARCH_SCHEMAS:
                archive.writestr('academic_research_kernel/schemas/' + name, '{}')
            for name in manifests.PORTABLE_SKILL_FILES:
                archive.writestr(name, '# portable workflow fixture\n')
            for name in ('research/sources.py', 'research/analysis.py', 'ingestion/paper_research.py'):
                archive.writestr('academic_research_kernel/' + name, '# source fixture\n')
    sdist = directory / f'academic_research_kernel-{version}.tar.gz'
    with tarfile.open(sdist, 'w:gz') as archive:
        members = {'PKG-INFO': metadata(internal_version),
                   'scripts/_version.py': f'__version__ = "{runtime_version}"\n'.encode(),
                   'plugin.json': json.dumps({'name': 'academic-skills', 'version': version}).encode(),
                   'server.json': json.dumps({'name': 'io.github.xngg1021/academic-research-kernel', 'version': version,
                                             'packages': [{'identifier': 'academic-research-kernel', 'version': version}]}).encode()}
        for name, data in members.items():
            info = tarfile.TarInfo(f'academic_research_kernel-{version}/' + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return [wheel, sdist]


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), '-c', 'user.name=Release Test',
                                    '-c', 'user.email=release-test@example.invalid', *args],
                                   text=True, stderr=subprocess.PIPE).strip()


@pytest.fixture
def release_case(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'scripts').mkdir()
    (source / 'scripts/_version.py').write_text(f'__version__ = "{VERSION}"\n', encoding='utf-8')
    (source / 'uv.lock').write_text('lock fixture\n', encoding='utf-8')
    server = {'name': 'io.github.xngg1021/academic-research-kernel', 'version': VERSION,
              'packages': [{'registryType': 'pypi', 'identifier': 'academic-research-kernel',
                            'version': VERSION, 'transport': {'type': 'stdio'}}]}
    (source / 'server.json').write_text(json.dumps(server), encoding='utf-8')
    git(source, 'init', '--initial-branch=main')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'release source fixture')
    git(source, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    git(source, 'tag', '-a', TAG, '-m', 'release fixture')
    directory = tmp_path / 'release-input'
    artifacts = [manifests.inspect_artifact(path, VERSION) for path in packages(directory)]
    target = manifests.validate_target(VERSION, TAG, source)
    manifest = {'package': 'academic-research-kernel', 'version': VERSION, 'git_tag': TAG, 'intended_tag': TAG,
                'source_commit': target['commit'], 'source_tree': target['tree'], 'tag_object': target['tag_object'],
                'source_dirty': False, 'plugin': {'name': 'academic-skills', 'version': VERSION}, 'artifacts': artifacts}
    (directory / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (directory / 'SHA256SUMS').write_text(''.join(item['sha256'] + '  ' + item['filename'] + '\n' for item in artifacts), encoding='utf-8')
    (directory / 'server.json').write_text(json.dumps(server), encoding='utf-8')
    return source, directory, manifest


def verify_case(case, tmp_path, **kwargs):
    source, directory, manifest = case
    return releases.verify(directory, VERSION, TAG, tmp_path / 'verified', source, **kwargs)


def test_normal_201_release_has_exact_verified_bytes(release_case, tmp_path):
    result = verify_case(release_case, tmp_path)
    assert result == release_case[2]
    assert {path.name for path in (tmp_path / 'verified').iterdir()} == manifests.package_filenames(VERSION)
    for item in result['artifacts']:
        assert hashlib.sha256((tmp_path / 'verified' / item['filename']).read_bytes()).hexdigest() == item['sha256']


def test_210_distribution_requires_new_portable_resources_and_preserves_201_inventory(tmp_path):
    for path in packages(tmp_path / 'current', internal_version='2.1.0', version='2.1.0'):
        assert manifests.inspect_artifact(path, '2.1.0')['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    for path in packages(tmp_path / 'historical'):
        assert manifests.inspect_artifact(path, VERSION)['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize('damage', ['missing_skill', 'missing_runtime', 'renamed_schema', 'extra_schema', 'foreign_skill'])
def test_210_rejects_incomplete_or_unexpected_runtime_resources(tmp_path, damage):
    wheel, _ = packages(tmp_path / 'current', internal_version='2.1.0', version='2.1.0')
    with zipfile.ZipFile(wheel) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    if damage == 'missing_skill':
        del files['academic_research_kernel/skills/paper-research/SKILL.md']
    elif damage == 'missing_runtime':
        del files['academic_research_kernel/ingestion/paper_research.py']
    elif damage == 'renamed_schema':
        files['academic_research_kernel/schemas/invented.schema.json'] = files.pop('academic_research_kernel/schemas/paper-extraction.schema.json')
    elif damage == 'extra_schema':
        files['academic_research_kernel/schemas/invented.schema.json'] = b'{}'
    else:
        files['academic_research_kernel/skills/foreign-skill/SKILL.md'] = b'foreign'
    with zipfile.ZipFile(wheel, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    with pytest.raises(ValueError):
        manifests.inspect_artifact(wheel, '2.1.0')


@pytest.mark.parametrize(('version', 'tag'), [('2.0.0', TAG), (VERSION, 'latest'), ('02.0.1', 'v02.0.1'),
                                             ('2.0.1\nother=value', TAG), ('', 'v'), ('2.0.1rc1', 'v2.0.1rc1')])
def test_reject_ambiguous_or_conflicting_explicit_target(version, tag):
    with pytest.raises(ValueError):
        manifests.validate_version_tag(version, tag)


@pytest.mark.parametrize(('field', 'value'), [('version', '2.0.0'), ('git_tag', 'v2.0.0'),
                                            ('source_dirty', True), ('source_commit', 'a' * 40),
                                            ('source_tree', 'b' * 40), ('tag_object', 'c' * 40)])
def test_reject_manifest_source_or_target_mismatch(release_case, tmp_path, field, value):
    source, directory, manifest = release_case
    manifest[field] = value
    (directory / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        verify_case(release_case, tmp_path)
    assert not (tmp_path / 'verified').exists()


@pytest.mark.parametrize('field', ['sha256', 'size_bytes', 'file_count'])
def test_reject_wrong_artifact_hash_size_or_inventory(release_case, tmp_path, field):
    source, directory, manifest = release_case
    manifest['artifacts'][0][field] = '0' * 64 if field == 'sha256' else 1
    (directory / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError):
        verify_case(release_case, tmp_path)


@pytest.mark.parametrize('extra', ['academic_research_kernel-2.0.0.tar.gz', 'extra.whl', 'extra.txt'])
def test_reject_extra_release_files_before_copy(release_case, tmp_path, extra):
    (release_case[1] / extra).write_text('unexpected', encoding='utf-8')
    with pytest.raises(ValueError, match='exactly'):
        verify_case(release_case, tmp_path)
    assert not (tmp_path / 'verified').exists()


def test_reject_old_internal_metadata_even_with_fresh_outer_hashes(tmp_path):
    paths = packages(tmp_path / 'packages', internal_version='2.0.0')
    for path in paths:
        with pytest.raises(ValueError, match='metadata mismatch: Version'):
            manifests.inspect_artifact(path, VERSION)


@pytest.mark.parametrize('index', [0, 1])
def test_reject_old_internal_runtime_even_with_current_package_metadata(tmp_path, index):
    paths = packages(tmp_path / 'packages', runtime_version='2.0.0')
    with pytest.raises(ValueError, match='internal runtime version'):
        manifests.inspect_artifact(paths[index], VERSION)


def test_reject_checksum_and_registry_source_mismatch(release_case, tmp_path):
    source, directory, manifest = release_case
    sums = (directory / 'SHA256SUMS').read_text(encoding='utf-8')
    (directory / 'SHA256SUMS').write_text('0' * 64 + sums[64:], encoding='utf-8')
    with pytest.raises(ValueError, match='SHA256SUMS'):
        verify_case(release_case, tmp_path)
    (directory / 'SHA256SUMS').write_text(sums, encoding='utf-8')
    server = json.loads((directory / 'server.json').read_text(encoding='utf-8'))
    server['extra'] = 'not in tagged source'
    (directory / 'server.json').write_text(json.dumps(server), encoding='utf-8')
    with pytest.raises(ValueError, match='tagged source'):
        verify_case(release_case, tmp_path)


def test_reject_dirty_source_nonempty_output_and_moved_target(release_case, tmp_path):
    source, directory, manifest = release_case
    with pytest.raises(ValueError, match='moved'):
        verify_case(release_case, tmp_path, expected_commit='0' * 40)
    (source / 'uv.lock').write_text('changed', encoding='utf-8')
    with pytest.raises(ValueError, match='clean'):
        verify_case(release_case, tmp_path)
    git(source, 'restore', 'uv.lock')
    (tmp_path / 'verified').mkdir()
    (tmp_path / 'verified/old.whl').write_text('old', encoding='utf-8')
    with pytest.raises(ValueError, match='empty'):
        verify_case(release_case, tmp_path)


def test_publication_trampoline_cannot_contaminate_separate_clean_source(release_case, tmp_path):
    source, directory, manifest = release_case
    generated = source / '.github/.tmp/.generated-actions/run-pypi-publish-in-docker-container'
    generated.mkdir(parents=True)
    (generated / 'action.yml').write_text('generated publisher trampoline\n', encoding='utf-8')
    with pytest.raises(ValueError, match='clean'):
        manifests.validate_target(VERSION, TAG, source, require_head=True)
    clean = tmp_path / 'public-source'
    git(source, 'worktree', 'add', '--detach', str(clean), TAG)
    result = releases.verify(directory, VERSION, TAG, tmp_path / 'verified', clean)
    assert result['source_commit'] == manifest['source_commit']
    assert result['source_tree'] == manifest['source_tree']
    assert git(clean, 'status', '--porcelain', '--untracked-files=normal') == ''


def test_reject_tag_outside_main_and_lightweight_tag(release_case):
    source, directory, manifest = release_case
    git(source, 'update-ref', 'refs/remotes/origin/main', '0' * 40)
    with pytest.raises(ValueError, match='ancestor'):
        manifests.validate_target(VERSION, TAG, source)
    git(source, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    git(source, 'tag', '-d', TAG)
    git(source, 'tag', TAG)
    with pytest.raises(ValueError, match='annotated'):
        manifests.validate_target(VERSION, TAG, source)


def test_reject_head_or_source_version_differing_from_tag(release_case):
    source, directory, manifest = release_case
    (source / 'another.txt').write_text('later main', encoding='utf-8')
    git(source, 'add', '.')
    git(source, 'commit', '-m', 'later main fixture')
    git(source, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
    with pytest.raises(ValueError, match='HEAD'):
        manifests.validate_target(VERSION, TAG, source, require_head=True)
    with pytest.raises(ValueError):
        manifests.validate_target('2.0.2', 'v2.0.2', source)


def published(manifest, count=2):
    return {'info': {'name': 'academic-research-kernel', 'version': VERSION},
            'urls': [{'filename': item['filename'], 'digests': {'sha256': item['sha256']},
                      'size': item['size_bytes']} for item in manifest['artifacts'][:count]]}


@pytest.mark.parametrize('count', [0, 1, 2])
def test_partial_pypi_upload_stages_only_same_frozen_missing_files(release_case, tmp_path, count):
    manifest = verify_case(release_case, tmp_path)
    remote = None if count == 0 else published(manifest, count)
    result = releases.plan_pypi_upload(manifest, tmp_path / 'verified', tmp_path / 'upload', remote)
    assert result['upload_count'] == 2 - count
    assert {path.name for path in (tmp_path / 'upload').iterdir()} == set(result['missing'])
    assert set(result['already_published']) == {item['filename'] for item in manifest['artifacts'][:count]}


@pytest.mark.parametrize('change', ['hash', 'size', 'filename', 'version', 'duplicate'])
def test_pypi_same_version_conflicts_fail_before_staging(release_case, tmp_path, change):
    manifest = verify_case(release_case, tmp_path)
    remote = published(manifest)
    if change == 'hash':
        remote['urls'][0]['digests']['sha256'] = '0' * 64
    elif change == 'size':
        remote['urls'][0]['size'] += 1
    elif change == 'filename':
        remote['urls'][0]['filename'] = 'different.whl'
    elif change == 'version':
        remote['info']['version'] = '2.0.0'
    else:
        remote['urls'].append(remote['urls'][0])
    with pytest.raises(ValueError):
        releases.plan_pypi_upload(manifest, tmp_path / 'verified', tmp_path / 'upload', remote)
    assert not (tmp_path / 'upload').exists()


def test_verify_only_requires_both_files_and_never_stages_upload(release_case, tmp_path):
    manifest = verify_case(release_case, tmp_path)
    with pytest.raises(ValueError, match='both frozen files'):
        releases.plan_pypi_upload(manifest, tmp_path / 'verified', tmp_path / 'partial', published(manifest, 1), True)
    result = releases.plan_pypi_upload(manifest, tmp_path / 'verified', tmp_path / 'complete', published(manifest), True)
    assert result['upload_count'] == 0 and not list((tmp_path / 'complete').iterdir())


@pytest.mark.parametrize('code', [404, 403, 429, 503])
def test_pypi_only_actual_404_means_version_absent(monkeypatch, code):
    def fail(*args, **kwargs):
        raise HTTPError('https://pypi.org/pypi/test/json', code, 'fixture', {}, None)
    monkeypatch.setattr(releases, 'urlopen', fail)
    if code == 404:
        assert releases.fetch_pypi_version(VERSION) is None
    else:
        with pytest.raises(HTTPError):
            releases.fetch_pypi_version(VERSION)


def test_pypi_transport_failure_does_not_become_missing_version(monkeypatch):
    def fail(*args, **kwargs):
        raise URLError('fixture network unavailable')
    monkeypatch.setattr(releases, 'urlopen', fail)
    with pytest.raises(URLError):
        releases.fetch_pypi_version(VERSION)


def test_release_gates_remain_enabled_under_python_optimization(release_case, tmp_path):
    source, directory, manifest = release_case
    manifest['artifacts'][0]['sha256'] = '0' * 64
    (directory / 'release-manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    process = subprocess.run([sys.executable, '-O', str(SCRIPTS / 'verify_release_assets.py'), str(directory),
                              '--version', VERSION, '--tag', TAG, '--repo', str(source),
                              '--dist', str(tmp_path / 'verified')], text=True, capture_output=True, timeout=30)
    assert process.returncode != 0 and 'sha256 mismatch' in process.stderr
    assert not (tmp_path / 'verified').exists()


def test_candidate_manifest_compatibility_and_formal_mode(release_case, tmp_path, monkeypatch):
    source, directory, original = release_case
    # The only external build tool boundary is the uv version probe.
    real_output = manifests.subprocess.check_output
    def output(command, *args, **kwargs):
        return 'uv test-fixture' if command == ['uv', '--version'] else real_output(command, *args, **kwargs)
    monkeypatch.setattr(manifests.subprocess, 'check_output', output)
    monkeypatch.setattr(manifests, '__version__', VERSION)
    candidate = manifests.create_manifest(directory, root=source)
    assert candidate['version'] == VERSION and candidate['git_tag'] is None
    monkeypatch.setenv('SOURCE_DATE_EPOCH', git(source, 'show', '-s', '--format=%ct', 'HEAD'))
    formal = manifests.create_manifest(directory, VERSION, TAG, True, source)
    assert formal['git_tag'] == TAG and formal['tag_object'] == original['tag_object']
    monkeypatch.delenv('SOURCE_DATE_EPOCH')
    with pytest.raises(ValueError, match='SOURCE_DATE_EPOCH'):
        manifests.create_manifest(directory, VERSION, TAG, True, source)
    with pytest.raises(ValueError, match='explicit'):
        manifests.main(['--release', '--dist', str(directory), '--output', str(tmp_path / 'manifest.json')])


def test_publish_workflow_uses_validated_target_and_selective_recovery():
    workflow = yaml.load((ROOT / '.github/workflows/publish-pypi.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
    inputs = workflow['on']['workflow_dispatch']['inputs']
    assert inputs['version']['required'] == inputs['tag']['required'] == 'true'
    assert inputs['verify_only']['type'] == 'boolean'
    job = workflow['jobs']['publish']
    assert job['if'] == "github.ref == 'refs/heads/main'" and job['environment']['name'] == 'pypi'
    assert job['permissions']['id-token'] == 'write'
    checkouts = [step for step in job['steps'] if step.get('uses', '').startswith('actions/checkout@')]
    assert [step['with']['ref'] for step in checkouts] == ['${{ github.sha }}', '${{ steps.target.outputs.commit }}']
    publisher = next(step for step in job['steps'] if step.get('uses', '').startswith('pypa/gh-action-pypi-publish@'))
    assert publisher['if'] == "inputs.verify_only == false && steps.assets.outputs.upload_count != '0'"
    assert 'skip-existing' not in publisher.get('with', {})
    assert publisher['with']['packages-dir'] == '${{ runner.temp }}/pypi-upload/'
    for step in job['steps']:
        assert '${{ inputs.' not in step.get('run', '')
    smoke = job['steps'][-1]['run']
    assert 'git worktree add --detach "$RUNNER_TEMP/public-source" "$RELEASE_COMMIT"' in smoke
    assert '--repo "$RUNNER_TEMP/public-source"' in smoke
    assert '--expected-version "$RELEASE_VERSION"' in smoke
    assert 'academic-research-kernel==$RELEASE_VERSION' in smoke and 'academic-research-kernel@$RELEASE_VERSION' in smoke

"""Fail closed before publication; upload only missing, manifest-bound bytes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from release_manifest import (PACKAGE, ROOT, inspect_artifact, package_filenames,
                              require, validate_target, validate_version_tag)


def verify(directory, version, tag, dist=Path('dist'), root=ROOT, expected_commit=None):
    directory, dist = Path(directory), Path(dist)
    target = validate_target(version, tag, root, expected_commit, require_head=True)
    expected_names = package_filenames(version)
    entries = list(directory.iterdir())
    require(all(path.is_file() and not path.is_symlink() for path in entries), 'release input contains non-regular entries')
    require({path.name for path in entries} == expected_names | {'release-manifest.json', 'SHA256SUMS', 'server.json'},
            'release input must contain exactly the expected packages, manifest, SHA256SUMS, and server.json')
    manifest = json.loads((directory / 'release-manifest.json').read_text(encoding='utf-8'))
    require(manifest.get('package') == PACKAGE and manifest.get('version') == version, 'manifest package/version mismatch')
    require(manifest.get('git_tag') == tag and manifest.get('intended_tag') == tag, 'manifest release tag mismatch')
    require(manifest.get('source_dirty') is False, 'manifest source must be clean')
    require(manifest.get('source_commit') == target['commit'], 'manifest source commit differs from the actual tag')
    require(manifest.get('source_tree') == target['tree'], 'manifest source tree differs from the actual tag')
    require(manifest.get('tag_object') == target['tag_object'], 'manifest tag object differs from the actual annotated tag')
    require(manifest.get('plugin') == {'name': 'academic-skills', 'version': version}, 'manifest plugin identity/version mismatch')
    artifacts = manifest.get('artifacts')
    require(isinstance(artifacts, list) and len(artifacts) == 2 and all(isinstance(item, dict) for item in artifacts),
            'manifest must contain exactly two package records')
    require({item.get('filename') for item in artifacts} == expected_names, 'manifest artifact filenames mismatch')
    verified = {}
    for artifact in artifacts:
        path = directory / artifact['filename']
        actual = inspect_artifact(path, version)
        require(isinstance(artifact.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', artifact['sha256']), 'manifest SHA-256 invalid')
        require(type(artifact.get('size_bytes')) is int and artifact['size_bytes'] > 0, 'manifest artifact size invalid')
        for key in ('sha256', 'size_bytes', 'file_count'):
            require(artifact.get(key) == actual[key], 'artifact ' + key + ' mismatch: ' + path.name)
        verified[path.name] = actual
    sums = {}
    for line in (directory / 'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64}) [ *]([^/\\]+)', line)
        require(match is not None and match[2] not in sums, 'SHA256SUMS contains an invalid or duplicate entry')
        sums[match[2]] = match[1]
    require(sums == {name: item['sha256'] for name, item in verified.items()}, 'SHA256SUMS differs from the verified package bytes')
    server = json.loads((directory / 'server.json').read_text(encoding='utf-8'))
    require(server.get('name') == 'io.github.xngg1021/academic-research-kernel' and server.get('version') == version,
            'Registry namespace/version mismatch')
    packages = server.get('packages')
    require(isinstance(packages, list) and len(packages) == 1, 'Registry must reference exactly one package')
    package = packages[0]
    require(package.get('registryType') == 'pypi' and package.get('identifier') == PACKAGE
            and package.get('version') == version and package.get('transport', {}).get('type') == 'stdio',
            'Registry PyPI reference or transport mismatch')
    import subprocess
    source_server = subprocess.check_output(['git', '-C', str(root), 'show', target['commit'] + ':server.json'], text=True)
    require(server == json.loads(source_server), 'Registry metadata differs from the tagged source')
    require(dist.resolve() != directory.resolve(), 'verified output must differ from release input')
    dist.mkdir(parents=True, exist_ok=True)
    require(not list(dist.iterdir()), 'verified package directory must be empty')
    for name in sorted(expected_names):
        shutil.copyfile(directory / name, dist / name)
    print('PASS explicit release target/main ancestry, commit/tree/tag, metadata, sizes and SHA-256')
    return manifest


def fetch_pypi_version(version):
    validate_version_tag(version, 'v' + version)
    request = Request('https://pypi.org/pypi/' + PACKAGE + '/' + version + '/json',
                      headers={'User-Agent': PACKAGE + '/release-verification'})
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        if error.code == 404:
            return None
        raise


def plan_pypi_upload(manifest, verified_dist, upload_dist, published, verify_only=False):
    """Already-published same-hash files are complete; conflicts always fail."""
    version = manifest['version']
    validate_version_tag(version, manifest['git_tag'])
    expected = {item['filename']: item for item in manifest['artifacts']}
    require(set(expected) == package_filenames(version), 'upload plan artifact filenames mismatch')
    verified_dist, upload_dist = Path(verified_dist), Path(upload_dist)
    require(verified_dist.resolve() != upload_dist.resolve(), 'upload staging must differ from verified package directory')
    require({path.name for path in verified_dist.iterdir()} == set(expected), 'verified directory contains extra or missing upload files')
    for name, item in expected.items():
        path = verified_dist / name
        require(path.is_file() and not path.is_symlink(), 'verified upload file must be regular')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'] and path.stat().st_size == item['size_bytes'],
                'verified package changed before upload planning: ' + name)
    remote = {}
    if published is not None:
        info = published.get('info', {})
        require(info.get('name') == PACKAGE and info.get('version') == version, 'PyPI returned a different package/version')
        urls = published.get('urls')
        require(isinstance(urls, list), 'PyPI version file list is invalid')
        for item in urls:
            name = item.get('filename')
            require(name in expected and name not in remote, 'PyPI has an unexpected or duplicate same-version file')
            require(item.get('digests', {}).get('sha256') == expected[name]['sha256']
                    and item.get('size') == expected[name]['size_bytes'], 'PyPI same-name bytes conflict: ' + name)
            remote[name] = item
    missing = sorted(set(expected) - set(remote))
    require(not verify_only or not missing, 'verify-only requires both frozen files already published on PyPI')
    upload_dist.mkdir(parents=True, exist_ok=True)
    require(not list(upload_dist.iterdir()), 'upload staging directory must be empty')
    for name in missing:
        shutil.copyfile(verified_dist / name, upload_dist / name)
    result = {'version': version, 'already_published': sorted(remote), 'missing': missing, 'upload_count': len(missing)}
    print(json.dumps(result))
    return result


def write_outputs(path, values):
    if path:
        with Path(path).open('a', encoding='utf-8') as stream:
            for key, value in values.items():
                stream.write(f'{key}={value}\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?')
    parser.add_argument('--version', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--repo', type=Path, default=ROOT, help='local source checkout used for Git identity validation')
    parser.add_argument('--expected-commit', help='previously resolved target commit; reject a moved tag')
    parser.add_argument('--validate-target', action='store_true', help='only resolve the annotated tag and prove its main ancestry')
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--pypi-upload-dir', type=Path, help='read exact PyPI version and stage only missing verified files')
    parser.add_argument('--verify-only', action='store_true', help='require matching public PyPI files without staging an upload')
    parser.add_argument('--github-output', type=Path, help='append validated target and upload count to GITHUB_OUTPUT')
    args = parser.parse_args(argv)
    require(not args.verify_only or args.pypi_upload_dir is not None, '--verify-only requires --pypi-upload-dir')
    if args.validate_target:
        require(args.directory is None and args.pypi_upload_dir is None, 'target validation does not consume release files')
        target = validate_target(args.version, args.tag, args.repo, args.expected_commit)
        write_outputs(args.github_output, target)
        print(json.dumps(target))
        return
    require(args.directory is not None, 'release input directory is required')
    manifest = verify(args.directory, args.version, args.tag, args.dist, args.repo, args.expected_commit)
    if args.pypi_upload_dir is not None:
        result = plan_pypi_upload(manifest, args.dist, args.pypi_upload_dir,
                                  fetch_pypi_version(args.version), args.verify_only)
        write_outputs(args.github_output, {'upload_count': result['upload_count']})


if __name__ == '__main__':
    main()

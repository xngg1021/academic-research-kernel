"""Inspect distribution contents and record auditable release identities."""
import argparse
import ast
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import zipfile

from _version import __version__
from qa import EXCLUDED_TREES, hygiene


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'academic-research-kernel'
SIDECARS = {'release-manifest.json', 'SHA256SUMS', 'server.json'}


def require(condition, message):
    """Publication gates must remain active under python -O."""
    if not condition:
        raise ValueError(message)


def validate_version_tag(version, tag):
    require(isinstance(version, str) and re.fullmatch(r'\d+\.\d+\.\d+', version),
            'version must be an explicit canonical stable X.Y.Z version')
    require(all(str(int(part)) == part for part in version.split('.')), 'version cannot contain leading zeroes')
    require(tag == 'v' + version, 'tag must equal v followed by the expected version')
    return version, tag


def git(root, *args):
    try:
        return subprocess.check_output(['git', '-C', str(root), *args], text=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as error:
        raise ValueError('Git source identity unavailable: ' + args[-1]) from error


def read_source_version(text):
    tree = ast.parse(text)
    versions = [node.value.value for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)]
    require(len(versions) == 1, 'source must declare exactly one literal __version__')
    return versions[0]


def validate_target(version, tag, root=ROOT, expected_commit=None, require_head=False):
    """Resolve the exact tag once, and prove its release source belongs to main."""
    validate_version_tag(version, tag)
    tag_ref = 'refs/tags/' + tag
    require(git(root, 'cat-file', '-t', tag_ref) == 'tag', 'release tag must be annotated')
    commit = git(root, 'rev-parse', tag_ref + '^{commit}')
    tree = git(root, 'rev-parse', commit + '^{tree}')
    require(re.fullmatch('[0-9a-f]{40}', commit) and re.fullmatch('[0-9a-f]{40}', tree), 'invalid Git source identity')
    if expected_commit is not None:
        require(commit == expected_commit, 'release tag moved or differs from the verified target commit')
    ancestry = subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor', commit, 'origin/main'],
                              capture_output=True, text=True)
    require(ancestry.returncode == 0, 'release tag commit must already be an ancestor of origin/main')
    require(read_source_version(git(root, 'show', commit + ':scripts/_version.py')) == version,
            'tag source version differs from the expected version')
    if require_head:
        require(git(root, 'rev-parse', 'HEAD') == commit, 'checkout HEAD differs from the release tag commit')
        require(not git(root, 'status', '--porcelain', '--untracked-files=normal'), 'release source must be clean')
    return {'version': version, 'tag': tag, 'commit': commit, 'tree': tree,
            'tag_object': git(root, 'rev-parse', tag_ref)}


def package_filenames(version):
    return {'academic_research_kernel-' + version + '-py3-none-any.whl',
            'academic_research_kernel-' + version + '.tar.gz'}


def inspect_artifact(path, version=None):
    version = __version__ if version is None else version
    validate_version_tag(version, 'v' + version)
    require(path.name in package_filenames(version), 'unexpected package filename or version: ' + path.name)
    require(path.is_file() and not path.is_symlink(), 'package must be a regular file')
    wheel = path.suffix == '.whl'
    if wheel:
        with zipfile.ZipFile(path) as archive:
            members = archive.namelist()
            require(len(members) == len(set(members)), 'duplicate archive member')
            require(all((info.external_attr >> 16) & 0o170000 != 0o120000 for info in archive.infolist()),
                    'archive links are not allowed')
            files = {name: archive.read(name) for name in members if not name.endswith('/')}
    else:
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            require(all(member.isfile() or member.isdir() for member in members), 'archive links or special files are not allowed')
            require(len(members) == len({member.name for member in members}), 'duplicate archive member')
            files = {member.name: archive.extractfile(member).read() for member in members if member.isfile()}
    for name, data in files.items():
        parts = PurePosixPath(name).parts
        require(not PurePosixPath(name).is_absolute() and '..' not in parts and '\\' not in name,
                'unsafe archive path: ' + name)
        require(not any(part in EXCLUDED_TREES or part.startswith('.env') for part in parts), 'excluded archive path: ' + name)
        require(not name.endswith(('.pyc', '.log')), 'excluded archive file: ' + name)
        require(not hygiene(data.decode('utf-8')), 'known secret/personal path in ' + name)
        if wheel:
            require(parts[0] == 'academic_research_kernel' or parts[0] == 'academic_research_kernel-' + version + '.dist-info',
                    'unexpected wheel root: ' + name)
            require(not any(part in {'skills', 'tests', 'scripts'} for part in parts), 'wheel runtime boundary violated: ' + name)
        else:
            require(parts[0] == 'academic_research_kernel-' + version, 'unexpected sdist root: ' + name)
    metadata_name = ('academic_research_kernel-' + version + '.dist-info/METADATA' if wheel
                     else 'academic_research_kernel-' + version + '/PKG-INFO')
    require(metadata_name in files, 'package metadata missing or at the wrong version path')
    info = BytesParser().parsebytes(files[metadata_name])
    for field, value in [('Name', PACKAGE), ('Version', version), ('Requires-Python', '<3.15,>=3.10'),
                         ('License-Expression', 'LicenseRef-Source-Lineage-1.0')]:
        require(info.get_all(field) == [value], 'package metadata mismatch: ' + field)
    require('mcp-name: io.github.xngg1021/academic-research-kernel' in info.get_payload(), 'MCP namespace declaration missing')
    version_name = ('academic_research_kernel/_version.py' if wheel
                    else 'academic_research_kernel-' + version + '/scripts/_version.py')
    require(version_name in files, 'internal runtime version file missing')
    require(read_source_version(files[version_name].decode('utf-8')) == version,
            'internal runtime version differs from the expected version')
    if not wheel:
        prefix = 'academic_research_kernel-' + version + '/'
        require(prefix + 'plugin.json' in files and prefix + 'server.json' in files,
                'sdist plugin or Registry version metadata missing')
        plugin = json.loads(files[prefix + 'plugin.json'])
        server = json.loads(files[prefix + 'server.json'])
        require(plugin.get('name') == 'academic-skills' and plugin.get('version') == version,
                'sdist plugin version mismatch')
        require(server.get('name') == 'io.github.xngg1021/academic-research-kernel'
                and server.get('version') == version, 'sdist Registry version mismatch')
        packages = server.get('packages')
        require(isinstance(packages, list) and len(packages) == 1
                and packages[0].get('identifier') == PACKAGE and packages[0].get('version') == version,
                'sdist Registry PyPI reference version mismatch')
    if wheel:
        require(len([name for name in files if '/schemas/' in name]) == 23, 'wheel schema inventory mismatch')
        require('academic_research_kernel/artifact-adapter-matrix.json' in files, 'wheel adapter matrix missing')
        require(all('academic_research_kernel/' + name in files for name in ('cli.py', 'mcp_server.py', 'recompute.py', 'ingestion/engine.py')),
                'wheel runtime files missing')
    return {'filename': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size_bytes': path.stat().st_size, 'file_count': len(files)}


def create_manifest(dist, version=None, tag=None, release=False, root=ROOT):
    version = __version__ if version is None else version
    tag = 'v' + version if tag is None else tag
    validate_version_tag(version, tag)
    require(read_source_version((root / 'scripts/_version.py').read_text(encoding='utf-8')) == version,
            'working source version differs from the expected version')
    commit, tree = git(root, 'rev-parse', 'HEAD'), git(root, 'rev-parse', 'HEAD^{tree}')
    dirty = bool(git(root, 'status', '--porcelain', '--untracked-files=normal'))
    epoch = git(root, 'show', '-s', '--format=%ct', 'HEAD')
    target = None
    if release:
        target = validate_target(version, tag, root, require_head=True)
        require(os.environ.get('SOURCE_DATE_EPOCH') == epoch, 'formal release requires SOURCE_DATE_EPOCH equal to the release commit timestamp')
    entries = list(dist.iterdir())
    require(all(entry.is_file() and not entry.is_symlink() for entry in entries), 'distribution directory contains non-regular entries')
    names = {entry.name for entry in entries}
    expected = package_filenames(version)
    require(names - SIDECARS == expected, 'distribution directory must contain exactly the expected wheel and sdist')
    artifacts = [inspect_artifact(dist / name, version) for name in sorted(expected)]
    manifest = {'package': PACKAGE, 'version': version,
                'source_commit': commit, 'source_tree': tree, 'source_dirty': dirty,
                'git_tag': tag if release else None, 'intended_tag': tag,
                'artifacts': artifacts, 'requires_python': '>=3.10,<3.15',
                'mcp': {'protocols': ['2026-07-28', '2024-11-05'], 'public_tool_count': 12},
                'plugin': {'name': 'academic-skills', 'version': version},
                'license_reference': 'LicenseRef-Source-Lineage-1.0',
                'build': {'backend': 'hatchling==1.29.0', 'source_date_epoch': epoch,
                          'uv_version': subprocess.check_output(['uv', '--version'], text=True).strip(),
                          'lock_sha256': hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest()},
                'publication': {'github': 'pending', 'pypi': 'pending', 'mcp_registry': 'pending'}}
    if target:
        manifest['tag_object'] = target['tag_object']
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', help='explicit expected package version (required for --release)')
    parser.add_argument('--tag', help='explicit expected annotated release tag (required for --release)')
    parser.add_argument('--release', action='store_true', help='require explicit --version/--tag, clean tagged HEAD on main, and SOURCE_DATE_EPOCH')
    args = parser.parse_args(argv)
    if args.release:
        require(args.version is not None and args.tag is not None, '--release requires explicit --version and --tag')
    manifest = create_manifest(args.dist, args.version, args.tag, args.release)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'manifest': args.output.name, 'artifacts': manifest['artifacts']}))


if __name__ == '__main__':
    main()

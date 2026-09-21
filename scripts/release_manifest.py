"""Inspect distribution contents and record auditable release identities."""
import argparse
from email.parser import BytesParser
import hashlib
from importlib import metadata
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import zipfile

from _version import __version__
from qa import EXCLUDED_TREES, hygiene


def inspect_artifact(path):
    if path.suffix == '.whl':
        with zipfile.ZipFile(path) as archive:
            files = {name: archive.read(name) for name in archive.namelist() if not name.endswith('/')}
    else:
        with tarfile.open(path) as archive:
            members = archive.getmembers()
            assert all(not p.issym() and not p.islnk() for p in members), 'archive links are not allowed'
            files = {p.name: archive.extractfile(p).read() for p in members if p.isfile()}
    for name, data in files.items():
        parts = PurePosixPath(name).parts
        assert not PurePosixPath(name).is_absolute() and '..' not in parts, name
        assert not any(p in EXCLUDED_TREES or p.startswith('.env') for p in parts), name
        assert not name.endswith(('.pyc', '.log')), name
        text = data.decode('utf-8')  # approved contents are all source text
        assert not hygiene(text), f'known secret/personal path in {name}'
        if path.suffix == '.whl':
            assert parts[0] == 'academic_research_kernel' or parts[0].endswith('.dist-info'), name
            assert not any(p in {'skills', 'tests', 'scripts'} for p in parts), name
    metadata_name = next(n for n in files if n.endswith('/METADATA' if path.suffix == '.whl' else '/PKG-INFO'))
    info = BytesParser().parsebytes(files[metadata_name])
    assert info['Name'] == 'academic-research-kernel'
    assert info['Version'] == __version__
    assert info['Requires-Python'] == '<3.15,>=3.10'
    assert info['License-Expression'] == 'LicenseRef-Source-Lineage-1.0'
    assert 'mcp-name: io.github.xngg1021/academic-research-kernel' in info.get_payload()
    if path.suffix == '.whl':
        assert len([n for n in files if '/schemas/' in n]) == 23
        assert 'academic_research_kernel/artifact-adapter-matrix.json' in files
        assert all('academic_research_kernel/' + p in files for p in ('cli.py', 'mcp_server.py', 'recompute.py', 'ingestion/engine.py'))
    return {'filename': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'size_bytes': path.stat().st_size, 'file_count': len(files)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--release', action='store_true', help='require clean HEAD tagged v2.0.0')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    def git(*argv):
        return subprocess.check_output(['git', '-C', str(root), *argv], text=True).strip()
    commit, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    dirty = bool(git('status', '--porcelain', '--untracked-files=normal'))
    tag = 'v' + __version__
    if args.release:
        assert not dirty, 'release source must be clean'
        assert git('rev-parse', tag + '^{commit}') == commit, 'release tag must identify HEAD'
    artifacts = [inspect_artifact(p) for p in sorted(args.dist.iterdir()) if p.name.endswith(('.whl', '.tar.gz'))]
    assert len(artifacts) == 2 and any(a['filename'].endswith('.whl') for a in artifacts)
    manifest = {'package': 'academic-research-kernel', 'version': __version__,
                'source_commit': commit, 'source_tree': tree, 'source_dirty': dirty,
                'git_tag': tag if args.release else None, 'intended_tag': tag,
                'artifacts': artifacts, 'requires_python': '>=3.10,<3.15',
                'mcp': {'protocols': ['2026-07-28', '2024-11-05'], 'public_tool_count': 12},
                'plugin': {'name': 'academic-skills', 'version': __version__},
                'license_reference': 'LicenseRef-Source-Lineage-1.0',
                'build': {'backend': 'hatchling==1.29.0', 'source_date_epoch': git('show', '-s', '--format=%ct', 'HEAD'),
                          'uv_version': subprocess.check_output(['uv', '--version'], text=True).strip(),
                          'lock_sha256': hashlib.sha256((root / 'uv.lock').read_bytes()).hexdigest()},
                'publication': {'github': 'pending', 'pypi': 'pending_external_authorization',
                                'mcp_registry': 'pending_pypi_and_authentication'}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'manifest': args.output.name, 'artifacts': artifacts}))


if __name__ == '__main__':
    main()

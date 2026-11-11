"""Fresh wheel/sdist installations outside the source tree, on all three OSes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile

from _version import __version__


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--expected-version', default=__version__, help='Expected package version')
    parser.add_argument('--uvx', action='store_true')
    parser.add_argument('--source-checks', action='store_true', help='Run full tests, static QA, executable fences and i18n in the unmodified extracted sdist')
    parser.add_argument('--cpu-torch', action='store_true', help='Include the optional CPU backend in raw sdist tests')
    parser.add_argument('--report', type=Path, help='Persist hashes and actual installed import paths')
    args = parser.parse_args()
    expected_version = args.expected_version
    ver_tuple = tuple(map(int, expected_version.split('.')))
    dist_dir = args.dist.resolve()
    require(dist_dir.is_dir(), f'distribution directory missing: {dist_dir}')
    sidecars = {'release-manifest.json', 'SHA256SUMS', 'server.json', '.gitignore'}
    all_entries = sorted(p for p in dist_dir.iterdir() if p.is_file() and p.name not in sidecars)
    artifacts = [p for p in all_entries if p.name.endswith(('.whl', '.tar.gz'))]
    require(len(artifacts) == 2 and len(all_entries) == 2, f'expected exactly 1 wheel and 1 sdist, got {[p.name for p in all_entries]}')
    require(sum(p.suffix == '.whl' for p in artifacts) == 1, 'exactly one wheel is required')
    require(sum(p.name.endswith('.tar.gz') for p in artifacts) == 1, 'exactly one sdist is required')
    uv = shutil.which('uv')
    require(bool(uv), 'uv is required by this acceptance driver')
    report = {'expected_version': expected_version, 'artifacts': [], 'source_checks': 'not_requested'}
    try:
        with tempfile.TemporaryDirectory(prefix='ark-package-') as directory:
            temp = Path(directory)
            smoke = temp / 'distribution_smoke.py'
            shutil.copyfile(Path(__file__).with_name('distribution_smoke.py'), smoke)
            env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'ARK_REPO', 'ARK_SDIST')}
            from release_manifest import inspect_artifact
            for i, artifact in enumerate(artifacts):
                inspect_artifact(artifact, expected_version)
                base_venv = temp / f'env-{i}-base'
                subprocess.run([uv, 'venv', '--python', sys.executable, str(base_venv)], check=True, env=env, cwd=temp)
                base_py = base_venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                subprocess.run([uv, 'pip', 'install', '--python', str(base_py), str(artifact)], check=True, env=env, cwd=temp)
                base_out = json.loads(subprocess.check_output([str(base_py), '-I', str(smoke), '--expected-version', expected_version], text=True, env=env, cwd=temp))
                require(base_out.get('installed_e2e') == 'PASS', 'base installed smoke did not report PASS')
                package_file = subprocess.check_output([str(base_py), '-I', '-c',
                    'import academic_research_kernel; print(academic_research_kernel.__file__)'], text=True, env=env, cwd=temp).strip()
                art_record = {
                    'filename': artifact.name,
                    'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
                    'python': str(base_py),
                    'import_path': package_file,
                    'installed_smoke': 'passed',
                    'research_extra_smoke': 'not_applicable' if ver_tuple < (2, 1, 0) else 'pending',
                }
                report['artifacts'].append(art_record)

                if ver_tuple >= (2, 1, 0):
                    res_venv = temp / f'env-{i}-research'
                    subprocess.run([uv, 'venv', '--python', sys.executable, str(res_venv)], check=True, env=env, cwd=temp)
                    res_py = res_venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                    subprocess.run([uv, 'pip', 'install', '--python', str(res_py), f'{artifact}[research]'], check=True, env=env, cwd=temp)
                    res_out = json.loads(subprocess.check_output([str(res_py), '-I', str(smoke), '--expected-version', expected_version, '--require-pdf'], text=True, env=env, cwd=temp))
                    require(res_out.get('installed_e2e') == 'PASS' and res_out.get('research', {}).get('pdf_smoke') == 'passed',
                            'research extra smoke did not pass PDF verification')
                    art_record['research_extra_smoke'] = 'passed'

                if args.uvx and artifact.suffix == '.whl':
                    isolated = dict(env, UV_CACHE_DIR=str(temp / 'uvx-cache'))
                    subprocess.run([str(base_py), '-I', str(smoke), '--expected-version', expected_version, '--', uv, 'tool', 'run', '--python', sys.executable,
                                    '--from', str(artifact), 'academic-research-kernel'], check=True, env=isolated, cwd=temp)
                    art_record['clean_cache_uvx'] = 'passed'

                if args.source_checks and artifact.name.endswith('.tar.gz'):
                    source = temp / 'source'
                    source.mkdir()
                    with tarfile.open(artifact) as archive:
                        archive.extractall(source, filter='data')
                    root, = source.iterdir()
                    # Dedicated clean venv for raw-sdist source checks so installed wheel/sdist
                    # never contaminates or masks missing files in the extracted source archive.
                    src_venv = temp / f'env-{i}-source-checks'
                    subprocess.run([uv, 'venv', '--python', sys.executable, str(src_venv)], check=True, env=env, cwd=temp)
                    src_py = src_venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
                    subprocess.run([uv, 'pip', 'install', '--python', str(src_py), '-r', str(root / 'requirements-qa.txt')],
                                   check=True, env=env, cwd=temp)
                    subprocess.run([uv, 'pip', 'install', '--python', str(src_py), '--no-build-isolation', '--no-deps', str(root)],
                                   check=True, env=env, cwd=temp)
                    if args.cpu_torch:
                        subprocess.run([uv, 'pip', 'install', '--python', str(src_py), 'torch>=2.5,<3',
                                        '--index-url', 'https://download.pytorch.org/whl/cpu'], check=True, env=env, cwd=temp)
                    raw_env = dict(env, ARK_REPO=str(root), ARK_SDIST=str(artifact),
                                   TEMP=str(temp), TMP=str(temp), PYTHONIOENCODING='utf-8')
                    for command in ([str(src_py), '-m', 'pytest', '-q', '-rs', 'tests', '--basetemp', str(temp / 'pytest')],
                                    [str(src_py), 'scripts/qa.py'],
                                    [str(src_py), 'scripts/i18n_sync.py', '--check'],
                                    [str(src_py), '-m', 'compileall', '-q', 'src', 'scripts', 'skills']):
                        subprocess.run(command, check=True, env=raw_env, cwd=root)
                    report['source_checks'] = 'passed'
                    report['source_archive'] = str(artifact)
                    report['raw_source_root'] = str(root)
    finally:
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS fresh wheel + sdist' + (' + clean-cache uvx' if args.uvx else ''))


if __name__ == '__main__':
    main()

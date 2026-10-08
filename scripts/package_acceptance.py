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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--uvx', action='store_true')
    parser.add_argument('--source-checks', action='store_true', help='Run full tests, static QA, executable fences and i18n in the unmodified extracted sdist')
    parser.add_argument('--cpu-torch', action='store_true', help='Include the optional CPU backend in raw sdist tests')
    parser.add_argument('--report', type=Path, help='Persist hashes and actual installed import paths')
    args = parser.parse_args()
    artifacts = sorted(args.dist.resolve().glob('*'))
    artifacts = [p for p in artifacts if p.name.endswith(('.whl', '.tar.gz'))]
    assert len(artifacts) == 2, artifacts
    assert sum(p.suffix == '.whl' for p in artifacts) == 1, 'exactly one wheel is required'
    assert sum(p.name.endswith('.tar.gz') for p in artifacts) == 1, 'exactly one sdist is required'
    uv = shutil.which('uv')
    assert uv, 'uv is required by this acceptance driver'
    report = {'artifacts': [], 'source_checks': 'not_requested'}
    with tempfile.TemporaryDirectory(prefix='ark-package-') as directory:
        temp = Path(directory)
        smoke = temp / 'distribution_smoke.py'
        shutil.copyfile(Path(__file__).with_name('distribution_smoke.py'), smoke)
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV', 'ARK_REPO', 'ARK_SDIST')}
        for i, artifact in enumerate(artifacts):
            venv = temp / f'env-{i}'
            subprocess.run([uv, 'venv', '--python', sys.executable, str(venv)], check=True, env=env, cwd=temp)
            python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            subprocess.run([uv, 'pip', 'install', '--python', str(python), str(artifact)], check=True, env=env, cwd=temp)
            subprocess.run([str(python), '-I', str(smoke)], check=True, env=env, cwd=temp)
            package_file = subprocess.check_output([str(python), '-I', '-c',
                'import academic_research_kernel; print(academic_research_kernel.__file__)'], text=True, env=env, cwd=temp).strip()
            report['artifacts'].append({'filename': artifact.name, 'sha256': hashlib.sha256(artifact.read_bytes()).hexdigest(),
                                        'python': str(python), 'import_path': package_file, 'installed_smoke': 'passed'})
            if args.uvx and artifact.suffix == '.whl':
                isolated = dict(env, UV_CACHE_DIR=str(temp / 'uvx-cache'))
                subprocess.run([str(python), '-I', str(smoke), '--', uv, 'tool', 'run', '--python', sys.executable,
                                '--from', str(artifact), 'academic-research-kernel'], check=True, env=isolated, cwd=temp)
                report['artifacts'][-1]['clean_cache_uvx'] = 'passed'
            if args.source_checks and artifact.name.endswith('.tar.gz'):
                source = temp / 'source'
                source.mkdir()
                with tarfile.open(artifact) as archive:
                    archive.extractall(source, filter='data')
                root, = source.iterdir()
                # All inputs, including fixtures and the QA dependency list, come
                # from this archive. Never copy missing files from the checkout.
                subprocess.run([uv, 'pip', 'install', '--python', str(python), '-r', str(root / 'requirements-qa.txt')],
                               check=True, env=env, cwd=temp)
                if args.cpu_torch:
                    subprocess.run([uv, 'pip', 'install', '--python', str(python), 'torch>=2.5,<3',
                                    '--index-url', 'https://download.pytorch.org/whl/cpu'], check=True, env=env, cwd=temp)
                raw_env = dict(env, ARK_REPO=str(root), ARK_SDIST=str(artifact),
                               TEMP=str(temp), TMP=str(temp), PYTHONIOENCODING='utf-8')
                for command in ([str(python), '-m', 'pytest', '-q', '-rs', 'tests', '--basetemp', str(temp / 'pytest')],
                                [str(python), 'scripts/qa.py'],
                                [str(python), 'scripts/i18n_sync.py', '--check'],
                                [str(python), '-m', 'compileall', '-q', 'src', 'scripts', 'skills']):
                    subprocess.run(command, check=True, env=raw_env, cwd=root)
                report['source_checks'] = 'passed'
                report['source_archive'] = str(artifact)
                report['raw_source_root'] = str(root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS fresh wheel + sdist' + (' + clean-cache uvx' if args.uvx else ''))


if __name__ == '__main__':
    main()

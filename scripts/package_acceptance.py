"""Fresh wheel/sdist installations outside the source tree, on all three OSes."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dist', type=Path, default=Path('dist'))
    parser.add_argument('--uvx', action='store_true')
    args = parser.parse_args()
    artifacts = sorted(args.dist.resolve().glob('*'))
    artifacts = [p for p in artifacts if p.name.endswith(('.whl', '.tar.gz'))]
    assert len(artifacts) == 2, artifacts
    uv = shutil.which('uv')
    assert uv, 'uv is required by this acceptance driver'
    with tempfile.TemporaryDirectory(prefix='ark-package-') as directory:
        temp = Path(directory)
        smoke = temp / 'distribution_smoke.py'
        shutil.copyfile(Path(__file__).with_name('distribution_smoke.py'), smoke)
        env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
        for i, artifact in enumerate(artifacts):
            venv = temp / f'env-{i}'
            subprocess.run([uv, 'venv', '--python', sys.executable, str(venv)], check=True, env=env, cwd=temp)
            python = venv / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
            subprocess.run([uv, 'pip', 'install', '--python', str(python), str(artifact)], check=True, env=env, cwd=temp)
            subprocess.run([str(python), '-I', str(smoke)], check=True, env=env, cwd=temp)
            if args.uvx and artifact.suffix == '.whl':
                isolated = dict(env, UV_CACHE_DIR=str(temp / 'uvx-cache'))
                subprocess.run([str(python), '-I', str(smoke), '--', uv, 'tool', 'run', '--python', sys.executable,
                                '--from', str(artifact), 'academic-research-kernel'], check=True, env=isolated, cwd=temp)
    print('PASS fresh wheel + sdist' + (' + clean-cache uvx' if args.uvx else ''))


if __name__ == '__main__':
    main()

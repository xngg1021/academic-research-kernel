"""Fail closed before publication; copy only manifest-bound package bytes."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def verify(directory):
    manifest = json.loads((directory / 'release-manifest.json').read_text(encoding='utf-8'))
    assert manifest['package'] == 'academic-research-kernel' and manifest['version'] == '2.0.0'
    assert manifest['git_tag'] == 'v2.0.0' and manifest['source_dirty'] is False
    for key, ref in [('source_commit', 'HEAD'), ('source_tree', 'HEAD^{tree}')]:
        assert manifest[key] == subprocess.check_output(['git', 'rev-parse', ref], text=True).strip()
    artifacts = manifest['artifacts']
    assert len(artifacts) == 2
    assert {a['filename'] for a in artifacts} == {'academic_research_kernel-2.0.0-py3-none-any.whl', 'academic_research_kernel-2.0.0.tar.gz'}
    for artifact in artifacts:
        path = directory / artifact['filename']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact['sha256']
        assert path.stat().st_size == artifact['size_bytes']
    dist = Path('dist')
    dist.mkdir(exist_ok=True)
    assert not list(dist.iterdir()), 'publication directory must be empty'
    for artifact in artifacts:
        shutil.copyfile(directory / artifact['filename'], dist / artifact['filename'])
    print('PASS release commit/tree/tag and wheel/sdist SHA-256')


if __name__ == '__main__':
    verify(Path(sys.argv[1]))

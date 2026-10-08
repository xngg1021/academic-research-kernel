"""Optimization cannot disable installed-version or real stdio failure gates.

The tiny package is an isolated installation-environment fixture, not a product
acceptance result. Only the external CLI is faulty; distribution_smoke executes
unchanged in a real subprocess with -I -O and no network or user package cache.
"""
import json
import os
from pathlib import Path
import subprocess
import venv

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def installed_fixture(tmp_path):
    prefix = tmp_path / 'installed-env'
    venv.EnvBuilder(with_pip=False).create(prefix)
    python = prefix / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    site_packages = Path(subprocess.check_output(
        [str(python), '-I', '-c', 'import sysconfig; print(sysconfig.get_path("purelib"))'],
        text=True, encoding='utf-8').strip())
    package = site_packages / 'academic_research_kernel'
    package.mkdir()
    # The smoke verifier needs only this import interface to construct requests.
    # No numerical result, product CLI response, or protocol response is mocked.
    (package / 'ingestion.py').write_text(
        'class ArtifactEnvelope:\n'
        '    @classmethod\n'
        '    def create(cls, **kwargs):\n'
        '        result = cls()\n'
        '        result.data = kwargs\n'
        '        return result\n'
        '    def to_dict(self):\n'
        '        return self.data\n', encoding='utf-8')
    return python, package


@pytest.mark.parametrize(('installed_version', 'failure'), [
    ('2.0.0', 'installed version mismatch'),
    ('2.0.1', 'missing replies or non-silent notifications'),
])
def test_optimized_smoke_rejects_wrong_version_and_empty_stdio(installed_fixture, tmp_path,
                                                              installed_version, failure):
    python, package = installed_fixture
    (package / '__init__.py').write_text('__version__ = ' + repr(installed_version) + '\n', encoding='utf-8')
    calls = tmp_path / 'external-calls.jsonl'
    external_cli = tmp_path / 'faulty_external_cli.py'
    external_cli.write_text(
        'import json, sys\n'
        'from pathlib import Path\n'
        f'with Path({str(calls)!r}).open("a", encoding="utf-8") as log:\n'
        '    log.write(json.dumps(sys.argv[1:]) + "\\n")\n'
        'if sys.argv[1] == "--version":\n'
        f'    print({installed_version!r})\n'
        'elif sys.argv[1] == "doctor":\n'
        f'    print(json.dumps({{"status": "ok", "package_location": {str(package / "__init__.py")!r}, '
        '"python": {"executable": sys.executable}, "mcp": {"tool_count": 12}, '
        '"external_services": {"OPENALEX_API_KEY": "configured"}}))\n'
        'elif sys.argv[1] == "mcp":\n'
        '    sys.stdin.read()\n'  # Broken external process exits cleanly with zero replies.
        'else:\n'
        '    raise SystemExit(2)\n', encoding='utf-8')
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
    environment.update(TEMP=str(tmp_path), TMP=str(tmp_path))
    result = subprocess.run(
        [str(python), '-I', '-O', str(ROOT / 'scripts/distribution_smoke.py'),
         '--expected-version', '2.0.1', '--', str(python), str(external_cli)],
        capture_output=True, text=True, encoding='utf-8', env=environment,
        cwd=tmp_path, timeout=60)
    assert result.returncode != 0
    assert failure in result.stderr, result.stderr
    assert '"installed_e2e": "PASS"' not in result.stdout
    if installed_version == '2.0.0':
        assert not calls.exists(), 'wrong installed version must fail before executing the external CLI'
    else:
        assert [json.loads(line)[0] for line in calls.read_text(encoding='utf-8').splitlines()] == [
            '--version', 'doctor', 'mcp']

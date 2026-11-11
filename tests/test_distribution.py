"""Distribution regressions that can run in the source correctness matrix."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_version_mirrors():
    spec = importlib.util.spec_from_file_location('product_version', ROOT / 'scripts/_version.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__version__ == '2.4.1'
    assert json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))['version'] == module.__version__
    server = json.loads((ROOT / 'server.json').read_text(encoding='utf-8'))
    assert server['version'] == server['packages'][0]['version'] == module.__version__
    sys.path.insert(0, str(ROOT / 'scripts'))
    import mcp_server
    assert mcp_server.process_message({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize'})['result']['serverInfo']['version'] == module.__version__


def test_windows_command_quoting_preserves_interpreter_and_spaces():
    sys.path.insert(0, str(ROOT / 'skills/cross-review-five/scripts'))
    from adapters import CommandReviewerAdapter
    assert CommandReviewerAdapter._split_command('"C:\\Program Files\\Python\\python.exe" "helper with spaces.py" "out file.md"', windows=True) == [
        'C:\\Program Files\\Python\\python.exe', 'helper with spaces.py', 'out file.md']


def test_plugin_uses_locked_isolated_runtime():
    config = json.loads((ROOT / 'mcp.json').read_text(encoding='utf-8'))['mcpServers']['academic-skills']
    assert config['command'] == 'uv'
    assert '--frozen' in config['args'] and '--no-editable' in config['args']
    assert config['env']['UV_PROJECT_ENVIRONMENT'].startswith('${PLUGIN_DATA}/')


def test_current_official_registry_metadata_schema():
    from jsonschema import Draft7Validator
    schema = json.loads((ROOT / 'tests/fixtures/mcp-registry-server.schema.json').read_text(encoding='utf-8'))
    Draft7Validator(schema).validate(json.loads((ROOT / 'server.json').read_text(encoding='utf-8')))
    assert 'mcp-name: io.github.xngg1021/academic-research-kernel' in (ROOT / 'README.md').read_text(encoding='utf-8')


def test_standalone_copied_skills_import_and_execute_outside_repo(tmp_path):
    """Copied skills must import and run in an isolated subprocess outside ROOT without ROOT/scripts on sys.path."""
    clean_env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'VIRTUAL_ENV')}
    skills_to_probe = (
        ('research-object-identity', 'provenance.py', ['--help']),
        ('claim-evidence-graph', 'graph.py', ['--help']),
        ('decision-ledger', 'ledger.py', ['--help']),
        ('academic-writing', 'pre_submission_linter.py', ['--help']),
        ('academic-source-verification', 'verify_work.py', ['--help']),
        ('retraction-watch', 'watch.py', ['--self-test']),
    )
    for skill_name, script_name, cli_args in skills_to_probe:
        dest = tmp_path / skill_name
        shutil.copytree(ROOT / 'skills' / skill_name, dest)
        script_path = dest / 'scripts' / script_name
        probe = (
            'import importlib.util, pathlib, sys\n'
            f'repo_root = pathlib.Path({str(ROOT)!r}).resolve()\n'
            'bad = [p for p in sys.path if p and (pathlib.Path(p).resolve() == repo_root or any(pathlib.Path(p).resolve().is_relative_to(repo_root / s) for s in ("src", "scripts", "skills")))]\n'
            'assert not bad, bad\n'
            f'sys.path.insert(0, {str(dest / "scripts")!r})\n'
            f'spec = importlib.util.spec_from_file_location("standalone_mod", {str(script_path)!r})\n'
            'mod = importlib.util.module_from_spec(spec)\n'
            'sys.modules["standalone_mod"] = mod\n'
            'spec.loader.exec_module(mod)\n'
        )
        res_imp = subprocess.run([sys.executable, '-I', '-c', probe], cwd=str(tmp_path), env=clean_env, capture_output=True, text=True, timeout=30)
        assert res_imp.returncode == 0, f'{skill_name}/{script_name} isolated import failed: {res_imp.stderr}'
        res_cli = subprocess.run([sys.executable, '-I', str(script_path), *cli_args], cwd=str(tmp_path), env=clean_env, capture_output=True, text=True, timeout=30)
        assert res_cli.returncode == 0, f'{skill_name}/{script_name} isolated CLI failed: {res_cli.stderr}'

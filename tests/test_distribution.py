"""Distribution regressions that can run in the source correctness matrix."""
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_version_mirrors():
    spec = importlib.util.spec_from_file_location('product_version', ROOT / 'scripts/_version.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.__version__ == '2.0.0'
    assert json.loads((ROOT / 'plugin.json').read_text(encoding='utf-8'))['version'] == module.__version__
    server = json.loads((ROOT / 'server.json').read_text(encoding='utf-8'))
    assert server['version'] == server['packages'][0]['version'] == module.__version__
    sys.path.insert(0, str(ROOT / 'scripts'))
    import mcp_server
    assert mcp_server.process_message({'method': 'initialize'})['result']['serverInfo']['version'] == module.__version__


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

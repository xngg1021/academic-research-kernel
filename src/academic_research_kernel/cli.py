"""Small installation/stdio boundary; no research workflow orchestration."""
import argparse
import importlib
from importlib import metadata, resources, util
import json
import os
import platform
import sys

from ._version import __version__

REQUIRED = ('jsonschema', 'numpy', 'scipy', 'statsmodels')
OPTIONAL = ('sympy', 'matplotlib', 'sklearn', 'networkx', 'lifelines', 'arch', 'pingouin', 'torch', 'cupy')
SERVICES = ('OPENALEX_API_KEY', 'UNPAYWALL_EMAIL', 'SCITE_API_KEY', 'WOS_API_KEY',
            'SCOPUS_API_KEY', 'DIMENSIONS_API_KEY')


def doctor():
    """Offline installation check. Values of external configuration never leave here."""
    report = {'version': __version__, 'python': {'executable': sys.executable,
              'version': platform.python_version()}, 'package_location': str(resources.files('academic_research_kernel')),
              'required_dependencies': {}, 'optional_dependencies': {},
              'external_services': {key: 'configured' if os.environ.get(key) else 'unconfigured (optional)' for key in SERVICES},
              'errors': []}
    for name in REQUIRED:
        try:
            importlib.import_module(name)
            report['required_dependencies'][name] = metadata.version(name)
        except Exception as exc:
            report['required_dependencies'][name] = 'unavailable'
            report['errors'].append(f'{name}: {type(exc).__name__}')
    for name in OPTIONAL:
        report['optional_dependencies'][name] = 'available' if util.find_spec(name) else 'not installed (optional)'
    try:
        from jsonschema import Draft202012Validator
        schemas = list(resources.files('academic_research_kernel').joinpath('schemas').iterdir())
        schemas = [p for p in schemas if p.name.endswith('.json')]
        if len(schemas) != 23:
            raise ValueError('incomplete schema inventory')
        for path in schemas:
            Draft202012Validator.check_schema(json.loads(path.read_text(encoding='utf-8')))
        report['schema_resources'] = {'status': 'ok', 'count': len(schemas)}
        matrix = resources.files('academic_research_kernel').joinpath('artifact-adapter-matrix.json')
        json.loads(matrix.read_text(encoding='utf-8'))
    except Exception as exc:
        report['schema_resources'] = {'status': 'error'}
        report['errors'].append(f'resources: {type(exc).__name__}')
    try:
        from . import mcp_server
        report['mcp'] = {'importable': True, 'tool_count': len(mcp_server.TOOLS)}
        if len(mcp_server.TOOLS) != 12:
            raise ValueError('unexpected tool count')
        pct = mcp_server.handle_tool_call('academic_check_percentage', {'count': 10, 'percent': 50, 'sample_size': 20})
        if pct.get('consistent') is not True:
            raise ValueError('statistics check failed')
    except Exception as exc:
        report['mcp'] = {'importable': False}
        report['errors'].append(f'MCP: {type(exc).__name__}')
    report['status'] = 'ok' if not report['errors'] else 'error'
    return report


def main(argv=None):
    if not (3, 10) <= sys.version_info[:2] < (3, 15):
        print('academic-research-kernel requires Python 3.10–3.14; use uvx --python 3.12 academic-research-kernel.', file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=__version__)
    commands = parser.add_subparsers(dest='command', required=True)
    check = commands.add_parser('doctor', help='offline environment diagnostic')
    check.add_argument('--json', action='store_true', help='machine-readable JSON')
    commands.add_parser('mcp', help='serve the existing 12 MCP tools over stdio')
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        report = doctor()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f'academic-research-kernel {__version__}: {report["status"]}')
            for key, value in report.items():
                if key not in ('version', 'status'):
                    print(f'{key}: {json.dumps(value, ensure_ascii=False)}')
        return 0 if report['status'] == 'ok' else 1
    try:
        from .mcp_server import main as serve
    except ImportError:
        print('Incomplete runtime installation. Run academic-research-kernel doctor.', file=sys.stderr)
        return 1
    serve()
    return 0

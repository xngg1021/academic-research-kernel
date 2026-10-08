"""Deterministic research utilities; semantic reading is supplied by your local agent."""
import argparse
import importlib
from importlib import metadata, resources, util
import json
import os
import platform
import sys
from pathlib import Path
import shutil

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
        expected_schemas = {
            'artifact-ingestion-receipt', 'claim-evidence-graph', 'computation-artifact', 'compute-receipt',
            'cross-review-artifact', 'decision-ledger-receipt', 'evidence-receipt', 'ingestion-kernel-state',
            'legacy-academic-evidence', 'lineage-receipt', 'literature-analysis-artifact', 'literature-delta',
            'opaque-manuscript', 'quantitative-audit', 'reproduction-receipt', 'research-artifact-envelope',
            'research-object', 'retraction-delta', 'review-finding', 'review-panel-spec', 'review-result',
            'review-run-receipt', 'systematic-review-artifact', 'research-documents', 'paper-extraction', 'paper-comparison'}
        if {p.name for p in schemas} != {n + '.schema.json' for n in expected_schemas}:
            raise ValueError('incomplete schema inventory')
        for path in schemas:
            Draft202012Validator.check_schema(json.loads(path.read_text(encoding='utf-8')))
        report['schema_resources'] = {'status': 'ok', 'count': len(schemas)}
        matrix = resources.files('academic_research_kernel').joinpath('artifact-adapter-matrix.json')
        json.loads(matrix.read_text(encoding='utf-8'))
        skill = resources.files('academic_research_kernel').joinpath('skills/paper-research/SKILL.md')
        if not skill.read_text(encoding='utf-8').strip():
            raise ValueError('portable paper-research skill missing')
        report['research'] = {'semantic_producer': 'local agent required',
                              'pdf_parser': metadata.version('pypdf') if util.find_spec('pypdf') else 'not installed; use [research]',
                              'portable_skill': 'available', 'schema_count': 3}
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
    research = commands.add_parser('research', help='prepare/read/verify/recompute/report with a local agent')
    steps = research.add_subparsers(dest='step', required=True)
    prep = steps.add_parser('prepare', help='acquire and locate raw materials; agent continues semantic reading')
    prep.add_argument('input')
    prep.add_argument('--project', required=True)
    finish = steps.add_parser('finish', help='validate an agent candidate, recompute, persist and report')
    finish.add_argument('--project', required=True)
    finish.add_argument('--candidate', required=True)
    comparison = steps.add_parser('compare', help='validate a sourced comparison supplied by the local agent')
    comparison.add_argument('left')
    comparison.add_argument('right')
    comparison.add_argument('--analysis', required=True)
    comparison.add_argument('--output', required=True)
    skill = steps.add_parser('skill', help='export the installed portable workflow and canonical contracts')
    skill.add_argument('--output', required=True)
    replay = steps.add_parser('replay', help='offline deterministic replay of a saved semantic snapshot')
    replay.add_argument('--project', required=True)
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
    if args.command == 'research':
        try:
            if args.step == 'prepare':
                from .research.sources import prepare
                result = prepare(args.input, args.project)
            elif args.step in ('finish', 'replay'):
                from .research.analysis import finish
                candidate = args.candidate if args.step == 'finish' else str(Path(args.project) / 'candidate.json')
                result = finish(args.project, candidate)
            elif args.step == 'compare':
                from .research.analysis import compare
                result = compare(args.left, args.right, args.analysis, args.output)
            else:
                target = Path(args.output).resolve()
                target.mkdir(parents=True, exist_ok=True)
                root = resources.files('academic_research_kernel')
                source = root.joinpath('skills/paper-research')
                def copy_resource(src, dst):
                    dst.mkdir(parents=True, exist_ok=True)
                    for item in src.iterdir():
                        if item.is_dir():
                            copy_resource(item, dst / item.name)
                        else:
                            (dst / item.name).write_bytes(item.read_bytes())
                copy_resource(source, target)
                for name in ('paper-extraction', 'paper-comparison', 'research-documents'):
                    p = target / 'references' / (name + '.schema.json')
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_bytes(root.joinpath('schemas/' + p.name).read_bytes())
                result = {'skill': str(target / 'SKILL.md'), 'version': __version__, 'semantic_producer': 'your local agent'}
            print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return 0
        except (ValueError, OSError, KeyError, ImportError) as exc:
            print(json.dumps({'status': 'error', 'step': args.step, 'reason': str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 1
    try:
        from .mcp_server import main as serve
    except ImportError:
        print('Incomplete runtime installation. Run academic-research-kernel doctor.', file=sys.stderr)
        return 1
    serve()
    return 0

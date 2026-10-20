"""Deterministic research utilities; semantic reading is supplied by your local agent."""
import argparse
import importlib
from importlib import metadata, resources, util
import json
import math
import os
import platform
import sys
from pathlib import Path
import shutil

from ._version import __version__

REQUIRED = ('jsonschema',)
STATS = ('numpy', 'scipy', 'statsmodels')
OPTIONAL = ('sympy', 'matplotlib', 'sklearn', 'networkx', 'lifelines', 'arch', 'pingouin', 'torch', 'cupy')
SERVICES = ('OPENALEX_API_KEY', 'UNPAYWALL_EMAIL', 'SCITE_API_KEY', 'WOS_API_KEY',
            'SCOPUS_API_KEY', 'DIMENSIONS_API_KEY')


def _error_hint(step: str, reason: str) -> str:
    lower = reason.lower()
    if 'signature missing' in lower or 'not a pdf' in lower or ('pdf' in lower and 'landing' in lower):
        return 'File is not a valid PDF (e.g. HTML landing or error page); provide a real PDF or full-text HTML/XML file'
    if 'budget' in lower or 'too large' in lower or (
        'exceeded' in lower and any(k in lower for k in ('size', 'page', 'zip', 'archive', 'content', 'file'))
    ):
        return 'Input exceeds size or page budget; provide a smaller file or extract relevant sections'
    if 'pypdf' in lower or 'fonttools' in lower or 'research extra' in lower or 'academic-research-kernel[research]' in lower or (
        'pdf' in lower and any(k in lower for k in ('install', 'require', 'unavailable', 'support'))
    ):
        return 'Install PDF support with: pip install "academic-research-kernel[research]"'
    if 'stale' in lower or 'fingerprint' in lower or 'changed' in lower:
        return 'Materials changed; re-run: academic-research-kernel research prepare <input> --project <dir>'
    if 'semantic producer' in lower or 'candidate' in lower or 'schema' in lower:
        return 'Have your Agent read the prepared materials using skills/paper-research/SKILL.md and pass --candidate'
    return f'Check inputs for step "{step}" or run: academic-research-kernel doctor'


def _package_root():
    for pkg in ('academic_research_kernel', __package__):
        if not pkg:
            continue
        try:
            candidate = resources.files(pkg)
            if candidate.joinpath('schemas').is_dir():
                return candidate
        except Exception:
            continue
    pkg_dir = Path(__file__).resolve().parent
    if (pkg_dir / 'schemas').is_dir():
        return pkg_dir
    return pkg_dir.parents[1]


def _safe_find_spec(name: str) -> bool:
    try:
        return util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def _safe_importable(name: str) -> bool:
    if not _safe_find_spec(name):
        return False
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _load_bundled_module(mod_name: str, repo_rel_path: str):
    for pkg in (__package__, 'academic_research_kernel'):
        if not pkg:
            continue
        try:
            return importlib.import_module(f'{pkg}.{mod_name}')
        except ImportError:
            continue
    repo_file = Path(__file__).resolve().parents[2] / repo_rel_path
    spec = util.spec_from_file_location(f'academic_research_kernel.{mod_name}', repo_file)
    if spec is None or spec.loader is None:
        raise ImportError(f'Unable to load bundled module {mod_name}')
    module = util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def doctor():
    """Offline installation check. Values of external configuration never leave here."""
    root = _package_root()
    report = {'version': __version__, 'python': {'executable': sys.executable,
              'version': platform.python_version()}, 'package_location': str(root),
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
    for name in STATS:
        if _safe_find_spec(name):
            try:
                report['required_dependencies'][name] = metadata.version(name)
            except Exception:
                report['required_dependencies'][name] = 'available'
        else:
            report['required_dependencies'][name] = 'not installed (install numpy, scipy, and statsmodels for statistical recomputation)'
    for name in OPTIONAL:
        report['optional_dependencies'][name] = 'available' if _safe_find_spec(name) else 'not installed (optional)'
    try:
        from jsonschema import Draft202012Validator
        schemas = list(root.joinpath('schemas').iterdir())
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
        matrix = root.joinpath('artifact-adapter-matrix.json')
        try:
            matrix_text = matrix.read_text(encoding='utf-8')
        except FileNotFoundError:
            matrix_text = root.joinpath('docs/artifact-adapter-matrix.json').read_text(encoding='utf-8')
        json.loads(matrix_text)
        skill = root.joinpath('skills/paper-research/SKILL.md')
        try:
            skill_text = skill.read_text(encoding='utf-8')
        except FileNotFoundError:
            repo_skill = Path(__file__).resolve().parents[2] / 'skills' / 'paper-research' / 'SKILL.md'
            skill_text = repo_skill.read_text(encoding='utf-8')
        if not skill_text.strip():
            raise ValueError('portable paper-research skill missing')
        portable_skill_status = 'available'
    except Exception as exc:
        report['schema_resources'] = {'status': 'error'}
        report['errors'].append(f'resources: {type(exc).__name__}')
        portable_skill_status = 'unavailable'
    has_pypdf = _safe_importable('pypdf')
    has_fonttools = _safe_importable('fontTools') or _safe_importable('fonttools')
    pdf_ready = has_pypdf and has_fonttools and portable_skill_status == 'available'
    try:
        pypdf_ver = metadata.version('pypdf') if has_pypdf else 'not installed; use [research]'
    except Exception:
        pypdf_ver = 'available' if has_pypdf else 'not installed; use [research]'
    try:
        ft_ver = metadata.version('fonttools') if has_fonttools else 'not installed; use [research]'
    except Exception:
        ft_ver = 'available' if has_fonttools else 'not installed; use [research]'
    report['research'] = {
        'semantic_producer': 'local agent required',
        'pdf_parser': pypdf_ver,
        'font_decoder': ft_ver,
        'pdf_ready': pdf_ready,
        'portable_skill': portable_skill_status,
        'schema_count': 3,
    }
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
    report['readiness'] = {
        'core_verification_and_mcp': 'ready' if report['status'] == 'ok' else 'error',
        'pdf_reading': 'ready' if pdf_ready else 'not ready (install academic-research-kernel[research] to parse PDF files)',
        'local_agent': 'connect your Agent (Claude Code, Cursor, Codex, Gemini CLI, or Hermes) to run paper-research',
    }
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
    verify_cmd = commands.add_parser('verify-source', help='normalize scholarly identifiers and verify OpenAlex/Crossref records')
    verify_cmd.add_argument('identifier', help='DOI, arXiv ID, PMID, OpenAlex ID, or URL')
    verify_cmd.add_argument('--openalex-json', help='offline OpenAlex work JSON file')
    verify_cmd.add_argument('--crossref-json', help='offline Crossref message JSON file')
    verify_cmd.add_argument('--offline', action='store_true', help='disable network requests')
    verify_cmd.add_argument('--normalize-only', action='store_true', help='only normalize identifier without querying metadata')
    bib_cmd = commands.add_parser('bibliography', help='convert between BibTeX, RIS, CSL-JSON, Crossref, and OpenAlex records')
    bib_cmd.add_argument('--from', dest='source_format', required=True, choices=['bibtex', 'ris', 'csl', 'crossref', 'openalex'])
    bib_cmd.add_argument('--to', dest='target_format', required=True, choices=['bibtex', 'ris', 'csl', 'canonical'])
    bib_cmd.add_argument('--input', required=True, help='input file path')
    meta_cmd = commands.add_parser('meta-analyze', help='run fixed/random-effects pooling, heterogeneity, and publication-bias checks')
    meta_cmd.add_argument('--input', required=True, help='JSON file with {"studies": [{"yi": float, "vi": float, ...}]}')
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
    if args.command in ('verify-source', 'bibliography', 'meta-analyze'):
        try:
            if args.command == 'verify-source':
                norm_mod = _load_bundled_module('normalize_identifier', 'skills/academic-source-verification/scripts/normalize_identifier.py')
                ver_mod = _load_bundled_module('verify_work', 'skills/academic-source-verification/scripts/verify_work.py')
                norm = norm_mod.normalize_identifier(args.identifier)
                if args.normalize_only or norm['type'] != 'doi':
                    print(json.dumps(norm, ensure_ascii=False, indent=2))
                    return 0 if norm['type'] != 'unknown' else 1
                doi = norm['value']
                sources_out, parsed = {}, []
                explicit_file_failed = False
                for s_name, j_path, live_fn, parse_fn in (
                    ('openalex', args.openalex_json, ver_mod.fetch_openalex, ver_mod.parse_openalex_work),
                    ('crossref', args.crossref_json, ver_mod.fetch_crossref, ver_mod.parse_crossref_work),
                ):
                    if j_path:
                        try:
                            w = parse_fn(json.loads(Path(j_path).read_text(encoding='utf-8')))
                            sources_out[s_name] = {'status': 'ok', 'mode': 'offline-file', 'work': w}
                            parsed.append(w)
                        except Exception as exc:
                            explicit_file_failed = True
                            sources_out[s_name] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
                    elif args.offline:
                        sources_out[s_name] = {'status': 'skipped', 'reason': 'offline mode; no input file; no result inferred'}
                    else:
                        try:
                            w = parse_fn(live_fn(doi))
                            sources_out[s_name] = {'status': 'ok', 'mode': 'live', 'work': w}
                            parsed.append(w)
                        except Exception as exc:
                            sources_out[s_name] = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
                comparison = ver_mod.compare_works(parsed, target_doi=doi) if parsed else None
                payload = {
                    'normalized': norm,
                    'target_doi': doi,
                    'sources': sources_out,
                    'comparison': comparison,
                }
                print(json.dumps(payload, ensure_ascii=False, indent=2))
                if explicit_file_failed:
                    return 1
                return 0 if (args.offline or any(s['status'] == 'ok' for s in sources_out.values())) else 1
            if args.command == 'bibliography':
                interop_mod = _load_bundled_module('interop', 'skills/literature-analysis/scripts/interop.py')
                raw_text = Path(args.input).read_text(encoding='utf-8')
                sf = args.source_format
                if sf == 'bibtex':
                    works = interop_mod.from_bibtex(raw_text)
                elif sf == 'ris':
                    works = interop_mod.from_ris(raw_text)
                elif sf == 'csl':
                    data = json.loads(raw_text)
                    items = data if isinstance(data, list) else [data]
                    works = [interop_mod.from_csl_json(x) for x in items]
                elif sf == 'crossref':
                    data = json.loads(raw_text)
                    items = data if isinstance(data, list) else [data.get('message', data) if isinstance(data, dict) else data]
                    works = [interop_mod.from_crossref_json(x) for x in items]
                else:
                    data = json.loads(raw_text)
                    items = data if isinstance(data, list) else (data.get('results', [data]) if isinstance(data, dict) else [data])
                    works = [interop_mod.from_openalex_json(x) for x in items]
                tf = args.target_format
                if tf == 'bibtex':
                    print('\n\n'.join(interop_mod.to_bibtex(w) for w in works))
                elif tf == 'ris':
                    print('\n\n'.join(interop_mod.to_ris(w) for w in works))
                elif tf == 'csl':
                    print(json.dumps([interop_mod.to_csl_json(w) for w in works], ensure_ascii=False, indent=2))
                else:
                    from dataclasses import asdict
                    print(json.dumps([asdict(w) for w in works], ensure_ascii=False, indent=2))
                return 0
            if args.command == 'meta-analyze':
                from dataclasses import asdict
                meta_mod = _load_bundled_module('meta_core', 'skills/systematic-review-meta-analysis/scripts/meta_core.py')
                data = json.loads(Path(args.input).read_text(encoding='utf-8'))
                if isinstance(data, list):
                    studies = data
                elif isinstance(data, dict):
                    studies = data.get('studies', [])
                else:
                    raise ValueError('meta-analyze input must be a JSON object with "studies" or a JSON array')
                if not isinstance(studies, list) or not studies:
                    raise ValueError('meta-analyze requires at least one study entry')
                yi, vi = [], []
                for idx, s in enumerate(studies):
                    if not isinstance(s, dict) or 'yi' not in s or 'vi' not in s:
                        raise ValueError(f'study[{idx}] must be an object with "yi" and "vi"')
                    raw_y, raw_v = s['yi'], s['vi']
                    if isinstance(raw_y, bool) or isinstance(raw_v, bool):
                        raise ValueError(f'study[{idx}] yi/vi must be numbers, not booleans')
                    yv, vv = float(raw_y), float(raw_v)
                    if not (math.isfinite(yv) and math.isfinite(vv)) or vv <= 0:
                        raise ValueError(f'study[{idx}] requires finite yi and positive finite vi')
                    yi.append(yv)
                    vi.append(vv)
                fixed = asdict(meta_mod.pool_fixed(yi, vi))
                random_dl = asdict(meta_mod.pool_random(yi, vi))
                loo = [asdict(r) for r in meta_mod.leave_one_out(yi, vi)] if len(yi) >= 2 else []
                bias = None
                if len(yi) >= 3:
                    try:
                        intercept, t_val, p_val = meta_mod.egger_test(yi, vi)
                        egger_out = {'status': 'ok', 'intercept': intercept, 't': t_val if math.isfinite(t_val) else None, 'p': p_val if math.isfinite(p_val) else None}
                    except ValueError as exc:
                        egger_out = {'status': 'not_estimable', 'reason': str(exc)}
                    try:
                        tf_res = meta_mod.trim_and_fill(yi, vi)
                    except ValueError as exc:
                        tf_res = {'status': 'not_estimable', 'reason': str(exc)}
                    bias = {'egger': egger_out, 'trim_and_fill': tf_res}
                print(json.dumps({
                    'study_count': len(yi),
                    'fixed_effect': fixed,
                    'random_effects_dl': random_dl,
                    'leave_one_out': loo,
                    'publication_bias': bias,
                }, ensure_ascii=False, indent=2, allow_nan=False))
                return 0
        except (ValueError, OSError, KeyError, TypeError) as exc:
            print(json.dumps({
                'status': 'error',
                'command': args.command,
                'error': str(exc),
                'hint': _error_hint(str(exc)),
            }, ensure_ascii=False, indent=2))
            return 1
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
                root = _package_root()
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
            reason = str(exc)
            print(json.dumps({
                'status': 'error',
                'step': args.step,
                'reason': reason,
                'hint': _error_hint(args.step, reason),
            }, ensure_ascii=False), file=sys.stderr)
            return 1
    try:
        from .mcp_server import main as serve
    except ImportError:
        print('Incomplete runtime installation. Run academic-research-kernel doctor.', file=sys.stderr)
        return 1
    serve()
    return 0

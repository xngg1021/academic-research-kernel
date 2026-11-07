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
    tf_cmd = commands.add_parser('table-forensics', help='audit AI/CS paper tables for partition conservation, constant-offset deltas, and bandwidth bounds')
    tf_cmd.add_argument('--input', required=True, help='JSON file specifying partition, ablation_matrix, or storage_bandwidth parameters')
    or_cmd = commands.add_parser('openreview-audit', help='audit OpenReview submission status, decision, rating distribution, or venue stats')
    or_cmd.add_argument('--forum-id', help='OpenReview forum ID')
    or_cmd.add_argument('--input-json', help='offline OpenReview notes JSON file')
    or_cmd.add_argument('--mirror-json', help='optional OpenReview mirror JSON list for 403 fallback')
    or_cmd.add_argument('--venue-stats', help='compute macro statistics over a venue mirror JSON list')
    or_cmd.add_argument('--topic-regex', help='optional regex filter for --venue-stats')
    rf_cmd = commands.add_parser('repo-forensics', help='audit code repository structure (first-party core vs vendored vs unit tests)')
    rf_cmd.add_argument('--local-repo', '--repo-dir', dest='local_repo', help='local repository path')
    rf_cmd.add_argument('--tree-json', help='offline GitHub git/trees JSON file')
    rf_cmd.add_argument('--github-repo', help='remote GitHub owner/repo')
    ltx_cmd = commands.add_parser('receipt-to-latex', help='render a deterministic booktabs LaTeX table from a JSON receipt')
    ltx_cmd.add_argument('--input', required=True, help='JSON table specification file')
    ltx_cmd.add_argument('--output', help='optional output .tex path')
    sb_cmd = commands.add_parser('sanitize-blind', help='scan a manuscript or reproduction bundle for double-blind anonymity leaks')
    sb_cmd.add_argument('target_pos', nargs='?', help='manuscript file or directory to scan (positional)')
    sb_cmd.add_argument('--target', dest='target_opt', help='manuscript file or directory to scan')
    sb_cmd.add_argument('--forbidden-token', action='append', default=[], help='forbidden author/repo/issue token (repeatable)')
    ps_cmd = commands.add_parser('pre-submission-lint', help='audit manuscript for venue formatting, required sections, dispersion, and CEG bindings')
    ps_cmd.add_argument('--tex', required=True, help='path to main .tex entry file')
    ps_cmd.add_argument('--venue', default='iclr', help='target venue key')
    ps_cmd.add_argument('--phase', choices=['submission', 'rebuttal', 'camera_ready'], default='submission', help='submission phase')
    ps_cmd.add_argument('--contribution-type', default='general_empirical', help='contribution type key')
    ps_cmd.add_argument('--pdf', help='optional compiled PDF path')
    ps_cmd.add_argument('--ceg', help='optional ClaimEvidenceGraph JSON path')
    ps_cmd.add_argument('--require-ceg-binding', action='store_true', help='flag ungrounded quantitative claims in abstract/conclusion')
    ps_cmd.add_argument('--output', help='optional output JSON path')
    vt_cmd = commands.add_parser('venue-template', help='list target venue contracts or scaffold an external manuscript workspace')
    vt_cmd.add_argument('--action', choices=['list-venues', 'scaffold', 'verify-styles'], default='list-venues')
    vt_cmd.add_argument('--workspace-dir', help='target parent workspace directory for scaffold')
    vt_cmd.add_argument('--slug', help='project directory slug')
    vt_cmd.add_argument('--venue', default='iclr', help='venue key')
    vt_cmd.add_argument('--year', type=int, default=2027, help='target publication year')
    vt_cmd.add_argument('--contribution-type', default='general_empirical', help='contribution type key')
    vt_cmd.add_argument('--force', action='store_true', help='overwrite existing workspace if venue differs')
    vt_cmd.add_argument('--manuscript-dir', help='manuscript directory for verify-styles')
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
    if args.command in ('table-forensics', 'openreview-audit', 'repo-forensics', 'receipt-to-latex', 'sanitize-blind', 'pre-submission-lint', 'venue-template'):
        try:
            if args.command == 'table-forensics':
                recomp_mod = _load_bundled_module('recompute', 'skills/quantitative-paper-audit/scripts/recompute.py')
                spec = json.loads(Path(args.input).read_text(encoding='utf-8'))
                if not isinstance(spec, dict):
                    raise ValueError('table-forensics input must be a JSON object')
                out = {}
                if 'partition' in spec:
                    p = spec['partition']
                    out['partition_conservation'] = recomp_mod.check_partition_conservation(
                        p['total'], p['parts'], reported_shares=p.get('reported_shares'),
                        tol=p.get('tol', 0), share_tol_pct=p.get('share_tol_pct', 0.5),
                        share_unit=p.get('share_unit', 'auto'),
                    )
                if 'ablation_matrix' in spec:
                    ab = spec['ablation_matrix']
                    if isinstance(ab, dict):
                        out['ablation_delta_regularity'] = recomp_mod.check_ablation_delta_regularity(
                            ab['matrix'], baseline_col=ab.get('baseline_col', spec.get('baseline_col', 0)),
                            min_rows=ab.get('min_rows', spec.get('min_rows', 3)),
                            tol=ab.get('tol', spec.get('tol', 1e-9)),
                        )
                    else:
                        out['ablation_delta_regularity'] = recomp_mod.check_ablation_delta_regularity(
                            ab, baseline_col=spec.get('baseline_col', 0),
                            min_rows=spec.get('min_rows', 3),
                            tol=spec.get('tol', 1e-9),
                        )
                if 'storage_bandwidth' in spec:
                    sb = spec['storage_bandwidth']
                    out['storage_bandwidth_bounds'] = recomp_mod.check_storage_bandwidth_bounds(
                        sb['item_count'], sb['vector_dim'],
                        bytes_per_element=sb.get('bytes_per_element', 4),
                        reported_size_mb=sb.get('reported_size_mb'),
                        reported_latency_us=sb.get('reported_latency_us'),
                        max_bandwidth_gbps=sb.get('max_bandwidth_gbps', 4000.0),
                        rel_tol=sb.get('rel_tol', 1e-2),
                        claims_full_system_storage=sb.get('claims_full_system_storage', True),
                    )
                if not out:
                    raise ValueError('table-forensics input must contain at least one of: partition, ablation_matrix, storage_bandwidth')
                out['consistent'] = all(v.get('consistent') is True for v in out.values() if isinstance(v, dict))
                print(json.dumps(out, ensure_ascii=False, indent=2))
                return 0
            if args.command == 'openreview-audit':
                if not (args.forum_id or args.input_json or args.venue_stats):
                    raise ValueError('openreview-audit requires --forum-id, --input-json, or --venue-stats')
                or_mod = _load_bundled_module('openreview_audit', 'skills/academic-source-verification/scripts/openreview_audit.py')
                sub_argv = []
                if args.forum_id:
                    sub_argv.extend(['--forum-id', args.forum_id])
                if args.input_json:
                    sub_argv.extend(['--input-json', args.input_json])
                if args.mirror_json:
                    sub_argv.extend(['--mirror-json', args.mirror_json])
                if args.venue_stats:
                    sub_argv.extend(['--venue-stats', args.venue_stats])
                if args.topic_regex:
                    sub_argv.extend(['--topic-regex', args.topic_regex])
                return or_mod.main(sub_argv)
            if args.command == 'repo-forensics':
                if not (args.local_repo or args.tree_json or args.github_repo):
                    raise ValueError('repo-forensics requires one of --local-repo, --tree-json, or --github-repo')
                rf_mod = _load_bundled_module('github_repo_forensics', 'skills/academic-source-verification/scripts/github_repo_forensics.py')
                sub_argv = []
                if args.local_repo:
                    sub_argv.extend(['--local-repo', args.local_repo])
                if args.tree_json:
                    sub_argv.extend(['--tree-json', args.tree_json])
                if args.github_repo:
                    sub_argv.extend(['--github-repo', args.github_repo])
                return rf_mod.main(sub_argv)
            if args.command == 'receipt-to-latex':
                ltx_mod = _load_bundled_module('receipt_to_latex_table', 'skills/academic-writing/scripts/receipt_to_latex_table.py')
                sub_argv = ['--input', args.input]
                if args.output:
                    sub_argv.extend(['--output', args.output])
                return ltx_mod.main(sub_argv)
            if args.command == 'sanitize-blind':
                sb_target = args.target_opt or args.target_pos
                if not sb_target:
                    raise ValueError('sanitize-blind requires --target <path> or a positional target path')
                sb_mod = _load_bundled_module('double_blind_sanitizer', 'skills/academic-writing/scripts/double_blind_sanitizer.py')
                sub_argv = ['--target', sb_target]
                for tok in args.forbidden_token:
                    sub_argv.extend(['--forbidden-token', tok])
                return sb_mod.main(sub_argv)
            if args.command == 'pre-submission-lint':
                ps_mod = _load_bundled_module('pre_submission_linter', 'skills/academic-writing/scripts/pre_submission_linter.py')
                sub_argv = ['--tex', args.tex, '--venue', args.venue, '--phase', args.phase, '--contribution-type', args.contribution_type]
                if args.pdf:
                    sub_argv.extend(['--pdf', args.pdf])
                if args.ceg:
                    sub_argv.extend(['--ceg', args.ceg])
                if args.require_ceg_binding:
                    sub_argv.append('--require-ceg-binding')
                if args.output:
                    sub_argv.extend(['--output', args.output])
                return ps_mod.main(sub_argv)
            if args.command == 'venue-template':
                vt_mod = _load_bundled_module('venue_template_manager', 'skills/academic-writing/scripts/venue_template_manager.py')
                sub_argv = ['--action', args.action, '--venue', args.venue, '--year', str(args.year), '--contribution-type', args.contribution_type]
                if args.workspace_dir:
                    sub_argv.extend(['--workspace-dir', args.workspace_dir])
                if args.slug:
                    sub_argv.extend(['--slug', args.slug])
                if args.force:
                    sub_argv.append('--force')
                if args.manuscript_dir:
                    sub_argv.extend(['--manuscript-dir', args.manuscript_dir])
                return vt_mod.main(sub_argv)
        except Exception as exc:
            print(json.dumps({
                'status': 'error',
                'command': args.command,
                'error': str(exc),
                'hint': _error_hint(args.command, str(exc)),
            }, ensure_ascii=False, indent=2))
            return 1
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
                    except (ValueError, ZeroDivisionError) as exc:
                        egger_out = {'status': 'not_estimable', 'reason': str(exc)}
                    try:
                        tf_res = meta_mod.trim_and_fill(yi, vi)
                    except (ValueError, ZeroDivisionError) as exc:
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
        except (ValueError, ZeroDivisionError, OSError, KeyError, TypeError) as exc:
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

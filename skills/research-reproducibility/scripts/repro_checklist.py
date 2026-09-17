"""Structured reproduction checklist engine: records facts, never runs a reproduction.

Input is a checklist JSON describing what was actually verified at each stage of
the fourteen-stage pipeline (paper identity -> official code link -> repository
identity -> version/date consistency -> pinned release/commit -> dataset ->
model weights -> dependency environment -> license -> build/install -> smoke
run -> claimed metrics -> measured metrics -> metric diff). Output is a
ReproductionReceipt JSON with a four-state verdict
(reproducible / partially-reproducible / blocked / inconsistent) and a
five-level fact tier (no-code-found / environment-broken / runs /
direction-reproduced / numbers-reproduced, or null when facts are insufficient).

An AcademicEvidenceReceipt (schemas/evidence-receipt.schema.json) can be merged
in as one input format: identifiers are backfilled and its sources are recorded
as identity-stage evidence. No stage is ever auto-passed by the engine; stage
statuses come only from actual checking by the operator.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

SCHEMA_VERSION = '1.0'

STAGES = (
    ('identity', '论文身份确认'),
    ('code-link', '官方代码链接'),
    ('repo-identity', '仓库身份'),
    ('version-consistency', '论文与代码版本/日期一致性'),
    ('release-commit', '固定 release 或 commit'),
    ('dataset', '数据集可得性'),
    ('model-weights', '模型权重可得性'),
    ('dependencies', '依赖环境'),
    ('license', '许可证'),
    ('build-install', '构建安装'),
    ('smoke-run', '最小示例执行'),
    ('claimed-metrics', '论文声称指标提取'),
    ('measured-metrics', '实测指标'),
    ('metric-diff', '声称与实测差异对照'),
)
STAGE_IDS = [sid for sid, _ in STAGES]
STAGE_LABELS = dict(STAGES)

# Hard stages gate every positive verdict: fail/missing/blocked or simply
# unchecked on any of them means no reproducibility claim can stand.
HARD_STAGES = ('identity', 'code-link', 'repo-identity', 'dependencies', 'build-install', 'smoke-run')
# Soft stages may be waived (skipped with waived=true plus a reason) without
# losing the "reproducible" verdict, e.g. a training-free method has no weights.
WAIVABLE_STAGES = ('dataset', 'model-weights', 'license')

STAGE_STATUSES = ('pass', 'fail', 'mismatch', 'missing', 'blocked', 'skipped', 'unknown')
NEGATIVE = ('fail', 'missing', 'blocked')
UNCHECKED = ('skipped', 'unknown')

VERDICTS = ('reproducible', 'partially-reproducible', 'blocked', 'inconsistent')
TIERS = ('no-code-found', 'environment-broken', 'runs', 'direction-reproduced', 'numbers-reproduced')

OFFICIALITY = ('official', 'author-affiliated', 'third-party', 'unknown')

_STAGE_OPTIONAL = ('evidence', 'detail', 'checked_at', 'waived', 'reason', 'artifacts',
                   'claimed_value', 'measured_value', 'tolerance')


class ChecklistError(ValueError):
    """Raised when a checklist or evidence receipt is structurally invalid."""


def _strict_bool(value, field):
    """严格 JSON 布尔: 只接受 bool, 字符串 'true'/'false' 一律拒绝 (RP-01)。"""
    if isinstance(value, bool):
        return value
    raise ChecklistError(f'{field} 必须是 JSON 布尔值, got {value!r}')


def normalize(checklist):
    """Validate a checklist dict and return a canonical form with all 14 stages.

    Stages absent from the input are filled as status "unknown". The result is
    idempotent: normalize(normalize(x)) == normalize(x).
    """
    if not isinstance(checklist, dict):
        raise ChecklistError('checklist must be a JSON object')
    paper = checklist.get('paper')
    if not isinstance(paper, dict) or not any(paper.get(k) for k in ('title', 'doi', 'arxiv_id')):
        raise ChecklistError('paper must carry at least one of title / doi / arxiv_id')
    raw_stages = checklist.get('stages', [])
    if not isinstance(raw_stages, list):
        raise ChecklistError('stages must be a list')
    by_id = {}
    for entry in raw_stages:
        if not isinstance(entry, dict):
            raise ChecklistError('each stage must be an object')
        sid = entry.get('id')
        if sid not in STAGE_IDS:
            raise ChecklistError(f'unknown stage id: {sid!r}')
        if sid in by_id:
            raise ChecklistError(f'duplicate stage id: {sid!r}')
        status = entry.get('status')
        if status not in STAGE_STATUSES:
            raise ChecklistError(f'stage {sid}: invalid status {status!r}; '
                                 f'expected one of {STAGE_STATUSES}')
        # RP-01: 豁免契约 = 严格布尔 + 允许阶段 + skipped 状态 + 非空理由
        waived = False
        if entry.get('waived') is not None:
            waived = _strict_bool(entry.get('waived'), f'stage {sid}.waived')
        if waived:
            if status != 'skipped':
                raise ChecklistError(f'stage {sid}: waived is only valid with status "skipped"')
            if sid not in WAIVABLE_STAGES:
                raise ChecklistError(f'stage {sid}: 不在可豁免阶段 {sorted(WAIVABLE_STAGES)}')
            if not str(entry.get('reason') or '').strip():
                raise ChecklistError(f'stage {sid}: waived 必须附带非空 reason')
        record = {'id': sid, 'status': status}
        for key in _STAGE_OPTIONAL:
            if key in entry:
                record[key] = (waived if key == 'waived' else entry[key])
        by_id[sid] = record
    stages = [by_id.get(sid) or {'id': sid, 'status': 'unknown', 'detail': '未提供该阶段记录'}
              for sid in STAGE_IDS]
    repo = checklist.get('repository')
    if repo is not None:
        if not isinstance(repo, dict):
            raise ChecklistError('repository must be an object when present')
        off = repo.get('officiality')
        if off is not None and off not in OFFICIALITY:
            raise ChecklistError(f'repository.officiality must be one of {OFFICIALITY}')
    out = {'schema_version': SCHEMA_VERSION, 'paper': paper, 'repository': repo, 'stages': stages}
    for key in ('notes', 'generated_at'):
        if key in checklist:
            out[key] = checklist[key]
    return out


def _tier(stages):
    """Five-level fact tier from run-progress facts alone; None when indeterminate."""
    def status(sid):
        return stages[sid]['status']
    if status('identity') in NEGATIVE or status('identity') == 'mismatch':
        return None
    # A mismatched code link or repository means the found code is not the
    # paper's code: factually the same tier as having found no code at all.
    if status('code-link') in (*NEGATIVE, 'mismatch') or status('repo-identity') in (*NEGATIVE, 'mismatch'):
        return 'no-code-found'
    if status('code-link') in UNCHECKED or status('repo-identity') in UNCHECKED:
        return None
    if status('identity') in UNCHECKED:
        return None
    for sid in ('dependencies', 'build-install', 'smoke-run'):
        if status(sid) in NEGATIVE:
            return 'environment-broken'
        if status(sid) in UNCHECKED:
            return None
    if status('claimed-metrics') != 'pass' or status('measured-metrics') != 'pass':
        return 'runs'
    diff = status('metric-diff')
    if diff == 'pass':
        return 'numbers-reproduced'
    if diff == 'fail':
        return 'direction-reproduced'
    return 'runs'


def adjudicate(checklist, generated_at=None):
    """Turn a checklist into a ReproductionReceipt dict.

    Verdict precedence: any mismatch anywhere -> inconsistent; then any hard
    stage not passed (negative or unchecked) -> blocked; then all stages passed
    or waived -> reproducible; otherwise -> partially-reproducible.
    """
    cl = normalize(checklist)
    stages = {entry['id']: entry for entry in cl['stages']}
    contradictions = [e['id'] for e in cl['stages'] if e['status'] == 'mismatch']

    def waived_ok(e):
        return e['status'] == 'skipped' and e.get('waived') is True and e['id'] in WAIVABLE_STAGES

    blocking = [e['id'] for e in cl['stages']
                if e['id'] in HARD_STAGES and e['status'] != 'pass']
    gaps = [e['id'] for e in cl['stages']
            if e['status'] != 'pass' and e['id'] not in HARD_STAGES and not waived_ok(e)]
    if contradictions:
        verdict = 'inconsistent'
    elif blocking:
        verdict = 'blocked'
    elif not gaps:
        verdict = 'reproducible'
    else:
        verdict = 'partially-reproducible'
    receipt_stages = []
    for e in cl['stages']:
        item = {'id': e['id'], 'label': STAGE_LABELS[e['id']], 'status': e['status']}
        for key in ('detail', 'evidence'):
            if key in e:
                item[key] = e[key]
        receipt_stages.append(item)
    return {
        'kind': 'ReproductionReceipt',
        'schema_version': SCHEMA_VERSION,
        'status': verdict,
        'tier': _tier(stages),
        'paper': cl['paper'],
        'repository': cl['repository'],
        'stages': receipt_stages,
        'contradictions': contradictions,
        'blocking': blocking,
        'gaps': gaps,
        'generated_at': generated_at or cl.get('generated_at') or _now(),
    }


def merge_evidence_receipt(checklist, evidence):
    """Merge an AcademicEvidenceReceipt into a checklist; returns (checklist, warnings).

    Backfills paper identifiers, appends the receipt's ok sources to the
    identity stage as evidence, and warns on identifier conflicts. Never marks
    any stage as passed: statuses still require actual checking.
    """
    if not isinstance(evidence, dict) or evidence.get('schema_version') != '1.0':
        raise ChecklistError('evidence receipt must be a JSON object with schema_version "1.0"')
    identifiers = evidence.get('identifiers')
    if not isinstance(identifiers, dict):
        raise ChecklistError('evidence receipt missing identifiers object')
    cl = dict(checklist)
    paper = dict(cl.get('paper') or {})
    warnings = []
    for key in ('doi', 'arxiv_id'):
        value = identifiers.get(key)
        if not value:
            continue
        if paper.get(key) and paper[key] != value:
            warnings.append(f'identifier conflict on {key}: checklist {paper[key]!r} vs evidence {value!r}')
        else:
            paper.setdefault(key, value)
    cl['paper'] = paper
    ok_sources = [s.get('source') for s in evidence.get('sources', [])
                  if isinstance(s, dict) and s.get('status') == 'ok' and s.get('source')]
    note = '证据回执来源: ' + (', '.join(ok_sources) or '无 ok 来源')
    stages = [dict(s) for s in cl.get('stages', [])]
    for s in stages:
        if s.get('id') == 'identity':
            s['evidence'] = (s['evidence'] + '; ' if s.get('evidence') else '') + note
            break
    else:
        stages.append({'id': 'identity', 'status': 'unknown', 'evidence': note})
    cl['stages'] = stages
    return cl, warnings


def _now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def _load_json(value):
    if value is None or value == '-':
        return json.loads(sys.stdin.read())
    return json.loads(Path(value).read_text(encoding='utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Adjudicate a reproduction checklist into a ReproductionReceipt.')
    parser.add_argument('input', nargs='?', default='-',
                        help='checklist JSON path (default: read stdin)')
    parser.add_argument('-o', '--out', help='also write the receipt JSON to this path')
    parser.add_argument('--evidence-receipt',
                        help='merge an AcademicEvidenceReceipt before adjudicating')
    parser.add_argument('--generated-at', help='fixed ISO-8601 timestamp for deterministic output')
    parser.add_argument('--pretty', action='store_true', help='indent JSON output')
    args = parser.parse_args(argv)
    try:
        checklist = _load_json(args.input)
        if args.evidence_receipt:
            checklist, warnings = merge_evidence_receipt(checklist, _load_json(args.evidence_receipt))
            for warning in warnings:
                print(f'warning: {warning}', file=sys.stderr)
        receipt = adjudicate(checklist, generated_at=args.generated_at)
    except (ChecklistError, json.JSONDecodeError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 2
    text = json.dumps(receipt, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        Path(args.out).write_text(text + '\n', encoding='utf-8')
    print(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

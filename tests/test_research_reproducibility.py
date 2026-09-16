"""Tests for the research-reproducibility checklist engine and receipt adjudication."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'research-reproducibility' / 'scripts' / 'repro_checklist.py'
spec = importlib.util.spec_from_file_location('repro_checklist', SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

STAGE_IDS = [sid for sid, _ in engine.STAGES]
PAPER = {'title': 'Example Paper', 'doi': '10.1234/example', 'arxiv_id': '2401.00001'}
FIXED_TS = '2026-09-16T00:00:00+00:00'


def stage(sid, status, **kw):
    return {'id': sid, 'status': status, **kw}


def checklist(stages):
    return {'schema_version': '1.0', 'paper': dict(PAPER), 'stages': stages}


def full_pass(**overrides):
    stages = []
    for sid in STAGE_IDS:
        entry = {'id': sid, 'status': 'pass'}
        if sid in overrides:
            value = overrides[sid]
            entry.update({'status': value} if isinstance(value, str) else value)
        stages.append(entry)
    return checklist(stages)


def verdict(cl):
    return engine.adjudicate(cl, generated_at=FIXED_TS)


# ---------------------------------------------------------------- four states

def test_all_pass_is_reproducible_with_numbers_tier():
    receipt = verdict(full_pass())
    assert receipt['status'] == 'reproducible'
    assert receipt['tier'] == 'numbers-reproduced'
    assert receipt['contradictions'] == [] and receipt['blocking'] == [] and receipt['gaps'] == []


def test_waived_soft_stages_keep_reproducible():
    receipt = verdict(full_pass(**{
        'dataset': {'status': 'skipped', 'waived': True, 'reason': 'synthetic data shipped'},
        'model-weights': {'status': 'skipped', 'waived': True, 'reason': 'training-free method'},
    }))
    assert receipt['status'] == 'reproducible'
    assert receipt['tier'] == 'numbers-reproduced'


def test_missing_code_link_is_blocked_no_code_found():
    receipt = verdict(checklist([stage('identity', 'pass'), stage('code-link', 'missing')]))
    assert receipt['status'] == 'blocked'
    assert receipt['tier'] == 'no-code-found'
    assert 'code-link' in receipt['blocking']


def test_broken_dependencies_blocked_environment_broken():
    receipt = verdict(full_pass(**{'dependencies': 'fail', 'build-install': 'skipped',
                                   'smoke-run': 'skipped', 'claimed-metrics': 'skipped',
                                   'measured-metrics': 'skipped', 'metric-diff': 'skipped'}))
    assert receipt['status'] == 'blocked'
    assert receipt['tier'] == 'environment-broken'
    assert 'dependencies' in receipt['blocking']


def test_smoke_failure_is_blocked_environment_broken():
    receipt = verdict(full_pass(**{'smoke-run': 'fail', 'metric-diff': 'skipped',
                                   'measured-metrics': 'skipped'}))
    assert receipt['status'] == 'blocked'
    assert receipt['tier'] == 'environment-broken'


def test_unchecked_hard_stage_is_blocked_with_null_tier():
    receipt = verdict(full_pass(**{'smoke-run': 'unknown'}))
    assert receipt['status'] == 'blocked'
    assert receipt['tier'] is None
    assert 'smoke-run' in receipt['blocking']


def test_runs_only_is_partially_reproducible():
    receipt = verdict(full_pass(**{'claimed-metrics': 'skipped', 'measured-metrics': 'skipped',
                                   'metric-diff': 'skipped'}))
    assert receipt['status'] == 'partially-reproducible'
    assert receipt['tier'] == 'runs'
    assert set(receipt['gaps']) == {'claimed-metrics', 'measured-metrics', 'metric-diff'}


def test_direction_only_is_partially_reproducible():
    receipt = verdict(full_pass(**{'metric-diff': {'status': 'fail', 'claimed_value': 92.4,
                                                   'measured_value': 89.8, 'tolerance': '±0.5pp'}}))
    assert receipt['status'] == 'partially-reproducible'
    assert receipt['tier'] == 'direction-reproduced'


def test_metric_contradiction_is_inconsistent():
    receipt = verdict(full_pass(**{'metric-diff': 'mismatch'}))
    assert receipt['status'] == 'inconsistent'
    assert receipt['contradictions'] == ['metric-diff']
    assert receipt['tier'] == 'runs'


def test_version_mismatch_is_inconsistent_despite_passes():
    receipt = verdict(full_pass(**{'version-consistency': 'mismatch'}))
    assert receipt['status'] == 'inconsistent'
    assert 'version-consistency' in receipt['contradictions']


def test_identity_mismatch_is_inconsistent():
    receipt = verdict(full_pass(**{'identity': 'mismatch'}))
    assert receipt['status'] == 'inconsistent'
    assert receipt['contradictions'] == ['identity']


def test_soft_gap_caps_at_partially_even_with_numbers():
    receipt = verdict(full_pass(**{'license': 'fail'}))
    assert receipt['status'] == 'partially-reproducible'
    assert receipt['tier'] == 'numbers-reproduced'
    assert receipt['gaps'] == ['license']


def test_repo_identity_mismatch_beats_blocked():
    receipt = verdict(full_pass(**{'repo-identity': 'mismatch', 'dataset': 'missing'}))
    assert receipt['status'] == 'inconsistent'
    assert receipt['tier'] == 'no-code-found'


# ------------------------------------------------------- normalization & I/O

def test_missing_stages_filled_unknown_in_order():
    receipt = verdict(checklist([stage('metric-diff', 'pass')]))
    assert [s['id'] for s in receipt['stages']] == STAGE_IDS
    assert receipt['stages'][0]['status'] == 'unknown'
    assert receipt['status'] == 'blocked'  # hard stages unknown


def test_normalize_is_idempotent():
    once = engine.normalize(full_pass(**{'dataset': 'missing'}))
    assert engine.normalize(once) == once


def test_receipt_json_round_trip_is_stable():
    receipt = verdict(full_pass(**{'metric-diff': 'fail'}))
    assert json.loads(json.dumps(receipt, ensure_ascii=False)) == receipt


def test_cli_in_process_round_trip(tmp_path, capsys):
    src = tmp_path / 'cl.json'
    src.write_text(json.dumps(full_pass(), ensure_ascii=False), encoding='utf-8')
    out = tmp_path / 'receipt.json'
    assert engine.main([str(src), '-o', str(out), '--generated-at', FIXED_TS]) == 0
    from_file = json.loads(out.read_text(encoding='utf-8'))
    from_stdout = json.loads(capsys.readouterr().out)
    assert from_file == from_stdout
    assert from_file['status'] == 'reproducible' and from_file['generated_at'] == FIXED_TS


def test_cli_subprocess_end_to_end(tmp_path):
    src = tmp_path / 'cl.json'
    src.write_text(json.dumps(checklist([stage('identity', 'pass'),
                                         stage('code-link', 'missing')])), encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), str(src), '--generated-at', FIXED_TS],
                            capture_output=True)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    receipt = json.loads(result.stdout)
    assert receipt['status'] == 'blocked' and receipt['tier'] == 'no-code-found'


def test_cli_rejects_invalid_input(tmp_path, capsys):
    src = tmp_path / 'bad.json'
    src.write_text('{"paper": {}}', encoding='utf-8')
    assert engine.main([str(src)]) == 2
    assert 'error:' in capsys.readouterr().err


# -------------------------------------------------------------- validation

def test_invalid_stage_status_rejected():
    with pytest.raises(engine.ChecklistError):
        verdict(checklist([stage('identity', 'looks-good')]))


def test_unknown_and_duplicate_stage_rejected():
    with pytest.raises(engine.ChecklistError):
        verdict(checklist([stage('vibes', 'pass')]))
    with pytest.raises(engine.ChecklistError):
        verdict(checklist([stage('identity', 'pass'), stage('identity', 'fail')]))


def test_waived_requires_skipped():
    with pytest.raises(engine.ChecklistError):
        verdict(checklist([stage('dataset', 'pass', waived=True)]))


# -------------------------------------------------------- evidence receipt

def evidence_receipt(doi=PAPER['doi']):
    return {'schema_version': '1.0', 'query': 'verify example paper',
            'identifiers': {'doi': doi, 'arxiv_id': PAPER['arxiv_id'],
                            'openalex_id': None, 'pmid': None},
            'sources': [{'source': 'crossref', 'queried_at': FIXED_TS, 'status': 'ok'},
                        {'source': 'openalex', 'queried_at': FIXED_TS, 'status': 'failed'}],
            'claims': [], 'conflicts': [], 'failures': [], 'artifacts': [],
            'generated_at': FIXED_TS}


def test_evidence_receipt_backfills_identifiers_and_sources():
    cl, warnings = engine.merge_evidence_receipt(checklist([stage('identity', 'unknown')]),
                                                 evidence_receipt())
    assert warnings == []
    assert cl['paper']['doi'] == PAPER['doi']
    identity = next(s for s in cl['stages'] if s['id'] == 'identity')
    assert 'crossref' in identity['evidence'] and 'openalex' not in identity['evidence']
    assert identity['status'] == 'unknown'  # evidence never auto-passes a stage


def test_evidence_receipt_identifier_conflict_warns():
    cl, warnings = engine.merge_evidence_receipt(full_pass(), evidence_receipt(doi='10.9999/other'))
    assert cl['paper']['doi'] == PAPER['doi']
    assert warnings and 'doi' in warnings[0]


def test_malformed_evidence_receipt_rejected():
    with pytest.raises(engine.ChecklistError):
        engine.merge_evidence_receipt(full_pass(), {'schema_version': '2.0'})

"""Tests for the research-reproducibility checklist engine and receipt adjudication."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
from academic_research_kernel import repro_checklist as engine

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



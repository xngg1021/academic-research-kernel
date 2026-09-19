"""Run the pinned upstream per-skill tests unchanged, with this tap's skill population."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(__file__).parent / 'upstream'
spec = importlib.util.spec_from_file_location('pinned_hermes_authoring', UPSTREAM / 'hermes_authoring_standards.py')
upstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream)
upstream.REPO = ROOT
provenance = json.loads((UPSTREAM / 'provenance.json').read_text())
local = {p.parent.name for p in ROOT.glob('skills/*/SKILL.md')}
upstream.ALL_SKILL_NAMES = local | {k for k, paths in provenance['related_skills'].items() if paths}
RULES = [value for name, value in vars(upstream).items() if name.startswith('test_')
         and callable(value) and 'p' in value.__code__.co_varnames[:value.__code__.co_argcount]]


@pytest.mark.parametrize('path', sorted(ROOT.glob('skills/*/SKILL.md')), ids=lambda p: p.parent.name)
@pytest.mark.parametrize('rule', RULES, ids=lambda f: f.__name__)
def test_current_hermes_rules(path, rule):
    rule(path)


def test_all_rules_and_skills_present():
    assert len(RULES) == 6
    assert len(local) == 13
    assert not upstream.GRANDFATHER

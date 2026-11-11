"""Run the pinned upstream per-skill tests unchanged, plus current Hermes paste-safety and provenance integrity."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(__file__).parent / 'upstream'
spec = importlib.util.spec_from_file_location('pinned_hermes_authoring', UPSTREAM / 'hermes_authoring_standards.py')
upstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream)
upstream.REPO = ROOT
provenance = json.loads((UPSTREAM / 'provenance.json').read_text(encoding='utf-8'))
local = {p.parent.name for p in ROOT.glob('skills/*/SKILL.md')}
upstream.ALL_SKILL_NAMES = local | {k for k, paths in provenance['related_skills'].items() if paths}
RULES = [value for name, value in vars(upstream).items() if name.startswith('test_')
         and callable(value) and 'p' in value.__code__.co_varnames[:value.__code__.co_argcount]]

SHELL_FENCE_OPEN = re.compile(r"^\s*(`{3,}|~{3,})\s*(bash|sh|shell|zsh|console)\b", re.IGNORECASE)
CONTINUATION_THEN_COMMENT = re.compile(r"\\\s+#")


def _shell_fence_lines(content: str):
    fence = None
    for i, line in enumerate(content.splitlines(), 1):
        if fence is None:
            m = SHELL_FENCE_OPEN.match(line)
            if m:
                fence = m.group(1)
            continue
        if line.strip().startswith(fence):
            fence = None
            continue
        yield i, line


@pytest.mark.parametrize('path', sorted(ROOT.glob('skills/*/SKILL.md')), ids=lambda p: p.parent.name)
@pytest.mark.parametrize('rule', RULES, ids=lambda f: f.__name__)
def test_current_hermes_rules(path, rule):
    rule(path)


@pytest.mark.parametrize('path', sorted(ROOT.glob('skills/*/SKILL.md')), ids=lambda p: p.parent.name)
def test_shell_snippets_paste_safe(path):
    """Current Hermes authoring standard (#113448): no comment after line-continuation backslash in shell fences."""
    content = path.read_text(encoding='utf-8')
    bad = [
        f"{path.parent.name}/SKILL.md:{i}: {line.strip()}"
        for i, line in _shell_fence_lines(content)
        if CONTINUATION_THEN_COMMENT.search(line)
    ]
    assert not bad, "comment after a line-continuation backslash breaks pasted command:\n" + "\n".join(bad)


def test_all_rules_and_skills_present():
    assert len(RULES) == 6
    assert len(local) == 14
    assert not upstream.GRANDFATHER
    for fname, meta in provenance['vendored_files'].items():
        actual_sha = hashlib.sha256((UPSTREAM / fname).read_bytes()).hexdigest()
        assert actual_sha == meta['sha256'], f"vendored {fname} sha256 mismatch"

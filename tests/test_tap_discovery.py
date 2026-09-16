"""Execute the pinned upstream discovery method against local Contents-API fixtures."""
from pathlib import Path
import hashlib
import json
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = Path(__file__).parent / 'upstream'


def test_pinned_source_integrity():
    data = json.loads((UPSTREAM / 'provenance.json').read_text())
    for name, info in data['vendored_files'].items():
        assert hashlib.sha256((UPSTREAM / name).read_bytes()).hexdigest() == info['sha256']


def test_actual_upstream_discovers_five_skills():
    ns = {'List': list, 'SkillMeta': object, '_API': 'https://api.github.com/repos',
          '_cached_metas': lambda key: None, '_cache_metas': lambda key, values: None}
    exec(compile((UPSTREAM / 'tap_discovery.py').read_text(), 'pinned_tap_discovery', 'exec'), ns)
    class Source:
        def _github_get(self, url):
            assert url.endswith('/contents/skills')
            entries = [{'type': 'dir', 'name': p.name} for p in (ROOT / 'skills').iterdir() if p.is_dir()]
            return SimpleNamespace(status_code=200, json=lambda: entries)
        def _get_skillsh_groupings(self, repo):
            return None
        def inspect(self, identifier):
            _, _, relative = identifier.split('/', 2)
            path = ROOT / relative / 'SKILL.md'
            return SimpleNamespace(name=path.parent.name, extra={}) if path.is_file() else None
    found = ns['_list_skills_in_repo'](Source(), 'xngg1021/hermes-academic-skills', 'skills/')
    assert {skill.name for skill in found} == {'academic-source-verification', 'academic-writing',
                                              'literature-analysis', 'math-computation',
                                              'research-reproducibility'}

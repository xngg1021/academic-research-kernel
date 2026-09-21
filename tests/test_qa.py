"""Mutation checks: the guard must actually reject the failures it advertises."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('qa', Path(__file__).resolve().parents[1] / 'scripts/qa.py')
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


def test_pandas_pseudo_alternative_rejected():
    assert qa.code_issues('df = pd.read_csv(path) / pd.read_excel(path)')
    assert not qa.code_issues('df = pd.read_csv(path)')


def test_unexpanded_save_path_rejected():
    assert qa.code_issues("fig.savefig('~/plots/a.png')")
    assert not qa.code_issues("fig.savefig(Path('~/plots/a.png').expanduser())")


def test_personal_paths_and_secret_rejected():
    for value in ['C:' + '/Users/' + 'alice/venv/python.exe', '/' + 'home/alice/venv',
                  '/' + 'Users/alice/plots', 'ghp_' + 'a'*36,
                  "api_key = '" + 'A'*24 + "'"]:
        assert qa.hygiene(value)
    assert not qa.hygiene('C:/Users/<user>/python.exe OPENALEX_API_KEY=YOUR_KEY')


def test_missing_and_case_mismatched_reference(tmp_path):
    ref = tmp_path / 'references'
    ref.mkdir()
    (ref / 'Valid.md').write_text('ok')
    md = tmp_path / 'SKILL.md'
    md.write_text('[reference](references/missing.md)')
    assert qa.reference_issues(md, tmp_path)
    md.write_text('[reference](references/valid.md)')
    assert qa.reference_issues(md, tmp_path)
    md.write_text('[reference](references/Valid.md)')
    assert not qa.reference_issues(md, tmp_path)


def test_unclassified_python_not_silently_skipped(tmp_path):
    p = tmp_path / 'example.md'
    p.write_text('```python\nprint(1)\n```\n')
    with pytest.raises(ValueError):
        list(qa.fences(p))


def test_failed_numeric_assertion_is_a_failure(tmp_path):
    p = tmp_path / 'SKILL.md'
    p.write_text('# isolated skill')
    result = qa.run_fence(p, 1, 'assert 100 == 10000')
    assert result.returncode != 0


def test_inventory_prunes_local_environments_and_binary_garbage(tmp_path):
    import subprocess
    for tree in qa.EXCLUDED_TREES - {'.git'}:
        path = tmp_path / tree / 'nested'
        path.mkdir(parents=True)
        (path / 'poison.md').write_bytes(b'\xff\xfe\x00')
        (path / 'poison.py').write_bytes(b'\x80\x00')
    (tmp_path / 'README.md').write_text('source', encoding='utf-8')
    assert [p.name for p in qa.source_files(tmp_path)] == ['README.md']
    # Git inventory also ignores unrelated untracked text, not just known caches.
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    subprocess.run(['git', '-C', str(tmp_path), 'add', 'README.md'], check=True)
    (tmp_path / 'random.md').write_bytes(b'\xff')
    assert [p.name for p in qa.source_files(tmp_path)] == ['README.md']

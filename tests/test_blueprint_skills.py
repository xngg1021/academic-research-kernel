"""blueprint 技能（literature-watch / retraction-watch）的 frontmatter 与自检合规测试。"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ['literature-watch', 'retraction-watch']
SLL = 'LicenseRef-Source-Lineage-1.0'

# Hermes 官方 creating-skills 文档规定的 blueprint 字段
BLUEPRINT_FIELDS = {'schedule', 'deliver', 'prompt', 'no_agent'}


def frontmatter(name):
    path = ROOT / 'skills' / name / 'SKILL.md'
    text = path.read_text(encoding='utf-8')
    assert text.startswith('---\n'), name
    end = text.index('\n---', 3)
    return yaml.safe_load(text[3:end]), text


@pytest.mark.parametrize('name', SKILLS)
def test_blueprint_block_matches_official_fields(name):
    fm, _ = frontmatter(name)
    blueprint = fm['metadata']['hermes']['blueprint']
    assert set(blueprint) <= BLUEPRINT_FIELDS, f'未知 blueprint 字段: {set(blueprint) - BLUEPRINT_FIELDS}'
    schedule = blueprint['schedule']
    assert isinstance(schedule, str) and schedule.strip()
    fields = schedule.split()
    assert len(fields) == 5, f'schedule 应为 cron 五段式: {schedule!r}'
    assert fields[4] != '*', '周级任务的 day-of-week 段必须点名（每周运行）'
    assert re.fullmatch(r'[\d,*/-]+', fields[0]) and re.fullmatch(r'[\d,*/-]+', fields[1])
    assert blueprint.get('deliver', 'origin') == 'origin'
    assert isinstance(blueprint.get('prompt'), str) and len(blueprint['prompt']) > 20
    assert name.replace('-', ' ') in blueprint['prompt'] or name in blueprint['prompt']
    assert blueprint.get('no_agent') is False


@pytest.mark.parametrize('name', SKILLS)
def test_sll_frontmatter_and_required_env(name):
    fm, _ = frontmatter(name)
    assert fm['name'] == name
    assert fm['license'] == SLL
    assert fm['author'] == 'SJF, Hermes Agent'
    assert fm['platforms'] == ['linux', 'macos', 'windows']
    assert re.fullmatch(r'\d+\.\d+\.\d+', fm['version'])
    env = fm['required_environment_variables']
    assert any(e['name'] == 'OPENALEX_API_KEY' for e in env)
    for entry in env:
        assert set(entry) <= {'name', 'prompt', 'help', 'required_for'}
        assert entry.get('prompt') and entry.get('help') and entry.get('required_for')


@pytest.mark.parametrize('name', SKILLS)
def test_watchlist_config_declared_and_documented(name):
    fm, text = frontmatter(name)
    config = fm['metadata']['hermes']['config']
    keys = {entry['key'] for entry in config}
    prefix = name.replace('-', '_')
    assert f'{prefix}.watchlist' in keys
    for entry in config:
        assert set(entry) <= {'key', 'description', 'default', 'prompt'}
        assert entry.get('description')
    # SKILL.md 必须说清安装后如何配置 schedule 与 watchlist
    assert '/suggestions accept' in text
    assert 'hermes config set skills.config.' in text
    assert 'blueprint' in text
    assert '```json' in text, 'watchlist JSON 结构示例缺失'


@pytest.mark.parametrize('name', SKILLS)
def test_self_test_offline_and_live_skipped(name):
    script = ROOT / 'skills' / name / 'scripts' / 'watch.py'
    assert script.is_file()
    result = subprocess.run([sys.executable, str(script), '--self-test'],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert 'SKIP live OpenAlex/Crossref checks' in result.stdout
    assert 'self-test PASS' in result.stdout


@pytest.mark.parametrize('name', SKILLS)
def test_watch_script_is_stdlib_only(name):
    import ast
    tree = ast.parse((ROOT / 'skills' / name / 'scripts' / 'watch.py')
                     .read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = [a.name.split('.')[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots = [node.module.split('.')[0]]
        else:
            continue
        for root in roots:
            assert root in sys.stdlib_module_names, f'非标准库依赖: {root}'


def test_state_files_are_json_round_trippable(tmp_path):
    """两个脚本的状态写入格式都是 JSON，可被对方之外的工具读取。"""
    for payload in ({'10.1/a': {'is_retracted': False, 'signals': []}}, ['doi:10.1/a']):
        path = tmp_path / 'state.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        assert json.loads(path.read_text(encoding='utf-8')) == payload


def test_retraction_watch_uses_update_to_not_relation():
    """回归测试:撤稿信号必须来自 updates:<DOI> 的 update-to 条目。

    早期版本曾查 Crossref relation 字段找 retract 键,漏掉 Retraction
    Watch 数据模型里位于更新记录 update-to 的撤稿条目;relation 字段
    本身不构成撤稿信号。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        'watch', ROOT / 'skills' / 'retraction-watch' / 'scripts' / 'watch.py')
    watch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watch)

    target = '10.1177/1758835920922055'
    records = [
        {'update-to': [{'DOI': target, 'type': 'retraction', 'source': 'retraction-watch'}]},
        {'relation': {'is-retraction-of': [{'id': target}]}},
        {'update-to': [{'DOI': '10.9/other', 'type': 'retraction', 'source': 'publisher'}]},
    ]
    signals = watch.update_signals_from_records(records, target)
    assert signals == ['retraction(retraction-watch)'], signals
    assert 'is-retraction-of' not in ''.join(signals)


def test_retraction_watch_skill_contract_matches_implementation():
    """SKILL.md 的 Crossref 语义必须与 watch.py 实现一致。

    曾出现实现改成 updates:<DOI> 反向查询后 SKILL.md 仍保留
    relation 旧语义（含 blueprint prompt 本身），导致运行时指令与
    脚本行为矛盾。此测试锁住新口径：文档必须含 update-to 表述，
    不得含 relation 扫描表述。
    """
    text = (ROOT / 'skills' / 'retraction-watch' / 'SKILL.md').read_text(encoding='utf-8')
    assert 'update-to' in text
    assert 'filter=updates' in text
    assert 'select=relation' not in text
    assert 'relation 键名' not in text
    assert 'is-retraction-of' not in text

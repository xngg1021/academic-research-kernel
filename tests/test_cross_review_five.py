"""cross-review-five 编排器的离线可测部分。"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "orchestrate", ROOT / "skills" / "cross-review-five" / "scripts" / "orchestrate.py")
oc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(oc)


def test_five_model_table_complete():
    expected = {
        "kimi-k3": ("kimi", "kimi-k3"),
        "dsv4pro": ("deepseek", "deepseek-v4-pro"),
        "glm53": ("zai", "glm-5.3"),
        "gemini38flash": ("google", "gemini-3.8-flash"),
        "gemini31pro": ("google", "gemini-3.1-pro-preview"),
    }
    assert oc.MODELS == expected
    assert oc.DEFAULT_MODELS == list(oc.MODELS)


def test_pairings_rotate_over_all_five():
    keys = ["kimi-k3", "dsv4pro", "glm53", "gemini38flash", "gemini31pro"]
    pairs = oc.pairings(keys)
    assert len(pairs) == 5
    assert pairs[0] == ("kimi-k3", "dsv4pro")
    assert pairs[-1] == ("gemini31pro", "kimi-k3")
    reviewers = {p[0] for p in pairs}
    targets = {p[1] for p in pairs}
    assert reviewers == set(keys) and targets == set(keys)


def test_pairings_under_two_models_is_empty():
    assert oc.pairings(["kimi-k3"]) == []
    assert oc.pairings([]) == []


def test_plan_prompt_renders_paths():
    text = oc.PLAN_PROMPT.format(task_path="T", out_path="O")
    assert "T" in text and "O" in text
    assert "不得修改其他评审者的产出文件" in text


def test_review_prompt_renders_paths():
    text = oc.REVIEW_PROMPT.format(task_path="T", target_path="X", out_path="O")
    assert "T" in text and "X" in text and "O" in text


def test_main_rejects_unknown_model(monkeypatch, capsys):
    rc = oc.main(["--stage", "status", "--models", "no-such-model", str(ROOT)])
    assert rc == 2
    assert "未知模型短名" in capsys.readouterr().err

"""Guard the direction-primitive grouping and its recomputed coverage.

The 2026-09-17 agenda audit found that the direction coverage numbers were
computed from an oral grouping that was never stored. These tests pin the
stored grouping (docs/direction-primitive-mapping.json) and the recompute
script (scripts/recompute_direction_coverage.py) so the numbers can be
reproduced and the old 146/138/136 figures can never silently return.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GROUPING = ROOT / "docs" / "direction-primitive-mapping.json"
MATRIX = ROOT / "docs" / "factor-matrix.json"
RECOMPUTE = ROOT / "scripts" / "recompute_direction_coverage.py"


def _load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def test_grouping_is_valid_json_and_consistent_with_matrix():
    grouping = _load(GROUPING)
    matrix = _load(MATRIX)
    prim_ids = {str(k) for k in matrix["primitives"]}
    assert len(grouping["directions"]) == 6
    names = [d["name"] for d in grouping["directions"]]
    assert names == [
        "Research Object Identity and Lineage",
        "Method / Supplement Miner",
        "Claim-Evidence Graph",
        "Decision / Negative Result Ledger",
        "Learning Error + Adaptive Practice",
        "Constraint Compiler",
    ]
    for d in grouping["directions"]:
        assert d["core_primitives"], d["id"]
        # every referenced primitive exists in the matrix primitive table
        for p in d["core_primitives"] + d["extended_primitives"]:
            assert str(p) in prim_ids, (d["id"], p)
        # core and extended do not overlap
        assert not (set(d["core_primitives"]) & set(d["extended_primitives"])), d["id"]
        assert d["rationale"].strip()


def test_recompute_matches_recorded_baseline():
    out = subprocess.run(
        [sys.executable, str(RECOMPUTE)],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )
    assert out.returncode == 0, out.stderr
    # baseline run is the operational grouping quoted in the research plan
    expect = {
        "Research Object Identity and Lineage": ("88", "37.4"),
        "Method / Supplement Miner": ("85", "36.2"),
        "Decision / Negative Result Ledger": ("63", "26.8"),
        "Claim-Evidence Graph": ("58", "24.7"),
        "Constraint Compiler": ("49", "20.9"),
        "Learning Error + Adaptive Practice": ("29", "12.3"),
    }
    baseline_section = out.stdout.split("=== baseline ===")[1].split("===")[0]
    for name, (count, pct) in expect.items():
        match = re.search(
            rf"^\s*{re.escape(name)}\s+{count} / 235 = {pct}%$",
            baseline_section, re.M,
        )
        assert match, (name, count, pct)


def test_rank_stability_line_present():
    out = subprocess.run(
        [sys.executable, str(RECOMPUTE)],
        capture_output=True, text=True, encoding="utf-8", cwd=ROOT,
    )
    assert out.returncode == 0, out.stderr
    assert "rank stability" in out.stdout.lower()
    # Identity and Method hold the top three in all runs (positions <= 3)
    section = out.stdout.split("=== rank stability")[1]
    for name, expect_pos in [
        ("Research Object Identity and Lineage", "[2, 1, 1]"),
        ("Method / Supplement Miner", "[3, 2, 2]"),
    ]:
        assert expect_pos in section, (name, section)
    assert all(int(x) <= 3 for x in "[2, 1, 1]".strip("[]").split(","))
    assert all(int(x) <= 3 for x in "[3, 2, 2]".strip("[]").split(","))


def test_matrix_has_no_direction_field():
    """The audit found the aggregation rule was never stored in the matrix.
    It must stay in the grouping file, not sneak back into the matrix."""
    matrix = _load(MATRIX)
    for item in matrix["items"]:
        assert "direction" not in item, item["id"]


def test_grouping_mentioned_in_plan_both_languages():
    for f in ["docs/research-plan-v0.en.md", "docs/research-plan-v0.zh.md"]:
        text = (ROOT / f).read_text(encoding="utf-8")
        assert "direction-primitive-mapping.json" in text, f
        assert "recompute_direction_coverage.py" in text, f

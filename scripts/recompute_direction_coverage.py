# -*- coding: utf-8 -*-
"""Recompute direction coverage from the stored primitive grouping.

The agenda audit (2026-09-17) found that the coverage numbers quoted in the
research plan (146/138/136) were computed from an oral grouping that was never
stored. This script recomputes them from docs/direction-primitive-mapping.json
under three sensitivity runs:

    core      -- each direction covers items whose primitives intersect its
                 core set only.
    baseline  -- core plus extended (the intended operational grouping).
    single    -- only the first core primitive of each direction (the
                 narrowest defensible grouping).

It prints the three tables plus a rank-stability summary, so the plan can
quote numbers together with their perturbation range instead of one figure.

Usage: python scripts/recompute_direction_coverage.py
"""

import json
import sys
from collections import OrderedDict
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def covered_count(items, prim_set):
    return sum(1 for it in items if set(it["primitives"]) & prim_set)


def main():
    matrix = load(ROOT / "docs/factor-matrix.json")
    grouping = load(ROOT / "docs/direction-primitive-mapping.json")
    items = matrix["items"]
    total = len(items)

    directions = grouping["directions"]
    prim_names = {str(k): v for k, v in matrix["primitives"].items()}

    runs = OrderedDict()
    runs["single"] = {d["id"]: {d["core_primitives"][0]} for d in directions}
    runs["core"] = {d["id"]: set(d["core_primitives"]) for d in directions}
    runs["baseline"] = {
        d["id"]: set(d["core_primitives"] + d["extended_primitives"])
        for d in directions
    }

    for run_name, sets in runs.items():
        print(f"=== {run_name} ===")
        rows = []
        for d in directions:
            count = covered_count(items, sets[d["id"]])
            pct = count / total * 100
            rows.append((count, pct, d["name"]))
            print(f"  {d['name']:<36} {count:>3} / {total} = {pct:.1f}%")
        order = sorted(rows, reverse=True)
        print("  ranking:", " > ".join(r[2].split()[0] for r in order))
        print()

    print("=== rank stability (position per direction across runs) ===")
    for d in directions:
        positions = []
        for run_name, sets in runs.items():
            counts = {
                dd["id"]: covered_count(items, sets[dd["id"]]) for dd in directions
            }
            ranked = sorted(counts, key=counts.get, reverse=True)
            positions.append(ranked.index(d["id"]) + 1)
        print(f"  {d['name']:<36} positions {positions}")


if __name__ == "__main__":
    main()

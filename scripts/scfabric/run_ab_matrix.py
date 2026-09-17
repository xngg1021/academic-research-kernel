# -*- coding: utf-8 -*-
"""Run the full first-round A/B matrix and save receipts to a JSON file."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import admission as ad  # noqa: E402

if __name__ == "__main__":
    rows = ad.run_matrix(
        workloads=None, scales=("small", "medium", "large"),
        dtype="float64", gain_threshold=1.5)
    out = Path(__file__).resolve().parent / "receipts-a-b-float64.json"
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
    print(f"wrote {out} with {len(rows)} receipts")
    for r in rows:
        import compute_receipt as cr
        print(cr.receipt_headline(r))

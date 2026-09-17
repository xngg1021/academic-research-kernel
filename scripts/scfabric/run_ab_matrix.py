# -*- coding: utf-8 -*-
"""Run the scientific compute fabric A/B matrix with flexible CLI options."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import admission as ad  # noqa: E402
import compute_receipt as cr  # noqa: E402
import workload_profiles as wp  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workloads", nargs="*", default=None,
                        help="Specific workloads to run (default: all)")
    parser.add_argument("--scales", nargs="*", default=["small", "medium", "large"],
                        help="Scales to evaluate (default: small medium large)")
    parser.add_argument("--dtype", default="float64", choices=["float32", "float64"],
                        help="Data precision contract (default: float64)")
    parser.add_argument("--gain-threshold", type=float, default=1.5,
                        help="Speedup threshold required for admission (default: 1.5)")
    parser.add_argument("--warmup", type=int, default=2,
                        help="Warmup iterations before timing (default: 2)")
    parser.add_argument("--repeat", type=int, default=5,
                        help="Repeats for median timing (default: 5)")
    parser.add_argument("--out", type=str, default=None,
                        help="Output JSON file path (default: receipts-a-b-<dtype>.json)")
    args = parser.parse_args(argv)

    out_path = Path(args.out) if args.out else Path(__file__).resolve().parent / f"receipts-a-b-{args.dtype}.json"

    rows = []
    workloads = args.workloads or list(wp.SCALES)
    for w in workloads:
        for s in args.scales:
            receipt = ad.run_admission(
                workload=w, scale=s, dtype=args.dtype,
                gain_threshold=args.gain_threshold,
                warmup=args.warmup, repeat=args.repeat,
            )
            rows.append(receipt)
            print(cr.receipt_headline(receipt))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=2, default=str)
    print(f"wrote {out_path} with {len(rows)} receipts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

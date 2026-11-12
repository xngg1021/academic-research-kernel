#!/usr/bin/env python3
"""Reproducible 30-item real-world scholarly verification & statistical audit benchmark.

Evaluates `academic-research-kernel` without adding any runtime dependencies or
wheel payload bloat:
- Track 1 (N=16): Real published retracted papers (Wakefield 1998, Mehra Lancet 2020,
  Mehra NEJM 2020, Obokata 2014, Snider 2020, Hwang 2005, Dasenbrock-Gammon 2023,
  Shu et al. 2012), hallucinated/non-existent DOIs, and intact landmark controls
  (LeCun 2015, Jordan & Mitchell 2015, Jumper 2021, Krizhevsky 2017, Silver 2016,
  Nuijten 2016).
- Track 2 (N=14): 12 published statistical examples and observations from
  Nuijten et al. (2016, DOI: 10.3758/s13428-015-0664-2, PMC5101263) and
  Bakker & Wicherts (2011, DOI: 10.3758/s13428-011-0089-5, PMC3174372), plus
  2 repository-grounded gate cases (ICLR 2026 partition conservation from
  `docs/benchmarks/iclr2026-openreview-incidence-receipt.json` and dangling-CEG
  pre-submission linting).

Supports `--offline` (default deterministic replay verifying `content_sha256`,
per-item DOI snapshot bindings, and full payload equality) and `--capture-live`
(queries live OpenAlex & Crossref APIs and writes an updated receipt).
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import re
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
for _extra_dir in (
    ROOT / "src",
    ROOT / "skills" / "quantitative-paper-audit" / "scripts",
    ROOT / "skills" / "academic-writing" / "scripts",
):
    _extra_str = str(_extra_dir)
    if _extra_str not in sys.path:
        sys.path.insert(0, _extra_str)

DEFAULT_RECEIPT = ROOT / "docs" / "benchmarks" / "real-world-audit-benchmark-v1.json"

BIBLIOGRAPHIC_CASES = [
    {"id": "B01", "doi": "10.1016/s0140-6736(97)11096-0", "expected_defect": True, "category": "retracted_work", "citation": "Wakefield et al. (1998), The Lancet"},
    {"id": "B02", "doi": "10.1016/s0140-6736(20)31180-6", "expected_defect": True, "category": "retracted_work", "citation": "Mehra et al. (2020), The Lancet"},
    {"id": "B03", "doi": "10.1056/nejmoa2007621", "expected_defect": True, "category": "retracted_work", "citation": "Mehra et al. (2020), NEJM"},
    {"id": "B04", "doi": "10.1038/nature12968", "expected_defect": True, "category": "retracted_work", "citation": "Obokata et al. (2014), Nature"},
    {"id": "B05", "doi": "10.1038/s41586-020-2801-z", "expected_defect": True, "category": "retracted_work", "citation": "Snider et al. (2020), Nature"},
    {"id": "B06", "doi": "10.1126/science.1112286", "expected_defect": True, "category": "retracted_work", "citation": "Hwang et al. (2005), Science"},
    {"id": "B07", "doi": "10.1038/s41586-023-05742-0", "expected_defect": True, "category": "retracted_work", "citation": "Dasenbrock-Gammon et al. (2023), Nature"},
    {"id": "B08", "doi": "10.1073/pnas.1209746109", "expected_defect": True, "category": "retracted_work", "citation": "Shu et al. (2012), PNAS"},
    {"id": "B09", "doi": "10.1038/s41586-2099-99999-z", "expected_defect": True, "category": "hallucinated_doi", "citation": "Synthetic non-existent Nature DOI"},
    {"id": "B10", "doi": "10.1126/science.1107108", "expected_defect": True, "category": "hallucinated_doi", "citation": "Misremembered non-existent Science DOI suffix"},
    {"id": "B11", "doi": "10.1038/nature14539", "expected_defect": False, "category": "intact_control", "citation": "LeCun, Bengio & Hinton (2015), Nature"},
    {"id": "B12", "doi": "10.1126/science.aaa8415", "expected_defect": False, "category": "intact_control", "citation": "Jordan & Mitchell (2015), Science"},
    {"id": "B13", "doi": "10.1038/s41586-021-03819-2", "expected_defect": False, "category": "intact_control", "citation": "Jumper et al. (2021), Nature"},
    {"id": "B14", "doi": "10.1145/3065386", "expected_defect": False, "category": "intact_control", "citation": "Krizhevsky, Sutskever & Hinton (2017), CACM"},
    {"id": "B15", "doi": "10.1038/nature16961", "expected_defect": False, "category": "intact_control", "citation": "Silver et al. (2016), Nature"},
    {"id": "B16", "doi": "10.3758/s13428-015-0664-2", "expected_defect": False, "category": "intact_control", "citation": "Nuijten et al. (2016), Behavior Research Methods"},
]

STATISTICAL_AND_GATE_CASES = [
    {"id": "S01", "kind": "f_lt", "provenance_type": "published_example", "params": {"f": 1.203, "df1": 2, "df2": 56, "threshold": 0.001}, "expected_defect": True, "source_doi": "10.3758/s13428-015-0664-2", "source_pmcid": "PMC5101263", "reported_expression": "F(2,56) = 1.203, p < .001"},
    {"id": "S02", "kind": "f_eq", "provenance_type": "published_example", "params": {"f": 2.78, "df1": 3, "df2": 58, "p": 0.04, "p_literal": "0.04"}, "expected_defect": True, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "F(3, 58) = 2.78, p = .04"},
    {"id": "S03", "kind": "f_eq", "provenance_type": "published_example", "params": {"f": 15.2, "df1": 2, "df2": 20, "p": 0.001, "p_literal": "0.001"}, "expected_defect": True, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "F(2, 20) = 15.2, p = .001"},
    {"id": "S04", "kind": "f_eq", "provenance_type": "published_observation", "params": {"f": 6.646, "df1": 1, "df2": 39, "p": 0.015, "p_literal": "0.015"}, "expected_defect": True, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "F(1, 39) = 6.646, p = .015"},
    {"id": "S05", "kind": "f_eq", "provenance_type": "published_observation", "params": {"f": 1.175, "df1": 1, "df2": 26, "p": 0.020, "p_literal": "0.020"}, "expected_defect": True, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "F(1, 26) = 1.175, p = .020"},
    {"id": "S06", "kind": "f_eq", "provenance_type": "published_observation", "params": {"f": 4.175, "df1": 1, "df2": 26, "p": 0.020, "p_literal": "0.020"}, "expected_defect": True, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "F(1,26) = 4.175, p = .020"},
    {"id": "S07", "kind": "partition", "provenance_type": "repository_receipt_gate", "params": {"total": 19473, "parts": [224, 5134, 8453, 4980]}, "expected_defect": True, "source_doi": "docs/benchmarks/iclr2026-openreview-incidence-receipt.json", "source_pmcid": None, "reported_expression": "ALL_SCORED=19473 vs omitting Desk Reject (682) -> 224+5134+8453+4980=18791"},
    {"id": "S08", "kind": "ceg_dangling_lint", "provenance_type": "constructed_gate_regression", "params": {"claim_text": "Our method improves accuracy by 12.4\\% on DatasetA."}, "expected_defect": True, "source_doi": "skills/academic-writing/scripts/pre_submission_linter.py", "source_pmcid": None, "reported_expression": "support_status='supported' pointing to missing evidence_id='MISSING' with evidence=[]"},
    {"id": "S09", "kind": "f_lt", "provenance_type": "published_example", "params": {"f": 12.03, "df1": 2, "df2": 56, "threshold": 0.001}, "expected_defect": False, "source_doi": "10.3758/s13428-015-0664-2", "source_pmcid": "PMC5101263", "reported_expression": "F(2,56) = 12.03, p < .001"},
    {"id": "S10", "kind": "f_lt", "provenance_type": "published_observation", "params": {"f": 18.11, "df1": 1, "df2": 95, "threshold": 0.001}, "expected_defect": False, "source_doi": "10.3758/s13428-015-0664-2", "source_pmcid": "PMC5101263", "reported_expression": "F[1, 95] = 18.11, p < .001"},
    {"id": "S11", "kind": "f_lt", "provenance_type": "published_observation", "params": {"f": 45.98, "df1": 1, "df2": 47, "threshold": 0.01}, "expected_defect": False, "source_doi": "10.3758/s13428-015-0664-2", "source_pmcid": "PMC5101263", "reported_expression": "F(1, 47) = 45.98, p < .01"},
    {"id": "S12", "kind": "t_lt", "provenance_type": "published_apa_manual_example", "params": {"t": 3.51, "df": 177, "threshold": 0.001}, "expected_defect": False, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "t(177) = 3.51, p < .001"},
    {"id": "S13", "kind": "ci", "provenance_type": "published_apa_manual_example", "params": {"estimate": 0.65, "lower": 0.35, "upper": 0.95, "level": 0.95}, "expected_defect": False, "source_doi": "10.3758/s13428-011-0089-5", "source_pmcid": "PMC3174372", "reported_expression": "d = 0.65, 95% CI [0.35, 0.95]"},
    {
        "id": "S14",
        "kind": "t_eq",
        "provenance_type": "published_example",
        "params": {"t": 2.3, "df": 15, "p": 0.033, "p_literal": "0.033"},
        "expected_defect": False,
        "source_doi": "10.3758/s13428-011-0089-5",
        "source_pmcid": "PMC3174372",
        "reported_expression": "t(15) = 2.3, p = .033",
        "boundary_note": "True t in [2.25, 2.35) yields p in [0.0329, 0.0399]; point-statistic evaluation at t=2.3000 yields p=0.03622 and flags a false positive when input statistic rounding is not intervalized.",
    },
]


def _compute_payload_sha256(payload: dict) -> str:
    raw_canon = json.dumps(
        {k: v for k, v in payload.items() if k != "content_sha256"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw_canon).hexdigest()


def verify_receipt_integrity(recorded: dict) -> None:
    expected = recorded.get("content_sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("Missing or invalid content_sha256 in benchmark receipt")
    actual = _compute_payload_sha256(recorded)
    if actual != expected:
        raise ValueError(f"Benchmark receipt content_sha256 mismatch: got {actual}, expected {expected}")


def _run_cli_json(argv: list[str]) -> tuple[int, dict]:
    from academic_research_kernel import cli
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = cli.main(argv)
    return rc, json.loads(buf.getvalue())


def _is_explicit_404(src_dict: object) -> bool:
    if not isinstance(src_dict, dict):
        return False
    if src_dict.get("status") == "not_found" or src_dict.get("http_status") == 404:
        return True
    err = str(src_dict.get("error") or "").strip()
    return src_dict.get("status") == "failed" and bool(re.search(r"(?:^|\b)HTTP Error 404(?:\b|:)", err))


def _eval_bib_from_snapshot(expected_doi: str, snap: dict) -> tuple[bool, dict]:
    v = snap["verify"]
    u = snap["updates"]
    norm_doi = expected_doi.strip().lower()
    if str(v.get("target_doi", "")).strip().lower() != norm_doi:
        raise ValueError(f"Snapshot verify.target_doi ({v.get('target_doi')!r}) != expected DOI ({norm_doi!r})")
    if str(u.get("target_doi", "")).strip().lower() != norm_doi:
        raise ValueError(f"Snapshot updates.target_doi ({u.get('target_doi')!r}) != expected DOI ({norm_doi!r})")

    srcs = v.get("sources") or {}
    oa = srcs.get("openalex") or {}
    cr = srcs.get("crossref") or {}
    for src_name, src_obj in (("openalex", oa), ("crossref", cr)):
        if not isinstance(src_obj, dict):
            raise RuntimeError(f"Inconclusive bibliographic snapshot for {expected_doi}: missing {src_name} source record")
        if src_obj.get("status") == "ok":
            work_obj = src_obj.get("work")
            if not isinstance(work_obj, dict) or not work_obj:
                raise RuntimeError(f"Inconclusive bibliographic snapshot for {expected_doi}: {src_name} status='ok' missing work payload")
            if src_name == "openalex" and not isinstance(work_obj.get("is_retracted"), bool):
                raise RuntimeError(f"Inconclusive bibliographic snapshot for {expected_doi}: openalex work missing boolean is_retracted")
        elif not _is_explicit_404(src_obj):
            raise RuntimeError(
                f"Inconclusive bibliographic snapshot for {expected_doi}: {src_name} status={src_obj.get('status')!r}, "
                f"error={src_obj.get('error')!r}"
            )

    oa_ok = oa.get("status") == "ok"
    cr_ok = cr.get("status") == "ok"
    not_found = (not oa_ok) and (not cr_ok)

    if oa_ok and cr_ok and not isinstance(v.get("comparison"), dict):
        raise RuntimeError(f"Inconclusive bibliographic snapshot for {expected_doi}: missing comparison record")

    sig_counts = u.get("signal_counts")
    if u.get("status") != "ok" or bool(u.get("truncated")) or not isinstance(sig_counts, dict):
        raise RuntimeError(
            f"Inconclusive update-lookup snapshot for {expected_doi}: status={u.get('status')!r}, "
            f"truncated={u.get('truncated')!r}, signal_counts={type(sig_counts).__name__}"
        )

    oa_ret = bool(oa["work"].get("is_retracted")) if oa_ok else False
    cr_ret = bool(cr["work"].get("is_retracted")) if cr_ok else False
    upd_ret = int(sig_counts.get("retraction", 0)) > 0
    cmp_obj = v.get("comparison") or {}
    mismatch = bool(cmp_obj.get("identity_binding_mismatch"))
    detected_defect = bool(not_found or mismatch or oa_ret or cr_ret or upd_ret)
    return detected_defect, {
        "not_found": not_found,
        "openalex_retracted": oa_ret,
        "crossref_retracted": cr_ret,
        "update_retraction_signals": int(sig_counts.get("retraction", 0)),
    }


def _canon_float(value: float | None) -> float | None:
    if value is None:
        return None
    return float(f"{float(value):.12g}")


def _eval_stat_case(case: dict) -> tuple[bool, dict]:
    import pre_submission_linter
    import recompute

    kind = case["kind"]
    p = case["params"]
    if kind == "f_lt":
        rec = recompute.p_from_f(p["f"], p["df1"], p["df2"], reported=p["threshold"])
        consistent = bool(rec["recomputed"] < p["threshold"])
        return (not consistent), {"recomputed_p": _canon_float(rec["recomputed"]), "consistent": consistent}
    if kind == "f_eq":
        rec = recompute.p_from_f(p["f"], p["df1"], p["df2"], reported=p["p"])
        m = recompute.check_p_match(p["p"], rec["recomputed"], reported_literal=p["p_literal"])
        return (not m["consistent"]), {"recomputed_p": _canon_float(rec["recomputed"]), "consistent": m["consistent"]}
    if kind == "t_lt":
        rec = recompute.p_from_t(p["t"], p["df"], reported=p["threshold"])
        consistent = bool(rec["recomputed"] < p["threshold"])
        return (not consistent), {"recomputed_p": _canon_float(rec["recomputed"]), "consistent": consistent}
    if kind == "t_eq":
        rec = recompute.p_from_t(p["t"], p["df"], reported=p["p"])
        m = recompute.check_p_match(p["p"], rec["recomputed"], reported_literal=p["p_literal"])
        return (not m["consistent"]), {"recomputed_p": _canon_float(rec["recomputed"]), "consistent": m["consistent"]}
    if kind == "ci":
        m = recompute.check_ci_consistency(p["estimate"], p["lower"], p["upper"], level=p["level"])
        return (not m["consistent"]), {"consistent": m["consistent"], "implied_se": _canon_float(m.get("implied_se"))}
    if kind == "partition":
        m = recompute.check_partition_conservation(p["total"], p["parts"])
        return (not m["consistent"]), {"consistent": m["consistent"], "sum_parts": m.get("sum_parts"), "missing_or_excess": m.get("missing_or_excess")}
    if kind == "ceg_dangling_lint":
        with tempfile.TemporaryDirectory(prefix="ark-bench-ceg-") as td:
            td_p = Path(td)
            tex = td_p / "main.tex"
            ceg = td_p / "dangling.json"
            tex.write_text(
                "\\documentclass{article}\n\\begin{document}\n\\begin{abstract}\n"
                "% ark:claim=C1\n"
                f"{p['claim_text']}\n"
                "\\end{abstract}\n\\section{Introduction}\nText.\n\\section{Limitations}\nText.\n\\end{document}\n",
                encoding="utf-8",
            )
            ceg.write_text(
                json.dumps({
                    "claims": [{"id": "C1", "text": p["claim_text"]}],
                    "evidence": [],
                    "support_edges": [{"claim_id": "C1", "evidence_id": "MISSING", "support_status": "supported"}],
                }),
                encoding="utf-8",
            )
            rep = pre_submission_linter.lint_manuscript(tex, venue="iclr", ceg_path=ceg, require_ceg_binding=True)
            flagged = any(h["code"] == "UNGROUNDED_QUANTITATIVE_CLAIM" for h in rep["hits"])
            return flagged, {"flagged_ungrounded": flagged}
    raise ValueError(f"Unknown case kind: {kind}")


def _confusion(rows: list[dict]) -> dict:
    tp = sum(1 for r in rows if r["expected_defect"] and r["detected_defect"])
    tn = sum(1 for r in rows if (not r["expected_defect"]) and (not r["detected_defect"]))
    fp = sum(1 for r in rows if (not r["expected_defect"]) and r["detected_defect"])
    fn = sum(1 for r in rows if r["expected_defect"] and (not r["detected_defect"]))
    return {
        "n": len(rows),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "specificity": round(tn / (tn + fp), 4) if (tn + fp) else None,
        "accuracy": round((tp + tn) / len(rows), 4) if rows else None,
    }


def run_benchmark(capture_live: bool = False, receipt_path: Path = DEFAULT_RECEIPT) -> dict:
    from academic_research_kernel import __version__

    frozen_snaps: dict[str, dict] = {}
    snap_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not capture_live:
        existing = json.loads(receipt_path.read_text(encoding="utf-8"))
        verify_receipt_integrity(existing)
        frozen_snaps = existing["frozen_live_bibliographic_snapshots"]
        snap_date = str(existing["snapshot_date_utc"])

    bib_rows = []
    for c in BIBLIOGRAPHIC_CASES:
        doi = c["doi"]
        if capture_live:
            v_rc, v_out = _run_cli_json(["verify-source", doi])
            u_rc, u_out = _run_cli_json(["verify-source", doi, "--check-updates"])
            u_clean = {k: val for k, val in u_out.items() if k != "queried_at"}
            snap = {"verify_rc": v_rc, "verify": v_out, "updates_rc": u_rc, "updates": u_clean}
            frozen_snaps[c["id"]] = snap
        else:
            if c["id"] not in frozen_snaps:
                raise KeyError(f"Missing frozen bibliographic snapshot for {c['id']}")
            snap = frozen_snaps[c["id"]]
        detected, detail = _eval_bib_from_snapshot(doi, snap)
        bib_rows.append({
            "id": c["id"],
            "doi": doi,
            "category": c["category"],
            "citation": c["citation"],
            "expected_defect": c["expected_defect"],
            "detected_defect": detected,
            "correct": detected == c["expected_defect"],
            "detail": detail,
        })

    stat_rows = []
    for c in STATISTICAL_AND_GATE_CASES:
        detected, detail = _eval_stat_case(c)
        row = {
            "id": c["id"],
            "kind": c["kind"],
            "provenance_type": c["provenance_type"],
            "source_doi": c["source_doi"],
            "source_pmcid": c["source_pmcid"],
            "reported_expression": c["reported_expression"],
            "expected_defect": c["expected_defect"],
            "detected_defect": detected,
            "correct": detected == c["expected_defect"],
            "detail": detail,
        }
        if "boundary_note" in c:
            row["boundary_note"] = c["boundary_note"]
        stat_rows.append(row)

    payload = {
        "schema": "ark-real-world-audit-benchmark/1.0",
        "kernel_version": __version__,
        "snapshot_date_utc": snap_date,
        "summary": {
            "bibliographic_track": _confusion(bib_rows),
            "statistical_and_gate_track": _confusion(stat_rows),
            "combined": _confusion(bib_rows + stat_rows),
        },
        "known_limitations": [
            "S14 (Bakker & Wicherts 2011, t(15)=2.3, p=.033) is a documented false positive under point-statistic recomputation because recompute.py bounds p-value rounding intervals without varying the rounded input statistic across [2.25, 2.35).",
            "Track 2 combines 12 published statistical examples/observations (PMC5101263, PMC3174372; S12 and S13 derive from the same APA Manual reporting example) with 2 repository-grounded partition/CEG gate cases (S07, S08).",
            "Bibliographic offline replay verifies deterministic classification over frozen OpenAlex/Crossref API responses; pass --capture-live to re-query live upstream APIs.",
        ],
        "bibliographic_results": bib_rows,
        "statistical_and_gate_results": stat_rows,
        "frozen_live_bibliographic_snapshots": frozen_snaps,
    }
    payload["content_sha256"] = _compute_payload_sha256(payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", help="Deterministic offline replay against frozen receipt (default)")
    mode.add_argument("--capture-live", action="store_true", help="Query live OpenAlex & Crossref APIs and write updated benchmark receipt")
    ap.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT, help="Benchmark receipt JSON path")
    args = ap.parse_args(argv)

    if args.capture_live:
        payload = run_benchmark(capture_live=True, receipt_path=args.receipt)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        recorded = json.loads(args.receipt.read_text(encoding="utf-8"))
        verify_receipt_integrity(recorded)
        payload = run_benchmark(capture_live=False, receipt_path=args.receipt)
        if payload != recorded:
            raise AssertionError("Offline benchmark replay drifted from recorded receipt payload")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

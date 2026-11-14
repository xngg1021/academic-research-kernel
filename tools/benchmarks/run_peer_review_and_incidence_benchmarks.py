#!/usr/bin/env python3
"""Reproducible builder & verifier for the 5-venue OpenReview forensics and ICLR 2026 keyword-screening receipts.

Upstream frozen public mirrors:
- Five-venue metadata mirrors: `https://github.com/papercopilot/paperlists` at commit
  `181a85021c63ab26745c42ed70a9d9ea7b57ad7e` (`iclr/iclr2026.json`, `iclr/iclr2027.json`,
  `icml/icml2026.json`, `nips/nips2025.json`, `colm/colm2025.json`).
- ICLR 2026 review text corpus: `https://huggingface.co/datasets/insomnia7/iclr2026_stats` at commit
  `50507ab355c3442f7f4dd2a3df0e18aee8e0edbc` (`iclr2026_stats.jsonl`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_PEER_RECEIPT = ROOT / "docs" / "benchmarks" / "peer-review-forensics-2025-2027-v1.json"
DEFAULT_INCIDENCE_RECEIPT = ROOT / "docs" / "benchmarks" / "iclr2026-openreview-incidence-receipt.json"

PAPERCOPILOT_COMMIT = "181a85021c63ab26745c42ed70a9d9ea7b57ad7e"
HF_STATS_COMMIT = "50507ab355c3442f7f4dd2a3df0e18aee8e0edbc"

FIVE_VENUES = (
    (
        "ICLR.cc/2026/Conference",
        "all_public_submissions",
        "1-10 even integers (2, 4, 6, 8, 10); non-positive rating=0 entries isolated in non_positive_rating_anomalies",
        "iclr/iclr2026.json",
        ("iclr2026.json",),
        "fc6f5e5b6ba0fb28bec691a8b8d7a922e9d7bb1615209695ad79fafe62a75d4a",
        88818779,
    ),
    (
        "ICLR.cc/2027/Conference",
        "public_rebuttal_window_snapshot",
        "1-4 integers (1, 2, 3, 4)",
        "iclr/iclr2027.json",
        ("iclr2027_20261112_181a8502.json", "iclr2027.json"),
        "c885c659e8b00c6ed3873f667f43ce0246166819b068e0e9b169253f43e11a04",
        210812868,
    ),
    (
        "ICML.cc/2026/Conference",
        "accepted_public_submissions",
        "1-5 integer recommendations",
        "icml/icml2026.json",
        ("icml2026.json",),
        "4d7bdf4090a48d41f605d831ab0d6cdd0ab1f0d18cdfc73caa86affff3445ccf",
        30546029,
    ),
    (
        "NeurIPS.cc/2025/Conference",
        "accepted_public_submissions",
        "1-6 integer ratings",
        "nips/nips2025.json",
        ("nips2025.json",),
        "70fed9e85ceef1557c629a192ed04a1f43aea33644e3a62570d64467834574d4",
        38038097,
    ),
    (
        "colmweb.org/COLM/2025/Conference",
        "accepted_public_submissions",
        "1-10 ratings",
        "colm/colm2025.json",
        ("colm2025.json",),
        "c20ca69ed00126d8ad5d2bc9ef5fa13d2cd12aa05798751d871bf218805660d4",
        1965990,
    ),
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def build_five_venue_receipt(mirror_dir: Path) -> dict:
    from academic_research_kernel import __version__, openreview_audit as ora

    venues_out = []
    for vid, scope, scale, up_path, cand_names, exp_sha, exp_bytes in FIVE_VENUES:
        matched_file = None
        for cname in cand_names:
            cand = mirror_dir / cname
            if not cand.exists() and (mirror_dir / up_path).exists():
                cand = mirror_dir / up_path
            if cand.exists() and cand.stat().st_size == exp_bytes and _sha256_file(cand) == exp_sha:
                matched_file = cand
                break
        if matched_file is None:
            raise FileNotFoundError(
                f"Missing frozen mirror for {vid} ({up_path} @ {PAPERCOPILOT_COMMIT}, expected sha256={exp_sha})"
            )

        recs = json.loads(matched_file.read_text(encoding="utf-8"))
        summary = ora.summarize_venue_mirror(recs)

        means = []
        seen = set()
        for r in recs:
            if not isinstance(r, dict):
                continue
            fid = r.get("id") or r.get("openreview_forum")
            if fid:
                if fid in seen:
                    continue
                seen.add(fid)
            raw_r = ora._parse_semi_numbers(r.get("rating"))
            if not raw_r and r.get("recommendation") is not None:
                raw_r = ora._parse_semi_numbers(r.get("recommendation"))
            pos_r = [x for x in raw_r if x > 0]
            if pos_r:
                means.append(sum(pos_r) / len(pos_r))
        means.sort()

        def _q(p: float) -> float:
            idx = int(round((len(means) - 1) * p))
            return round(means[idx], 4)

        wc_med = summary["review_word_count_stats"]["median"] if summary["review_word_count_stats"] else None
        venues_out.append({
            "venue_id": vid,
            "scope": scope,
            "rating_scale": scale,
            "upstream_repository": "https://github.com/papercopilot/paperlists",
            "upstream_commit": PAPERCOPILOT_COMMIT,
            "upstream_path": up_path,
            "upstream_frozen_url": f"https://github.com/papercopilot/paperlists/blob/{PAPERCOPILOT_COMMIT}/{up_path}",
            "mirror_bytes": exp_bytes,
            "mirror_sha256": exp_sha,
            "reproduction_command": f"academic-research-kernel openreview-audit --venue-summary {Path(up_path).name}",
            "raw_record_count": summary["raw_record_count"],
            "duplicate_records_skipped": summary["duplicate_records_skipped"],
            "paper_count": summary["total_submissions"],
            "scored_paper_count": summary["scored_submissions"],
            "multi_reviewer_paper_count": summary["review_forensics"]["multi_review_submissions"],
            "total_reviews": summary["total_reviews"],
            "non_positive_rating_anomalies": summary["non_positive_rating_anomalies"],
            "raw_rating_histogram": summary["raw_rating_histogram"],
            "overall_paper_mean": round(sum(means) / len(means), 4),
            "paper_mean_quantiles": {
                "min": round(means[0], 4),
                "p25": _q(0.25),
                "median": round(statistics.median(means), 4),
                "p75": _q(0.75),
                "p90": _q(0.90),
                "max": round(means[-1], 4),
            },
            "review_word_count_median": wc_med,
            "word_count_median_by_confidence": summary["review_forensics"]["word_count_median_by_confidence"],
            "unanimous_identical_rating_count": summary["review_forensics"]["unanimous_identical_rating_count"],
            "unanimous_identical_rating_share": summary["review_forensics"]["unanimous_identical_rating_share"],
        })

    return {
        "schema": "ark-peer-review-forensics-receipt/2.0",
        "kernel_version": __version__,
        "snapshot_date_utc": "2026-11-14",
        "upstream_source": {
            "repository": "https://github.com/papercopilot/paperlists",
            "frozen_commit": PAPERCOPILOT_COMMIT,
            "reproduction_script": "python tools/benchmarks/run_peer_review_and_incidence_benchmarks.py --mirror-dir <dir>",
        },
        "methodological_notes": [
            "All counts, histograms, quantiles, and word-count medians are deterministically computed by academic_research_kernel.openreview_audit.summarize_venue_mirror over the exact SHA-256-verified files from papercopilot/paperlists@181a85021c63ab26745c42ed70a9d9ea7b57ad7e.",
            "Non-positive rating tokens (such as the 1,319 rating=0 entries across 1,096 ICLR 2026 submissions) are preserved in non_positive_rating_anomalies and excluded from positive review-score means and unanimous-score denominators rather than silently dropped or averaged as valid 2-10 scores.",
            "Confidence values (1-5 or 1-4) reflect reviewer self-reported confidence scores in OpenReview metadata, not independently verified domain-expertise credentials; unanimous identical-score rates and word-count distributions are descriptive structural indicators whose values depend on rating-scale cardinality, submission stage, and public acceptance filtering.",
            "PaperCopilot JSON mirrors leave wc_reply_reviewers/wc_reply_authors at zero and aggregate decision/meta-review notes into replies_avg differently across venues; cross-venue zero-discussion rates are therefore omitted from headline comparisons.",
        ],
        "totals": {
            "venue_count": len(venues_out),
            "total_raw_records": sum(v["raw_record_count"] for v in venues_out),
            "total_unique_submissions": sum(v["paper_count"] for v in venues_out),
            "total_scored_papers": sum(v["scored_paper_count"] for v in venues_out),
            "total_positive_reviews": sum(v["total_reviews"] for v in venues_out),
        },
        "venues": venues_out,
    }


def verify_receipts_offline(peer_path: Path = DEFAULT_PEER_RECEIPT, inc_path: Path = DEFAULT_INCIDENCE_RECEIPT) -> dict:
    peer = json.loads(peer_path.read_text(encoding="utf-8"))
    venues = peer["venues"]
    assert peer["totals"]["venue_count"] == len(venues) == 5
    assert peer["totals"]["total_raw_records"] == sum(v["raw_record_count"] for v in venues)
    assert peer["totals"]["total_unique_submissions"] == sum(v["paper_count"] for v in venues)
    assert peer["totals"]["total_scored_papers"] == sum(v["scored_paper_count"] for v in venues)
    assert peer["totals"]["total_positive_reviews"] == sum(v["total_reviews"] for v in venues)
    exp_sha_by_vid = {vid: exp_sha for vid, _, _, _, _, exp_sha, _ in FIVE_VENUES}
    exp_size_by_vid = {vid: exp_sz for vid, _, _, _, _, _, exp_sz in FIVE_VENUES}
    for v in venues:
        assert v["upstream_commit"] == PAPERCOPILOT_COMMIT
        assert v["mirror_sha256"] == exp_sha_by_vid[v["venue_id"]]
        assert v["mirror_bytes"] == exp_size_by_vid[v["venue_id"]]
        calc_share = round(v["unanimous_identical_rating_count"] / v["multi_reviewer_paper_count"], 4)
        assert calc_share == v["unanimous_identical_rating_share"]

    inc = json.loads(inc_path.read_text(encoding="utf-8"))
    assert inc["measurement_scope"] == "lexical_keyword_screening_mention_rate"
    assert inc["upstream_sources"]["metadata_snapshot"]["commit"] == PAPERCOPILOT_COMMIT
    assert inc["upstream_sources"]["metadata_snapshot"]["sha256"] == exp_sha_by_vid["ICLR.cc/2026/Conference"]
    assert inc["upstream_sources"]["review_text_corpus"]["commit"] == HF_STATS_COMMIT
    assert inc["upstream_sources"]["review_text_corpus"]["sha256"] == "01f394abceb02bb382471b89462cf7abbbd77018dfbb56648ddcc36d545738d1"
    pc = inc["partition_conservation"]
    tiers = inc["tiers"]
    assert tiers["Oral"]["papers_n"] + tiers["Poster"]["papers_n"] + tiers["Rejected"]["papers_n"] + tiers["Withdrawn"]["papers_n"] == pc["standard_decision_tiers_sum"]
    assert pc["standard_decision_tiers_sum"] + pc["desk_reject_with_reviews"] == pc["total_scored_manuscripts"]
    for t_name, t_obj in tiers.items():
        pn = int(t_obj["papers_n"])
        assert pn > 0, f"Empty tier {t_name}"
        ha = t_obj["hit_any"]
        assert round(100.0 * int(ha["k"]) / pn, 1) == ha["pct"], f"hit_any pct mismatch in {t_name}"
        for cat_k, cat_obj in (t_obj.get("by_category") or {}).items():
            assert round(100.0 * int(cat_obj["k"]) / pn, 1) == cat_obj["pct"], f"{cat_k} pct mismatch in {t_name}"
    return {"peer_totals": peer["totals"], "incidence_scored_manuscripts": pc["total_scored_manuscripts"]}


def verify_iclr2026_incidence_raw(mirror_dir: Path, inc_path: Path = DEFAULT_INCIDENCE_RECEIPT) -> dict:
    from academic_research_kernel import openreview_audit as ora

    inc = json.loads(inc_path.read_text(encoding="utf-8"))
    meta_p = mirror_dir / "iclr2026.json"
    jsonl_p = mirror_dir / "iclr2026_stats.jsonl"
    assert _sha256_file(meta_p) == inc["upstream_sources"]["metadata_snapshot"]["sha256"]
    assert _sha256_file(jsonl_p) == inc["upstream_sources"]["review_text_corpus"]["sha256"]

    pats = {k: re.compile(v, re.I) for k, v in inc["methodology"]["regex_patterns"].items()}
    meta_recs = json.loads(meta_p.read_text(encoding="utf-8"))
    meta_by_id = {str(r.get("id") or r.get("openreview_forum")): r for r in meta_recs if isinstance(r, dict)}

    rows_n = 0
    joined_scored = 0
    total_revs = 0
    any_hits = 0
    seen = set()
    with jsonl_p.open("r", encoding="utf-8") as fh:
        for line in fh:
            rows_n += 1
            obj = json.loads(line)
            fid = str(obj.get("id") or "")
            if not fid or fid in seen:
                continue
            seen.add(fid)
            mrec = meta_by_id.get(fid)
            revs = [rv for rv in (obj.get("reviews") or []) if isinstance(rv, dict) and rv.get("rating") is not None]
            if not mrec or not revs:
                continue
            joined_scored += 1
            total_revs += len(revs)
            blob = "\n".join(f"{rv.get('weaknesses') or ''}\n{rv.get('questions') or ''}" for rv in revs)
            if any(rx.search(blob) for rx in pats.values()):
                any_hits += 1
    assert rows_n == inc["upstream_sources"]["review_text_corpus"]["total_rows"]
    assert joined_scored == inc["partition_conservation"]["total_scored_manuscripts"]
    assert total_revs == inc["partition_conservation"]["total_official_reviews"]
    assert any_hits == inc["tiers"]["ALL_SCORED"]["hit_any"]["k"]
    return {"rows": rows_n, "joined_scored": joined_scored, "official_reviews": total_revs, "any_keyword_hits": any_hits}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mirror-dir", type=Path, help="Directory holding frozen PaperCopilot JSON mirrors to rebuild five-venue receipt")
    ap.add_argument("--verify-iclr2026-incidence", action="store_true", help="Also replay 316MB iclr2026_stats.jsonl inside --mirror-dir")
    ap.add_argument("--verify-receipts", action="store_true", help="Verify stored JSON receipts offline")
    args = ap.parse_args(argv)

    if args.mirror_dir:
        peer_doc = build_five_venue_receipt(args.mirror_dir)
        DEFAULT_PEER_RECEIPT.write_text(json.dumps(peer_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out = {"rebuilt_five_venues": peer_doc["totals"]}
        if args.verify_iclr2026_incidence:
            out["verified_iclr2026_incidence"] = verify_iclr2026_incidence_raw(args.mirror_dir)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    res = verify_receipts_offline()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

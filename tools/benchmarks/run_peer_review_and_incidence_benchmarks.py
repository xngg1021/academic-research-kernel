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
import math
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
FROZEN_SNAPSHOT_DATE_UTC = "2026-11-14"
HF_STATS_COMMIT = "50507ab355c3442f7f4dd2a3df0e18aee8e0edbc"
HF_STATS_SHA256 = "01f394abceb02bb382471b89462cf7abbbd77018dfbb56648ddcc36d545738d1"
HF_STATS_BYTES = 316261882

INCIDENCE_CAT_KEYS = ("hit_dispersion", "hit_format", "hit_table_quant", "hit_bib", "hit_repro")
INCIDENCE_REGEX_TO_HIT = {
    "dispersion_error_bars": "hit_dispersion",
    "format_section_page": "hit_format",
    "table_quant_ablation": "hit_table_quant",
    "citation_baseline": "hit_bib",
    "reproducibility_code": "hit_repro",
}
INCIDENCE_REGEX_PATTERNS = {
    "dispersion_error_bars": r"\b(?:error\s+bars?|standard\s+deviations?|std\b|stdev\b|confidence\s+intervals?|statistical\s+significance|multiple\s+(?:runs|seeds)|random\s+seeds?|variance\s+across)\b",
    "format_section_page": r"\b(?:typos?|grammatical|grammar\s+errors?|broken\s+references?|missing\s+references?|citation\s+format|template|page\s+limit|over\s+length|limitations?\s+section|no\s+limitations?|lack\s+of\s+limitations?|unresolved\s+reference)\b",
    "table_quant_ablation": r"\b(?:inconsistent\s+numbers?|mismatch\s+between\s+table|table\s+\d+\s+and\s+table\s+\d+|ablation\s+study\s+is\s+missing|no\s+ablation|marginal\s+improvement|overclaimed|over-claimed|hyperbole|exaggerated|numbers?\s+in\s+table\s+\d+\s+do\s+not\\s+match|sum\s+to\s+100)\b".replace("\\\\s", "\\s"),
    "citation_baseline": r"\b(?:missing\s+citations?|missing\s+references?|outdated\s+baselines?|recent\s+baselines?|duplicate\s+citations?|duplicate\s+references?|wrong\s+citation|incorrect\s+citation|hallucinated\s+reference|non-existent\s+reference)\b",
    "reproducibility_code": r"\b(?:no\s+code|code\s+is\s+not\s+provided|code\s+is\s+not\s+available|missing\s+code|anonymous\s+(?:code|repo|repository|link)|reproducib(?:le|ility)|hyperparameters?\s+are\s+not\s+specified|implementation\s+details?\s+are\s+missing)\b",
}

FIVE_VENUES = (
    (
        "ICLR.cc/2026/Conference",
        "all_public_submissions_snapshot",
        "2-10 even integers (2, 4, 6, 8, 10); non-positive rating=0 entries isolated in non_positive_rating_anomalies",
        (2, 4, 6, 8, 10),
        None,
        None,
        "iclr/iclr2026.json",
        ("iclr2026.json",),
        "fc6f5e5b6ba0fb28bec691a8b8d7a922e9d7bb1615209695ad79fafe62a75d4a",
        88818779,
    ),
    (
        "ICLR.cc/2027/Conference",
        "public_rebuttal_window_snapshot",
        "1-4 integers (1, 2, 3, 4)",
        (1, 2, 3, 4),
        None,
        None,
        "iclr/iclr2027.json",
        ("iclr2027_20261112_181a8502.json", "iclr2027.json"),
        "c885c659e8b00c6ed3873f667f43ce0246166819b068e0e9b169253f43e11a04",
        210812868,
    ),
    (
        "ICML.cc/2026/Conference",
        "main_track_accepted_public_snapshot",
        "1-6 integer recommendations (1, 2, 3, 4, 5, 6)",
        (1, 2, 3, 4, 5, 6),
        ("main",),
        ("Oral", "Spotlight", "Poster"),
        "icml/icml2026.json",
        ("icml2026.json",),
        "4d7bdf4090a48d41f605d831ab0d6cdd0ab1f0d18cdfc73caa86affff3445ccf",
        30546029,
    ),
    (
        "NeurIPS.cc/2025/Conference",
        "main_track_accepted_public_snapshot",
        "1-6 integer ratings (1, 2, 3, 4, 5, 6); Datasets & Benchmarks, Position, and public Reject cohorts preserved in mirror_cohort_breakdown",
        (1, 2, 3, 4, 5, 6),
        ("main",),
        ("Oral", "Spotlight", "Poster"),
        "nips/nips2025.json",
        ("nips2025.json",),
        "70fed9e85ceef1557c629a192ed04a1f43aea33644e3a62570d64467834574d4",
        38038097,
    ),
    (
        "colmweb.org/COLM/2025/Conference",
        "main_track_accepted_public_snapshot",
        "1-10 integer ratings (1..10)",
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        None,
        ("Oral", "Spotlight", "Poster"),
        "colm/colm2025.json",
        ("colm2025.json",),
        "c20ca69ed00126d8ad5d2bc9ef5fa13d2cd12aa05798751d871bf218805660d4",
        1965990,
    ),
)


def require(cond: bool, msg: str) -> None:
    """Enforce benchmark invariants even under python -O."""
    if not cond:
        raise ValueError(msg)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(4 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def _canonical_body_sha256(doc: dict) -> str:
    body = {k: v for k, v in doc.items() if k != "receipt_sha256"}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def build_five_venue_receipt(mirror_dir: Path) -> dict:
    from collections import Counter
    from academic_research_kernel import __version__, openreview_audit as ora

    venues_out = []
    full_mirror_unique_total = 0
    for vid, scope, scale, valid_scores, track_filter, status_filter, up_path, cand_names, exp_sha, exp_bytes in FIVE_VENUES:
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

        all_recs = json.loads(matched_file.read_text(encoding="utf-8"))
        full_summary = ora.summarize_venue_mirror(all_recs)
        full_mirror_unique_total += int(full_summary["total_submissions"])

        track_status_counts: Counter[tuple[str, str]] = Counter()
        out_of_main_scale_by_track: Counter[str] = Counter()
        out_of_main_scale_papers: set[str] = set()
        valid_set = set(valid_scores)
        cohort_recs: list[dict] = []
        for idx_r, r in enumerate(all_recs):
            if not isinstance(r, dict):
                continue
            tr = str(r.get("track") or "<unspecified>")
            st = str(r.get("status") or "<unspecified>")
            track_status_counts[(tr, st)] += 1
            raw_r0 = ora._parse_semi_numbers(r.get("rating"))
            if not raw_r0 and r.get("recommendation") is not None:
                raw_r0 = ora._parse_semi_numbers(r.get("recommendation"))
            outside = [x for x in raw_r0 if x > 0 and x not in valid_set]
            if outside:
                out_of_main_scale_by_track[tr] += len(outside)
                out_of_main_scale_papers.add(str(r.get("id") or r.get("openreview_forum") or f"row-{idx_r}"))
            if track_filter is not None and tr not in track_filter:
                continue
            if status_filter is not None and st not in status_filter:
                continue
            cohort_recs.append(r)

        summary = ora.summarize_venue_mirror(cohort_recs)

        means = []
        multi_review_counts: Counter[int] = Counter()
        seen = set()
        for r in cohort_recs:
            fid = r.get("id") or r.get("openreview_forum")
            if fid:
                if fid in seen:
                    continue
                seen.add(fid)
            raw_r = ora._parse_semi_numbers(r.get("rating"))
            if not raw_r and r.get("recommendation") is not None:
                raw_r = ora._parse_semi_numbers(r.get("recommendation"))
            pos_r = [x for x in raw_r if x > 0]
            for pv in pos_r:
                require(
                    pv in valid_set,
                    f"{vid} primary cohort contains rating {pv} outside declared_valid_ratings {valid_scores}",
                )
            if pos_r:
                means.append(sum(pos_r) / len(pos_r))
            if len(pos_r) >= 2:
                multi_review_counts[len(pos_r)] += 1
        means.sort()

        def _q(p: float) -> float:
            idx = int(round((len(means) - 1) * p))
            return round(means[idx], 4)

        probs = [n / summary["total_reviews"] for n in summary["raw_rating_histogram"].values()]
        iid_baseline = (
            round(
                sum(n * sum(p ** m for p in probs) for m, n in multi_review_counts.items())
                / sum(multi_review_counts.values()),
                4,
            )
            if multi_review_counts
            else None
        )
        modal_multi_m = max(multi_review_counts.items(), key=lambda kv: (kv[1], -kv[0]))[0] if multi_review_counts else None
        mean_revs = round(summary["total_reviews"] / summary["scored_submissions"], 4) if summary["scored_submissions"] else 0.0

        wc_med = summary["review_word_count_stats"]["median"] if summary["review_word_count_stats"] else None
        breakdown_rows = [
            {"track": tr_k, "status": st_k, "records": cnt_v}
            for (tr_k, st_k), cnt_v in sorted(track_status_counts.items())
        ]
        venues_out.append({
            "venue_id": vid,
            "scope": scope,
            "cohort_filter": {
                "tracks": list(track_filter) if track_filter is not None else "all_present_in_mirror",
                "statuses": list(status_filter) if status_filter is not None else "all_present_in_mirror",
            },
            "rating_scale": scale,
            "declared_valid_ratings": list(valid_scores),
            "upstream_repository": "https://github.com/papercopilot/paperlists",
            "upstream_commit": PAPERCOPILOT_COMMIT,
            "upstream_path": up_path,
            "upstream_frozen_url": f"https://github.com/papercopilot/paperlists/blob/{PAPERCOPILOT_COMMIT}/{up_path}",
            "mirror_bytes": exp_bytes,
            "mirror_sha256": exp_sha,
            "reproduction_command": (
                f"academic-research-kernel openreview-audit --venue-summary {Path(up_path).name}"
                if track_filter is None and status_filter is None
                else "python tools/benchmarks/run_peer_review_and_incidence_benchmarks.py --mirror-dir <dir>"
            ),
            "full_mirror_raw_record_count": len(all_recs),
            "full_mirror_unique_submission_count": full_summary["total_submissions"],
            "excluded_from_primary_scope_count": len(all_recs) - summary["raw_record_count"],
            "mirror_cohort_breakdown": {
                "by_track_and_status": breakdown_rows,
                "ratings_above_or_outside_main_scale_in_excluded_tracks": {
                    "rating_count": sum(out_of_main_scale_by_track.values()),
                    "paper_count": len(out_of_main_scale_papers),
                    "by_track": dict(sorted(out_of_main_scale_by_track.items())),
                },
            },
            "raw_record_count": summary["raw_record_count"],
            "duplicate_records_skipped": summary["duplicate_records_skipped"],
            "paper_count": summary["total_submissions"],
            "scored_paper_count": summary["scored_submissions"],
            "multi_reviewer_paper_count": summary["review_forensics"]["multi_review_submissions"],
            "total_reviews": summary["total_reviews"],
            "mean_reviews_per_scored_paper": mean_revs,
            "modal_multi_review_count": modal_multi_m,
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
            "iid_marginal_unanimity_baseline": iid_baseline,
        })

    out_doc = {
        "schema": "ark-peer-review-forensics-receipt/2.1",
        "kernel_version": __version__,
        "snapshot_date_utc": FROZEN_SNAPSHOT_DATE_UTC,
        "upstream_source": {
            "repository": "https://github.com/papercopilot/paperlists",
            "frozen_commit": PAPERCOPILOT_COMMIT,
            "reproduction_script": "python tools/benchmarks/run_peer_review_and_incidence_benchmarks.py --mirror-dir <dir>",
        },
        "methodological_notes": [
            "All counts, histograms, quantiles, and word-count medians are deterministically computed over the SHA-256-verified frozen snapshots from papercopilot/paperlists@181a85021c63ab26745c42ed70a9d9ea7b57ad7e across four AI conference series (five yearly snapshots).",
            "Each snapshot declares an explicit track, decision-status cohort, and valid rating scale (declared_valid_ratings). In nips/nips2025.json (6,212 raw public records), the primary main-track accepted cohort covers 5,275 Oral/Spotlight/Poster papers (21,301 reviews on 1-6), while Datasets & Benchmarks (591 records), Position (95 records, containing all 125 ratings > 6 across 74 papers under Position's distinct scale), and opted-in public Reject records (400 across tracks, including 251 in main) are preserved transparently in mirror_cohort_breakdown.",
            "Non-positive rating tokens (such as the 1,319 rating=0 entries across 1,096 ICLR 2026 submissions) are preserved in non_positive_rating_anomalies and excluded from positive review-score means and unanimous-score denominators.",
            "Unanimous identical-score rates and word-count distributions are descriptive snapshot statistics, not standalone AI-authorship or collusion detectors: rating-scale cardinality, review-stage visibility, public acceptance filtering, and per-paper reviewer counts (e.g., ICLR mean reviews per scored paper shifting from 3.83 in 2026 to 3.10 in 2027, raising the empirical-marginal i.i.d. unanimity baseline from 5.07% to 19.80%) mechanically shift unanimity base rates.",
            "PaperCopilot JSON mirrors leave wc_reply_reviewers/wc_reply_authors at zero and aggregate decision/meta-review notes into replies_avg differently across venues; cross-venue zero-discussion rates are therefore omitted from headline comparisons.",
        ],
        "totals": {
            "conference_series_count": 4,
            "venue_count": len(venues_out),
            "full_mirror_raw_records": sum(v["full_mirror_raw_record_count"] for v in venues_out),
            "full_mirror_unique_submissions": full_mirror_unique_total,
            "total_raw_records": sum(v["raw_record_count"] for v in venues_out),
            "total_unique_submissions": sum(v["paper_count"] for v in venues_out),
            "total_scored_papers": sum(v["scored_paper_count"] for v in venues_out),
            "total_positive_reviews": sum(v["total_reviews"] for v in venues_out),
        },
        "venues": venues_out,
    }
    out_doc["receipt_sha256"] = _canonical_body_sha256(out_doc)
    return out_doc


def _map_iclr2026_status(st: str) -> str:
    if "Oral" in st:
        return "Oral"
    if "Poster" in st:
        return "Poster"
    if st == "Reject":
        return "Rejected"
    if st == "Withdraw":
        return "Withdrawn"
    if st == "Desk Reject":
        return "Desk Reject"
    raise ValueError(f"Unexpected ICLR 2026 status: {st!r}")


def _agg_incidence_rows(rows: list[tuple[str, str, str, int, int, float, float, set[str]]]) -> dict:
    pn = len(rows)
    require(pn > 0, "Cannot aggregate empty incidence subset")
    rn = sum(r[4] for r in rows)
    mr = round(sum(r[5] for r in rows) / pn, 3)
    ms = round(sum(r[6] for r in rows) / pn, 3)
    out: dict[str, object] = {
        "papers_n": pn,
        "reviews_n": rn,
        "mean_rating": mr,
        "mean_soundness": ms,
    }
    ha = sum(1 for r in rows if r[7])
    out["hit_any"] = {"k": ha, "pct": round(100.0 * ha / pn, 1)}
    for hk in INCIDENCE_CAT_KEYS:
        k = sum(1 for r in rows if hk in r[7])
        out[hk] = {"k": k, "pct": round(100.0 * k / pn, 1)}
    return out


def _build_tier_group(rows: list[tuple[str, str, str, int, int, float, float, set[str]]]) -> dict[str, dict]:
    tiers: dict[str, dict] = {}
    for t in ("Oral", "Poster", "Rejected", "Withdrawn"):
        tiers[t] = _agg_incidence_rows([r for r in rows if r[1] == t])
    tiers["STANDARD_DECISION_TIERS"] = _agg_incidence_rows([r for r in rows if r[1] in ("Oral", "Poster", "Rejected", "Withdrawn")])
    tiers["Desk Reject"] = _agg_incidence_rows([r for r in rows if r[1] == "Desk Reject"])
    tiers["ALL_SCORED"] = _agg_incidence_rows(rows)
    for sb in ("SOUND_HIGH(>=3.25)", "SOUND_MID(2.0_to_3.25)", "SOUND_LOW(<=2.0)"):
        tiers[sb] = _agg_incidence_rows([r for r in rows if r[2] == sb])
    return tiers


def build_iclr2026_incidence_receipt(mirror_dir: Path) -> dict:
    meta_p = mirror_dir / "iclr2026.json"
    if not meta_p.exists() and (mirror_dir / "iclr/iclr2026.json").exists():
        meta_p = mirror_dir / "iclr/iclr2026.json"
    jsonl_p = mirror_dir / "iclr2026_stats.jsonl"
    exp_meta_sha = FIVE_VENUES[0][8]
    exp_meta_sz = FIVE_VENUES[0][9]
    require(meta_p.is_file() and meta_p.stat().st_size == exp_meta_sz and _sha256_file(meta_p) == exp_meta_sha, "iclr2026.json SHA-256/size mismatch")
    require(jsonl_p.is_file() and jsonl_p.stat().st_size == HF_STATS_BYTES and _sha256_file(jsonl_p) == HF_STATS_SHA256, "iclr2026_stats.jsonl SHA-256/size mismatch")

    meta_list = json.loads(meta_p.read_text(encoding="utf-8"))
    meta_by_id: dict[str, dict] = {}
    for rec in meta_list:
        if isinstance(rec, dict):
            fid = str(rec.get("id") or rec.get("openreview_forum") or "")
            if fid and fid not in meta_by_id:
                meta_by_id[fid] = rec

    compiled_rx = {k: re.compile(v, re.I) for k, v in INCIDENCE_REGEX_PATTERNS.items()}
    rows: list[tuple[str, str, str, int, int, float, float, set[str]]] = []
    total_jsonl_rows = 0
    seen_ids: set[str] = set()
    with jsonl_p.open("r", encoding="utf-8") as fh:
        for line in fh:
            total_jsonl_rows += 1
            obj = json.loads(line)
            fid = str(obj.get("id") or "")
            if not fid or fid in seen_ids:
                continue
            seen_ids.add(fid)
            mrec = meta_by_id.get(fid)
            revs = [rv for rv in (obj.get("reviews") or []) if isinstance(rv, dict) and rv.get("rating") is not None]
            if not mrec or not revs:
                continue
            st = _map_iclr2026_status(str(mrec["status"]))
            r_vals = [float(rv["rating"]) for rv in revs]
            s_vals = [float(rv["soundness"]) for rv in revs if rv.get("soundness") is not None]
            mean_r = sum(r_vals) / len(r_vals)
            mean_s = sum(s_vals) / len(s_vals) if s_vals else 0.0
            blob = "\n".join(f"{rv.get('weaknesses') or ''}\n{rv.get('questions') or ''}" for rv in revs)
            hits = {INCIDENCE_REGEX_TO_HIT[k] for k, pat in compiled_rx.items() if pat.search(blob)}
            split_idx = int(hashlib.sha256(fid.encode("utf-8")).hexdigest(), 16) % 2
            if mean_s >= 3.25:
                sbin = "SOUND_HIGH(>=3.25)"
            elif mean_s <= 2.0:
                sbin = "SOUND_LOW(<=2.0)"
            else:
                sbin = "SOUND_MID(2.0_to_3.25)"
            rows.append((fid, st, sbin, split_idx, len(revs), mean_r, mean_s, hits))

    tiers = _build_tier_group(rows)
    split_half = {
        "split_0": _build_tier_group([r for r in rows if r[3] == 0]),
        "split_1": _build_tier_group([r for r in rows if r[3] == 1]),
    }

    doc = {
        "schema_version": "1.2.0",
        "study_id": "iclr2026-openreview-5family-incidence-v1",
        "measurement_scope": "lexical_keyword_screening_mention_rate",
        "description": "De-identified paper-level lexical keyword-screening mention rates across 5 topic families in official ICLR 2026 peer-review Weaknesses and Questions fields. Because regex matching is polarity-blind (e.g. 'confidence intervals are correctly reported' or 'reproducibility is excellent' also match), these rates measure topic-term mention/screening prevalence inside Weaknesses/Questions rather than manually adjudicated defect ground truth.",
        "reproduction_command": "python tools/benchmarks/run_peer_review_and_incidence_benchmarks.py --mirror-dir <dir> --verify-iclr2026-incidence",
        "known_limitations": [
            "Lexical regexes match topic phrases without sentiment/negation parsing; positive or neutral mentions inside Weaknesses/Questions (such as praising reproducibility or comprehensive limitations) are counted alongside critiques.",
            "Join denominator (19,473 scored manuscripts, 75,769 reviews) requires both a non-empty review list in iclr2026_stats.jsonl and a matching forum ID in iclr2026.json (with ConditionalOral -> Oral, ConditionalPoster -> Poster, Reject -> Rejected, Withdraw -> Withdrawn).",
        ],
        "methodology": {
            "unit_of_analysis": "scored_manuscript",
            "status_normalization": "ConditionalOral -> Oral; ConditionalPoster -> Poster; Reject -> Rejected; Withdraw -> Withdrawn",
            "text_fields_concatenated": ["reviews[*].weaknesses", "reviews[*].questions"],
            "aggregation_rule": "k / N manuscripts where at least one official review matches the category regex (case-insensitive)",
            "split_half_rule": "int(hashlib.sha256(forum_id.encode('utf-8')).hexdigest(), 16) % 2",
            "zero_fitted_parameters": True,
            "regex_patterns": dict(INCIDENCE_REGEX_PATTERNS),
        },
        "upstream_sources": {
            "metadata_snapshot": {
                "source": "papercopilot/paperlists (iclr/iclr2026.json)",
                "repository": "https://github.com/papercopilot/paperlists",
                "commit": PAPERCOPILOT_COMMIT,
                "frozen_url": f"https://github.com/papercopilot/paperlists/blob/{PAPERCOPILOT_COMMIT}/iclr/iclr2026.json",
                "total_records": len(meta_list),
                "unique_records": len(meta_by_id),
                "sha256": exp_meta_sha,
                "size_bytes": exp_meta_sz,
            },
            "review_text_corpus": {
                "source": "HuggingFace datasets/insomnia7/iclr2026_stats (iclr2026_stats.jsonl)",
                "repository": "https://huggingface.co/datasets/insomnia7/iclr2026_stats",
                "commit": HF_STATS_COMMIT,
                "frozen_url": f"https://huggingface.co/datasets/insomnia7/iclr2026_stats/blob/{HF_STATS_COMMIT}/iclr2026_stats.jsonl",
                "total_rows": total_jsonl_rows,
                "scored_joined_manuscripts": tiers["ALL_SCORED"]["papers_n"],
                "official_reviews": tiers["ALL_SCORED"]["reviews_n"],
                "sha256": HF_STATS_SHA256,
                "size_bytes": HF_STATS_BYTES,
            },
        },
        "partition_conservation": {
            "total_scored_manuscripts": tiers["ALL_SCORED"]["papers_n"],
            "total_official_reviews": tiers["ALL_SCORED"]["reviews_n"],
            "standard_decision_tiers_sum": tiers["STANDARD_DECISION_TIERS"]["papers_n"],
            "desk_reject_with_reviews": tiers["Desk Reject"]["papers_n"],
            "decision_partition_identities": {
                "224 + 5134 + 8453 + 4980": tiers["STANDARD_DECISION_TIERS"]["papers_n"],
                "18791 + 682": tiers["ALL_SCORED"]["papers_n"],
                "any_hit_k_sum_108_2772_5057_3117_434": tiers["ALL_SCORED"]["hit_any"]["k"],
            },
            "soundness_partition_identities": {
                "1077 + 15535 + 2861": tiers["ALL_SCORED"]["papers_n"],
                "any_hit_k_sum_529_9031_1928": tiers["ALL_SCORED"]["hit_any"]["k"],
            },
            "split_half_partition_identities": {
                "9765 + 9708": tiers["ALL_SCORED"]["papers_n"],
                "any_hit_k_sum_5824_5664": tiers["ALL_SCORED"]["hit_any"]["k"],
            },
        },
        "tiers": tiers,
        "split_half": split_half,
    }
    doc["receipt_sha256"] = _canonical_body_sha256(doc)
    return doc


def _req_strict_int(v: object, ctx: str) -> int:
    require(isinstance(v, int) and not isinstance(v, bool), f"{ctx} must be an exact integer, got {v!r}")
    return v


def _verify_tier_block(tiers: dict, *, label: str) -> None:
    expected_tier_names = {
        "Oral",
        "Poster",
        "Rejected",
        "Withdrawn",
        "STANDARD_DECISION_TIERS",
        "Desk Reject",
        "ALL_SCORED",
        "SOUND_HIGH(>=3.25)",
        "SOUND_MID(2.0_to_3.25)",
        "SOUND_LOW(<=2.0)",
    }
    require(isinstance(tiers, dict) and set(tiers.keys()) == expected_tier_names, f"{label} tier key set mismatch")
    for t_name, t_obj in tiers.items():
        require(isinstance(t_obj, dict), f"{label}.{t_name} must be a JSON object")
        pn = _req_strict_int(t_obj.get("papers_n"), f"{label}.{t_name}.papers_n")
        rn = _req_strict_int(t_obj.get("reviews_n"), f"{label}.{t_name}.reviews_n")
        require(pn > 0 and rn >= pn, f"{label}.{t_name} invalid papers_n/reviews_n")
        mr = t_obj.get("mean_rating")
        require(
            isinstance(mr, (int, float)) and not isinstance(mr, bool) and math.isfinite(float(mr)) and 1.0 <= float(mr) <= 10.0,
            f"{label}.{t_name}.mean_rating={mr!r} out of valid [1.0, 10.0] finite range",
        )
        ms = t_obj.get("mean_soundness")
        require(
            isinstance(ms, (int, float)) and not isinstance(ms, bool) and math.isfinite(float(ms)) and 0.0 <= float(ms) <= 10.0,
            f"{label}.{t_name}.mean_soundness={ms!r} out of valid [0.0, 10.0] finite range",
        )
        for ck in ("hit_any", *INCIDENCE_CAT_KEYS):
            require(ck in t_obj and isinstance(t_obj[ck], dict), f"{label}.{t_name} missing or non-object category {ck}")
            k_val = _req_strict_int(t_obj[ck].get("k"), f"{label}.{t_name}.{ck}.k")
            pct_raw = t_obj[ck].get("pct")
            require(isinstance(pct_raw, (int, float)) and not isinstance(pct_raw, bool), f"{label}.{t_name}.{ck}.pct not numeric")
            pct_val = float(pct_raw)
            require(0 <= k_val <= pn, f"{label}.{t_name}.{ck}.k={k_val} out of bounds [0, {pn}]")
            require(round(100.0 * k_val / pn, 1) == pct_val, f"{label}.{t_name}.{ck} pct mismatch")
        max_cat_k = max(_req_strict_int(t_obj[ck]["k"], ck) for ck in INCIDENCE_CAT_KEYS)
        sum_cat_k = sum(_req_strict_int(t_obj[ck]["k"], ck) for ck in INCIDENCE_CAT_KEYS)
        any_k = _req_strict_int(t_obj["hit_any"]["k"], "hit_any")
        require(max_cat_k <= any_k <= sum_cat_k, f"{label}.{t_name} hit_any={any_k} violates union bounds [{max_cat_k}, {sum_cat_k}]")

    std_names = ("Oral", "Poster", "Rejected", "Withdrawn")
    snd_names = ("SOUND_HIGH(>=3.25)", "SOUND_MID(2.0_to_3.25)", "SOUND_LOW(<=2.0)")
    # Weighted mean_rating partition checks (within 0.02 rounding tolerance of 2-decimal rounded means)
    std_w_sum = sum(float(tiers[t]["mean_rating"]) * int(tiers[t]["papers_n"]) for t in std_names)
    std_w_mean = std_w_sum / int(tiers["STANDARD_DECISION_TIERS"]["papers_n"])
    require(
        abs(std_w_mean - float(tiers["STANDARD_DECISION_TIERS"]["mean_rating"])) <= 0.02,
        f"{label} STANDARD_DECISION_TIERS mean_rating inconsistent with weighted tier means",
    )
    all_w_sum = std_w_sum + float(tiers["Desk Reject"]["mean_rating"]) * int(tiers["Desk Reject"]["papers_n"])
    all_w_mean = all_w_sum / int(tiers["ALL_SCORED"]["papers_n"])
    require(
        abs(all_w_mean - float(tiers["ALL_SCORED"]["mean_rating"])) <= 0.02,
        f"{label} ALL_SCORED mean_rating inconsistent with weighted tier means",
    )
    snd_w_mean = sum(float(tiers[t]["mean_rating"]) * int(tiers[t]["papers_n"]) for t in snd_names) / int(tiers["ALL_SCORED"]["papers_n"])
    require(
        abs(snd_w_mean - float(tiers["ALL_SCORED"]["mean_rating"])) <= 0.02,
        f"{label} soundness partition mean_rating inconsistent with ALL_SCORED",
    )
    std_s_sum = sum(float(tiers[t]["mean_soundness"]) * int(tiers[t]["papers_n"]) for t in std_names)
    std_s_mean = std_s_sum / int(tiers["STANDARD_DECISION_TIERS"]["papers_n"])
    require(
        abs(std_s_mean - float(tiers["STANDARD_DECISION_TIERS"]["mean_soundness"])) <= 0.02,
        f"{label} STANDARD_DECISION_TIERS mean_soundness inconsistent with weighted tier means",
    )
    all_s_sum = std_s_sum + float(tiers["Desk Reject"]["mean_soundness"]) * int(tiers["Desk Reject"]["papers_n"])
    all_s_mean = all_s_sum / int(tiers["ALL_SCORED"]["papers_n"])
    require(
        abs(all_s_mean - float(tiers["ALL_SCORED"]["mean_soundness"])) <= 0.02,
        f"{label} ALL_SCORED mean_soundness inconsistent with weighted tier means",
    )
    snd_s_mean = sum(float(tiers[t]["mean_soundness"]) * int(tiers[t]["papers_n"]) for t in snd_names) / int(tiers["ALL_SCORED"]["papers_n"])
    require(
        abs(snd_s_mean - float(tiers["ALL_SCORED"]["mean_soundness"])) <= 0.02,
        f"{label} soundness partition mean_soundness inconsistent with ALL_SCORED",
    )
    for count_key in ("papers_n", "reviews_n"):
        require(
            sum(int(tiers[t][count_key]) for t in std_names) == int(tiers["STANDARD_DECISION_TIERS"][count_key]),
            f"{label} standard decision {count_key} sum mismatch",
        )
        require(
            int(tiers["STANDARD_DECISION_TIERS"][count_key]) + int(tiers["Desk Reject"][count_key]) == int(tiers["ALL_SCORED"][count_key]),
            f"{label} ALL_SCORED {count_key} sum mismatch",
        )
        require(
            sum(int(tiers[t][count_key]) for t in snd_names) == int(tiers["ALL_SCORED"][count_key]),
            f"{label} soundness {count_key} sum mismatch",
        )
    for ck in ("hit_any", *INCIDENCE_CAT_KEYS):
        require(
            sum(int(tiers[t][ck]["k"]) for t in std_names) == int(tiers["STANDARD_DECISION_TIERS"][ck]["k"]),
            f"{label} standard decision {ck}.k sum mismatch",
        )
        require(
            int(tiers["STANDARD_DECISION_TIERS"][ck]["k"]) + int(tiers["Desk Reject"][ck]["k"]) == int(tiers["ALL_SCORED"][ck]["k"]),
            f"{label} ALL_SCORED {ck}.k sum mismatch",
        )
        require(
            sum(int(tiers[t][ck]["k"]) for t in snd_names) == int(tiers["ALL_SCORED"][ck]["k"]),
            f"{label} soundness {ck}.k sum mismatch",
        )


def verify_receipts_offline(peer_path: Path = DEFAULT_PEER_RECEIPT, inc_path: Path = DEFAULT_INCIDENCE_RECEIPT) -> dict:
    peer = json.loads(peer_path.read_text(encoding="utf-8"))
    require("receipt_sha256" in peer and peer["receipt_sha256"] == _canonical_body_sha256(peer), "peer-review receipt_sha256 missing or tampered")
    require(peer.get("snapshot_date_utc") == FROZEN_SNAPSHOT_DATE_UTC, f"peer-review snapshot_date_utc {peer.get('snapshot_date_utc')!r} != {FROZEN_SNAPSHOT_DATE_UTC!r}")
    venues = peer["venues"]
    require(peer["totals"]["venue_count"] == len(venues) == 5, "venue_count mismatch")
    require(peer["totals"].get("conference_series_count") == 4, "conference_series_count mismatch")
    require(peer["totals"]["full_mirror_raw_records"] == sum(v["full_mirror_raw_record_count"] for v in venues), "full_mirror_raw_records mismatch")
    require(peer["totals"]["full_mirror_unique_submissions"] == sum(v["full_mirror_unique_submission_count"] for v in venues), "full_mirror_unique_submissions mismatch")
    require(peer["totals"]["total_raw_records"] == sum(v["raw_record_count"] for v in venues), "total_raw_records mismatch")
    require(peer["totals"]["total_unique_submissions"] == sum(v["paper_count"] for v in venues), "total_unique_submissions mismatch")
    require(peer["totals"]["total_scored_papers"] == sum(v["scored_paper_count"] for v in venues), "total_scored_papers mismatch")
    require(peer["totals"]["total_positive_reviews"] == sum(v["total_reviews"] for v in venues), "total_positive_reviews mismatch")
    exp_sha_by_vid = {vid: exp_sha for vid, _, _, _, _, _, _, _, exp_sha, _ in FIVE_VENUES}
    exp_size_by_vid = {vid: exp_sz for vid, _, _, _, _, _, _, _, _, exp_sz in FIVE_VENUES}
    exp_valid_by_vid = {vid: set(valid_s) for vid, _, _, valid_s, _, _, _, _, _, _ in FIVE_VENUES}
    for v in venues:
        require(v["upstream_commit"] == PAPERCOPILOT_COMMIT, "upstream_commit mismatch")
        require(v["mirror_sha256"] == exp_sha_by_vid[v["venue_id"]], "mirror_sha256 mismatch")
        require(v["mirror_bytes"] == exp_size_by_vid[v["venue_id"]], "mirror_bytes mismatch")
        require(
            _req_strict_int(v.get("raw_record_count"), f"{v['venue_id']}.raw_record_count")
            + _req_strict_int(v.get("excluded_from_primary_scope_count"), f"{v['venue_id']}.excluded_from_primary_scope_count")
            == _req_strict_int(v.get("full_mirror_raw_record_count"), f"{v['venue_id']}.full_mirror_raw_record_count"),
            f"{v['venue_id']} cohort record partition mismatch",
        )
        decl_valid = v.get("declared_valid_ratings")
        require(
            isinstance(decl_valid, list) and set(decl_valid) == exp_valid_by_vid[v["venue_id"]],
            f"{v['venue_id']}.declared_valid_ratings {decl_valid!r} mismatch",
        )
        tot_rev = _req_strict_int(v.get("total_reviews"), f"{v['venue_id']}.total_reviews")
        hist = v.get("raw_rating_histogram")
        require(isinstance(hist, dict) and len(hist) > 0, f"{v['venue_id']}.raw_rating_histogram must be a non-empty dict")
        hist_sum = 0
        for hk, hv in hist.items():
            require(isinstance(hk, str) and hk.strip(), f"{v['venue_id']}.raw_rating_histogram key must be non-empty string")
            try:
                hk_int = int(hk)
            except ValueError as exc:
                raise ValueError(f"{v['venue_id']}.raw_rating_histogram key {hk!r} is not an integer") from exc
            require(
                hk_int in exp_valid_by_vid[v["venue_id"]],
                f"{v['venue_id']}.raw_rating_histogram key {hk_int} outside declared_valid_ratings {sorted(exp_valid_by_vid[v['venue_id']])}",
            )
            hc = _req_strict_int(hv, f"{v['venue_id']}.raw_rating_histogram[{hk!r}]")
            require(hc >= 0, f"{v['venue_id']}.raw_rating_histogram[{hk!r}]={hc} must be non-negative")
            hist_sum += hc
        require(hist_sum == tot_rev, f"{v['venue_id']}.raw_rating_histogram sum {hist_sum} != total_reviews {tot_rev}")
        calc_share = round(v["unanimous_identical_rating_count"] / v["multi_reviewer_paper_count"], 4)
        require(calc_share == v["unanimous_identical_rating_share"], "unanimous_identical_rating_share mismatch")

    inc = json.loads(inc_path.read_text(encoding="utf-8"))
    require("receipt_sha256" in inc and inc["receipt_sha256"] == _canonical_body_sha256(inc), "incidence receipt_sha256 missing or tampered")
    require(inc["measurement_scope"] == "lexical_keyword_screening_mention_rate", "measurement_scope mismatch")
    require(inc["upstream_sources"]["metadata_snapshot"]["commit"] == PAPERCOPILOT_COMMIT, "metadata commit mismatch")
    require(inc["upstream_sources"]["metadata_snapshot"]["sha256"] == exp_sha_by_vid["ICLR.cc/2026/Conference"], "iclr2026 sha mismatch")
    require(inc["upstream_sources"]["review_text_corpus"]["commit"] == HF_STATS_COMMIT, "HF commit mismatch")
    require(inc["upstream_sources"]["review_text_corpus"]["sha256"] == HF_STATS_SHA256, "HF sha mismatch")
    pc = inc["partition_conservation"]
    tiers = inc["tiers"]
    splits = inc["split_half"]
    _verify_tier_block(tiers, label="tiers")
    _verify_tier_block(splits["split_0"], label="split_half.split_0")
    _verify_tier_block(splits["split_1"], label="split_half.split_1")

    for t_name in tiers:
        for count_key in ("papers_n", "reviews_n"):
            require(
                int(splits["split_0"][t_name][count_key]) + int(splits["split_1"][t_name][count_key]) == int(tiers[t_name][count_key]),
                f"split_0 + split_1 != tiers on {t_name}.{count_key}",
            )
        sp_w_mean = (
            float(splits["split_0"][t_name]["mean_rating"]) * int(splits["split_0"][t_name]["papers_n"])
            + float(splits["split_1"][t_name]["mean_rating"]) * int(splits["split_1"][t_name]["papers_n"])
        ) / int(tiers[t_name]["papers_n"])
        require(
            abs(sp_w_mean - float(tiers[t_name]["mean_rating"])) <= 0.02,
            f"split_0 + split_1 weighted mean_rating != tiers on {t_name}",
        )
        sp_s_mean = (
            float(splits["split_0"][t_name]["mean_soundness"]) * int(splits["split_0"][t_name]["papers_n"])
            + float(splits["split_1"][t_name]["mean_soundness"]) * int(splits["split_1"][t_name]["papers_n"])
        ) / int(tiers[t_name]["papers_n"])
        require(
            abs(sp_s_mean - float(tiers[t_name]["mean_soundness"])) <= 0.02,
            f"split_0 + split_1 weighted mean_soundness != tiers on {t_name}",
        )
        for ck in ("hit_any", *INCIDENCE_CAT_KEYS):
            require(
                int(splits["split_0"][t_name][ck]["k"]) + int(splits["split_1"][t_name][ck]["k"]) == int(tiers[t_name][ck]["k"]),
                f"split_0 + split_1 != tiers on {t_name}.{ck}.k",
            )

    pc_std = _req_strict_int(pc.get("standard_decision_tiers_sum"), "partition_conservation.standard_decision_tiers_sum")
    pc_desk = _req_strict_int(pc.get("desk_reject_with_reviews"), "partition_conservation.desk_reject_with_reviews")
    pc_tot_m = _req_strict_int(pc.get("total_scored_manuscripts"), "partition_conservation.total_scored_manuscripts")
    pc_tot_r = _req_strict_int(pc.get("total_official_reviews"), "partition_conservation.total_official_reviews")
    require(_req_strict_int(tiers["STANDARD_DECISION_TIERS"]["papers_n"], "std.papers_n") == pc_std, "standard_decision_tiers_sum mismatch")
    require(_req_strict_int(tiers["Desk Reject"]["papers_n"], "desk.papers_n") == pc_desk, "desk_reject_with_reviews mismatch")
    require(_req_strict_int(tiers["ALL_SCORED"]["papers_n"], "all.papers_n") == pc_tot_m, "total_scored_manuscripts mismatch")
    require(_req_strict_int(tiers["ALL_SCORED"]["reviews_n"], "all.reviews_n") == pc_tot_r, "total_official_reviews mismatch")

    dec_key_1 = " + ".join(str(tiers[t]["papers_n"]) for t in ("Oral", "Poster", "Rejected", "Withdrawn"))
    dec_key_2 = f"{pc_std} + {pc_desk}"
    dec_key_3 = "any_hit_k_sum_" + "_".join(str(tiers[t]["hit_any"]["k"]) for t in ("Oral", "Poster", "Rejected", "Withdrawn", "Desk Reject"))
    exp_dec_ids = {dec_key_1: pc_std, dec_key_2: pc_tot_m, dec_key_3: tiers["ALL_SCORED"]["hit_any"]["k"]}

    snd_tiers = ("SOUND_HIGH(>=3.25)", "SOUND_MID(2.0_to_3.25)", "SOUND_LOW(<=2.0)")
    snd_key_1 = " + ".join(str(tiers[t]["papers_n"]) for t in snd_tiers)
    snd_key_2 = "any_hit_k_sum_" + "_".join(str(tiers[t]["hit_any"]["k"]) for t in snd_tiers)
    exp_snd_ids = {snd_key_1: pc_tot_m, snd_key_2: tiers["ALL_SCORED"]["hit_any"]["k"]}

    sp_key_1 = f"{splits['split_0']['ALL_SCORED']['papers_n']} + {splits['split_1']['ALL_SCORED']['papers_n']}"
    sp_key_2 = f"any_hit_k_sum_{splits['split_0']['ALL_SCORED']['hit_any']['k']}_{splits['split_1']['ALL_SCORED']['hit_any']['k']}"
    exp_sp_ids = {sp_key_1: pc_tot_m, sp_key_2: tiers["ALL_SCORED"]["hit_any"]["k"]}

    for id_map_key, exp_id_map in (
        ("decision_partition_identities", exp_dec_ids),
        ("soundness_partition_identities", exp_snd_ids),
        ("split_half_partition_identities", exp_sp_ids),
    ):
        id_map = pc.get(id_map_key)
        require(isinstance(id_map, dict) and set(id_map.keys()) == set(exp_id_map.keys()), f"partition_conservation.{id_map_key} key set mismatch")
        for ik, exp_iv in exp_id_map.items():
            got_iv = _req_strict_int(id_map[ik], f"partition_conservation.{id_map_key}.{ik}")
            require(got_iv == exp_iv, f"partition_conservation.{id_map_key}[{ik!r}]={got_iv} != expected {exp_iv}")
    return {"peer_totals": peer["totals"], "incidence_scored_manuscripts": pc_tot_m}


def verify_iclr2026_incidence_raw(mirror_dir: Path, inc_path: Path = DEFAULT_INCIDENCE_RECEIPT) -> dict:
    verify_receipts_offline(inc_path=inc_path)
    inc = json.loads(inc_path.read_text(encoding="utf-8"))
    rebuilt = build_iclr2026_incidence_receipt(mirror_dir)
    for section in ("methodology", "upstream_sources", "partition_conservation", "tiers", "split_half", "receipt_sha256"):
        require(
            inc.get(section) == rebuilt.get(section),
            f"Raw corpus replay mismatch in section {section!r} against {inc_path}",
        )
    return {
        "rows": rebuilt["upstream_sources"]["review_text_corpus"]["total_rows"],
        "joined_scored": rebuilt["partition_conservation"]["total_scored_manuscripts"],
        "official_reviews": rebuilt["partition_conservation"]["total_official_reviews"],
        "any_keyword_hits": rebuilt["tiers"]["ALL_SCORED"]["hit_any"]["k"],
        "format_hits": rebuilt["tiers"]["ALL_SCORED"]["hit_format"]["k"],
        "receipt_sha256": rebuilt["receipt_sha256"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mirror-dir", type=Path, help="Directory holding frozen PaperCopilot JSON mirrors to rebuild receipts")
    ap.add_argument("--rebuild-iclr2026-incidence", action="store_true", help="Rebuild iclr2026-openreview-incidence-receipt.json from 316MB JSONL")
    ap.add_argument("--verify-iclr2026-incidence", action="store_true", help="Replay and verify every tier/category/split against 316MB JSONL")
    ap.add_argument("--verify-receipts", action="store_true", help="Verify stored JSON receipts offline")
    args = ap.parse_args(argv)

    if args.mirror_dir:
        peer_doc = build_five_venue_receipt(args.mirror_dir)
        DEFAULT_PEER_RECEIPT.write_text(json.dumps(peer_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        out: dict[str, object] = {"rebuilt_five_venues": peer_doc["totals"], "peer_receipt_sha256": peer_doc["receipt_sha256"]}
        if args.rebuild_iclr2026_incidence:
            inc_doc = build_iclr2026_incidence_receipt(args.mirror_dir)
            DEFAULT_INCIDENCE_RECEIPT.write_text(json.dumps(inc_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            out["rebuilt_iclr2026_incidence_sha256"] = inc_doc["receipt_sha256"]
        if args.verify_iclr2026_incidence:
            out["verified_iclr2026_incidence"] = verify_iclr2026_incidence_raw(args.mirror_dir)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0

    res = verify_receipts_offline()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

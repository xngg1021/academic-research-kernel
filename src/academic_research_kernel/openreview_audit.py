"""OpenReview API v2 稿件状态、审稿分分布与顶会全量放榜统计确定性核验工具。

支持三种工作模式：
1. 单篇稿件核验：传入 --forum-id（若传入 --mirror-json 则优先或回退检索镜像库）或 --input-json。
2. 镜像单篇核验：传入 --forum-id 与 --mirror-json（支持 PaperCopilot OpenReview 全量镜像格式，提取 rating/confidence/soundness/contribution/presentation 与 rebuttal 字数）。
3. 顶会全量放榜统计：传入 --venue-stats <mirror_json>（可选 --topic-regex），确定性核算总投稿量、各档录用/拒稿/撤稿/Desk Reject 占比、评分直方图与分位数。
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request

from ._stdlib import safe_path
from .research.sources import controlled_urlopen

USER_AGENT = "Mozilla/5.0 (compatible; academic-research-kernel/3.0)"
ACCEPT_VENUE_RE = re.compile(r"\b(?:poster|spotlight|oral|notable)\b", re.I)
ACCEPT_DECISION_RE = re.compile(r"(?<!not\s)(?<!un)(?<!cannot\s)(?<!never\s)\baccept(?:ed)?\b(?!\s+threshold)", re.I)
REJECT_DECISION_RE = re.compile(r"\breject(?:ed)?\b|\bdesk[\s_-]*reject", re.I)
WITHDRAWN_RE = re.compile(r"\bwithdraw(?:n|al)?\b", re.I)
NUMERIC_PREFIX_RE = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*(?::|$|\s+-)")


def _unwrap(val):
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val


def _parse_semi_numbers(val) -> list[float]:
    if isinstance(val, list):
        out = []
        for x in val:
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                f = float(x)
                if math.isfinite(f):
                    out.append(f)
        return out
    if not isinstance(val, str) or not val.strip():
        return []
    out = []
    for part in val.split(";"):
        part = part.strip()
        if part:
            try:
                f = float(part)
                if math.isfinite(f):
                    out.append(f)
            except ValueError:
                pass
    return out


def _parse_semi_slots(val: Any) -> list[Optional[float]]:
    if isinstance(val, list):
        out: list[Optional[float]] = []
        for x in val:
            if isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x)):
                out.append(float(x))
            else:
                out.append(None)
        return out
    if not isinstance(val, str) or not val.strip():
        return []
    out = []
    for part in val.split(";"):
        part = part.strip()
        if not part:
            out.append(None)
            continue
        try:
            f = float(part)
            out.append(f if math.isfinite(f) else None)
        except ValueError:
            out.append(None)
    return out


def _is_decision_note(note: dict) -> bool:
    invs = note.get("invitations")
    if isinstance(invs, list):
        inv_text = " ".join(str(x) for x in invs).lower()
    else:
        inv_text = str(note.get("invitation") or "").lower()
    if "meta_review" in inv_text or "metareview" in inv_text:
        return False
    return "decision" in inv_text or "acceptance" in inv_text


def parse_mirror_record(rec: dict) -> dict:
    """解析 PaperCopilot OpenReview 镜像单条记录，还原完整评分、子维度与作者 Rebuttal 字数。"""
    if not isinstance(rec, dict):
        raise ValueError("Mirror record must be a JSON object")
    fid = rec.get("id") or rec.get("openreview_forum")
    title = rec.get("title")
    raw_authors = rec.get("author") or ""
    if isinstance(raw_authors, str):
        authors = [a.strip() for a in raw_authors.split(";") if a.strip()]
    elif isinstance(raw_authors, list):
        authors = [str(a).strip() for a in raw_authors if str(a).strip()]
    else:
        authors = []
    is_anonymous = not authors or any("anonymous" in a.lower() for a in authors)
    raw_status = str(rec.get("status") or "").strip()
    status_low = raw_status.lower()

    if WITHDRAWN_RE.search(status_low):
        status = "withdrawn"
    elif REJECT_DECISION_RE.search(status_low):
        status = "rejected_or_unaccepted"
    elif ACCEPT_VENUE_RE.search(status_low) or ACCEPT_DECISION_RE.search(status_low):
        status = "accepted"
    elif status_low in ("active", "under review", "submitted"):
        status = "under_review"
    else:
        status = "unknown"

    ratings = _parse_semi_numbers(rec.get("rating"))
    score_field = "rating"
    if not ratings and rec.get("recommendation") is not None:
        ratings = _parse_semi_numbers(rec.get("recommendation"))
        if ratings:
            score_field = "recommendation"
    confidences = _parse_semi_numbers(rec.get("confidence"))
    soundness = _parse_semi_numbers(rec.get("soundness"))
    contribution = _parse_semi_numbers(rec.get("contribution"))
    informativeness = _parse_semi_numbers(rec.get("informativeness"))
    presentation = _parse_semi_numbers(rec.get("presentation"))
    clarity = _parse_semi_numbers(rec.get("clarity"))
    quality = _parse_semi_numbers(rec.get("quality"))
    significance = _parse_semi_numbers(rec.get("significance"))
    originality = _parse_semi_numbers(rec.get("originality"))
    review_words = _parse_semi_numbers(rec.get("wc_review"))
    summary_words = _parse_semi_numbers(rec.get("wc_summary"))
    strengths_words = _parse_semi_numbers(rec.get("wc_strengths"))
    weaknesses_words = _parse_semi_numbers(rec.get("wc_weaknesses"))
    sw_combined_words = _parse_semi_numbers(rec.get("wc_strengths_and_weaknesses"))
    limitations_words = _parse_semi_numbers(rec.get("wc_limitations"))
    question_words = _parse_semi_numbers(rec.get("wc_questions"))

    has_rebuttal_field = ("wc_reply_authors" in rec and rec.get("wc_reply_authors") is not None) or (
        "reply_authors" in rec and rec.get("reply_authors") is not None
    )
    rebuttal_words = _parse_semi_numbers(rec.get("wc_reply_authors"))
    if has_rebuttal_field:
        did_rebut: bool | None = bool(sum(rebuttal_words) > 0) if rebuttal_words else bool(rec.get("reply_authors"))
        completeness = "complete"
    else:
        did_rebut = None
        completeness = "partial_mirror"

    has_rev_reply_field = ("wc_reply_reviewers" in rec and rec.get("wc_reply_reviewers") is not None) or (
        "reply_reviewers" in rec and rec.get("reply_reviewers") is not None
    )
    rev_reply_words = _parse_semi_numbers(rec.get("wc_reply_reviewers"))
    if has_rev_reply_field:
        did_rev_reply: bool | None = (
            bool(sum(rev_reply_words) > 0) if rev_reply_words else bool(rec.get("reply_reviewers"))
        )
    else:
        did_rev_reply = None

    return {
        "forum_id": fid,
        "title": title,
        "authors": authors,
        "is_anonymous": bool(is_anonymous),
        "venue": raw_status,
        "primary_area": rec.get("primary_area") or "",
        "decisions": [raw_status] if raw_status else [],
        "reviewer_recommendations": [],
        "status_classification": status,
        "completeness": completeness,
        "review_count": len(ratings),
        "score_field": score_field,
        "ratings": ratings,
        "mean_rating": float(sum(ratings) / len(ratings)) if ratings else None,
        "confidences": confidences,
        "soundness": soundness,
        "contribution": contribution,
        "informativeness": informativeness,
        "presentation": presentation,
        "clarity": clarity,
        "quality": quality,
        "significance": significance,
        "originality": originality,
        "review_word_counts": [int(x) for x in review_words],
        "summary_word_counts": [int(x) for x in summary_words],
        "strengths_word_counts": [int(x) for x in strengths_words],
        "weaknesses_word_counts": [int(x) for x in weaknesses_words],
        "strengths_and_weaknesses_word_counts": [int(x) for x in sw_combined_words],
        "limitations_word_counts": [int(x) for x in limitations_words],
        "question_word_counts": [int(x) for x in question_words],
        "author_rebuttal_word_counts": [int(x) for x in rebuttal_words],
        "reviewer_reply_word_counts": [int(x) for x in rev_reply_words],
        "did_authors_rebut": did_rebut,
        "did_reviewers_reply": did_rev_reply,
    }


def parse_openreview_notes(payload: dict | list, forum_id: str | None = None) -> dict:
    """从 OpenReview API v2 notes JSON 或镜像列表中提取投稿元数据、审稿评分与录用状态判定。"""
    if isinstance(payload, list):
        if not forum_id:
            if len(payload) == 1 and isinstance(payload[0], dict):
                return parse_mirror_record(payload[0])
            raise ValueError("When input is a mirror record list, --forum-id is required")
        for item in payload:
            if isinstance(item, dict) and (item.get("id") == forum_id or item.get("openreview_forum") == forum_id):
                return parse_mirror_record(item)
        raise ValueError(f"Forum ID {forum_id!r} not found in mirror list ({len(payload)} records)")

    if isinstance(payload, dict) and "notes" not in payload and (
        "id" in payload or "openreview_forum" in payload or "rating" in payload or "recommendation" in payload
    ):
        rec_fid = payload.get("id") or payload.get("openreview_forum")
        if forum_id and rec_fid and rec_fid != forum_id:
            raise ValueError(f"Record ID mismatch: requested {forum_id!r}, got {rec_fid!r}")
        return parse_mirror_record(payload)

    if not isinstance(payload, dict) or not isinstance(payload.get("notes"), list):
        raise ValueError("OpenReview payload must be a JSON object containing a 'notes' list")
    raw_notes = [n for n in payload["notes"] if isinstance(n, dict)]
    if not raw_notes:
        raise ValueError("OpenReview notes list is empty")

    submission = None
    if forum_id:
        for n in raw_notes:
            if n.get("id") == forum_id:
                submission = n
                break
        if submission is None:
            raise ValueError(f"Root submission note for forum_id={forum_id!r} not found")
    else:
        roots = [n for n in raw_notes if isinstance(n.get("id"), str) and n["id"] and n.get("id") == n.get("forum")]
        if len(roots) > 1:
            distinct_forums = {r["id"] for r in roots}
            if len(distinct_forums) > 1:
                raise ValueError("Multiple forums present in notes; specify --forum-id")
        if roots:
            submission = roots[0]
        elif len(raw_notes) == 1 and isinstance(raw_notes[0].get("id"), str) and raw_notes[0]["id"]:
            submission = raw_notes[0]
        else:
            raise ValueError("Could not unambiguously identify root submission note; specify --forum-id")

    fid = submission.get("id")
    content = submission.get("content") if isinstance(submission.get("content"), dict) else {}
    title = _unwrap(content.get("title"))
    authors = _unwrap(content.get("authors"))
    if not isinstance(authors, list):
        authors = []
    venue = str(_unwrap(content.get("venue")) or "")
    venueid = str(_unwrap(content.get("venueid")) or "")

    ratings = []
    confidences = []
    soundness = []
    contribution = []
    informativeness = []
    presentation = []
    decisions = []
    reviewer_recommendations = []

    root_dec = _unwrap(content.get("decision"))
    if isinstance(root_dec, str) and root_dec.strip():
        decisions.append(root_dec.strip())

    for n in raw_notes:
        if n.get("id") == fid:
            continue
        if fid and n.get("forum") != fid:
            continue
        c = n.get("content") if isinstance(n.get("content"), dict) else {}
        is_dec = _is_decision_note(n)

        dec = _unwrap(c.get("decision"))
        if isinstance(dec, str) and dec.strip():
            if is_dec:
                decisions.append(dec.strip())
            else:
                reviewer_recommendations.append(dec.strip())

        rat = _unwrap(c.get("rating"))
        if rat is None:
            rat = _unwrap(c.get("overall_assessment"))
        if rat is None and not is_dec:
            rat = _unwrap(c.get("overall_decision"))
        rec = _unwrap(c.get("recommendation"))
        if rat is None and rec is not None:
            if isinstance(rec, (int, float)) and not isinstance(rec, bool):
                rat = rec
            elif isinstance(rec, str) and NUMERIC_PREFIX_RE.match(rec):
                rat = rec
            elif isinstance(rec, str) and rec.strip():
                if is_dec and dec is None:
                    decisions.append(rec.strip())
                else:
                    reviewer_recommendations.append(rec.strip())

        if rat is not None and not isinstance(rat, bool):
            m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(rat))
            if m:
                f_val = float(m.group(1))
                if math.isfinite(f_val):
                    ratings.append(f_val)

        conf = _unwrap(c.get("confidence"))
        if conf is not None and not isinstance(conf, bool):
            m = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(conf))
            if m:
                c_val = float(m.group(1))
                if math.isfinite(c_val):
                    confidences.append(c_val)

        for key_name, bucket in (
            ("soundness", soundness),
            ("contribution", contribution),
            ("informativeness", informativeness),
            ("presentation", presentation),
        ):
            s_raw = _unwrap(c.get(key_name))
            if s_raw is not None and not isinstance(s_raw, bool):
                m_sub = re.match(r"^\s*(-?\d+(?:\.\d+)?)", str(s_raw))
                if m_sub:
                    sv = float(m_sub.group(1))
                    if math.isfinite(sv):
                        bucket.append(sv)

    venue_lower = venue.lower()
    venueid_lower = venueid.lower()
    dec_text = " | ".join(decisions)
    is_anonymous = (
        not authors
        or any("anonymous" in str(a).lower() for a in authors)
    )

    if WITHDRAWN_RE.search(venue_lower) or WITHDRAWN_RE.search(venueid_lower) or WITHDRAWN_RE.search(dec_text):
        status = "withdrawn"
    elif (
        REJECT_DECISION_RE.search(venue_lower)
        or REJECT_DECISION_RE.search(venueid_lower)
        or REJECT_DECISION_RE.search(dec_text)
        or "not accepted" in dec_text.lower()
    ):
        status = "rejected_or_unaccepted"
    elif (
        ACCEPT_VENUE_RE.search(venue_lower)
        or ACCEPT_DECISION_RE.search(venue_lower)
        or ACCEPT_DECISION_RE.search(dec_text)
    ):
        status = "accepted"
    elif "submitted to" in venue_lower:
        if is_anonymous or not ratings or "tmlr" in venue_lower or "transactions" in venue_lower:
            status = "under_review"
        else:
            status = "rejected_or_unaccepted"
    else:
        status = "unknown"

    declared_count = payload.get("count")
    completeness = "complete"
    if isinstance(declared_count, int) and declared_count > len(raw_notes):
        completeness = "incomplete"

    return {
        "forum_id": fid,
        "title": title,
        "authors": authors,
        "is_anonymous": bool(is_anonymous),
        "venue": venue,
        "venueid": venueid,
        "decisions": decisions,
        "reviewer_recommendations": reviewer_recommendations,
        "status_classification": status,
        "completeness": completeness,
        "review_count": len(ratings),
        "ratings": ratings,
        "mean_rating": float(sum(ratings) / len(ratings)) if ratings else None,
        "confidences": confidences,
        "soundness": soundness,
        "contribution": contribution,
        "informativeness": informativeness,
        "presentation": presentation,
    }


def summarize_venue_mirror(records: list[dict], topic_regex: str | None = None) -> dict:
    """对顶会全量 OpenReview 镜像列表执行确定性统计（状态分布、评分分位数、子维度均值、词数与主题筛选）。"""
    if not isinstance(records, list) or not records:
        raise ValueError("Venue mirror records must be a non-empty JSON list")
    status_cnt = Counter()
    area_cnt = Counter()
    all_means = []
    raw_hist: Counter[float] = Counter()
    by_status = {}
    topic_matches = []
    topic_re = re.compile(topic_regex, re.I) if topic_regex else None
    sub_totals: dict[str, list[float]] = {
        "soundness": [],
        "presentation": [],
        "contribution": [],
        "informativeness": [],
        "clarity": [],
        "quality": [],
        "significance": [],
        "originality": [],
        "confidence": [],
    }
    wc_reviews_pos: list[float] = []
    wc_by_conf: dict[int, list[float]] = {}
    multi_rev_papers = 0
    unanimous_papers = 0
    reply_eligible_reviews = 0
    zero_rev_reply_reviews = 0

    seen_ids = set()
    valid_submissions = 0
    invalid_skipped = 0
    duplicate_skipped = 0

    for r in records:
        if not isinstance(r, dict):
            invalid_skipped += 1
            continue
        fid = r.get("id") or r.get("openreview_forum")
        if fid:
            if fid in seen_ids:
                duplicate_skipped += 1
                continue
            seen_ids.add(fid)
        valid_submissions += 1
        st = str(r.get("status") or "Unknown").strip()
        status_cnt[st] += 1
        area = str(r.get("primary_area") or "").strip()
        if area:
            area_cnt[area] += 1
        rats = _parse_semi_numbers(r.get("rating"))
        if not rats and r.get("recommendation") is not None:
            rats = _parse_semi_numbers(r.get("recommendation"))
        if rats:
            m = sum(rats) / len(rats)
            all_means.append(m)
            by_status.setdefault(st, []).append(m)
            for x in rats:
                raw_hist[round(float(x), 4)] += 1
            if len(rats) >= 2:
                multi_rev_papers += 1
                if len({round(float(x), 4) for x in rats}) == 1:
                    unanimous_papers += 1
        for sk in sub_totals:
            vals_sk = _parse_semi_numbers(r.get(sk))
            if vals_sk:
                sub_totals[sk].extend(vals_sk)
        conf_slots = _parse_semi_slots(r.get("confidence"))
        wc_slots = _parse_semi_slots(r.get("wc_review"))
        if not any(x is not None and x > 0 for x in wc_slots):
            sw_s = _parse_semi_slots(r.get("wc_strengths_and_weaknesses"))
            lim_s = _parse_semi_slots(r.get("wc_limitations"))
            if sw_s or lim_s:
                wc_slots = [
                    ((sw_s[i] or 0.0) + (lim_s[i] or 0.0))
                    if ((i < len(sw_s) and sw_s[i] is not None) or (i < len(lim_s) and lim_s[i] is not None))
                    else None
                    for i in range(max(len(sw_s), len(lim_s)))
                ]
        for idx_w, wv in enumerate(wc_slots):
            if wv is not None and wv > 0:
                wc_reviews_pos.append(wv)
                if idx_w < len(conf_slots) and conf_slots[idx_w] is not None:
                    wc_by_conf.setdefault(int(round(conf_slots[idx_w])), []).append(wv)
        if r.get("replies_avg") is not None and rats:
            ravg = r.get("replies_avg")
            if isinstance(ravg, list) and ravg and isinstance(ravg[0], (int, float)):
                reply_eligible_reviews += 1
                if float(ravg[0]) <= len(rats):
                    zero_rev_reply_reviews += 1
        if topic_re:
            blob = f"{r.get('title', '')} {r.get('keywords', '')} {r.get('abstract', '')}"
            if topic_re.search(blob):
                topic_matches.append({
                    "id": fid,
                    "title": r.get("title"),
                    "status": st,
                    "rating": r.get("rating") if r.get("rating") is not None else r.get("recommendation"),
                    "mean_rating": round(sum(rats) / len(rats), 2) if rats else None,
                })

    tier_stats = {}
    for st, vals in by_status.items():
        s_vals = sorted(vals)
        tier_stats[st] = {
            "scored_count": len(s_vals),
            "mean": round(sum(s_vals) / len(s_vals), 3),
            "median": round(statistics.median(s_vals), 3),
            "min": round(s_vals[0], 3),
            "max": round(s_vals[-1], 3),
        }

    subscore_means = {
        sk: (round(sum(sv) / len(sv), 3) if sv else None)
        for sk, sv in sub_totals.items()
    }
    wc_stats = (
        {
            "count": len(wc_reviews_pos),
            "mean": round(sum(wc_reviews_pos) / len(wc_reviews_pos), 2),
            "median": round(statistics.median(wc_reviews_pos), 2),
        }
        if wc_reviews_pos
        else None
    )

    out = {
        "raw_record_count": len(records),
        "invalid_records_skipped": invalid_skipped,
        "duplicate_records_skipped": duplicate_skipped,
        "total_submissions": valid_submissions,
        "scored_submissions": len(all_means),
        "total_reviews": int(sum(raw_hist.values())),
        "overall_mean_rating": round(sum(all_means) / len(all_means), 3) if all_means else None,
        "overall_median_rating": round(statistics.median(all_means), 3) if all_means else None,
        "status_counts": dict(status_cnt),
        "tier_rating_stats": tier_stats,
        "raw_rating_histogram": {f"{k:g}": v for k, v in sorted(raw_hist.items(), key=lambda kv: kv[0])},
        "subscore_means": subscore_means,
        "review_word_count_stats": wc_stats,
        "review_forensics": {
            "multi_review_submissions": multi_rev_papers,
            "unanimous_identical_rating_count": unanimous_papers,
            "unanimous_identical_rating_share": (
                round(unanimous_papers / multi_rev_papers, 4) if multi_rev_papers else None
            ),
            "discussion_tracked_submissions": reply_eligible_reviews,
            "zero_discussion_beyond_reviews_share": (
                round(zero_rev_reply_reviews / reply_eligible_reviews, 4) if reply_eligible_reviews else None
            ),
            "word_count_median_by_confidence": {
                str(k): round(statistics.median(v), 1) for k, v in sorted(wc_by_conf.items()) if v
            },
        },
        "top_primary_areas": area_cnt.most_common(10),
    }
    if topic_re:
        out["topic_filter"] = {
            "pattern": topic_regex,
            "match_count": len(topic_matches),
            "by_status": dict(Counter(m["status"] for m in topic_matches)),
            "top_samples": sorted([m for m in topic_matches if m["mean_rating"] is not None], key=lambda x: -x["mean_rating"])[:10],
        }
    return out


def _find_local_mirror_fallback(forum_id: str, mirror_path: str | None = None) -> tuple[dict, str] | None:
    """Resolve from an explicitly provided mirror_path or explicit OPENREVIEW_MIRROR_DIR only (never ambient TMPDIR/TEMP)."""
    candidates: list[Path] = []
    if mirror_path and str(mirror_path).strip():
        candidates.append(Path(str(mirror_path).strip()))
    explicit_dir = (os.environ.get("OPENREVIEW_MIRROR_DIR") or "").strip()
    if explicit_dir:
        base_dir = safe_path(explicit_dir, must_exist=True)
        for p in sorted(base_dir.glob("iclr2027_*.json"), reverse=True):
            if p not in candidates:
                candidates.append(p)
        for fn in ("iclr2027.json", "iclr2026.json", "iclr2025.json", "icml2026.json", "nips2025.json", "colm2025.json"):
            p = base_dir / fn
            if p.exists() and p not in candidates:
                candidates.append(p)
        for p in sorted(base_dir.glob("*.json"), reverse=True):
            if p not in candidates:
                candidates.append(p)
    for raw_p in candidates:
        try:
            p = safe_path(raw_p, must_exist=True)
            if not p.is_file():
                continue
            raw_bytes = p.read_bytes()
            sha = hashlib.sha256(raw_bytes).hexdigest()
            data = json.loads(raw_bytes.decode("utf-8"))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and (item.get("id") == forum_id or item.get("openreview_forum") == forum_id):
                        rec = parse_mirror_record(item)
                        rec["verification_status"] = "unverified_local_mirror"
                        rec["authenticated"] = False
                        rec["mirror_sha256"] = sha
                        rec["source"] = f"mirror-fallback:{p.name}"
                        return rec, f"mirror-fallback:{p.name}"
        except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
    return None


def audit_forum(forum_id: str, mirror_path: str | None = None) -> dict:
    """Audit a single OpenReview forum via live API with explicit local mirror fallback on HTTP/network blocks."""
    if mirror_path and str(mirror_path).strip():
        p = safe_path(mirror_path, must_exist=True)
        raw_bytes = p.read_bytes()
        sha = hashlib.sha256(raw_bytes).hexdigest()
        payload = json.loads(raw_bytes.decode("utf-8"))
        res = parse_openreview_notes(payload, forum_id=forum_id)
        if isinstance(payload, list):
            res["verification_status"] = "unverified_local_mirror"
            res["authenticated"] = False
            res["mirror_sha256"] = sha
        return res
    try:
        live_payload = fetch_openreview_forum(forum_id)
        res = parse_openreview_notes(live_payload, forum_id=forum_id)
        res.setdefault("verification_status", "live_openreview_api")
        res.setdefault("authenticated", False)
        return res
    except (HTTPError, URLError, TimeoutError, OSError):
        fb = _find_local_mirror_fallback(forum_id)
        if fb is not None:
            return fb[0]
        raise


def fetch_openreview_forum(forum_id: str, max_bytes: int = 16 * 1024 * 1024) -> dict:
    url = "https://api2.openreview.net/notes?" + urlencode({"forum": forum_id, "limit": 1000})
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with controlled_urlopen(req, timeout=20, max_bytes=max_bytes) as resp:
        raw = resp.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError(f"OpenReview response exceeds {max_bytes} byte cap")
        data = json.loads(raw.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("OpenReview forum response must be a JSON object")
        return data

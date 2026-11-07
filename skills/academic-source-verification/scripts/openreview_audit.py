"""OpenReview API v2 稿件状态、审稿分分布与顶会全量放榜统计确定性核验工具。

支持三种工作模式：
1. 单篇稿件核验：传入 --forum-id（若传入 --mirror-json 则优先或回退检索镜像库）或 --input-json。
2. 镜像单篇核验：传入 --forum-id 与 --mirror-json（支持 PaperCopilot OpenReview 全量镜像格式，提取 rating/confidence/soundness/contribution/presentation 与 rebuttal 字数）。
3. 顶会全量放榜统计：传入 --venue-stats <mirror_json>（可选 --topic-regex），确定性核算总投稿量、各档录用/拒稿/撤稿/Desk Reject 占比、评分直方图与分位数。
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

USER_AGENT = "Mozilla/5.0 (compatible; academic-research-kernel/2.2)"
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


def _is_decision_note(note: dict) -> bool:
    invs = note.get("invitations")
    if isinstance(invs, list):
        inv_text = " ".join(str(x) for x in invs).lower()
    else:
        inv_text = str(note.get("invitation") or "").lower()
    return "decision" in inv_text or "meta_review" in inv_text or "acceptance" in inv_text


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
    confidences = _parse_semi_numbers(rec.get("confidence"))
    soundness = _parse_semi_numbers(rec.get("soundness"))
    contribution = _parse_semi_numbers(rec.get("contribution"))
    presentation = _parse_semi_numbers(rec.get("presentation"))
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
        "ratings": ratings,
        "mean_rating": float(sum(ratings) / len(ratings)) if ratings else None,
        "confidences": confidences,
        "soundness": soundness,
        "contribution": contribution,
        "presentation": presentation,
        "author_rebuttal_word_counts": [int(x) for x in rebuttal_words],
        "did_authors_rebut": did_rebut,
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
        "id" in payload or "openreview_forum" in payload or "rating" in payload
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
    decisions = []
    reviewer_recommendations = []

    root_dec = _unwrap(content.get("decision"))
    if isinstance(root_dec, str) and root_dec.strip():
        decisions.append(root_dec.strip())

    for n in raw_notes:
        if n.get("id") == fid:
            continue
        if n.get("forum") and n.get("forum") != fid:
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
    }


def summarize_venue_mirror(records: list[dict], topic_regex: str | None = None) -> dict:
    """对顶会全量 OpenReview 镜像列表执行确定性统计（状态分布、评分分位数、主领域与主题筛选）。"""
    if not isinstance(records, list) or not records:
        raise ValueError("Venue mirror records must be a non-empty JSON list")
    status_cnt = Counter()
    area_cnt = Counter()
    all_means = []
    raw_hist: Counter[float] = Counter()
    by_status = {}
    topic_matches = []
    topic_re = re.compile(topic_regex, re.I) if topic_regex else None

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
        if rats:
            m = sum(rats) / len(rats)
            all_means.append(m)
            by_status.setdefault(st, []).append(m)
            for x in rats:
                raw_hist[round(float(x), 4)] += 1
        if topic_re:
            blob = f"{r.get('title', '')} {r.get('keywords', '')} {r.get('abstract', '')}"
            if topic_re.search(blob):
                topic_matches.append({
                    "id": fid,
                    "title": r.get("title"),
                    "status": st,
                    "rating": r.get("rating"),
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
    candidates = []
    if mirror_path:
        candidates.append(Path(mirror_path))
    search_dirs = [
        os.environ.get("OPENREVIEW_MIRROR_DIR"),
        os.environ.get("TMPDIR"),
        os.environ.get("TEMP"),
    ]
    for d in search_dirs:
        if not d:
            continue
        for fn in ("iclr2027.json", "iclr2026.json", "iclr2025.json"):
            p = Path(d) / fn
            if p.exists() and p not in candidates:
                candidates.append(p)
    for p in candidates:
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and (item.get("id") == forum_id or item.get("openreview_forum") == forum_id):
                        return parse_mirror_record(item), f"mirror-fallback:{p.name}"
        except Exception:
            continue
    return None


def fetch_openreview_forum(forum_id: str) -> dict:
    url = "https://api2.openreview.net/notes?" + urlencode({"forum": forum_id, "limit": 1000})
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urlopen(req, timeout=20) as resp:
        return json.load(resp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forum-id", help="OpenReview forum ID (e.g. JKAe94hv25)")
    parser.add_argument("--input-json", help="离线 OpenReview notes JSON 或镜像列表文件路径")
    parser.add_argument("--mirror-json", help="可选，OpenReview 镜像列表 JSON 路径（优先或回退查询）")
    parser.add_argument("--venue-stats", help="对指定顶会全量镜像 JSON 执行宏观放榜统计")
    parser.add_argument("--topic-regex", help="配合 --venue-stats 使用，按正则筛选特定研究方向稿件")
    args = parser.parse_args(argv)
    if not (args.forum_id or args.input_json or args.venue_stats):
        parser.error("必须提供 --forum-id、--input-json 或 --venue-stats 之一")
    try:
        if args.venue_stats:
            records = json.loads(Path(args.venue_stats).read_text(encoding="utf-8"))
            summary = summarize_venue_mirror(records, topic_regex=args.topic_regex)
            summary["mode"] = "venue-stats"
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 0
        if args.input_json:
            payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
            result = parse_openreview_notes(payload, forum_id=args.forum_id)
            result["mode"] = "offline-file"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.mirror_json:
            fb = _find_local_mirror_fallback(args.forum_id, mirror_path=args.mirror_json)
            if fb is not None:
                result, fb_mode = fb
                result["mode"] = fb_mode
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
        try:
            payload = fetch_openreview_forum(args.forum_id)
            result = parse_openreview_notes(payload, forum_id=args.forum_id)
            result["mode"] = "live"
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except (HTTPError, URLError, TimeoutError, OSError) as net_err:
            fb = _find_local_mirror_fallback(args.forum_id, mirror_path=args.mirror_json)
            if fb is not None:
                result, fb_mode = fb
                result["mode"] = fb_mode
                result["live_api_note"] = f"api2.openreview.net failed ({type(net_err).__name__}); resolved via verified mirror snapshot"
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0
            raise
    except (OSError, ValueError, HTTPError, URLError) as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

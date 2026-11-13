"""从结构化实验收据 JSON 确定性生成 LaTeX booktabs 三线表（杜绝手抄数字出错）。

输入 JSON 格式：
{
  "caption": "Main benchmark comparison",
  "label": "tab:main_results",
  "columns": ["Method", "Recall (%)", "Latency (ms)"],
  "rows": [
    ["Baseline", 81.84, 24.50],
    ["Ours", 100.00, 12.60]
  ],
  "decimals": 2,
  "bold_max_cols": [1],
  "bold_min_cols": [2]
}
"""
from __future__ import annotations

import argparse
from decimal import Decimal, ROUND_HALF_UP, localcontext
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "^": r"\textasciicircum{}",
    "~": r"\textasciitilde{}",
}
LABEL_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")


def escape_latex(text: str) -> str:
    out = []
    for ch in str(text):
        if ch in ("\r", "\n"):
            out.append(" ")
        else:
            out.append(LATEX_ESCAPES.get(ch, ch))
    return "".join(out)


def _quantize_cell_number(val: int | float, c_i: int, decimals: int) -> tuple[Decimal, str]:
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise ValueError(f"Expected numeric cell, got {val!r}")
    if isinstance(val, float) and not math.isfinite(val):
        raise ValueError(f"Non-finite number in row: {val!r}")
    if isinstance(val, int) and (decimals == 0 or c_i == 0):
        d = Decimal(val)
        return d, str(val)
    with localcontext() as ctx:
        mag = 1 if val == 0 else max(1, int(math.floor(math.log10(abs(float(val))))) + 1)
        ctx.prec = max(64, mag + decimals + 16)
        d_raw = Decimal(str(val))
        q_exp = Decimal(1) if decimals == 0 else Decimal("1." + ("0" * decimals))
        d_q = d_raw.quantize(q_exp, rounding=ROUND_HALF_UP)
        return d_q, f"{d_q:.{decimals}f}"


def render_booktabs_table(spec: dict, source_sha256: str | None = None) -> str:
    if not isinstance(spec, dict):
        raise ValueError("Table specification must be a JSON object")
    columns = spec.get("columns")
    rows = spec.get("rows")
    if not isinstance(columns, list) or not columns:
        raise ValueError("'columns' must be a non-empty list")
    if not isinstance(rows, list) or not rows:
        raise ValueError("'rows' must be a non-empty list")
    ncols = len(columns)
    for r_i, r in enumerate(rows):
        if not isinstance(r, list) or len(r) != ncols:
            raise ValueError(f"Row {r_i} length does not match columns length ({ncols})")

    raw_dec = spec.get("decimals", 2)
    if isinstance(raw_dec, bool) or not isinstance(raw_dec, int) or not (0 <= raw_dec <= 15):
        raise ValueError("'decimals' must be an integer between 0 and 15")
    decimals = raw_dec

    def _parse_col_indices(field_name: str) -> set[int]:
        raw_list = spec.get(field_name) or []
        if not isinstance(raw_list, list):
            raise ValueError(f"{field_name!r} must be a list of column indices")
        out_set = set()
        for idx in raw_list:
            if isinstance(idx, bool) or not isinstance(idx, int) or not (0 <= idx < ncols):
                raise ValueError(f"Invalid column index in {field_name!r}: {idx!r}")
            out_set.add(idx)
        return out_set

    bold_max = _parse_col_indices("bold_max_cols")
    bold_min = _parse_col_indices("bold_min_cols")
    if not bold_max.isdisjoint(bold_min):
        raise ValueError("'bold_max_cols' and 'bold_min_cols' must be disjoint")

    caption = str(spec.get("caption", "Experimental results"))
    label = str(spec.get("label", "tab:results")).strip()
    if not LABEL_RE.fullmatch(label):
        raise ValueError(f"Invalid LaTeX table label {label!r}: only ASCII alphanumerics and _.:- are allowed")

    if source_sha256 is not None:
        if not isinstance(source_sha256, str) or not SHA256_RE.fullmatch(source_sha256):
            raise ValueError(f"Invalid source_sha256: {source_sha256!r}")

    col_targets: dict[int, Decimal] = {}
    for c_i in range(ncols):
        if c_i not in bold_max and c_i not in bold_min:
            continue
        q_nums = []
        for r in rows:
            val = r[c_i]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                d_q, _ = _quantize_cell_number(val, c_i, decimals)
                q_nums.append(d_q)
        if q_nums:
            col_targets[c_i] = max(q_nums) if c_i in bold_max else min(q_nums)

    align = "l" + "r" * (ncols - 1)
    lines = []
    if source_sha256:
        lines.append(f"% Deterministic LaTeX table generated from receipt sha256:{source_sha256}")
    lines.append(r"\begin{table}[t]")
    lines.append(r"\centering")
    lines.append(f"\\caption{{{escape_latex(caption)}}}")
    lines.append(f"\\label{{{label}}}")
    lines.append(f"\\begin{{tabular}}{{{align}}}")
    lines.append(r"\toprule")
    lines.append(" & ".join(escape_latex(c) for c in columns) + r" \\")
    lines.append(r"\midrule")

    for r in rows:
        cells = []
        for c_i, val in enumerate(r):
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                d_q, formatted = _quantize_cell_number(val, c_i, decimals)
                if c_i in col_targets and d_q == col_targets[c_i]:
                    formatted = f"\\textbf{{{formatted}}}"
                cells.append(formatted)
            else:
                cells.append(escape_latex(str(val)))
        lines.append(" & ".join(cells) + r" \\")

    lines.append(r"\bottomrule")
    lines.append(r"\end{tabular}")
    lines.append(r"\end{table}")
    return "\n".join(lines) + "\n"


def _reject_nonfinite_research_value(value: Any, location: str = "data") -> None:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite numeric value at {location}: {value!r}")
    elif isinstance(value, dict):
        for key, item in value.items():
            _reject_nonfinite_research_value(item, f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_nonfinite_research_value(item, f"{location}[{index}]")


def convert_research_artifact_to_spec(
    data: Any,
    mode: str,
    *,
    caption: str | None = None,
    label: str | None = None,
    left_extraction: dict | None = None,
    right_extraction: dict | None = None,
) -> dict:
    """Convert paper-research extraction.json, results.json, or comparison.json into a deterministic table spec."""
    mode_norm = str(mode or "").strip().lower()
    if mode_norm not in ("extraction", "results", "comparison"):
        raise ValueError(f"Unsupported --from-research mode {mode!r}; expected extraction, results, or comparison")
    _reject_nonfinite_research_value(data, "data")
    _reject_nonfinite_research_value(left_extraction, "left_extraction")
    _reject_nonfinite_research_value(right_extraction, "right_extraction")

    if mode_norm == "extraction":
        if not isinstance(data, dict) or not isinstance(data.get("fields"), list) or not data["fields"]:
            raise ValueError("extraction artifact must be a JSON object with a non-empty 'fields' list")
        paper = data.get("paper") if isinstance(data.get("paper"), dict) else {}
        default_cap = f"Extracted fields: {paper.get('title') or paper.get('identifier') or 'Paper'}"
        columns = ["Field ID", "Metric / Variable", "Reported Literal", "Unit", "Context", "Source Locator"]
        rows = []
        for idx, f in enumerate(data["fields"]):
            if not isinstance(f, dict):
                raise ValueError(f"fields[{idx}] must be an object")
            fid = str(f.get("id") or f"field_{idx + 1}")
            fname = str(f.get("name") or fid)
            status = str(f.get("status") or "unknown")
            if status == "extracted":
                lit = f.get("literal")
                val = f.get("value")
                rep = str(lit) if lit not in (None, "") else (str(val) if val is not None else "N/A")
            else:
                reason = str(f.get("reason") or "").strip()
                rep = f"[{status}] {reason}".strip()
            unit = str(f.get("unit")) if f.get("unit") not in (None, "") else "-"
            ctx_obj = f.get("context") if isinstance(f.get("context"), dict) else {}
            ctx = "; ".join(f"{k}={v}" for k, v in ctx_obj.items() if v not in (None, "")) or "-"
            srcs = f.get("sources") if isinstance(f.get("sources"), list) else []
            loc = "; ".join(
                f"{s.get('document_id', '?')}#{s.get('locator', '?')}"
                for s in srcs
                if isinstance(s, dict)
            ) or "-"
            rows.append([fid, fname, rep, unit, ctx, loc])
        return {
            "caption": caption or default_cap,
            "label": label or "tab:extracted_fields",
            "columns": columns,
            "rows": rows,
            "decimals": 2,
            "bold_max_cols": [],
            "bold_min_cols": [],
        }

    if mode_norm == "results":
        items = data.get("results") if isinstance(data, dict) and isinstance(data.get("results"), list) else data
        if not isinstance(items, list) or not items:
            raise ValueError("results artifact must be a non-empty JSON list of check results")
        columns = ["Check ID", "Kind", "Reported", "Recomputed", "Status", "Consistency"]
        rows = []
        for idx, r in enumerate(items):
            if not isinstance(r, dict):
                raise ValueError(f"results[{idx}] must be an object")
            cid = str(r.get("id") or f"check_{idx + 1}")
            kind = str(r.get("kind") or "unknown")
            rep = str(r.get("reported")) if r.get("reported") not in (None, "") else "unreported"
            rec_val = r.get("recomputed")
            if rec_val is None:
                rec_str = "N/A"
            elif isinstance(rec_val, dict):
                parts = []
                for k, v in rec_val.items():
                    if v is None:
                        continue
                    if isinstance(v, bool):
                        parts.append(f"{k}={'true' if v else 'false'}")
                    elif isinstance(v, float):
                        if not math.isfinite(v):
                            raise ValueError(f"Non-finite recomputed value in {cid}: {v!r}")
                        parts.append(f"{k}={v:.6g}")
                    else:
                        parts.append(f"{k}={v}")
                rec_str = ", ".join(parts) if parts else "N/A"
            elif isinstance(rec_val, bool):
                rec_str = "true" if rec_val else "false"
            elif isinstance(rec_val, float):
                if not math.isfinite(rec_val):
                    raise ValueError(f"Non-finite recomputed value in {cid}: {rec_val!r}")
                rec_str = f"{rec_val:.6g}"
            else:
                rec_str = str(rec_val)
            status = str(r.get("status") or "unknown")
            cons_val = r.get("consistent")
            cons = "consistent" if cons_val is True else ("discrepant" if cons_val is False else "uncompared")
            rows.append([cid, kind, rep, rec_str, status, cons])
        return {
            "caption": caption or "Deterministic statistical recomputation results",
            "label": label or "tab:recomputed_results",
            "columns": columns,
            "rows": rows,
            "decimals": 2,
            "bold_max_cols": [],
            "bold_min_cols": [],
        }

    # mode_norm == "comparison"
    if not isinstance(data, dict) or not isinstance(data.get("rows"), list) or not data["rows"]:
        raise ValueError("comparison artifact must be a JSON object with a non-empty 'rows' list")

    def _build_fmap(ext: dict | None) -> dict[str, dict]:
        if not isinstance(ext, dict) or not isinstance(ext.get("fields"), list):
            return {}
        return {str(f["id"]): f for f in ext["fields"] if isinstance(f, dict) and f.get("id")}

    left_map = _build_fmap(left_extraction)
    right_map = _build_fmap(right_extraction)

    def _fmt_side(fids: Any, fmap: dict[str, dict], side_label: str) -> str:
        if not isinstance(fids, list):
            raise ValueError(f"{side_label}_field_ids must be a list")
        if not fids:
            return "-"
        pieces = []
        for fid in fids:
            fid_s = str(fid)
            if fmap:
                if fid_s not in fmap:
                    raise ValueError(f"Comparison references unknown {side_label} field_id: {fid_s!r}")
                f = fmap[fid_s]
                lit = f.get("literal")
                val = f.get("value")
                rep = str(lit) if lit not in (None, "") else (str(val) if val is not None else str(f.get("reason") or "N/A"))
                unit = f" {f['unit']}" if f.get("unit") not in (None, "") else ""
                pieces.append(f"{f.get('name', fid_s)}: {rep}{unit}")
            else:
                pieces.append(fid_s)
        return "; ".join(pieces)

    columns = ["Dimension", "Paper A (Reported)", "Paper B (Reported)", "Comparability", "Rationale"]
    rows = []
    for idx, r in enumerate(data["rows"]):
        if not isinstance(r, dict):
            raise ValueError(f"comparison rows[{idx}] must be an object")
        dim = str(r.get("dimension") or f"dim_{idx + 1}")
        left_cell = _fmt_side(r.get("left_field_ids", []), left_map, "left")
        right_cell = _fmt_side(r.get("right_field_ids", []), right_map, "right")
        assess = str(r.get("assessment") or "unknown")
        reason = str(r.get("reason") or "-")
        rows.append([dim, left_cell, right_cell, assess, reason])

    return {
        "caption": caption or "Two-paper structured comparison",
        "label": label or "tab:paper_comparison",
        "columns": columns,
        "rows": rows,
        "decimals": 2,
        "bold_max_cols": [],
        "bold_min_cols": [],
    }

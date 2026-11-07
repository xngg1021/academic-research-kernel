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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="实验收据表规格 JSON 文件路径")
    parser.add_argument("--output", help="可选，输出 .tex 文件路径")
    parser.add_argument("--rows", help="可选，JSON 路径（当输入为嵌套字典时提取指定行列表键）")
    parser.add_argument("--cols", help="可选，逗号分隔的列名覆盖列表")
    args = parser.parse_args(argv)
    try:
        raw_bytes = Path(args.input).read_bytes()
        sha = hashlib.sha256(raw_bytes).hexdigest()
        spec = json.loads(raw_bytes.decode("utf-8"))
        if args.rows and isinstance(spec, dict) and args.rows in spec and "rows" not in spec:
            spec = dict(spec, rows=spec[args.rows])
        if args.cols and isinstance(spec, dict):
            if args.cols in spec and isinstance(spec[args.cols], list):
                spec = dict(spec, columns=spec[args.cols])
            elif "," in args.cols:
                spec = dict(spec, columns=[c.strip() for c in args.cols.split(",") if c.strip()])
        latex = render_booktabs_table(spec, source_sha256=sha)
        if args.output:
            Path(args.output).write_text(latex, encoding="utf-8")
        print(json.dumps({
            "status": "ok",
            "source_sha256": sha,
            "row_count": len(spec["rows"]),
            "col_count": len(spec["columns"]),
            "latex": latex,
        }, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

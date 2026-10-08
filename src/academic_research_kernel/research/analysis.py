"""Validate semantic reading, reuse kernel calculations and emit located reports.

There is deliberately no model or hidden network call here. A portable Agent
reads prepared source material and supplies the typed candidate to ``finish``.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import html
import json
import math
import os
from importlib import metadata
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

PIPELINE_VERSION = "paper-research-analysis-1.0"
_DIGITS = r"(?:\d{1,3}(?:,\s*\d{3})+(?!\d)|\d+)"
_NUMBER = re.compile(r"[-+]?(?:" + _DIGITS + r"(?:\.\d+|\.(?=[eE][-+]?\d+))?|\.\d+)(?:[eE][-+]?\d+)?")
_NUMBER_WORDS = {word: value for value, word in enumerate((
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"))}
for _tens, _base in (("twenty", 20), ("thirty", 30), ("forty", 40), ("fifty", 50),
                     ("sixty", 60), ("seventy", 70), ("eighty", 80), ("ninety", 90)):
    _NUMBER_WORDS[_tens] = _base
    for _ones in ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine"):
        _NUMBER_WORDS[_tens + "-" + _ones] = _base + _NUMBER_WORDS[_ones]
        _NUMBER_WORDS[_tens + " " + _ones] = _base + _NUMBER_WORDS[_ones]
_STATUS = {"extracted": "已提取", "not_found": "本次未找到", "explicitly_unreported": "原文明示未报告",
           "parse_failed": "解析失败", "not_applicable": "不适用"}


def _kernel():
    from .. import mcp_server
    return mcp_server


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_bytes(value)).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _safe(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"Source path escapes project: {relative}")
    return path


def _space(text: str) -> str:
    return " ".join(text.split())


def _numeric_token(text: str) -> str:
    return re.sub(r"[,\s]", "", text)


def _literal(field: dict) -> str:
    word = (field["literal"] or "").strip().lower()
    if field["type"] == "integer" and word in _NUMBER_WORDS:
        if isinstance(field["value"], bool) or _NUMBER_WORDS[word] != field["value"]:
            raise ValueError(f"{field['id']}: normalized value differs from integer word")
        return str(_NUMBER_WORDS[word])
    matches = _NUMBER.findall((field["literal"] or "").replace("−", "-"))
    if len(matches) != 1:
        raise ValueError(f"{field['id']}: numeric literal must contain exactly one number")
    literal = _numeric_token(matches[0])
    try:
        number = Decimal(literal)
        actual = Decimal(str(field["value"]))
    except InvalidOperation as exc:
        raise ValueError(f"{field['id']}: invalid numeric literal") from exc
    if not number.is_finite() or not actual.is_finite() or number != actual:
        raise ValueError(f"{field['id']}: normalized value differs from literal {field['literal']!r}")
    return literal


def validate_candidate(project: str | Path, candidate: dict, *, documents: dict | None = None) -> dict:
    """Reject stale bytes, fabricated locations, unknown fields and empty reading."""
    root = Path(project).resolve()
    if documents is None:
        from .sources import verify
        documents = verify(root)
    kernel = _kernel()
    errors = kernel.validate_schema(candidate, "paper-extraction.schema.json")
    if errors:
        raise ValueError("Extraction schema: " + "; ".join(errors))
    if candidate["project_fingerprint"] != documents["fingerprint"]:
        raise ValueError("Extraction is stale: project fingerprint changed; read the current prepared materials")
    manifest_path = root / "manifest.json"
    if manifest_path.is_file():
        manifest = _json(manifest_path)
        title = manifest.get("title")
        if title and kernel.id_mod.normalize_title(title) != kernel.id_mod.normalize_title(candidate["paper"]["title"]):
            raise ValueError("Candidate paper title differs from acquired manifest identity")
        identifier = manifest.get("doi") or manifest.get("identifier")
        if identifier:
            normalized = kernel.id_mod.normalize("doi", identifier)
            if re.match(r"^10\.\d{4,9}/", normalized) and normalized != kernel.id_mod.normalize("doi", candidate["paper"]["identifier"]):
                raise ValueError("Candidate DOI differs from acquired manifest identity")
    docmap = {doc["document_id"]: doc for doc in documents["documents"]}
    successful = {key for key, doc in docmap.items() if doc.get("segments")}
    if set(candidate["search_scope"]) != successful:
        raise ValueError("search_scope must enumerate every successfully parsed body and attachment before declaring missing fields")
    for document in docmap.values():
        path = _safe(root, document["relative_path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != document["sha256"]:
            raise ValueError(f"Source bytes changed: {document['document_id']}")
    fields = candidate["fields"]
    ids = [f["id"] for f in fields]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate field IDs")
    if sum(f["status"] == "extracted" for f in fields) < 10:
        raise ValueError("At least ten populated, source-located key fields are required")
    for field in fields:
        if field["status"] == "extracted":
            value, kind = field["value"], field["type"]
            if kind in {"number", "integer", "p_value"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError(f"{field['id']}: expected finite number")
                _literal(field)
                if kind == "integer" and value != int(value):
                    raise ValueError(f"{field['id']}: expected integer")
                if kind == "p_value" and not 0 <= value <= 1:
                    raise ValueError(f"{field['id']}: p outside [0,1]")
            elif kind == "text" and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field['id']}: expected nonempty text")
            elif kind == "boolean" and not isinstance(value, bool):
                raise ValueError(f"{field['id']}: expected boolean")
        if field["status"] == "explicitly_unreported" and not field["sources"]:
            raise ValueError(f"{field['id']}: an explicit non-reporting statement requires a quotation")
        if field["status"] == "extracted" and field["type"] in {"text", "boolean"}:
            if not any(_space(field["literal"]) in _space(source["quote"]) for source in field["sources"]):
                raise ValueError(f"{field['id']}: raw text literal is absent from the cited quotation")
        for source in field["sources"]:
            document = docmap.get(source["document_id"])
            if document is None:
                raise ValueError(f"{field['id']}: unknown source document")
            segment = next((s for s in document["segments"] if s["locator"] == source["locator"]), None)
            if segment is None:
                raise ValueError(f"{field['id']}: source locator does not exist: {source['locator']}")
            if _space(source["quote"]) not in _space(segment["text"]):
                raise ValueError(f"{field['id']}: quoted text does not match source locator")
            if field["status"] == "extracted" and field["type"] in {"number", "integer", "p_value"}:
                # Source quotations must actually contain the numeric token,
                # including its reported decimal precision and trailing zeroes.
                literal = _literal(field)
                tokens = [_numeric_token(x) for x in _NUMBER.findall(source["quote"].replace("−", "-"))]
                word_literal = field["type"] == "integer" and (field["literal"] or "").strip().lower() in _NUMBER_WORDS
                word_present = word_literal and re.search(r"\b" + re.escape(field["literal"].strip()) + r"\b", source["quote"], re.I)
                if not word_present and literal not in tokens:
                    raise ValueError(f"{field['id']}: numeric literal/precision absent from quoted source")
                if field["type"] == "p_value":
                    operator = re.search(r"(<=|>=|<|>|≤|≥)", field["literal"])
                    relation = operator.group(1).replace("≤", "<=").replace("≥", ">=") if operator else "="
                    source_relations = {m.group(1).replace("≤", "<=").replace("≥", ">=")
                                        for m in re.finditer(r"(<=|>=|<|>|≤|≥)\s*(" + _NUMBER.pattern + r")", source["quote"])
                                        if _numeric_token(m.group(2)) == literal}
                    if (relation != "=" and relation not in source_relations) or (relation == "=" and source_relations):
                        raise ValueError(f"{field['id']}: p-value inequality differs from source quotation")
    known = set(ids)
    for key, item in candidate["summary"].items():
        if set(item["field_ids"]) - known:
            raise ValueError(f"summary.{key}: unknown field reference")
    check_ids = [check["id"] for check in candidate["checks"]]
    if len(check_ids) != len(set(check_ids)):
        raise ValueError("Duplicate check IDs")
    for check in candidate["checks"]:
        referenced = set(check["inputs"].values()) | ({check["reported"]} if check["reported"] else set())
        if referenced - known:
            raise ValueError(f"{check['id']}: unknown input field")
        if check["kind"] == "percentage" and check["reported"] != check["inputs"].get("percent"):
            raise ValueError(f"{check['id']}: percentage reported must reference the same field as inputs.percent")
    conflicts = []
    grouped: dict[str, list] = {}
    for field in fields:
        if field["status"] != "extracted":
            continue
        key = _digest({"name": field["name"], "context": field["context"], "unit": field["unit"]})
        grouped.setdefault(key, []).append(field)
    for group in grouped.values():
        if len({_digest(f["value"]) for f in group}) > 1:
            conflicts.append({"field_ids": [f["id"] for f in group], "name": group[0]["name"],
                              "context": group[0]["context"], "reason": "同名字段在同一条件下有不同报告值；保留双方来源。"})
    return {"valid": True, "field_count": len(fields), "extracted_count": sum(f["status"] == "extracted" for f in fields),
            "documents_fingerprint": documents["fingerprint"], "conflicts": conflicts}


def _context_errors(check: dict, fields: dict) -> list[str]:
    selected = {arg: fields[field_id] for arg, field_id in check["inputs"].items()}
    errors = []
    if check["kind"] == "percentage" and check["reported"] != check["inputs"].get("percent"):
        errors.append("百分比报告值必须与inputs.percent引用同一字段，拒绝错位的一致性判定")
    for arg, field in selected.items():
        if field["status"] != "extracted" or field["type"] not in {"number", "integer", "p_value"}:
            errors.append(f"{arg} 对应字段尚无可用数值 ({field['id']})")
    if errors:
        return errors
    contexts = [f["context"] for f in selected.values()]
    axes = ["dataset", "timepoint", "analysis_set", "condition"]
    if check["kind"] != "effect_size":
        axes.append("group")
    for axis in axes:
        if len({c[axis] for c in contexts}) > 1:
            errors.append(f"输入的 {axis} 不一致，不能合并计算")
    reported = fields.get(check["reported"])
    if reported:
        for axis in axes:
            if any(c[axis] != reported["context"][axis] for c in contexts):
                errors.append(f"论文报告值的 {axis} 与输入不一致")
    if check["kind"] == "effect_size":
        for suffix in ("1", "2"):
            triplet = [selected.get(key + suffix) for key in ("mean", "sd", "n")]
            if all(triplet) and len({f["context"]["group"] for f in triplet}) > 1:
                errors.append(f"第{suffix}组均值、SD、n 的组别不一致")
        units = {selected[key]["unit"] for key in ("mean1", "sd1", "mean2", "sd2") if key in selected}
        if len(units) > 1:
            errors.append("均值与SD单位/尺度不一致")
        for key in ("sd1", "sd2"):
            if key in selected and re.search(r"\bSE\b|standard error|标准误", selected[key]["name"] + " " + (selected[key]["unit"] or ""), re.I):
                errors.append(f"{key}引用标准误SE，所选函数需要标准差SD")
    return errors


def compute_checks(candidate: dict, documents: dict) -> list[dict]:
    """Use the installed existing MCP handlers and recompute library."""
    kernel = _kernel()
    fields = {f["id"]: f for f in candidate["fields"]}
    docs = {d["document_id"]: d for d in documents["documents"]}
    results = []
    required = {"t_p": {"t_stat", "df"}, "effect_size": {"mean1", "sd1", "n1", "mean2", "sd2", "n2"},
                "percentage": {"count", "percent", "sample_size"}}
    for check in candidate["checks"]:
        result = {"id": check["id"], "kind": check["kind"], "note": check["note"],
                  "reported": fields[check["reported"]]["literal"] if check["reported"] else None,
                  "inputs": {}, "input_chain": {}, "status": "not_computed", "consistent": None}
        for argument, field_id in check["inputs"].items():
            field = fields[field_id]
            result["inputs"][argument] = field["value"]
            result["input_chain"][argument] = {"field_id": field_id, "literal": field["literal"], "unit": field["unit"],
                "context": field["context"], "sources": [{**s, "sha256": docs[s["document_id"]]["sha256"],
                "relative_path": docs[s["document_id"]]["relative_path"]} for s in field["sources"]]}
        errors = _context_errors(check, fields)
        missing = required[check["kind"]] - set(check["inputs"])
        unknown = set(check["inputs"]) - required[check["kind"]]
        if missing:
            errors.append("缺少输入: " + ", ".join(sorted(missing)))
        if unknown:
            errors.append("未知函数参数: " + ", ".join(sorted(unknown)))
        if check["kind"] == "t_p" and check["tail"] not in {"two", "one"}:
            errors.append("t/p核对缺少单双尾定义；本次保留报告值")
        if check["kind"] == "t_p" and check["tail"] == "one" and check.get("alternative") not in {"less", "greater"}:
            errors.append("单尾t/p核对缺少明确alternative=less/greater；不按统计量符号猜方向")
        if errors:
            result["reason"] = "; ".join(errors)
            results.append(result)
            continue
        values = result["inputs"].copy()
        try:
            if check["kind"] == "t_p":
                reported = fields.get(check["reported"])
                relation = "="
                if reported:
                    match = re.search(r"(<=|>=|<|>|≤|≥)", reported["literal"])
                    relation = match.group(1) if match else "="
                    if relation == "=" and check["tail"] == "two":
                        values.update(p_value=reported["value"], p_value_literal=_literal(reported))
                output = kernel.handle_tool_call("academic_recompute_statistics", values)
                result["tool"] = "academic_recompute_statistics"
                result["recomputed"] = output.get("recomputed_p")
                result["formula"] = output.get("p_receipt", {}).get("formula")
                result["library"] = output.get("p_receipt", {}).get("library")
                if check["tail"] == "one" and result["recomputed"] is not None:
                    p_two, t_stat = result["recomputed"], values["t_stat"]
                    alternative = check["alternative"]
                    aligned = (alternative == "less" and t_stat < 0) or (alternative == "greater" and t_stat > 0)
                    p_one = .5 if t_stat == 0 else p_two / 2 if aligned else 1 - p_two / 2
                    conversion = "p_one=p_two/2" if aligned else "p_one=1-p_two/2" if t_stat else "p_one=0.5 at t=0"
                    result["tail_conversion"] = {"alternative": alternative, "two_sided_p": p_two, "one_sided_p": p_one, "formula": conversion}
                    result["recomputed"] = p_one
                    result["formula"] = (result["formula"] or "existing two-sided t probability") + "; " + conversion + "; alternative=" + alternative
                if reported and relation != "=":
                    actual, limit = result["recomputed"], reported["value"]
                    result["consistent"] = {"<": actual < limit, "<=": actual <= limit, "≤": actual <= limit,
                                             ">": actual > limit, ">=": actual >= limit, "≥": actual >= limit}[relation]
                    result["precision"] = {"relation": relation, "threshold_literal": _literal(reported),
                                           "interpretation": "inequality; no equality or rounding substitution"}
                elif reported:
                    precision = kernel.recompute.check_p_match(reported["value"], result["recomputed"], reported_literal=_literal(reported)) if check["tail"] == "one" else output.get("p_match")
                    result["consistent"] = precision.get("consistent") if precision else None
                    result["precision"] = precision
            elif check["kind"] == "effect_size":
                output = kernel.handle_tool_call("academic_recompute_statistics", values)
                result.update(tool="academic_recompute_statistics", recomputed={key: output[key] for key in ("cohens_d", "hedges_g", "pooled_sd", "df") if key in output},
                              formula="d=(mean1-mean2)/pooled SD; g=d*(1-3/(4df-1))", library="existing quantitative-paper-audit/recompute.cohens_d")
                if check["reported"]:
                    reported = fields[check["reported"]]
                    # values_agree is the existing general precision comparator.
                    tolerance = float(Decimal(5).scaleb(Decimal(_literal(reported)).as_tuple().exponent - 1))
                    precision = kernel.recompute.values_agree(reported["value"], output["cohens_d"], rel_tol=0, abs_tol=tolerance)
                    result.update(consistent=precision["consistent"], precision=precision)
            else:
                percent = fields[check["inputs"]["percent"]]
                values["percent"] = _literal(percent)
                output = kernel.handle_tool_call("academic_check_percentage", values)
                result.update(tool="academic_check_percentage", recomputed=output.get("recomputed_percent"), consistent=output.get("consistent"),
                              formula=output.get("formula"), library=output.get("library"),
                              precision={key: output[key] for key in ("decimals", "tolerance", "tolerance_decimal", "precision_source") if key in output})
            result["raw_result"] = output
            if output.get("error"):
                result.update(status="failed", reason=output["error"])
            else:
                result["status"] = "computed"
        except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
            result.update(status="failed", reason=str(exc))
        results.append(result)
    return results


def _citation(field: dict, documents: dict, *, prefix: str = "../../") -> str:
    docs = {d["document_id"]: d for d in documents["documents"]}
    links = []
    for source in field["sources"]:
        document = docs[source["document_id"]]
        segment = next(s for s in document["segments"] if s["locator"] == source["locator"])
        fragment = ""
        if document["format"] == "pdf" and isinstance(segment.get("page_index"), int):
            fragment = "#page=" + str(segment["page_index"] + 1)
        url = prefix + quote(document["relative_path"].replace("\\", "/"), safe="/") + fragment
        label = f"{source['document_id']} · {source['locator']}"
        if segment.get("printed_page") is not None:
            label += f" · 印刷页{segment['printed_page']}"
        anchor = source['document_id'] + '-' + hashlib.sha256(source['locator'].encode()).hexdigest()[:16]
        links.append(f"[{label}]({prefix}locations.html#{anchor}) · [原文件]({url})")
    return "；".join(links)


def _cell(value: Any) -> str:
    return str(value if value is not None else "未知").replace("|", "\\|").replace("\n", " ")


def _citations(field_ids: list[str], fields: dict, documents: dict) -> str:
    sources, seen = [], set()
    for field_id in field_ids:
        for source in fields[field_id]["sources"]:
            key = (source["document_id"], source["locator"])
            if key not in seen:
                sources.append(source)
                seen.add(key)
    return _citation({"sources": sources}, documents)


def _number_display(result: dict) -> str:
    value = result.get("recomputed")
    if isinstance(value, dict):
        return "，".join(f"{name}={number:.8g}" for name, number in value.items() if isinstance(number, (int, float)))
    if isinstance(value, (int, float)):
        name = "p" if result["kind"] == "t_p" else "百分比"
        return f"{name}={value:.10g}" + ("%" if result["kind"] == "percentage" else "")
    return str(value)


def _report(candidate: dict, documents: dict, validation: dict, results: list[dict], digest: str) -> str:
    fields = {f["id"]: f for f in candidate["fields"]}
    lines = [f"# {candidate['paper']['title']}：中文研究报告", "",
             f"出版标识：{candidate['paper']['identifier']}；具体版本：{candidate['paper']['version']}。", ""]
    for key, label in (("objective", "研究问题"), ("design", "方法"), ("main_results", "主要结果"), ("attention", "最值得关注")):
        statement = candidate["summary"][key]
        cites = _citations(statement["field_ids"], fields, documents)
        lines += [f"**{label}（Agent据原文整理）：** {statement['text']} {cites}", ""]
    completed = [r for r in results if r["status"] == "computed"]
    discrepancies = [r for r in completed if r["consistent"] is False]
    comparable = sum(isinstance(r["consistent"], bool) for r in completed)
    lines += [f"**本次实际计算：** {len(completed)}项；其中{comparable}项能与作者同口径报告值比较，{len(discrepancies)}项超出所用报告精度/阈值。其余{len(results)-len(completed)}项列出未计算原因。计算基于原文报告输入，输入自身四舍五入和分析条件会影响解释。", ""]
    for result in completed:
        verdict = "符合报告精度/阈值" if result["consistent"] is True else "超出报告精度/阈值" if result["consistent"] is False else "未提供对应的作者报告值，供尺度理解"
        cites = _citations([chain["field_id"] for chain in result["input_chain"].values()], fields, documents)
        lines.append(f"- **{result['id']}：** 作者报告 {result['reported'] or '未报告该项'}；实际重算 **{_number_display(result)}**；{verdict}。{cites}")
    lines += ["", "## 方法与关键字段", "", "| 字段 | 作者原始报告 / 状态 | 条件、单位 | 原文位置 |", "|---|---|---|---|"]
    for field in candidate["fields"]:
        context = "; ".join(f"{key}={value}" for key, value in field["context"].items() if value is not None)
        observed = field["literal"] if field["status"] == "extracted" else f"{_STATUS[field['status']]}：{field['reason']}"
        lines.append(f"| {_cell(field['name'])} (`{field['id']}`) | {_cell(observed)} | {_cell(context)}；单位={_cell(field['unit'])} | {_citation(field, documents)} |")
    lines += ["", "## 数值核对（程序调用现有计算工具）", ""]
    if not results:
        lines += ["本资料未形成满足现有计算函数输入条件的核对项；具体未报告字段及适用范围见上表。", ""]
    for result in results:
        verdict = "符合报告精度/阈值" if result["consistent"] is True else "超出报告精度/阈值" if result["consistent"] is False else "未给一致性判定"
        lines += [f"### {result['id']} — {verdict}", "", f"作者报告：{result['reported'] or '未提供与该函数对应的报告值'}。",
                  f"实际输入：`{json.dumps(result['inputs'], ensure_ascii=False)}`。",
                  f"计算结果：`{json.dumps(result.get('recomputed'), ensure_ascii=False)}`；状态：{result['status']}。",
                  f"方法：{result.get('formula') or result.get('reason', '输入不足')}。{result['note']}", ""]
        for argument, chain in result["input_chain"].items():
            field = fields[chain["field_id"]]
            lines.append(f"- `{argument}` ← `{field['id']}`（字面量 `{field['literal']}`）：{_citation(field, documents)}")
        if result.get("precision"):
            lines += ["", f"精度判据：`{json.dumps(result['precision'], ensure_ascii=False)}`。"]
        lines += [""]
    lines += ["## 原文片段与冲突", ""]
    for conflict in validation["conflicts"]:
        lines += [f"- {conflict['name']}：{conflict['reason']} 字段：{', '.join(conflict['field_ids'])}。"]
    quotations = {}
    for field in candidate["fields"]:
        for source in field["sources"]:
            key = _digest(source)
            entry = quotations.setdefault(key, {"source": source, "field_ids": []})
            entry["field_ids"].append(field["id"])
    for entry in quotations.values():
        source = entry["source"]
        lines += [f"**{', '.join(entry['field_ids'])}** · `{source['document_id']}#{source['locator']}`", "", f"> {_space(source['quote'])}", ""]
    lines += ["## 原始材料及可追溯状态", "", "| 文档 | 角色 / 格式 | SHA-256 | 来源 |", "|---|---|---|---|"]
    for doc in documents["documents"]:
        lines.append(f"| {_cell(doc['document_id'])} | {_cell(doc['role'])} / {_cell(doc['format'])} | `{doc['sha256']}` | {_cell(doc.get('source_url') or '本地资料包')} |")
    lines += ["", f"语义生产者：{candidate['producer']['name']}；模型：{candidate['producer']['model'] or '未取得具体版本'}；解析器：`{json.dumps(documents['parser'], ensure_ascii=False)}`。",
              f"项目材料指纹：`{documents['fingerprint']}`；本次分析指纹：`{digest}`。",
              "结构化输入与实际工具返回值保存在 extraction.json、results.json；ResearchObject、CEG、入库回执与谱系保存在 kernel-state.json、ingestion-receipts.json、lineage.json。"]
    return "\n".join(lines) + "\n"


def _html(markdown: str, title: str) -> str:
    def inline(text: str) -> str:
        text = html.escape(text)
        def link(match):
            label, url = match.groups()
            plain = html.unescape(url).strip()
            if re.search(r"[\x00-\x1f]", plain) or (":" in plain and not re.match(r"^(?:https?|file)://", plain, re.I)):
                return label
            return '<a href="' + url + '">' + label + '</a>'
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)
        text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
        return re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    blocks, in_table, in_list = [], False, False
    for line in markdown.splitlines():
        if not line.startswith("|") and in_table:
            blocks.append("</tbody></table></div>")
            in_table = False
        if not line.startswith("- ") and in_list:
            blocks.append("</ul>")
            in_list = False
        if line.startswith("|"):
            if re.match(r"^\|[-|: ]+\|$", line):
                continue
            cells = re.split(r"(?<!\\)\|", line)[1:-1]
            if not in_table:
                blocks.append('<div class="table"><table><tbody>')
                in_table = True
            blocks.append("<tr>" + "".join("<td>" + inline(c.strip().replace("\\|", "|")) + "</td>" for c in cells) + "</tr>")
        elif line.startswith("#"):
            level = min(6, len(line) - len(line.lstrip("#")))
            blocks.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
        elif line.startswith("> "):
            blocks.append("<blockquote>" + inline(line[2:]) + "</blockquote>")
        elif line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append("<li>" + inline(line[2:]) + "</li>")
        elif line.strip():
            blocks.append("<p>" + inline(line) + "</p>")
    if in_table:
        blocks.append("</tbody></table></div>")
    if in_list:
        blocks.append("</ul>")
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>' + html.escape(title) + '</title><style>body{font:16px/1.65 system-ui,sans-serif;color:#15252d;background:#f6f7f6;max-width:1100px;margin:0 auto;padding:32px}h1{font-size:27px;line-height:1.3}h2{border-bottom:1px solid #c8d1d3;padding-bottom:8px;margin-top:36px}h3{font-size:18px}a{color:#12637b}table{border-collapse:collapse;width:100%;font-size:14px;background:white}td{border:1px solid #d4dadd;padding:9px;vertical-align:top}tr:first-child{font-weight:600;background:#e9eef0}.table{overflow:auto}code{overflow-wrap:anywhere;font-size:13px}blockquote{border-left:3px solid #7e9ba7;margin:10px 0;padding:8px 14px;background:white;color:#334b56}p{overflow-wrap:anywhere}</style><main>' + "\n".join(blocks) + "</main></html>\n"


def _ingest(project: Path, run: Path, candidate: dict, documents: dict, results: list[dict]) -> dict:
    kernel = _kernel()
    ReceiptRef, LineageVerificationContext = kernel.ReceiptRef, kernel.LineageVerificationContext
    graph = kernel.prov_mod.LineageGraph(root_dir=project)
    extraction_id = "extraction-" + _digest(candidate)[:32]
    output_id = "results-" + _digest(results)[:32]
    graph.add_entity(extraction_id, "table_cell", sha256=hashlib.sha256((run / "extraction.json").read_bytes()).hexdigest(), locator=str((run / "extraction.json").relative_to(project)))
    graph.add_entity(output_id, "statistic_artifact", sha256=hashlib.sha256((run / "results.json").read_bytes()).hexdigest(), locator=str((run / "results.json").relative_to(project)))
    read_id, compute_id = "read-" + _digest(candidate)[:32], "compute-" + _digest(results)[:32]
    graph.add_activity(read_id, "table_extraction", parameters={"producer": candidate["producer"], "parser": documents["parser"]}, timestamp="1970-01-01T00:00:00Z")
    graph.record_generated(read_id, extraction_id)
    for document in documents["documents"]:
        source_id = "source-" + _digest({"sha256": document["sha256"], "document_id": document["document_id"]})
        graph.add_entity(source_id, "data_snapshot", sha256=document["sha256"], locator=document["relative_path"], metadata={"document_id": document["document_id"], "role": document["role"]})
        graph.record_used(read_id, source_id)
        graph.record_derivation(extraction_id, source_id, activity_id=read_id)
    graph.add_activity(compute_id, "statistical_analysis", command="existing MCP quantitative tools", parameters={"pipeline": PIPELINE_VERSION}, timestamp="1970-01-01T00:00:00Z")
    graph.record_used(compute_id, extraction_id)
    graph.record_generated(compute_id, output_id)
    graph.record_derivation(output_id, extraction_id, activity_id=compute_id)
    budget = sum(_safe(project, document["relative_path"]).stat().st_size for document in documents["documents"]) + sum((run / name).stat().st_size for name in ("extraction.json", "results.json"))
    context = LineageVerificationContext(content_root=project, max_content_bytes=max(10 * 1024 * 1024, budget + 1024))
    lineage = kernel.prov_mod.trace_origin(graph, output_id, verification_context=context).to_dict()
    if lineage["verification_status"] != "intact":
        raise ValueError("Lineage source verification failed: " + str(lineage.get("error_detail")))
    state = kernel.IngestionKernelState(verification_context=context, ceg=kernel.ceg_mod.ClaimEvidenceGraph(), ledger=kernel.ledger_mod.DecisionLedger())
    engine = kernel.IngestionEngine()
    receipts = []
    def ingest(payload, skill, schema, kind, **kwargs):
        envelope = kernel.ArtifactEnvelope.create(payload=payload, producer_skill=skill, producer_version="1.0.0", payload_schema=schema, artifact_kind=kind, **kwargs)
        receipt = engine.ingest(envelope, state=state)
        if receipt.status != "accepted":
            raise ValueError(f"Kernel rejected {schema}: {receipt.failure_reason}")
        receipts.append(receipt.to_dict())
    identifier = candidate["paper"]["identifier"]
    doi = kernel.id_mod.normalize("doi", identifier)
    is_doi = bool(re.match(r"^10\.\d{4,9}/", doi))
    object_id = ("work:doi:" + doi) if is_doi else "work:paper:" + _digest(identifier)[:32]
    research_object = {"object_id": object_id, "object_type": "Work", "title": candidate["paper"]["title"],
                       "identifiers": [{"type": "doi" if is_doi else "other", "value": identifier, "normalized": doi if is_doi else identifier}],
                       "manifestations": [], "relations": [], "lineage": [], "source_observations": [], "uncertainty": []}
    ingest(research_object, "research-object-identity", "research-object-1.0", "research_object")
    ingest(lineage, "research-object-identity", "lineage-receipt-1.0", "lineage_receipt")
    ref = ReceiptRef(kind="lineage", schema_version="lineage-receipt-1.0", receipt_id=lineage["receipt_id"], receipt_digest=lineage["receipt_digest"])
    ingest(candidate, "paper-research", "paper-extraction-1.0", "paper_extraction", lineage_ref=ref, subject_refs=[object_id])
    assertions = []
    for result in results:
        if result["status"] != "computed":
            continue
        assertions.append({"statistic": result["id"], "reported": result["reported"], "recomputed": result["recomputed"],
                           "consistent": result["consistent"], "inputs": result["inputs"], "formula": result.get("formula") or "existing tool",
                           "library": result.get("library") or "existing tool", "locator": f"results.json#{result['id']}",
                           "note": json.dumps({"input_chain": result["input_chain"], "note": result["note"]}, ensure_ascii=False)})
    if assertions:
        ingest({"paper_title": candidate["paper"]["title"], "assertions": assertions}, "quantitative-paper-audit", "quantitative-audit-1.0", "computed_evidence", lineage_ref=ref, subject_refs=[object_id])
    snapshot = state.to_dict()
    reloaded = kernel.IngestionKernelState.from_dict(json.loads(json.dumps(snapshot)), ceg_cls=kernel.ceg_mod.ClaimEvidenceGraph, ledger_cls=kernel.ledger_mod.DecisionLedger, verification_context=context)
    if reloaded.compute_digests() != state.compute_digests():
        raise ValueError("Kernel round-trip changed content digests")
    _write(run / "lineage.json", lineage)
    _write(run / "kernel-state.json", snapshot)
    _write(run / "ingestion-receipts.json", receipts)
    return {"kernel_digest": state.compute_digests()["kernel_content_digest"], "lineage_receipt_id": lineage["receipt_id"],
            "object_count": len(state.objects), "claim_count": len(state.ceg.claims), "ledger_decisions": len(state.ledger.to_dict()["decisions"]), "round_trip": "passed"}


def finish(project: str | Path, candidate_path: str | Path) -> dict:
    """Complete all deterministic stages after a source-grounded Agent reading."""
    project = Path(project).resolve()
    candidate = _json(Path(candidate_path))
    from .sources import verify
    documents = verify(project)
    validation = validate_candidate(project, candidate, documents=documents)
    kernel = _kernel()
    from ..ingestion import paper_research
    runtime = {"pipeline": PIPELINE_VERSION, "analysis_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "recompute_sha256": hashlib.sha256(Path(kernel.recompute.__file__).read_bytes()).hexdigest(),
               "mcp_sha256": hashlib.sha256(Path(kernel.__file__).read_bytes()).hexdigest(),
               "adapter_sha256": hashlib.sha256(Path(paper_research.__file__).read_bytes()).hexdigest(),
               "libraries": {name: metadata.version(name) for name in ("numpy", "scipy", "statsmodels")}}
    digest = _digest({"runtime": runtime, "documents": documents, "candidate": candidate})
    run = project / "runs" / digest[:24]
    completion = run / "completion.json"
    if completion.is_file():
        previous = _json(completion)
        expected = previous.get("artifact_hashes", {})
        if expected and all((run / name).is_file() and hashlib.sha256((run / name).read_bytes()).hexdigest() == sha for name, sha in expected.items()):
            replay = {**previous, "run_directory": str(run), "report_markdown": str(run / "report.md"),
                      "report_html": str(run / "report.html"), "extraction": str(run / "extraction.json"),
                      "results": str(run / "results.json"), "reused": True}
            _write(project / "latest.json", replay)
            return replay
    run.mkdir(parents=True, exist_ok=True)
    _write(project / "candidate.json", candidate)
    _write(run / "extraction.json", candidate)
    _write(run / "documents-snapshot.json", documents)
    _write(run / "validation.json", validation)
    results = compute_checks(candidate, documents)
    _write(run / "results.json", results)
    _write(run / "stage.json", {"stage": "computed", "analysis_fingerprint": digest})
    ingested = _ingest(project, run, candidate, documents, results)
    report = _report(candidate, documents, validation, results, digest)
    _write(run / "report.md", report)
    _write(run / "report.html", _html(report, candidate["paper"]["title"]))
    names = ["extraction.json", "documents-snapshot.json", "validation.json", "results.json", "lineage.json", "kernel-state.json", "ingestion-receipts.json", "report.md", "report.html"]
    receipt = {"status": "complete", "analysis_fingerprint": digest, "runtime": runtime, "project_fingerprint": documents["fingerprint"],
               "run_directory": str(run), "report_markdown": str(run / "report.md"), "report_html": str(run / "report.html"),
               "extraction": str(run / "extraction.json"), "results": str(run / "results.json"),
               "computed_checks": sum(r["status"] == "computed" for r in results),
               "compared_checks": sum(r["status"] == "computed" and isinstance(r["consistent"], bool) for r in results),
               "discrepancies": sum(r["consistent"] is False for r in results), "validation": validation,
               "ingestion": ingested, "reused": False,
               "artifact_hashes": {name: hashlib.sha256((run / name).read_bytes()).hexdigest() for name in names}}
    _write(completion, receipt)
    _write(project / "latest.json", receipt)
    _write(run / "stage.json", {"stage": "complete", "analysis_fingerprint": digest})
    return receipt


def compare(left: str | Path, right: str | Path, analysis_path: str | Path | None = None, output: str | Path | None = None) -> dict:
    """Validate the Agent's explicit alignment and render a two-paper report."""
    if analysis_path is None:
        raise ValueError("Comparison needs a semantic producer: read both completed projects with the paper-research skill and supply --analysis")
    roots = [Path(left).resolve(), Path(right).resolve()]
    latest = [_json(root / "latest.json") for root in roots]
    runs = [Path(receipt["run_directory"]) for receipt in latest]
    if any(not run.resolve().is_relative_to(root) for run, root in zip(runs, roots)):
        raise ValueError("Saved comparison run escapes its project; replay the relocated project first")
    candidates = [_json(run / "extraction.json") for run in runs]
    documents = []
    from .sources import verify
    for root, candidate in zip(roots, candidates):
        docs = verify(root)
        validate_candidate(root, candidate, documents=docs)
        documents.append(docs)
    analysis = _json(Path(analysis_path))
    errors = _kernel().validate_schema(analysis, "paper-comparison.schema.json")
    if errors:
        raise ValueError("Comparison schema: " + "; ".join(errors))
    if [analysis["left_project_fingerprint"], analysis["right_project_fingerprint"]] != [d["fingerprint"] for d in documents]:
        raise ValueError("Comparison is stale: material fingerprint changed")
    fieldmaps = [{f["id"]: f for f in c["fields"]} for c in candidates]
    for row in analysis["rows"] + [analysis["conclusion"]]:
        for side, mapping in zip(("left", "right"), fieldmaps):
            if set(row[side + "_field_ids"]) - set(mapping):
                raise ValueError("Comparison refers to an unknown " + side + " field")
        if row.get("assessment") == "direct":
            selected = [[mapping[i] for i in row[side + "_field_ids"]] for side, mapping in zip(("left", "right"), fieldmaps)]
            numeric = [[f for f in group if f["status"] == "extracted" and f["type"] in {"number", "integer", "p_value"}] for group in selected]
            for selected_side, other_side in ((numeric[0], numeric[1]), (numeric[1], numeric[0])):
                for field in selected_side:
                    same_name = [other for other in other_side if other["name"] == field["name"]]
                    if not same_name:
                        raise ValueError("Direct numeric comparison requires the same named metric on both sides")
                    if not any(field["unit"] == other["unit"] and field["context"] == other["context"] for other in same_name):
                        raise ValueError("Direct numeric comparison requires identical named metrics, units and evaluation contexts; use conditional/not_comparable")
    destination = Path(output).resolve() if output else roots[0] / "comparisons" / _digest(analysis)[:24]
    destination.mkdir(parents=True, exist_ok=True)
    assessments = {"direct": "可直接比较", "conditional": "有条件比较", "not_comparable": "不可直接比较", "not_applicable": "不适用"}
    def descriptions(side: str, ids: list[str]) -> str:
        index = 0 if side == "left" else 1
        return "；".join(f"{fieldmaps[index][i]['name']}：{fieldmaps[index][i]['literal'] or fieldmaps[index][i]['reason']}" for i in ids)
    lines = ["# 双论文比较报告", "", f"A：{candidates[0]['paper']['title']}（{candidates[0]['paper']['identifier']}）", "",
             f"B：{candidates[1]['paper']['title']}（{candidates[1]['paper']['identifier']}）", "",
             "**比较判断（Agent基于以下字段与原文）：** " + analysis["conclusion"]["text"], "",
             "| 维度 | A：原始报告 | B：原始报告 | 可比性及理由 |", "|---|---|---|---|"]
    for row in analysis["rows"]:
        lines.append(f"| {_cell(row['dimension'])} | {_cell(descriptions('left', row['left_field_ids']))} | {_cell(descriptions('right', row['right_field_ids']))} | {assessments[row['assessment']]}：{_cell(row['reason'])} |")
    lines += ["", "## 判断来源", ""]
    for index, side in enumerate(("left", "right")):
        try:
            prefix = quote(os.path.relpath(roots[index], destination).replace("\\", "/"), safe="/") + "/"
        except ValueError:
            prefix = roots[index].as_uri() + "/"
        ids = sorted({i for row in analysis["rows"] + [analysis["conclusion"]] for i in row[side + "_field_ids"]})
        for field_id in ids:
            field = fieldmaps[index][field_id]
            for source in field["sources"]:
                doc = next(d for d in documents[index]["documents"] if d["document_id"] == source["document_id"])
                citation = _citation({"sources": [source]}, documents[index], prefix=prefix)
                lines += [f"**{'A' if index == 0 else 'B'} / {field_id}** · {citation} · SHA-256 `{doc['sha256']}`", "", f"> {_space(source['quote'])}", ""]
    lines += [f"语义生产者：{analysis['producer']['name']}；模型：{analysis['producer']['model'] or '未取得具体版本'}。", "",
              "计算复核引用两篇各自的 results.json；该比较不把不同分析集、时间点、预处理或评估协议下的同名数字自动合并。"]
    markdown = "\n".join(lines) + "\n"
    _write(destination / "comparison.json", analysis)
    _write(destination / "comparison.md", markdown)
    _write(destination / "comparison.html", _html(markdown, "双论文比较"))
    kernel = _kernel()
    state = kernel.IngestionKernelState(ceg=kernel.ceg_mod.ClaimEvidenceGraph(), ledger=kernel.ledger_mod.DecisionLedger())
    envelope = kernel.ArtifactEnvelope.create(payload=analysis, producer_skill="paper-research", producer_version="1.0.0", payload_schema="paper-comparison-1.0", artifact_kind="paper_comparison")
    receipt = kernel.IngestionEngine().ingest(envelope, state=state)
    if receipt.status != "accepted":
        raise ValueError("Comparison ingestion failed: " + str(receipt.failure_reason))
    _write(destination / "kernel-state.json", state.to_dict())
    _write(destination / "ingestion-receipt.json", receipt.to_dict())
    return {"status": "complete", "comparison_markdown": str(destination / "comparison.md"), "comparison_html": str(destination / "comparison.html"),
            "comparison_json": str(destination / "comparison.json"), "rows": len(analysis["rows"]), "receipt_id": receipt.receipt_id}

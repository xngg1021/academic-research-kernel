"""投稿前版式、双盲宏包、必含章节、统计离散度与论断收据绑定确定性检查器。

严格遵循确定性核验与非打分原则：
- 只输出带文件、行号或 PDF 页码定位的确定性命中清单（hits）与分类计数（summary_counts），绝不合成任何主观审稿分数或录用概率。
- 将会刊官方硬性规定（如双盲禁用终稿宏、必含 Limitations / Checklist 章节、正文页数上限）与方法论完整度提示（如实验数值表缺少误差棒/置信区间、摘要定量论断未绑定 CEG 收据）分层报告。
"""
from __future__ import annotations

import argparse
from bisect import bisect_right
from collections import Counter
import json
from pathlib import Path
import re
import sys
from typing import Any

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

MAX_INCLUDE_DEPTH = 5
MAX_TEX_FILES = 64
MAX_TOTAL_BYTES = 20 * 1024 * 1024

INPUT_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
EXTERNAL_DOC_RE = re.compile(r"\\(?:externaldocument|includeonly)\b")
PACKAGE_OR_CLASS_RE = re.compile(r"\\(?:usepackage|documentclass)\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}", re.S)
SECTION_RE = re.compile(
    r"\\(?:section|subsection|paragraph|chapter)\*?\s*\{([^}]+)\}|^#{1,3}\s+(.+)$",
    re.M,
)
ACKS_SECTION_BLOCK_RE = re.compile(
    r"(\\(?:section|subsection|subsubsection|paragraph)\*?\s*\{\s*(?:Acknowledgments?|Acknowledgements?)\s*\.?\s*\}|(?:\\noindent\s*)?\\textbf\{\s*(?:Acknowledgments?|Acknowledgements?)\s*\.?\s*\})(.*?)(?=\\(?:section|subsection|subsubsection|paragraph|chapter)\*?\{|\\bibliography|\\appendix|\\end\{document\}|$)",
    re.S | re.I,
)
ANON_ACKS_FULLMATCH_RE = re.compile(
    r"\s*(?:(?:Acknowledgments?|Acknowledgements?|Funding(?:\s+details)?|Grant\s+information)\s+"
    r"(?:are\s+|is\s+)?(?:omitted|anonymi[sz]ed|redacted|withheld|hidden|left\s+blank)"
    r"(?:\s+(?:for|during)\s+(?:anonymous|double-blind|blind)\s+review)?\s*[.!]?\s*)+\s*",
    re.I,
)
GRANT_DISCLOSURE_RE = re.compile(
    r"(?:\b(?:grant|award|contract|project|fund(?:ed|ing))\s*(?:no\.?|number|id|#|:)?\s*(?=[A-Za-z0-9/_-]*\d)[A-Za-z0-9][A-Za-z0-9/_-]{2,}|\bsupported\s+by\b[^.\n]{0,120}\b(?:NIH|NSF|DARPA|DOE|ONR|AFOSR|ERC|EPSRC|NSFC|BMBF|JSPS|National\s+Science\s+Foundation|National\s+Institutes\s+of\s+Health)\b)",
    re.I,
)
CHECKLIST_ENV_RE = re.compile(r"\\begin\{(?:checklist|neuripschecklist)\}", re.I)
UNRESOLVED_REF_RE = re.compile(
    r"(?:\\cite[a-zA-Z*]*\s*\{[^}]*\?[^}]*\}|\\(?:ref|eqref|autoref|Cref|cref)\*?\s*\{\s*(?:\?+)?\s*\}|\b(?:Section|Sec\.|Table|Tab\.|Figure|Fig\.|Eq\.|Equation|Theorem|Appendix|Algorithm|Alg\.)\s+\?\?(?!\w))",
)
PDF_UNRESOLVED_REF_RE = re.compile(
    r"(?:\b(?:Section|Sec\.|Table|Tab\.|Figure|Fig\.|Eq\.|Equation|Theorem|Appendix|Algorithm|Alg\.)\s+\?\?(?!\w)|\[\s*\?\s*\])",
)
LABEL_DEF_RE = re.compile(r"\\label\s*\{([^}]+)\}")
ENV_OPT_HEAD_RE = re.compile(r"\\begin\{(?:lstlisting|minted|tcolorbox)\}\s*\[")
REF_CALL_RE = re.compile(r"\\(?:ref|eqref|autoref|Cref|cref|pageref)\*?\s*\{([^}]+)\}")
BARE_CITE_CALL_RE = re.compile(r"\\cite\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}")
NATBIB_CITE_CALL_RE = re.compile(r"\\cite(?:p|t|alt|alp|author|year|num)\*?\s*(?:\[[^\]]*\])*\s*\{([^}]+)\}")
AUTHOR_ET_AL_BARE_CITE_RE = re.compile(
    r"\b([A-Z][A-Za-z'-]{1,30}\s+et\s+al\.)\s*(?:~|\s+)\s*(\\(?:cite|citet)\*?\s*\{[^}]+\})"
)
AUTHOR_YEAR_STYLE_PKG_RE = re.compile(
    r"(?:^|,|\s)(?:iclr20\d{2}_conference|acl|emnlp|naacl|coling|arr|icml20\d{2}|natbib)\b",
    re.I,
)
CITE_RELEVANT_PKG_RE = re.compile(
    r"(?:^|,|\s)(?:natbib|biblatex|cite|neurips\w*|iclr\w*|icml\w*|acl\w*|emnlp\w*|naacl\w*|coling\w*|arr\w*)\b",
    re.I,
)
TODO_MARKER_RE = re.compile(r"\b(?:TODO|FIXME|TBD|XXX)\b|\\(?:todo|TODO)\b(?![A-Za-z@])")
MACRO_DEF_HEAD_RE = re.compile(
    r"\\(?:(?:newcommand|renewcommand|providecommand|DeclareRobustCommand)[^\S\n]{0,40}\*?[^\S\n]{0,40}(?:\{[^\S\n]{0,40}\\[A-Za-z@]+[^\S\n]{0,40}\}|\\[A-Za-z@]+)[^\S\n]{0,40}(?:\[\s*\d+\s*\])?[^\S\n]{0,40}(?:\[[^\n\]]{0,200}\])?[^\S\n]{0,40}|def[^\S\n]{0,40}\\[A-Za-z@]+[^\n\\{]{0,120})\{"
)
INLINE_VERB_RE = re.compile(r"\\verb\*?([^a-zA-Z0-9\s]).*?\1")
VERBATIM_ENV_RE = re.compile(
    r"\\begin\{(verbatim\*?|lstlisting|minted)\}(.*?)\\end\{\1\}|\\verb\*?([^a-zA-Z0-9\s]).*?\3",
    re.S,
)
TABLE_BLOCK_RE = re.compile(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", re.S)
NUMERIC_ROW_RE = re.compile(r"&[^\\]*\b\d+\.\d+\b")
DISPERSION_MARKER_RE = re.compile(
    r"(?:\\pm\b|±|\b(?:SD|SE|SEM|CI|IQR|std|stdev|variance|p\s*[<=>]|p-value|wilcoxon|mann-whitney|confidence\s+interval|seed|seeds)\b|\(\s*[+-]?\d+\.\d+\s*\))",
    re.I,
)
ABSTRACT_BLOCK_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
CONCLUSION_BLOCK_RE = re.compile(
    r"\\section\*?\{[^}]*(?:Conclusion|Conclusions|Discussion)[^}]*\}(.*?)(?=\\section\*?\{|\\bibliography|\\appendix|\\end\{document\}|$)",
    re.S | re.I,
)
CORE_QUANT_TOKEN_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\s*(?:%|\\%|\bpercent\b|(?:x\b|×)|\bfold\b|\btimes\s+(?:faster|higher|lower|smaller|better)\b)|\b(?:outperforms?|improves?|reduces?|accelerates?)\b[^.\n]{0,60}?\b\d+(?:\.\d+)?\s*(?:%|\\%|(?:x\b|×)))",
    re.I,
)
QUANT_CLAIM_RE = CORE_QUANT_TOKEN_RE
ABBREV_SUFFIX_RE = re.compile(
    r"\b(?:et\s+al|Fig|Figs|Eq|Eqs|Sec|Secs|Tab|Tabs|cf|e\.g|i\.e|vs|Dr|Prof|No|Vol|pp)\.$",
    re.I,
)
INLINE_CEG_TAG_RE = re.compile(r"%\s*(?:ark|ceg):(?:claim|receipt)=([A-Za-z0-9_.:-]+)")
REFERENCES_HEADING_RE = re.compile(r"^[ \t]*(?:References|Bibliography|参考文献)[ \t]*$", re.M | re.I)
APPENDIX_HEADING_RE = re.compile(
    r"^[ \t]*(?:(?:Appendix|Appendices|Supplementary[ \t]+Materials?|附录)|Appendix[ \t]+[A-Z](?:[ \t]*[:.-][ \t]+[A-Z][A-Za-z0-9 \t,:;-]{1,70})?)[ \t]*$",
    re.M | re.I,
)
CONCLUSION_HEADING_LINE_RE = re.compile(
    r"^[ \t]*(?:\d+(?:\.\d+)*\.?[ \t]*)?(?:Conclusions?|Discussion|Summary[ \t]+and[ \t]+Conclusions?)[ \t]*\.?[ \t]*$",
    re.I,
)
NUMBERED_MAIN_HEADING_LINE_RE = re.compile(r"^[ \t]*\d+(?:\.\d+)*\.?[ \t]+[A-Z][A-Za-z0-9 \t,:;-]{2,80}$")
EXEMPT_STATEMENT_HEADING_RE = re.compile(
    r"^[ \t]*(?:\d+(?:\.\d+)*\.?[ \t]*)?(?:"
    r"Reproducibility[ \t]*Statements?|"
    r"Ethics[ \t]*Statements?|"
    r"Ethical[ \t]*Considerations?|"
    r"Broader[ \t]*Impacts?(?:[ \t]*Statements?)?|"
    r"Impact[ \t]*Statements?|"
    r"(?:The[ \t]*)?Use[ \t]*of[ \t]*Large[ \t]*Language[ \t]*Models?|"
    r"LLM[ \t]*(?:Usage|Disclosure)(?:[ \t]*Statements?)?|"
    r"Acknowledgments?|"
    r"Acknowledgements?"
    r")[ \t]*\.?[ \t]*$",
    re.M | re.I,
)
RUNNING_HEADER_LINE_RE = re.compile(
    r"^\s*(?:Under\s+review(?:\s+as\s+a\s+conference\s+paper.*)?|Published\s+as\s+a\s+conference\s+paper.*|Accepted\s+as\s+a\s+conference\s+paper.*|Anonymous\s+Authors?.*|Preprint\.(?:\s+Under\s+review\.?)?|Submitted\s+to\s+.*)$",
    re.I,
)
CAMERA_READY_HEADER_RE = re.compile(r"^\s*(?:Published|Accepted)\s+as\s+a\s+conference\s+paper\b", re.M | re.I)
FORBIDDEN_DOUBLE_BLIND_OPTION_TOKENS = {"final", "accepted", "preprint", "cameraready", "camera-ready", "nonblind"}

MATH_OR_QUOTE_OR_BIB_MASK_RE = re.compile(
    r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?|flalign\*?|math|displaymath|quote|quotation|thebibliography)\}.*?\\end\{(?:equation\*?|align\*?|gather\*?|multline\*?|flalign\*?|math|displaymath|quote|quotation|thebibliography)\}"
    r"|\$\$.*?\$\$"
    r"|\\\[.*?\\\]"
    r"|\\\(.*?\\\)"
    r"|(?<!\\)\$[^\n$]+?(?<!\\)\$"
    r"|\\(?:cite[a-zA-Z*]*|ref|eqref|autoref|Cref|cref|pageref|label|url)\*?\s*(?:\[[^\]]*\])*\s*\{[^}]*\}",
    re.S,
)
ACADEMIC_CLICHE_EN_RE = re.compile(
    r"\b(?:"
    r"delve(?:s|d|ing)?\s+into|"
    r"pivotal\s+role|"
    r"testament\s+to|"
    r"rich\s+tapestry|tapestry\s+of|"
    r"shed(?:s|ding)?\s+light\s+on|"
    r"in\s+the\s+realm\s+of|"
    r"paradigm\s+shift|"
    r"embark(?:s|ed|ing)?\s+on\s+a\s+journey|"
    r"a\s+myriad\s+of|"
    r"underscore(?:s|d|ing)?\s+the\s+(?:importance|significance|necessity)|"
    r"with\s+the\s+rapid\s+(?:development|advancement|proliferation|evolution)\s+of"
    r")\b",
    re.I,
)
ACADEMIC_CLICHE_ZH_RE = re.compile(
    r"(?:随着[^\n，。；]{1,25}的(?:飞速发展|蓬勃发展|日益普及|不断演进)|不仅[^\n，。；]{1,35}更为[^\n，。；]{1,35}提供了|赋能|抓手|形成闭环|底层逻辑|范式跃迁|注入新动能)"
)
STRONG_CLAIM_CANDIDATE_RE = re.compile(
    r"(?:\b(?:"
    r"we\s+prove|proves?\s+that|formally\s+guarantee(?:s|d)?|theoretically\s+guarantee(?:s|d)?|"
    r"statistically\s+significant(?:ly)?|"
    r"globally\s+optimal|universally\s+superior|unconditionally\s+outperforms?|always\s+outperforms?"
    r")\b|统计显著)",
    re.I,
)
NEGATION_WINDOW_RE = re.compile(
    r"(?:\b(?:not|no|never|neither|cannot|can\s+not|could\s+not|did\s+not|do\s+not|does\s+not|fail(?:s|ed)?\s+to|without|hard\s+to|difficult\s+to|impossible\s+to|open\s+problem|future\s+work|remains?\s+to\s+be)\b|并未|未能|无法|不能|难以|尚不|尚未|不一定|并非)",
    re.I,
)
CLAUSE_BREAK_RE = re.compile(r"(?:[,;，；:]|\b(?:but|however|yet|whereas|while|although)\b)", re.I)
THEOREM_ENV_BLOCK_RE = re.compile(
    r"\\begin\{(theorem|lemma|proposition|corollary)\*?\}(.*?)\\end\{\1\*?\}",
    re.S | re.I,
)
VAGUE_METHOD_PASSIVE_RE = re.compile(
    r"(?:\b(?:"
    r"hyperparameters?\s+(?:were|are|was)\s+(?:tuned|selected|chosen|set)\s+(?:appropriately|properly|carefully|empirically|suitably)|"
    r"data(?:sets?)?\s+(?:were|are|was)\s+(?:preprocessed|filtered|cleaned)\s+(?:appropriately|properly|carefully|suitably)"
    r")\b|超参数经过(?:适当|合理|精心)调优|数据经过(?:适当|合理|妥善)预处理)",
    re.I,
)
CONCRETE_METHOD_ANCHOR_RE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\b|\\(?:ref|eqref|autoref|Cref|cref)\b|\b(?:Table|Tab\.|Section|Sec\.|Appendix|Algorithm|Alg\.)\b)",
    re.I,
)


def _mask_math_quotes_and_bib_preserving_lines(masked_body: str) -> str:
    """Mask math, direct quote environments, bibliography, and cite/ref/url commands into spaces while preserving line numbers."""
    chars = list(masked_body)
    for m in MATH_OR_QUOTE_OR_BIB_MASK_RE.finditer(masked_body):
        for idx in range(m.start(), m.end()):
            if chars[idx] != "\n":
                chars[idx] = " "
    return "".join(chars)


def _extract_Strong_claim_sentences(prose_block: str, full_block: str) -> list[tuple[int, int, int, str, str]]:
    """Return (sent_start, match_start, sent_end, sentence_text, matched_token) scanning prose_block and slicing full_block."""
    n = len(prose_block)
    spans: list[tuple[int, int, int, str, str]] = []
    sent_punct = "!?;\u3002\uff01\uff1f\uff1b"
    for m in STRONG_CLAIM_CANDIDATE_RE.finditer(prose_block):
        s_idx = m.start()
        while s_idx > 0:
            ch = prose_block[s_idx - 1]
            if ch == "\n" and s_idx >= 2 and prose_block[s_idx - 2] == "\n":
                break
            if ch in sent_punct or (ch == "." and _is_sentence_boundary_dot(prose_block, s_idx - 1)):
                break
            s_idx -= 1
        e_idx = m.end()
        while e_idx < n:
            ch = prose_block[e_idx]
            if ch == "\n" and e_idx + 1 < n and prose_block[e_idx + 1] == "\n":
                break
            if ch in sent_punct or (ch == "." and _is_sentence_boundary_dot(prose_block, e_idx)):
                e_idx += 1
                break
            e_idx += 1
        # Check negation only within the current clause immediately preceding the match
        clause_prefix = prose_block[max(s_idx, m.start() - 60) : m.start()]
        clause_breaks = list(CLAUSE_BREAK_RE.finditer(clause_prefix))
        if clause_breaks:
            clause_prefix = clause_prefix[clause_breaks[-1].end() :]
        if NEGATION_WINDOW_RE.search(clause_prefix):
            continue
        sentence_raw = full_block[s_idx:e_idx]
        sentence = " ".join(sentence_raw.split()).strip()
        if len(sentence) >= 8:
            spans.append((s_idx, m.start(), e_idx, sentence, m.group(0)))
    return spans


def _scan_academic_style(
    rel_name: str,
    raw: str,
    uncommented: str,
    masked_body: str,
    defined_theorem_labels: set[str],
    verified_id_to_text: dict[str, str],
) -> tuple[list[dict[str, Any]], int]:
    """Run deterministic, non-scoring academic prose & claim-boundary checks returning (advisory_hits, macro_def_count)."""
    advisory_hits: list[dict[str, Any]] = []
    macro_def_count = sum(1 for _ in MACRO_DEF_HEAD_RE.finditer(uncommented))
    prose_only = _mask_math_quotes_and_bib_preserving_lines(masked_body)
    prose_lines = prose_only.splitlines()
    raw_lines = raw.splitlines()
    newline_offsets = [idx for idx, ch in enumerate(masked_body) if ch == "\n"]

    file_line_tags: dict[int, list[str]] = {}
    for l_idx, r_line in enumerate(raw_lines, 1):
        tids = INLINE_CEG_TAG_RE.findall(r_line)
        if tids:
            file_line_tags[l_idx] = tids

    # 1. Academic AI cliché scan on prose_only (comments, math, verbatim, quotes, bib masked)
    for line_idx, p_line in enumerate(prose_lines, 1):
        for pat_re in (ACADEMIC_CLICHE_EN_RE, ACADEMIC_CLICHE_ZH_RE):
            for m_cl in pat_re.finditer(p_line):
                advisory_hits.append({
                    "code": "ACADEMIC_AI_CLICHE_CANDIDATE",
                    "severity": "advisory",
                    "locator": f"{rel_name}:L{line_idx}",
                    "message": f"High-frequency template phrase {m_cl.group(0)!r} detected in prose; replace with concrete mechanism, boundary, or measurement.",
                    "excerpt": (raw_lines[line_idx - 1].strip() if line_idx - 1 < len(raw_lines) else p_line.strip())[:160],
                })

    # 2. Vague passive methodological description scan on prose_only
    sent_stops = ".!?\n\u3002\uff01\uff1f\uff1b"
    for m_vm in VAGUE_METHOD_PASSIVE_RE.finditer(prose_only):
        line_no = bisect_right(newline_offsets, m_vm.start()) + 1
        s_idx = m_vm.start()
        while s_idx > 0 and masked_body[s_idx - 1] not in sent_stops:
            s_idx -= 1
        e_idx = m_vm.end()
        while e_idx < len(masked_body) and masked_body[e_idx] not in sent_stops:
            e_idx += 1
        sent_with_refs = masked_body[s_idx:e_idx]
        if not CONCRETE_METHOD_ANCHOR_RE.search(sent_with_refs):
            advisory_hits.append({
                "code": "VAGUE_METHOD_DESCRIPTION_CANDIDATE",
                "severity": "advisory",
                "locator": f"{rel_name}:L{line_no}",
                "message": f"Vague methodological phrase {m_vm.group(0)!r} lacks concrete parameter values or Section/Table/Appendix reference in the same sentence.",
                "excerpt": " ".join(sent_with_refs.split())[:160],
            })

    # 3. Strong claim hedging calibration in Abstract & Conclusion blocks
    for block_kind, block_re in (("abstract", ABSTRACT_BLOCK_RE), ("conclusion", CONCLUSION_BLOCK_RE)):
        for m_blk in block_re.finditer(masked_body):
            blk_full = m_blk.group(1)
            blk_prose = prose_only[m_blk.start(1) : m_blk.end(1)]
            blk_start_line = masked_body[: m_blk.start(1)].count("\n") + 1
            blk_nl_offsets = [idx for idx, ch in enumerate(blk_full) if ch == "\n"]
            for s_idx, m_start, sent_end, claim_sent, tok in _extract_Strong_claim_sentences(blk_prose, blk_full):
                line_offset = bisect_right(blk_nl_offsets, m_start)
                sent_start_line = bisect_right(blk_nl_offsets, s_idx)
                sent_end_line = bisect_right(blk_nl_offsets, max(s_idx, sent_end - 1))
                loc_line = blk_start_line + line_offset
                abs_start_line = blk_start_line + sent_start_line
                abs_end_line = blk_start_line + sent_end_line

                norm_sent = _normalize_claim_text(claim_sent)
                has_verified_ceg = False
                for check_l in range(max(1, abs_start_line - 1), abs_end_line + 1):
                    for tid in file_line_tags.get(check_l, ()):
                        if tid not in verified_id_to_text:
                            continue
                        c_txt = _normalize_claim_text(verified_id_to_text[tid])
                        if c_txt and c_txt == norm_sent:
                            has_verified_ceg = True
                            break
                    if has_verified_ceg:
                        break
                if has_verified_ceg:
                    continue

                tok_low = tok.lower()
                if "significant" in tok_low or "显著" in tok_low:
                    if DISPERSION_MARKER_RE.search(claim_sent):
                        continue
                    advisory_hits.append({
                        "code": "UNANCHORED_STRONG_CLAIM_CANDIDATE",
                        "severity": "advisory",
                        "locator": f"{rel_name}:L{loc_line}",
                        "message": f"Statistical significance claim {tok!r} in {block_kind} has no same-sentence statistical test/p-value/CI marker or verified % ark:claim=<id> anchor.",
                        "excerpt": claim_sent[:180],
                    })
                else:
                    has_resolvable_thm = False
                    for m_ref in REF_CALL_RE.finditer(claim_sent):
                        for k in m_ref.group(1).split(","):
                            if k.strip() in defined_theorem_labels:
                                has_resolvable_thm = True
                                break
                    if has_resolvable_thm:
                        continue
                    advisory_hits.append({
                        "code": "UNANCHORED_STRONG_CLAIM_CANDIDATE",
                        "severity": "advisory",
                        "locator": f"{rel_name}:L{loc_line}",
                        "message": f"Strong formal/optimality claim {tok!r} in {block_kind} has no resolvable Theorem/Lemma/Proposition \\label reference or verified % ark:claim=<id> anchor.",
                        "excerpt": claim_sent[:180],
                    })

    return advisory_hits, macro_def_count


def _default_specs_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / "references" / "venue-specs.json",
        here.parent / "venue-specs.json",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError("venue-specs.json not found near pre_submission_linter.py")


def load_venue_specs(specs_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(specs_path) if specs_path else _default_specs_path()
    return json.loads(path.read_text(encoding="utf-8"))


_BEGIN_VERB_ENV_RE = re.compile(r"\\begin\{(verbatim\*?|lstlisting|minted)\}")


def _strip_latex_comments(text: str) -> str:
    """Strip unescaped % comments in a single top-to-bottom pass so commented-out \\begin{verbatim} never enters verbatim mode."""
    out_lines: list[str] = []
    active_env: str | None = None
    for line in text.splitlines():
        pos = 0
        n = len(line)
        kept: list[str] = []
        while pos < n:
            if active_env is not None:
                end_tok = f"\\end{{{active_env}}}"
                end_idx = line.find(end_tok, pos)
                if end_idx == -1:
                    kept.append(line[pos:])
                    pos = n
                    break
                after_end = end_idx + len(end_tok)
                kept.append(line[pos:after_end])
                pos = after_end
                active_env = None
                continue
            ch = line[pos]
            if ch == "%":
                break
            if ch == "\\":
                m_v = INLINE_VERB_RE.match(line, pos)
                if m_v:
                    kept.append(m_v.group(0))
                    pos = m_v.end()
                    continue
                m_b = _BEGIN_VERB_ENV_RE.match(line, pos)
                if m_b:
                    active_env = m_b.group(1)
                    kept.append(m_b.group(0))
                    pos = m_b.end()
                    continue
                if pos + 1 < n:
                    kept.append(line[pos : pos + 2])
                    pos += 2
                    continue
            kept.append(ch)
            pos += 1
        out_lines.append("".join(kept))
    return "\n".join(out_lines)


def _mask_balanced_braces(chars: list[str], open_brace_idx: int) -> int:
    """Replace characters inside balanced {...} starting at open_brace_idx with spaces, preserving newlines."""
    depth = 0
    i = open_brace_idx
    n = len(chars)
    while i < n:
        ch = chars[i]
        if ch == "\\":
            if i + 1 < n:
                if depth > 0 and chars[i] != "\n":
                    chars[i] = " "
                if depth > 0 and chars[i + 1] != "\n":
                    chars[i + 1] = " "
                i += 2
                continue
        if ch == "{":
            depth += 1
            if chars[i] != "\n":
                chars[i] = " "
        elif ch == "}":
            if chars[i] != "\n":
                chars[i] = " "
            depth -= 1
            if depth == 0:
                return i + 1
        else:
            if depth > 0 and ch != "\n":
                chars[i] = " "
        i += 1
    return n


def _skip_optional_bracket_block(text: str, pos: int) -> int:
    """If text[pos:] starts with optional whitespace and '[', return index after matching top-level ']'."""
    n = len(text)
    i = pos
    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] != "[":
        return pos
    i += 1
    brace_depth = 0
    while i < n:
        ch = text[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth = max(0, brace_depth - 1)
        elif ch == "]" and brace_depth == 0:
            return i + 1
        i += 1
    return pos


def _mask_macro_definitions_and_verbatim(uncommented: str) -> str:
    """Mask verbatim bodies (preserving brace-balanced lstlisting options) and macro definition bodies."""
    chars = list(uncommented)
    for m_verb in VERBATIM_ENV_RE.finditer(uncommented):
        if m_verb.group(2) is not None:
            s_span = _skip_optional_bracket_block(uncommented, m_verb.start(2))
            e_span = m_verb.end(2)
        else:
            s_span, e_span = m_verb.start(), m_verb.end()
        for idx in range(s_span, e_span):
            if chars[idx] != "\n":
                chars[idx] = " "
    masked_verb = "".join(chars)
    pos = 0
    while True:
        m = MACRO_DEF_HEAD_RE.search(masked_verb, pos)
        if not m:
            break
        open_idx = m.end() - 1
        for idx in range(m.start(), open_idx):
            if chars[idx] != "\n":
                chars[idx] = " "
        pos = _mask_balanced_braces(chars, open_idx)
    return "".join(chars)


def _extract_top_level_env_option_labels(text: str) -> list[str]:
    """Extract top-level label=... values from \\begin{lstlisting|minted|tcolorbox}[...] option blocks."""
    labels: list[str] = []
    n = len(text)
    for m in ENV_OPT_HEAD_RE.finditer(text):
        i = m.end()
        brace_depth = 0
        entries: list[str] = []
        cur: list[str] = []
        while i < n:
            ch = text[i]
            if ch == "\\" and i + 1 < n:
                cur.append(text[i : i + 2])
                i += 2
                continue
            if ch == "{":
                brace_depth += 1
                cur.append(ch)
            elif ch == "}":
                brace_depth = max(0, brace_depth - 1)
                cur.append(ch)
            elif ch == "]" and brace_depth == 0:
                entries.append("".join(cur))
                break
            elif ch == "," and brace_depth == 0:
                entries.append("".join(cur))
                cur = []
            else:
                cur.append(ch)
            i += 1
        for entry in entries:
            if "=" not in entry:
                continue
            k, v = entry.split("=", 1)
            if k.strip() != "label":
                continue
            val = v.strip()
            if val.startswith("{") and val.endswith("}"):
                val = val[1:-1].strip()
            if val and "#" not in val and "{" not in val and "}" not in val:
                labels.append(val)
    return labels


def _is_sentence_boundary_dot(text: str, dot_idx: int) -> bool:
    """Return True if text[dot_idx] == '.' is a true sentence boundary rather than a decimal or abbreviation."""
    n = len(text)
    if dot_idx > 0 and dot_idx + 1 < n and text[dot_idx - 1].isdigit() and text[dot_idx + 1].isdigit():
        return False
    prefix_window = text[max(0, dot_idx - 16) : dot_idx + 1]
    if ABBREV_SUFFIX_RE.search(prefix_window):
        return False
    return True


def _extract_quant_claim_spans(blk_uncommented: str) -> list[tuple[int, int, str]]:
    """Extract (start_offset, end_offset, sentence_text) for quantitative claims in strict O(L) without backtracking."""
    n = len(blk_uncommented)
    last_sent_end = -1
    spans: list[tuple[int, int, str]] = []
    for m in CORE_QUANT_TOKEN_RE.finditer(blk_uncommented):
        if m.start() < last_sent_end:
            continue
        s_idx = m.start()
        while s_idx > 0:
            ch = blk_uncommented[s_idx - 1]
            if ch == "\n" and s_idx >= 2 and blk_uncommented[s_idx - 2] == "\n":
                break
            if ch in "!?;" or (ch == "." and _is_sentence_boundary_dot(blk_uncommented, s_idx - 1)):
                break
            s_idx -= 1
        e_idx = m.end()
        while e_idx < n:
            ch = blk_uncommented[e_idx]
            if ch == "\n" and e_idx + 1 < n and blk_uncommented[e_idx + 1] == "\n":
                break
            if ch in "!?;" or (ch == "." and _is_sentence_boundary_dot(blk_uncommented, e_idx)):
                e_idx += 1
                break
            e_idx += 1
        last_sent_end = e_idx
        sentence = " ".join(blk_uncommented[s_idx:e_idx].split()).strip()
        if len(sentence) >= 10:
            spans.append((m.start(), e_idx, sentence))
    return spans


def collect_tex_tree(entry_tex: Path) -> tuple[list[tuple[Path, str]], list[dict[str, Any]]]:
    r"""Collect entry .tex and bounded relative \input / \include files without escaping manuscript root."""
    entry_tex = entry_tex.resolve()
    if not entry_tex.is_file():
        raise ValueError(f"TeX entry file does not exist: {entry_tex}")
    root_dir = entry_tex.parent
    visited: set[Path] = set()
    collected: list[tuple[Path, str]] = []
    include_hits: list[dict[str, Any]] = []
    total_bytes = 0

    def _resolve_include_candidate(current_file: Path, target: str) -> Path:
        for base_dir in (root_dir, current_file.parent):
            cand = base_dir / target
            if not cand.suffix:
                cand_tex = cand.with_suffix(".tex")
                if cand_tex.exists() or not cand.exists():
                    cand = cand_tex
            resolved = cand.resolve()
            if not resolved.is_relative_to(root_dir):
                raise ValueError(f"TeX include escapes manuscript root: {target}")
            if resolved.is_file():
                return resolved
        fallback = root_dir / target
        if not fallback.suffix:
            fallback = fallback.with_suffix(".tex")
        resolved_fb = fallback.resolve()
        if not resolved_fb.is_relative_to(root_dir):
            raise ValueError(f"TeX include escapes manuscript root: {target}")
        return resolved_fb

    def _walk(current: Path, depth: int, caller_locator: str | None = None) -> None:
        nonlocal total_bytes
        if depth > MAX_INCLUDE_DEPTH:
            include_hits.append({
                "code": "TEX_BUNDLE_TRUNCATED",
                "severity": "blocker",
                "locator": caller_locator or current.name,
                "message": f"TeX include depth exceeded maximum limit ({MAX_INCLUDE_DEPTH}); bundle coverage is incomplete.",
                "excerpt": str(current.name),
            })
            return
        if len(collected) >= MAX_TEX_FILES:
            include_hits.append({
                "code": "TEX_BUNDLE_TRUNCATED",
                "severity": "blocker",
                "locator": caller_locator or current.name,
                "message": f"TeX file count exceeded maximum limit ({MAX_TEX_FILES}); bundle coverage is incomplete.",
                "excerpt": str(current.name),
            })
            return
        resolved = current.resolve()
        if resolved in visited:
            return
        if not resolved.is_relative_to(root_dir):
            raise ValueError(f"TeX include escapes manuscript root: {current}")
        if not resolved.is_file():
            include_hits.append({
                "code": "UNRESOLVED_TEX_INCLUDE",
                "severity": "blocker",
                "locator": caller_locator or resolved.name,
                "message": f"Included TeX file not found: {resolved.relative_to(root_dir).as_posix()!r}.",
                "excerpt": str(resolved.name),
            })
            return
        size = resolved.stat().st_size
        if total_bytes + size > MAX_TOTAL_BYTES:
            raise ValueError(f"TeX bundle exceeds maximum byte budget ({MAX_TOTAL_BYTES} bytes)")
        visited.add(resolved)
        total_bytes += size
        raw = resolved.read_text(encoding="utf-8", errors="replace")
        collected.append((resolved, raw))
        uncommented = _strip_latex_comments(raw)
        masked_for_include = _mask_macro_definitions_and_verbatim(uncommented)
        rel_self = resolved.relative_to(root_dir).as_posix()
        for m in INPUT_RE.finditer(masked_for_include):
            target = m.group(1).strip()
            if not target:
                continue
            line_no = uncommented[: m.start()].count("\n") + 1
            cand = _resolve_include_candidate(resolved, target)
            _walk(cand, depth + 1, caller_locator=f"{rel_self}:L{line_no}")

    _walk(entry_tex, 0)
    return collected, include_hits


def _extract_pdf_page_texts(pdf_path: Path) -> tuple[list[str] | None, str | None]:
    """Extract per-page text using fitz (PyMuPDF) or pypdf (bundled with [research] extra)."""
    try:
        import fitz  # type: ignore
        doc = fitz.open(str(pdf_path))
        try:
            return [doc[idx].get_text("text") or "" for idx in range(len(doc))], "pymupdf"
        finally:
            doc.close()
    except ImportError:
        pass
    except Exception as exc:
        return None, f"invalid_pdf:{exc}"

    try:
        from pypdf import PdfReader  # type: ignore
        reader = PdfReader(str(pdf_path))
        return [(page.extract_text() or "") for page in reader.pages], "pypdf"
    except ImportError:
        return None, "missing_dependency"
    except Exception as exc:
        return None, f"invalid_pdf:{exc}"


def _page_has_substantive_main_body(
    text_slice: str,
    in_exempt_zone: bool = False,
) -> tuple[bool, bool]:
    """Return (has_main_body_lines, updated_in_exempt_zone) for a page or page prefix."""
    raw_lines = [ln.strip() for ln in text_slice.splitlines() if ln.strip()]
    if not raw_lines:
        return False, in_exempt_zone
    meaningful_lines: list[str] = []
    n_lines = len(raw_lines)
    for idx, s in enumerate(raw_lines):
        if re.fullmatch(r"\d+", s):
            continue
        if (idx < 3 or idx >= n_lines - 2) and RUNNING_HEADER_LINE_RE.match(s):
            continue
        if CONCLUSION_HEADING_LINE_RE.match(s):
            in_exempt_zone = False
            meaningful_lines.append(s)
            continue
        if EXEMPT_STATEMENT_HEADING_RE.match(s):
            is_numbered = bool(re.match(r"^\d+", s))
            is_llm_heading = bool(re.search(r"Language\s*Models?|LLM", s, re.I))
            if is_numbered and is_llm_heading:
                in_exempt_zone = False
            else:
                in_exempt_zone = True
                continue
        if in_exempt_zone and NUMBERED_MAIN_HEADING_LINE_RE.match(s) and not EXEMPT_STATEMENT_HEADING_RE.match(s):
            in_exempt_zone = False
        if not in_exempt_zone:
            meaningful_lines.append(s)
    return len(meaningful_lines) > 0, in_exempt_zone


def _has_main_body_before_heading(page_text: str, heading_match: re.Match, in_exempt_zone: bool = False) -> bool:
    """Return True if substantive main-body text appears on the same page prior to the heading."""
    prefix = page_text[: heading_match.start()].strip()
    if not prefix:
        return False
    has_body, _ = _page_has_substantive_main_body(prefix, in_exempt_zone=in_exempt_zone)
    return has_body


def _inspect_pdf_pages(
    pdf_path: Path,
    max_main_pages: int | None,
    references_unlimited: bool = True,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hits: list[dict[str, Any]] = []
    info: dict[str, Any] = {
        "pdf_inspected": False,
        "parser": None,
        "total_pages": None,
        "references_start_page": None,
        "appendix_start_page": None,
        "main_body_pages": None,
        "main_body_max_pages": max_main_pages,
        "references_unlimited": references_unlimited,
        "detected_camera_ready_header": False,
    }
    page_texts, status_or_parser = _extract_pdf_page_texts(pdf_path)
    if page_texts is None:
        if status_or_parser == "missing_dependency":
            info["note"] = "Neither pypdf nor pymupdf is installed; requested PDF check could not be executed."
            hits.append({
                "code": "PDF_INSPECTION_UNAVAILABLE",
                "severity": "blocker",
                "locator": pdf_path.name,
                "message": "PDF page-limit verification was requested via --pdf, but neither pypdf nor pymupdf is installed.",
                "excerpt": "Install academic-research-kernel[research] to enable PDF inspection.",
            })
        else:
            info["note"] = f"Failed to parse PDF file: {status_or_parser}"
            hits.append({
                "code": "INVALID_PDF_FILE",
                "severity": "blocker",
                "locator": pdf_path.name,
                "message": f"Supplied PDF file could not be parsed ({status_or_parser}).",
                "excerpt": pdf_path.name,
            })
        return info, hits

    total_pages = len(page_texts)
    ref_page = None
    ref_shared_with_body = False
    app_page = None
    app_shared_with_body = False
    detected_camera_ready = False
    in_exempt_zone = False
    last_substantive_body_page = 0

    for idx, page_text in enumerate(page_texts):
        page_num = idx + 1
        first_lines = "\n".join([ln.strip() for ln in page_text.splitlines() if ln.strip()][:3])
        if CAMERA_READY_HEADER_RE.search(first_lines):
            detected_camera_ready = True

        for m_pdf_ref in PDF_UNRESOLVED_REF_RE.finditer(page_text):
            hits.append({
                "code": "UNRESOLVED_LATEX_REFERENCE",
                "severity": "blocker",
                "locator": f"{pdf_path.name}:page={page_num}",
                "message": "Unresolved cross-reference or citation placeholder ('??' or '[?]') rendered in compiled PDF.",
                "excerpt": m_pdf_ref.group(0)[:160],
            })

        m_ref = REFERENCES_HEADING_RE.search(page_text)
        m_app = APPENDIX_HEADING_RE.search(page_text)

        if ref_page is None and m_ref:
            ref_page = page_num
            ref_shared_with_body, in_exempt_zone = _page_has_substantive_main_body(
                page_text[: m_ref.start()],
                in_exempt_zone=in_exempt_zone,
            )
            if ref_shared_with_body:
                last_substantive_body_page = page_num
        if app_page is None and m_app:
            app_page = page_num
            app_shared_with_body, _ = _page_has_substantive_main_body(
                page_text[: m_app.start()],
                in_exempt_zone=in_exempt_zone if ref_page is None else True,
            )
            if ref_page is None and app_shared_with_body:
                last_substantive_body_page = page_num

        if ref_page is None and app_page is None:
            has_body, in_exempt_zone = _page_has_substantive_main_body(
                page_text,
                in_exempt_zone=in_exempt_zone,
            )
            if has_body:
                last_substantive_body_page = page_num

    if not references_unlimited:
        if app_page is not None:
            main_pages = app_page if app_shared_with_body else max(1, app_page - 1)
        else:
            main_pages = total_pages
    else:
        cutoffs: list[int] = []
        if ref_page is not None:
            ref_cutoff = ref_page if ref_shared_with_body else max(1, ref_page - 1)
            if last_substantive_body_page > 0:
                ref_cutoff = min(ref_cutoff, last_substantive_body_page)
            cutoffs.append(ref_cutoff)
        if app_page is not None:
            app_cutoff = app_page if app_shared_with_body else max(1, app_page - 1)
            if ref_page is None and last_substantive_body_page > 0:
                app_cutoff = min(app_cutoff, last_substantive_body_page)
            cutoffs.append(app_cutoff)
        if cutoffs:
            main_pages = min(cutoffs)
        elif in_exempt_zone and last_substantive_body_page > 0:
            main_pages = last_substantive_body_page
        else:
            main_pages = total_pages

    info.update({
        "pdf_inspected": True,
        "parser": status_or_parser,
        "total_pages": total_pages,
        "references_start_page": ref_page,
        "appendix_start_page": app_page,
        "main_body_pages": main_pages,
        "detected_camera_ready_header": detected_camera_ready,
    })
    if max_main_pages is not None and main_pages > max_main_pages:
        hits.append({
            "code": "MAIN_BODY_PAGE_LIMIT_EXCEEDED",
            "severity": "blocker",
            "locator": f"{pdf_path.name}:page={main_pages}",
            "message": f"Estimated main body spans {main_pages} pages, exceeding venue limit of {max_main_pages} pages.",
            "excerpt": f"total_pages={total_pages}, references_start_page={ref_page}, appendix_start_page={app_page}",
        })
    return info, hits


def _normalize_claim_text(text: str) -> str:
    return " ".join(str(text or "").split()).rstrip(".").strip()


def _load_ceg_claim_map(ceg_path: Path | None) -> tuple[dict[str, str], set[str]]:
    """Return (verified_id_to_text, verified_texts) for claims with positive support and zero contradiction."""
    if ceg_path is None or not ceg_path.is_file():
        return {}, set()
    data = json.loads(ceg_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}, set()
    claims = data.get("claims") or data.get("ceg", {}).get("claims") or []
    edges = data.get("support_edges") or data.get("edges") or data.get("ceg", {}).get("support_edges") or []

    supported_ids: set[str] = set()
    contradicted_ids: set[str] = set()
    for e in edges:
        if not isinstance(e, dict):
            continue
        cid = str(e.get("claim_id") or e.get("target_claim_id") or e.get("target") or "")
        if not cid:
            continue
        status = str(
            e.get("support_status")
            if e.get("support_status") is not None
            else (e.get("status") or e.get("relation") or e.get("polarity") or "")
        ).strip().lower()
        if status in ("supported", "supports", "support", "verified_by"):
            supported_ids.add(cid)
        elif status in ("contradicted", "contradicts", "refuted", "refutes", "unverifiable", "out_of_scope"):
            contradicted_ids.add(cid)

    id_to_text: dict[str, str] = {}
    verified_texts: set[str] = set()
    for c in claims:
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or c.get("claim_id") or "")
        txt = str(c.get("text") or c.get("statement") or "").strip()
        c_status = str(c.get("support_status") or c.get("status") or "").strip().lower()
        if not cid or not txt or cid in contradicted_ids or c_status in ("contradicted", "unverifiable", "out_of_scope"):
            continue
        if cid in supported_ids:
            id_to_text[cid] = txt
            verified_texts.add(txt)
    return id_to_text, verified_texts


def _load_ceg_verified_claims(ceg_path: Path | None) -> set[str]:
    """Return set of verified claim IDs and statements that have positive support and zero contradiction."""
    id_to_text, verified_texts = _load_ceg_claim_map(ceg_path)
    return set(id_to_text.keys()) | verified_texts


def _check_package_options_for_double_blind(uncommented: str, rel_name: str) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for m in PACKAGE_OR_CLASS_RE.finditer(uncommented):
        opts_raw = m.group(1) or ""
        pkg_name = (m.group(2) or "").strip()
        if not opts_raw:
            continue
        line_no = uncommented[: m.start()].count("\n") + 1
        tokens = [t.strip().lower().replace(" ", "") for t in opts_raw.split(",") if t.strip()]
        for tok in tokens:
            if tok in FORBIDDEN_DOUBLE_BLIND_OPTION_TOKENS or tok == "anonymous=false" or tok == "review=false":
                hits.append({
                    "code": "FORBIDDEN_REVIEW_PATTERN",
                    "severity": "blocker",
                    "locator": f"{rel_name}:L{line_no}",
                    "message": f"De-anonymizing or camera-ready package option {tok!r} on {pkg_name!r} is forbidden in double-blind review.",
                    "excerpt": " ".join(m.group(0).split())[:160],
                })
    return hits


def lint_manuscript(
    tex_path: str | Path,
    venue: str = "iclr",
    contribution_type: str = "general_empirical",
    phase: str = "submission",
    pdf_path: str | Path | None = None,
    ceg_path: str | Path | None = None,
    require_ceg_binding: bool = False,
    check_academic_style: bool = False,
    specs_path: str | Path | None = None,
) -> dict[str, Any]:
    specs = load_venue_specs(specs_path)
    venues = specs.get("venues", {})
    venue_key = venue.strip().lower()
    if venue_key not in venues:
        raise ValueError(f"Unknown venue {venue!r}. Available venues: {sorted(venues.keys())}")
    vspec = venues[venue_key]

    phase_key = phase.strip().lower()
    if phase_key not in ("submission", "rebuttal", "camera_ready"):
        raise ValueError(f"Unknown phase {phase!r}. Must be 'submission', 'rebuttal', or 'camera_ready'.")

    ctypes = specs.get("contribution_types", {})
    ctype_key = contribution_type.strip().lower()
    if ctype_key not in ctypes:
        raise ValueError(f"Unknown contribution_type {contribution_type!r}. Available: {sorted(ctypes.keys())}")
    cspec = ctypes[ctype_key]

    entry_tex = Path(tex_path).resolve()
    tex_files, include_hits = collect_tex_tree(entry_tex)
    hits: list[dict[str, Any]] = list(include_hits)
    discovered_sections: list[str] = []

    verified_id_to_text, verified_texts = _load_ceg_claim_map(Path(ceg_path) if ceg_path else None)
    verified_ceg = set(verified_id_to_text.keys()) | verified_texts
    defined_labels: set[str] = set()
    defined_theorem_labels: set[str] = set()
    ref_invocations: list[tuple[str, int, str, str]] = []
    bare_cite_invocations: list[tuple[str, int, str]] = []
    author_dup_candidates: list[tuple[str, int, str, str, str]] = []
    natbib_cite_count = 0
    has_external_doc = False
    author_year_style_active = False
    numeric_cite_option_active = False

    for fpath, raw in tex_files:
        rel_name = fpath.name if len(tex_files) == 1 else fpath.relative_to(entry_tex.parent).as_posix()
        uncommented = _strip_latex_comments(raw)
        masked_body = _mask_macro_definitions_and_verbatim(uncommented)
        lines = uncommented.splitlines()
        masked_lines = masked_body.splitlines()
        newline_offsets = [idx for idx, ch in enumerate(uncommented) if ch == "\n"]

        if EXTERNAL_DOC_RE.search(uncommented):
            has_external_doc = True

        for m_pkg in PACKAGE_OR_CLASS_RE.finditer(uncommented):
            opts_raw = (m_pkg.group(1) or "").lower()
            pkgs_raw = (m_pkg.group(2) or "").lower()
            if CITE_RELEVANT_PKG_RE.search(pkgs_raw) and (
                "numbers" in opts_raw or "super" in opts_raw or "nonatbib" in opts_raw
            ):
                numeric_cite_option_active = True
            if AUTHOR_YEAR_STYLE_PKG_RE.search(pkgs_raw):
                author_year_style_active = True
        if re.search(r"\\setcitestyle\s*\{[^}]*\b(?:numbers|super)\b", uncommented, re.I):
            numeric_cite_option_active = True

        for m_lbl in LABEL_DEF_RE.finditer(masked_body):
            lbl_key = m_lbl.group(1).strip()
            if lbl_key and "#" not in lbl_key:
                defined_labels.add(lbl_key)
        for m_thm_env in THEOREM_ENV_BLOCK_RE.finditer(masked_body):
            for m_tlbl in LABEL_DEF_RE.finditer(m_thm_env.group(2)):
                tlbl_key = m_tlbl.group(1).strip()
                if tlbl_key and "#" not in tlbl_key:
                    defined_theorem_labels.add(tlbl_key)
        for lbl_key in _extract_top_level_env_option_labels(masked_body):
            defined_labels.add(lbl_key)

        for m_ref_call in REF_CALL_RE.finditer(masked_body):
            raw_keys = m_ref_call.group(1).strip()
            if not raw_keys or "?" in raw_keys or "#" in raw_keys:
                continue
            line_no = bisect_right(newline_offsets, m_ref_call.start()) + 1
            excerpt_line = lines[line_no - 1].strip()[:160] if 1 <= line_no <= len(lines) else m_ref_call.group(0)
            for k in raw_keys.split(","):
                k_clean = k.strip()
                if k_clean:
                    ref_invocations.append((rel_name, line_no, k_clean, excerpt_line))

        for m_bare in BARE_CITE_CALL_RE.finditer(masked_body):
            raw_keys = m_bare.group(1).strip()
            if not raw_keys or "?" in raw_keys or "#" in raw_keys:
                continue
            line_no = bisect_right(newline_offsets, m_bare.start()) + 1
            excerpt_line = lines[line_no - 1].strip()[:160] if 1 <= line_no <= len(lines) else m_bare.group(0)
            bare_cite_invocations.append((rel_name, line_no, excerpt_line))

        natbib_cite_count += sum(1 for _ in NATBIB_CITE_CALL_RE.finditer(masked_body))

        for m_dup in AUTHOR_ET_AL_BARE_CITE_RE.finditer(masked_body):
            if "?" in m_dup.group(2):
                continue
            line_no = bisect_right(newline_offsets, m_dup.start()) + 1
            author_dup_candidates.append(
                (rel_name, line_no, m_dup.group(1), m_dup.group(2), m_dup.group(0)[:160])
            )

        if phase_key != "camera_ready":
            for pat in vspec.get("forbidden_patterns_in_review", []):
                for idx, line in enumerate(lines, 1):
                    if pat in line:
                        hits.append({
                            "code": "FORBIDDEN_REVIEW_PATTERN",
                            "severity": "blocker",
                            "locator": f"{rel_name}:L{idx}",
                            "message": f"Forbidden pattern {pat!r} detected for {vspec['display_name']} ({vspec['review_mode']}).",
                            "excerpt": line.strip()[:160],
                        })
            if vspec.get("review_mode") == "double_blind":
                hits.extend(_check_package_options_for_double_blind(uncommented, rel_name))
                if phase_key == "submission":
                    for m_ack in ACKS_SECTION_BLOCK_RE.finditer(uncommented):
                        ack_body = m_ack.group(2).strip()
                        has_grant = bool(GRANT_DISCLOSURE_RE.search(ack_body))
                        if not has_grant and ANON_ACKS_FULLMATCH_RE.fullmatch(ack_body):
                            continue
                        ack_line = bisect_right(newline_offsets, m_ack.start()) + 1
                        hits.append({
                            "code": "FORBIDDEN_ACKS_IN_DOUBLE_BLIND_SUBMISSION",
                            "severity": "blocker" if has_grant else "warning",
                            "locator": f"{rel_name}:L{ack_line}",
                            "message": (
                                f"Dedicated Acknowledgments section detected in double-blind {vspec['display_name']} submission"
                                + (" with explicit grant/funding identifier disclosure." if has_grant else "; omit or anonymize until camera-ready.")
                            ),
                            "excerpt": " ".join((m_ack.group(1) + " " + ack_body).split())[:160],
                        })

        for m in SECTION_RE.finditer(masked_body):
            sec_title = (m.group(1) or m.group(2) or "").strip()
            if sec_title:
                discovered_sections.append(sec_title)
        if CHECKLIST_ENV_RE.search(masked_body):
            discovered_sections.append("NeurIPS Paper Checklist")

        for idx, line in enumerate(lines, 1):
            masked_line = masked_lines[idx - 1] if idx - 1 < len(masked_lines) else ""
            m_ref = UNRESOLVED_REF_RE.search(masked_line)
            if m_ref:
                hits.append({
                    "code": "UNRESOLVED_LATEX_REFERENCE",
                    "severity": "blocker",
                    "locator": f"{rel_name}:L{idx}",
                    "message": "Unresolved citation or cross-reference placeholder detected.",
                    "excerpt": m_ref.group(0)[:160],
                })
            m_todo = TODO_MARKER_RE.search(masked_line)
            if m_todo:
                hits.append({
                    "code": "LEFT_OVER_TODO_MARKER",
                    "severity": "warning",
                    "locator": f"{rel_name}:L{idx}",
                    "message": f"Draft marker {m_todo.group(0)!r} left in manuscript text.",
                    "excerpt": line.strip()[:160],
                })

        for m_tbl in TABLE_BLOCK_RE.finditer(masked_body):
            tbl_body = m_tbl.group(1)
            start_line = bisect_right(newline_offsets, m_tbl.start()) + 1
            if NUMERIC_ROW_RE.search(tbl_body) and not DISPERSION_MARKER_RE.search(tbl_body):
                hits.append({
                    "code": "TABLE_MISSING_DISPERSION",
                    "severity": "warning",
                    "locator": f"{rel_name}:L{start_line}",
                    "message": "Numeric result table reports point estimates without dispersion/uncertainty indicators (\\pm, SD, SE, CI, p-value, or seed count).",
                    "excerpt": " ".join(tbl_body.split())[:160],
                })

        if require_ceg_binding or ceg_path is not None:
            file_line_tags: dict[int, list[str]] = {}
            for l_idx, r_line in enumerate(raw.splitlines(), 1):
                tids = INLINE_CEG_TAG_RE.findall(r_line)
                if tids:
                    file_line_tags[l_idx] = tids
            for block_kind, block_re in (("abstract", ABSTRACT_BLOCK_RE), ("conclusion", CONCLUSION_BLOCK_RE)):
                for m_blk in block_re.finditer(masked_body):
                    blk_uncommented = m_blk.group(1)
                    blk_start_line = masked_body[: m_blk.start(1)].count("\n") + 1
                    blk_nl_offsets = [idx for idx, ch in enumerate(blk_uncommented) if ch == "\n"]
                    for token_start, sent_end, claim_sentence in _extract_quant_claim_spans(blk_uncommented):
                        line_offset = bisect_right(blk_nl_offsets, token_start)
                        sent_start_pos = blk_uncommented.rfind("\n", 0, token_start)
                        sent_start_line = bisect_right(blk_nl_offsets, sent_start_pos + 1) if sent_start_pos != -1 else 0
                        sent_end_line = bisect_right(blk_nl_offsets, max(token_start, sent_end - 1))
                        loc_line = blk_start_line + line_offset
                        abs_start_line = blk_start_line + sent_start_line
                        abs_end_line = blk_start_line + sent_end_line
                        norm_sent = _normalize_claim_text(claim_sentence)
                        tag_matched = False
                        for check_l in range(max(1, abs_start_line - 1), abs_end_line + 1):
                            for tid in file_line_tags.get(check_l, ()):
                                if tid not in verified_id_to_text:
                                    continue
                                c_txt = _normalize_claim_text(verified_id_to_text[tid])
                                if c_txt and c_txt == norm_sent:
                                    tag_matched = True
                                    break
                            if tag_matched:
                                break
                        if not tag_matched:
                            hits.append({
                                "code": "UNGROUNDED_QUANTITATIVE_CLAIM",
                                "severity": "warning",
                                "locator": f"{rel_name}:L{loc_line}",
                                "message": f"Quantitative claim in {block_kind} has no verified ClaimEvidenceGraph support edge or resolved % ark:claim=<id> anchor.",
                                "excerpt": claim_sentence[:180],
                            })

    if not include_hits and not has_external_doc:
        for rel_name, line_no, ref_key, excerpt_line in ref_invocations:
            if ref_key not in defined_labels:
                hits.append({
                    "code": "UNDEFINED_LATEX_LABEL_REF",
                    "severity": "warning",
                    "locator": f"{rel_name}:L{line_no}",
                    "message": f"Cross-reference target {ref_key!r} is not defined by any \\label{{...}} in the manuscript bundle.",
                    "excerpt": excerpt_line,
                })

    total_macros_masked = 0
    if check_academic_style:
        for fpath, raw in tex_files:
            rel_name = fpath.name if len(tex_files) == 1 else fpath.relative_to(entry_tex.parent).as_posix()
            uncommented = _strip_latex_comments(raw)
            masked_body = _mask_macro_definitions_and_verbatim(uncommented)
            adv_hits, macro_cnt = _scan_academic_style(
                rel_name=rel_name,
                raw=raw,
                uncommented=uncommented,
                masked_body=masked_body,
                defined_theorem_labels=defined_theorem_labels,
                verified_id_to_text=verified_id_to_text,
            )
            hits.extend(adv_hits)
            total_macros_masked += macro_cnt

    if author_year_style_active and not numeric_cite_option_active:
        for rel_name, line_no, dup_author, dup_cite, dup_excerpt in author_dup_candidates:
            hits.append({
                "code": "AUTHOR_YEAR_CITE_DUPLICATION",
                "severity": "warning",
                "locator": f"{rel_name}:L{line_no}",
                "message": (
                    f"Redundant prose author prefix {dup_author!r} before {dup_cite!r}; "
                    "under author-year bibliography styles this renders duplicated author names (use \\citet{...} alone or \\citep{...})."
                ),
                "excerpt": dup_excerpt,
            })

    if (
        author_year_style_active
        and not numeric_cite_option_active
        and len(bare_cite_invocations) >= 5
        and natbib_cite_count == 0
    ):
        first_rel, first_line, first_excerpt = bare_cite_invocations[0]
        hits.append({
            "code": "NATBIB_BARE_CITE_DOMINANT",
            "severity": "warning",
            "locator": f"{first_rel}:L{first_line}",
            "message": (
                f"Manuscript uses {len(bare_cite_invocations)} bare \\cite{{...}} calls and 0 \\citep/\\citet calls "
                "under an author-year conference style; in natbib author-year mode bare \\cite acts like textual \\citet without parentheses."
            ),
            "excerpt": first_excerpt,
        })

    for req_sec in vspec.get("required_sections", []):
        pat = re.compile(re.escape(req_sec), re.I)
        if not any(pat.search(s) for s in discovered_sections):
            hits.append({
                "code": "MISSING_REQUIRED_SECTION",
                "severity": "blocker",
                "locator": f"{entry_tex.name}:global",
                "message": f"Missing required dedicated section or checklist for {vspec['display_name']}: {req_sec!r}.",
                "excerpt": f"Discovered sections: {discovered_sections[:10]}",
            })

    phase_limits = vspec.get("phase_max_pages") or {}
    eff_max_pages = phase_limits.get(phase_key, vspec.get("main_body_max_pages"))
    pdf_info: dict[str, Any] = {"pdf_inspected": False, "main_body_max_pages": eff_max_pages, "phase": phase_key}
    if pdf_path is not None:
        p_path = Path(pdf_path)
        if not p_path.is_file():
            raise ValueError(f"PDF file does not exist: {pdf_path}")
        pdf_info, pdf_hits = _inspect_pdf_pages(
            p_path,
            eff_max_pages,
            references_unlimited=bool(vspec.get("references_unlimited", True)),
        )
        pdf_info["phase"] = phase_key
        hits.extend(pdf_hits)

    by_code = dict(Counter(h["code"] for h in hits))
    by_severity = dict(Counter(h["severity"] for h in hits))
    blocker_count = by_severity.get("blocker", 0)

    return {
        "schema_version": "1.0.0",
        "passed": blocker_count == 0,
        "venue": venue_key,
        "venue_display_name": vspec["display_name"],
        "phase": phase_key,
        "review_mode": vspec["review_mode"],
        "contribution_type": ctype_key,
        "contribution_label": cspec["label"],
        "files_scanned": len(tex_files),
        "discovered_sections": discovered_sections,
        "pdf_check": pdf_info,
        "style_check": {
            "enabled": bool(check_academic_style),
            "custom_macros_masked": total_macros_masked,
        },
        "summary_counts": {
            "total_hits": len(hits),
            "blockers": blocker_count,
            "warnings": by_severity.get("warning", 0),
            "advisories": by_severity.get("advisory", 0),
            "by_code": by_code,
        },
        "hits": hits,
        "prereview_checklist": {
            "contribution_specific_evidence": cspec["primary_evidence_requirements"],
            "official_venue_rules": vspec.get("official_guideline_rules", []),
            "recommended_sections": vspec.get("recommended_sections", []),
            "observed_form_metadata": vspec.get("observed_form_metadata", {}),
            "review_dimensions": specs.get("review_dimensions", []),
            "methodological_lenses": specs.get("methodological_lenses", []),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic pre-submission manuscript linter.")
    parser.add_argument("--tex", required=True, help="Path to main .tex entry file")
    parser.add_argument("--venue", default="iclr", help="Target venue key (iclr, neurips, icml, acl, kdd, ieee_tmm, acm_tois, arxiv_preprint)")
    parser.add_argument("--phase", choices=["submission", "rebuttal", "camera_ready"], default="submission", help="Submission phase")
    parser.add_argument("--contribution-type", default="general_empirical", help="Contribution type key")
    parser.add_argument("--pdf", help="Optional compiled PDF path for main-body page limit verification")
    parser.add_argument("--ceg", help="Optional ClaimEvidenceGraph JSON snapshot path")
    parser.add_argument("--require-ceg-binding", action="store_true", help="Flag quantitative claims in Abstract/Conclusion without CEG binding")
    parser.add_argument("--check-academic-style", action="store_true", help="Emit advisory hits for academic LLM cliches, unanchored strong claims, and vague passive methods")
    parser.add_argument("--output", help="Optional output JSON file path")
    args = parser.parse_args(argv)

    report = lint_manuscript(
        tex_path=args.tex,
        venue=args.venue,
        contribution_type=args.contribution_type,
        phase=args.phase,
        pdf_path=args.pdf,
        ceg_path=args.ceg,
        require_ceg_binding=args.require_ceg_binding,
        check_academic_style=args.check_academic_style,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

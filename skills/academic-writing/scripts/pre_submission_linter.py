"""投稿前版式、双盲宏包、必含章节、统计离散度与论断收据绑定确定性检查器。

严格遵循确定性核验与非打分原则：
- 只输出带文件、行号或 PDF 页码定位的确定性命中清单（hits）与分类计数（summary_counts），绝不合成任何主观审稿分数或录用概率。
- 将会刊官方硬性规定（如双盲禁用终稿宏、必含 Limitations / Checklist 章节、正文页数上限）与方法论完整度提示（如实验数值表缺少误差棒/置信区间、摘要定量论断未绑定 CEG 收据）分层报告。
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
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

try:
    from academic_research_kernel.research.sources import (
        TEXLIVE_GLYPH_SYSTEM_INPUTS,
        _TEX_BIB_HEAD_RE as BIB_FILE_CMD_RE,
        _TEX_INPUT_RE as INPUT_RE,
        _TEX_MACRO_HEAD_RE as MACRO_DEF_HEAD_RE,
        _extract_cmd_brace_args_after_opt_brackets,
        _find_tex_macro_body_open_brace as _find_macro_body_open_brace,
        _mask_macro_definitions_and_verbatim,
        _skip_balanced_braces,
        _skip_optional_bracket_block,
        _strip_comments_and_collect_verbatim_spans,
        inside as _inside_bounded,
    )
except ImportError:
    _src_dir = Path(__file__).resolve().parents[3] / "src"
    if _src_dir.is_dir() and str(_src_dir) not in sys.path:
        sys.path.insert(0, str(_src_dir))
    from academic_research_kernel.research.sources import (
        TEXLIVE_GLYPH_SYSTEM_INPUTS,
        _TEX_BIB_HEAD_RE as BIB_FILE_CMD_RE,
        _TEX_INPUT_RE as INPUT_RE,
        _TEX_MACRO_HEAD_RE as MACRO_DEF_HEAD_RE,
        _extract_cmd_brace_args_after_opt_brackets,
        _find_tex_macro_body_open_brace as _find_macro_body_open_brace,
        _mask_macro_definitions_and_verbatim,
        _skip_balanced_braces,
        _skip_optional_bracket_block,
        _strip_comments_and_collect_verbatim_spans,
        inside as _inside_bounded,
    )

MAX_INCLUDE_DEPTH = 5
MAX_TEX_FILES = 64
MAX_TOTAL_BYTES = 20 * 1024 * 1024

EXTERNAL_DOC_RE = re.compile(r"\\(?:externaldocument|includeonly)\b")
PACKAGE_OR_CLASS_RE = re.compile(r"(?<!\\)(?:\\\\)*\\(usepackage|documentclass)\s*(?:\[([^\]]*)\]\s*)?\{([^}{]+)\}", re.S)
_PKG_OR_CLS_HEAD_RE = re.compile(r"(?<!\\)(?:\\\\)*\\(usepackage|documentclass)(?![A-Za-z@])")
BENIGN_FINAL_OPT_PACKAGES = frozenset({
    "microtype", "graphicx", "hyperref", "listings", "pdfpages", "showkeys",
    "todonotes", "changes", "fixme", "ifdraft", "babel", "subcaption",
    "float", "booktabs", "amsmath", "amssymb", "geometry", "cleveref", "tikz",
})
CITE_CMD_HEAD_RE = re.compile(
    r"(?<!\\)(?:\\\\)*\\(cite|nocite|citet|citep|citealt|citealp|citeauthor|citeyear|citeyearpar|citenum|citen|citeonline|"
    r"Cite|Citet|Citep|Citealt|Citealp|Citeauthor|Citeyear|Citeyearpar|Citenum|"
    r"parencite|Parencite|textcite|Textcite|footcite|Footcite|footcitetext|Footcitetext|footfullcite|Footfullcite|"
    r"autocite|Autocite|smartcite|Smartcite|supercite|Supercite|fullcite|Fullcite|"
    r"cites|Cites|parencites|Parencites|textcites|Textcites|footcites|Footcites|footcitetexts|Footcitetexts|smartcites|Smartcites|supercites|Supercites|autocites|Autocites)(?![A-Za-z@])\*?"
)
MULTI_CITE_CMDS = frozenset({
    "cites", "Cites", "parencites", "Parencites", "textcites", "Textcites",
    "footcites", "Footcites", "footcitetexts", "Footcitetexts",
    "smartcites", "Smartcites", "supercites", "Supercites", "autocites", "Autocites",
})
BIBITEM_DEF_RE = re.compile(r"(?<!\\)(?:\\\\)*\\bibitem(?![A-Za-z@])")
CUSTOM_CITE_CONSTRUCT_RE = re.compile(
    r"(?<!\\)(?:\\\\)*\\(?:Declare(?:Cite|MultiCite|AutoCite)Command|defbibentryset|defcitealias|volcites?|pvolcites?|tvolcites?|fvolcites?|avolcites?)(?![A-Za-z@])"
)
LET_ALIAS_PREFIX_RE = re.compile(r"(?<!\\)(?:\\\\)*(?:\\global\s+)?\\let\s*(?:\{\s*\\[A-Za-z@]+\s*\}|\\[A-Za-z@]+)\s*(?:=\s*)?")
BIBTEX_TOP_TOKEN_RE = re.compile(r"%[^\n]*|@\s*([A-Za-z]+)\s*[\{\(]")
BIBTEX_META_TYPES = frozenset({"comment", "preamble", "string"})
SECTION_RE = re.compile(
    r"\\(?:section|subsection|paragraph|chapter)\*?\s*\{([^}{]+)\}|^#{1,3}\s+(.+)$",
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
    r"(?:\\(?:ref|eqref|autoref|Cref|cref)\*?\s*\{\s*(?:\?+\s*)?\}|\b(?:Section|Sec\.|Table|Tab\.|Figure|Fig\.|Eq\.|Equation|Theorem|Appendix|Algorithm|Alg\.)\s+\?\?(?!\w))",
)
UNRESOLVED_CITE_CALL_RE = re.compile(r"\\cite[a-zA-Z*]*\s*\{([^}{\n]*)\}")
PDF_UNRESOLVED_REF_RE = re.compile(
    r"(?:\b(?:Section|Sec\.|Table|Tab\.|Figure|Fig\.|Eq\.|Equation|Theorem|Appendix|Algorithm|Alg\.)\s+\?\?(?!\w)|\[\s*\?\s*\])",
)
LABEL_DEF_RE = re.compile(r"\\label\s*\{([^}{]+)\}")
ENV_OPT_HEAD_RE = re.compile(r"\\begin\{(?:lstlisting|minted|tcolorbox)\}\s*\[")
REF_CALL_RE = re.compile(r"\\(?:ref|eqref|autoref|Cref|cref|pageref)\*?\s*\{([^}{]+)\}")
BARE_CITE_CALL_RE = re.compile(r"\\cite\s*(?:\[[^\][]*\]\s*)?\{([^}{]+)\}")
NATBIB_CITE_CALL_RE = re.compile(r"\\cite(?:p|t|alt|alp|author|year|num)\*?\s*(?:\[[^\][]*\]\s*)*\{([^}{]+)\}")
AUTHOR_ET_AL_BARE_CITE_RE = re.compile(
    r"\b([A-Z][A-Za-z'-]{1,30}\s+et\s+al\.)[\s~]+(\\(?:cite|citet)\*?\s*\{[^}{]+\})"
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
TABLE_BLOCK_RE = re.compile(r"\\begin\{table\*?\}(.*?)\\end\{table\*?\}", re.S)
NUMERIC_ROW_RE = re.compile(r"&[^\\]*\b\d+\.\d+\b")
DISPERSION_MARKER_RE = re.compile(
    r"(?:\\pm\b|±|\b(?:SD|SE|SEM|CI|IQR|std|stdev|variance|p\s*[<=>]|p-value|wilcoxon|mann-whitney|confidence\s+interval|seed|seeds)\b|\(\s*[+-]?\d+\.\d+\s*\))",
    re.I,
)
ABSTRACT_BLOCK_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
_SECTION_CMD_HEAD_RE = re.compile(r"(?<!\\)(?:\\\\)*\\section\*?(?![A-Za-z@])")
_ANY_HEADING_CMD_HEAD_RE = re.compile(r"(?<!\\)(?:\\\\)*\\(?:section|subsection|paragraph|chapter)\*?(?![A-Za-z@])")
_MD_HEADING_LINE_RE = re.compile(r"^#{1,3}\s+(.+)$", re.M)
_CONCLUSION_TITLE_KW_RE = re.compile(r"Conclusion|Conclusions|Discussion", re.I)
_CONCLUSION_END_BOUNDARY_RE = re.compile(
    r"(?<!\\)(?:\\\\)*(\\(?:bibliography|appendix)(?![A-Za-z@])|\\end\{document\})"
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
    r"|\\(?:cite[a-zA-Z*]*|ref|eqref|autoref|Cref|cref|pageref|label|url)\*?\s*(?:\[[^\][]*\]\s*)*\{[^}{]*\}",
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


def _extract_strong_claim_sentences(prose_block: str, full_block: str) -> list[tuple[int, int, int, str, str]]:
    """Return (sent_start, match_start, sent_end, sentence_text, matched_token) scanning prose_block and slicing full_block."""
    n = len(prose_block)
    spans: list[tuple[int, int, int, str, str]] = []
    sent_punct = "!?;\u3002\uff01\uff1f\uff1b"
    cached_s_idx = -1
    cached_e_idx = -1
    cached_sentence = ""
    for m in STRONG_CLAIM_CANDIDATE_RE.finditer(prose_block):
        if cached_s_idx <= m.start() < cached_e_idx:
            s_idx, e_idx, sentence = cached_s_idx, cached_e_idx, cached_sentence
        else:
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
            sentence_raw = full_block[s_idx:e_idx]
            sentence = " ".join(sentence_raw.split()).strip()
            cached_s_idx, cached_e_idx, cached_sentence = s_idx, e_idx, sentence
        # Check negation only within the current clause immediately preceding the match
        clause_prefix = prose_block[max(s_idx, m.start() - 60) : m.start()]
        clause_breaks = list(CLAUSE_BREAK_RE.finditer(clause_prefix))
        if clause_breaks:
            clause_prefix = clause_prefix[clause_breaks[-1].end() :]
        if NEGATION_WINDOW_RE.search(clause_prefix):
            continue
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
    macro_def_count = 0
    pos_mc = 0
    n_unc = len(uncommented)
    while pos_mc < n_unc:
        m = MACRO_DEF_HEAD_RE.search(uncommented, pos_mc)
        if not m:
            break
        open_b, next_pos = _find_macro_body_open_brace(uncommented, m.end(1))
        if open_b is None:
            pos_mc = max(m.end(1), next_pos)
            continue
        after_b = _skip_balanced_braces(uncommented, open_b)
        if after_b < 0:
            break
        macro_def_count += 1
        pos_mc = after_b
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
    for block_kind, blk_start_idx, blk_end_idx, blk_full in _iter_abstract_and_conclusion_blocks(masked_body):
        blk_prose = prose_only[blk_start_idx:blk_end_idx]
        blk_start_line = bisect_left(newline_offsets, blk_start_idx) + 1
        blk_nl_offsets = [idx for idx, ch in enumerate(blk_full) if ch == "\n"]
        sent_eval_cache: dict[tuple[int, int], tuple[bool, bool, bool]] = {}
        for s_idx, m_start, sent_end, claim_sent, tok in _extract_strong_claim_sentences(blk_prose, blk_full):
            line_offset = bisect_right(blk_nl_offsets, m_start)
            loc_line = blk_start_line + line_offset
            sent_key = (s_idx, sent_end)
            cached_eval = sent_eval_cache.get(sent_key)
            if cached_eval is None:
                sent_start_line = bisect_right(blk_nl_offsets, s_idx)
                sent_end_line = bisect_right(blk_nl_offsets, max(s_idx, sent_end - 1))
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
                has_disp = bool(DISPERSION_MARKER_RE.search(claim_sent))
                has_resolvable_thm = False
                for m_ref in REF_CALL_RE.finditer(claim_sent):
                    for k in m_ref.group(1).split(","):
                        if k.strip() in defined_theorem_labels:
                            has_resolvable_thm = True
                            break
                cached_eval = (has_verified_ceg, has_disp, has_resolvable_thm)
                sent_eval_cache[sent_key] = cached_eval
            has_verified_ceg, has_disp, has_resolvable_thm = cached_eval
            if has_verified_ceg:
                continue

            tok_low = tok.lower()
            if "significant" in tok_low or "显著" in tok_low:
                if has_disp:
                    continue
                advisory_hits.append({
                    "code": "UNANCHORED_STRONG_CLAIM_CANDIDATE",
                    "severity": "advisory",
                    "locator": f"{rel_name}:L{loc_line}",
                    "message": f"Statistical significance claim {tok!r} in {block_kind} has no same-sentence statistical test/p-value/CI marker or verified % ark:claim=<id> anchor.",
                    "excerpt": claim_sent[:180],
                })
            else:
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



def _strip_latex_comments(text: str) -> str:
    """Strip unescaped % comments in a single top-to-bottom pass."""
    uncommented, _ = _strip_comments_and_collect_verbatim_spans(text)
    return uncommented


PACKAGE_OR_CLASS_BALANCED_RE = re.compile(
    r"(?<!\\)(?:\\\\)*\\(usepackage|documentclass)(?![A-Za-z@])\s*(?:\[((?:[^\[\]{}]|\{[^{}]*\})*)\]\s*)?\{([^}{]+)\}",
    re.S,
)
ABSTRACT_BLOCK_RE = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
CONCLUSION_BLOCK_RE = re.compile(
    r"(?<!\\)(?:\\\\)*\\section\*?(?:\s*\[(?:[^\[\]{}]|\{[^{}]*\})*\])?\s*\{[^}]*(?:Conclusion|Conclusions|Discussion)[^}]*\}(.*?)(?=(?<!\\)(?:\\\\)*\\(?:section\*?(?:\s*\[|\s*\{)|bibliography|addbibresource|appendix|end\{document\})|$)",
    re.S | re.I,
)


def _iter_package_or_class_decls(text: str) -> list[tuple[int, int, str, str, str]]:
    decls: list[tuple[int, int, str, str, str]] = []
    n, pos = len(text), 0
    while pos < n:
        m = _PKG_OR_CLS_HEAD_RE.search(text, pos)
        if not m:
            break
        cur = m.end()
        opt_end = _skip_optional_bracket_block(text, cur)
        if opt_end < 0:
            break
        opts_raw = text[text.find("[", cur, opt_end) + 1 : opt_end - 1] if opt_end > cur else ""
        cur = opt_end
        while cur < n and text[cur].isspace():
            cur += 1
        if cur >= n or text[cur] != "{":
            pos = max(m.end(), cur)
            continue
        pkg_end = _skip_balanced_braces(text, cur)
        if pkg_end < 0:
            break
        decls.append((m.start(1) - 1, pkg_end, m.group(1).lower(), opts_raw, text[cur + 1 : pkg_end - 1].strip()))
        pos = max(m.end(), pkg_end)
    return decls


def _iter_section_titles(text: str) -> list[str]:
    titles = [" ".join(arg.split()) for _, arg in _extract_cmd_brace_args_after_opt_brackets(text, _ANY_HEADING_CMD_HEAD_RE) if arg.strip()]
    titles.extend(m.group(1).strip() for m in _MD_HEADING_LINE_RE.finditer(text) if m.group(1).strip())
    return titles


def _iter_abstract_and_conclusion_blocks(text: str) -> list[tuple[str, int, int, str]]:
    blocks = [("abstract", m.start(1), m.end(1), m.group(1)) for m in ABSTRACT_BLOCK_RE.finditer(text)]
    blocks.extend(("conclusion", m.start(1), m.end(1), m.group(1)) for m in CONCLUSION_BLOCK_RE.finditer(text))
    return blocks


def _split_top_level_tex_delim(
    s: str,
    sep: str = ",",
    respect_quotes: bool = False,
) -> tuple[list[str], bool]:
    """Split s on sep at brace_depth == 0 (and outside quotes if respect_quotes). Returns (parts, balanced_ok)."""
    parts: list[str] = []
    cur: list[str] = []
    depth = 0
    in_quotes = False
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            cur.append(s[i : i + 2])
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif respect_quotes and ch == '"' and depth == 0:
            in_quotes = not in_quotes
        elif ch == sep and depth == 0 and not in_quotes:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts, (depth == 0 and not in_quotes)


def _split_top_level_tex_commas(s: str) -> list[str]:
    return _split_top_level_tex_delim(s, ",")[0]


def _extract_top_level_env_option_labels(text: str) -> list[str]:
    """Extract top-level label=... values from \\begin{lstlisting|minted|tcolorbox}[...] option blocks."""
    labels: list[str] = []
    n, pos_env = len(text), 0
    while pos_env < n:
        m = ENV_OPT_HEAD_RE.search(text, pos_env)
        if not m:
            break
        opt_end = _skip_optional_bracket_block(text, m.end() - 1)
        if opt_end < 0:
            opt_block = text[m.end() :]
            pos_env = n
        else:
            opt_block = text[m.end() : opt_end - 1]
            pos_env = max(m.end(), opt_end)
        for entry in _split_top_level_tex_commas(opt_block):
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




def _collect_tex_tree_views(
    entry_tex: Path,
) -> tuple[list[tuple[Path, str, str, str, list[int]]], list[dict[str, Any]], int]:
    r"""Collect entry .tex and bounded relative \input / \include files with cached preprocessed views."""
    entry_tex = entry_tex.resolve()
    if not entry_tex.is_file():
        raise ValueError(f"TeX entry file does not exist: {entry_tex}")
    root_dir = entry_tex.parent
    visited: set[Path] = set()
    views: list[tuple[Path, str, str, str, list[int]]] = []
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

    def _walk(current: Path, depth: int, caller_locator: str | None = None, raw_target: str = "") -> None:
        nonlocal total_bytes
        resolved = current.resolve()
        if resolved in visited:
            return
        if not resolved.is_relative_to(root_dir):
            raise ValueError(f"TeX include escapes manuscript root: {current}")
        if not resolved.is_file() and raw_target in TEXLIVE_GLYPH_SYSTEM_INPUTS:
            return
        if depth > MAX_INCLUDE_DEPTH or len(views) >= MAX_TEX_FILES:
            msg = (
                f"TeX include depth exceeded maximum limit ({MAX_INCLUDE_DEPTH}); bundle coverage is incomplete."
                if depth > MAX_INCLUDE_DEPTH
                else f"TeX file count exceeded maximum limit ({MAX_TEX_FILES}); bundle coverage is incomplete."
            )
            include_hits.append({
                "code": "TEX_BUNDLE_TRUNCATED",
                "severity": "blocker",
                "locator": caller_locator or current.name,
                "message": msg,
                "excerpt": str(current.name),
            })
            return
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
        uncommented, verb_spans = _strip_comments_and_collect_verbatim_spans(raw)
        masked_for_include = _mask_macro_definitions_and_verbatim(uncommented, verb_spans)
        newline_offsets = [idx for idx, ch in enumerate(uncommented) if ch == "\n"]
        views.append((resolved, raw, uncommented, masked_for_include, newline_offsets))
        rel_self = resolved.relative_to(root_dir).as_posix()
        for m in INPUT_RE.finditer(masked_for_include):
            raw_inc = m.group(1) or m.group(2) or m.group(3) or m.group(4) or ""
            target = (raw_inc).strip().strip('"')
            if not target:
                continue
            line_no = bisect_right(newline_offsets, m.start()) + 1
            cand = _resolve_include_candidate(resolved, target)
            _walk(cand, depth + 1, caller_locator=f"{rel_self}:L{line_no}", raw_target=target)

    _walk(entry_tex, 0)
    return views, include_hits, total_bytes


def collect_tex_tree(entry_tex: Path) -> tuple[list[tuple[Path, str]], list[dict[str, Any]]]:
    r"""Collect entry .tex and bounded relative \input / \include files without escaping manuscript root."""
    views, include_hits, _ = _collect_tex_tree_views(entry_tex)
    return [(fpath, raw) for fpath, raw, _, _, _ in views], include_hits

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


def _import_export_ceg_anchors():
    if __package__:
        from .venue_template_manager import export_ceg_anchors
        return export_ceg_anchors
    sibling_file = Path(__file__).resolve().with_name("venue_template_manager.py")
    if sibling_file.is_file():
        import importlib.util
        mod_key = f"_ark_colocated_vtm_{hash(str(sibling_file))}"
        mod = sys.modules.get(mod_key)
        if mod is None or getattr(mod, "__file__", None) != str(sibling_file):
            spec = importlib.util.spec_from_file_location(mod_key, sibling_file)
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot load co-located {sibling_file}")
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_key] = mod
            spec.loader.exec_module(mod)
        return mod.export_ceg_anchors
    from academic_research_kernel.venue_template_manager import export_ceg_anchors
    return export_ceg_anchors


def _load_ceg_claim_map(ceg_path: Path | None) -> tuple[dict[str, str], set[str]]:
    """Return (verified_id_to_text, verified_texts) for claims whose CEG anchor_status == 'eligible'."""
    if ceg_path is None:
        return {}, set()
    p = Path(ceg_path)
    if not p.exists() and not p.is_symlink():
        return {}, set()
    exported = _import_export_ceg_anchors()(p)
    id_to_text: dict[str, str] = {}
    verified_texts: set[str] = set()
    for anc in exported.get("anchors", ()):
        if anc.get("anchor_status") == "eligible":
            cid = str(anc["claim_id"])
            txt = str(anc["normalized_text"])
            id_to_text[cid] = txt
            verified_texts.add(txt)
    return id_to_text, verified_texts


def _load_ceg_verified_claims(ceg_path: Path | None) -> set[str]:
    """Return set of verified claim IDs and statements that have positive support and zero contradiction."""
    id_to_text, verified_texts = _load_ceg_claim_map(ceg_path)
    return set(id_to_text.keys()) | verified_texts


def _check_package_options_for_double_blind(
    masked_body: str,
    rel_name: str,
    newline_offsets: list[int] | None = None,
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    if newline_offsets is None:
        newline_offsets = [idx for idx, ch in enumerate(masked_body) if ch == "\n"]
    for decl_start, decl_end, cmd_kind, opts_raw, pkg_name in _iter_package_or_class_decls(masked_body):
        if not opts_raw:
            continue
        pkg_list = [p.strip().lower() for p in pkg_name.split(",") if p.strip()]
        is_benign_utility_pkg = (
            cmd_kind == "usepackage"
            and bool(pkg_list)
            and all(p in BENIGN_FINAL_OPT_PACKAGES for p in pkg_list)
        )
        line_no = bisect_right(newline_offsets, decl_start) + 1
        tokens = ["".join(t.split()).lower() for t in _split_top_level_tex_commas(opts_raw) if t.strip()]
        for tok in tokens:
            if tok == "final" and is_benign_utility_pkg:
                continue
            if tok in FORBIDDEN_DOUBLE_BLIND_OPTION_TOKENS or tok == "anonymous=false" or tok == "review=false":
                hits.append({
                    "code": "FORBIDDEN_REVIEW_PATTERN",
                    "severity": "blocker",
                    "locator": f"{rel_name}:L{line_no}",
                    "message": f"De-anonymizing or camera-ready package option {tok!r} on {pkg_name!r} is forbidden in double-blind review.",
                    "excerpt": " ".join(masked_body[decl_start:decl_end].split())[:160],
                })
    return hits



def _resolve_bounded_subpath(root_dir: Path, rel_str: str) -> Path | None:
    """Resolve rel_str inside root_dir rejecting absolute paths, '..', and any symlink/reparse component."""
    try:
        return _inside_bounded(root_dir, rel_str)
    except (ValueError, OSError):
        return None


def _consume_cite_invocation(
    masked_body: str,
    m: re.Match[str],
    groups: list[str],
    depth: int = 0,
) -> int:
    """Consume one citation invocation starting at match m, extracting nested citations inside option notes."""
    n = len(masked_body)
    is_multi = m.group(1) in MULTI_CITE_CMDS
    seen_mandatory = False
    pos = m.end()
    while pos < n:
        while pos < n and masked_body[pos].isspace():
            pos += 1
        if pos >= n:
            break
        ch = masked_body[pos]
        if ch == "[" or (ch == "(" and is_multi and not seen_mandatory):
            close_opt = "]" if ch == "[" else ")"
            brace_depth = 0
            pos += 1
            closed_opt = False
            while pos < n:
                c = masked_body[pos]
                if c == "\\":
                    inner_m = CITE_CMD_HEAD_RE.match(masked_body, pos)
                    if inner_m is not None and depth < 8:
                        pos = _consume_cite_invocation(masked_body, inner_m, groups, depth + 1)
                        continue
                    if pos + 1 < n:
                        pos += 2
                        continue
                if c == "{":
                    brace_depth += 1
                elif c == "}" and brace_depth > 0:
                    brace_depth -= 1
                elif c == close_opt and brace_depth == 0:
                    pos += 1
                    closed_opt = True
                    break
                pos += 1
            if not closed_opt:
                break
            continue
        if ch == "{":
            end_b = _skip_balanced_braces(masked_body, pos)
            if end_b < 0:
                pos = n
                break
            groups.append(masked_body[pos + 1 : end_b - 1])
            pos = end_b
            seen_mandatory = True
            if not is_multi:
                break
            continue
        if not seen_mandatory:
            groups.append("\\")
        break
    return max(m.end(), pos)


def _extract_cite_key_groups(masked_body: str) -> list[str]:
    """Extract mandatory {...} citation key arguments after \\cite* commands."""
    groups: list[str] = []
    n, outer_pos = len(masked_body), 0
    while outer_pos < n:
        m = CITE_CMD_HEAD_RE.search(masked_body, outer_pos)
        if not m:
            break
        outer_pos = _consume_cite_invocation(masked_body, m, groups, 0)
    return groups


def _has_custom_cite_or_bib_macro(raw: str, masked_body: str) -> bool:
    """Return True if manuscript defines custom citation commands/aliases or exotic citation constructs."""
    if CUSTOM_CITE_CONSTRUCT_RE.search(masked_body):
        return True
    uncommented, verb_spans = _strip_comments_and_collect_verbatim_spans(raw)
    chars = list(uncommented)
    for s_span, e_span in verb_spans:
        for idx in range(s_span, e_span):
            if chars[idx] != "\n":
                chars[idx] = " "
    masked_verb = "".join(chars)
    target_res = (CITE_CMD_HEAD_RE, BIB_FILE_CMD_RE, BIBITEM_DEF_RE, CUSTOM_CITE_CONSTRUCT_RE)
    for m_let in LET_ALIAS_PREFIX_RE.finditer(masked_verb):
        rhs = masked_verb[m_let.end() : m_let.end() + 64]
        if any(r.match(rhs) for r in target_res):
            return True
    pos, n_mv = 0, len(masked_verb)
    while pos < n_mv:
        m = MACRO_DEF_HEAD_RE.search(masked_verb, pos)
        if not m:
            break
        open_idx, next_pos = _find_macro_body_open_brace(masked_verb, m.end(1))
        if open_idx is None:
            pos = max(m.end(1), next_pos)
            continue
        end_idx = _skip_balanced_braces(masked_verb, open_idx)
        end_idx = n_mv if end_idx < 0 else end_idx
        span = masked_verb[m.start(1) : end_idx]
        if any(r.search(span) for r in target_res):
            return True
        pos = end_idx
    return False


def _extract_top_level_crossref_targets(fields_chunk: str) -> tuple[set[str], set[str], bool]:
    """Extract literal target keys from top-level crossref/xref/xdata/entryset/related and alias keys from ids."""
    targets: set[str] = set()
    aliases: set[str] = set()
    items, balanced = _split_top_level_tex_delim(fields_chunk, ",", respect_quotes=True)
    if not balanced:
        return set(), set(), False
    for item in items:
        if "=" not in item:
            continue
        k_raw, v_raw = item.split("=", 1)
        field_name = k_raw.strip().lower()
        if field_name not in ("crossref", "xref", "xdata", "entryset", "related", "ids"):
            continue
        val = v_raw.strip()
        if len(val) >= 2 and val[0] == "{" and _skip_balanced_braces(val, 0) == len(val):
            lit = val[1:-1]
        elif len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            lit = val[1:-1]
        else:
            return set(), set(), False
        dest = aliases if field_name == "ids" else targets
        for t in lit.split(","):
            t_clean = t.strip()
            if t_clean and "{" not in t_clean and "}" not in t_clean:
                dest.add(t_clean)
    return targets, aliases, True


def _parse_bibtex_entries_with_crossrefs(
    raw_bib: str,
    rel_bib: str,
) -> tuple[list[tuple[str, int, str, str, str]], dict[str, set[str]], bool]:
    """Extract (rel_bib, line_no, key, excerpt, 'bib'), crossref/xdata dependency map, and parse_ok from .bib text."""
    nl_offsets = [idx for idx, ch in enumerate(raw_bib) if ch == "\n"]
    raw_lines = raw_bib.splitlines()
    entries: list[tuple[str, int, str, str, str]] = []
    deps: dict[str, set[str]] = {}
    n_len, search_pos = len(raw_bib), 0
    while search_pos < n_len:
        m = BIBTEX_TOP_TOKEN_RE.search(raw_bib, search_pos)
        if not m:
            break
        if m.group(1) is None:
            search_pos = m.end()
            continue
        etype = m.group(1).strip().lower()
        open_delim = raw_bib[m.end() - 1]
        body_start = m.end()
        if open_delim == "{":
            end_b = _skip_balanced_braces(raw_bib, m.end() - 1)
            closed = end_b >= 0
            pos = end_b if closed else n_len
        else:
            paren_depth, brace_depth, in_quotes, pos = 1, 0, False, body_start
            while pos < n_len and paren_depth > 0:
                ch = raw_bib[pos]
                if ch == "\\" and pos + 1 < n_len:
                    pos += 2
                    continue
                if ch == "{":
                    brace_depth += 1
                elif ch == "}" and brace_depth > 0:
                    brace_depth -= 1
                elif ch == '"' and brace_depth == 0:
                    in_quotes = not in_quotes
                elif brace_depth == 0 and not in_quotes:
                    if ch == "(":
                        paren_depth += 1
                    elif ch == ")":
                        paren_depth -= 1
                pos += 1
            closed = paren_depth == 0
        search_pos = pos
        if not closed:
            return entries, deps, False
        if etype in BIBTEX_META_TYPES:
            continue
        chunk = raw_bib[body_start : pos - 1]
        comma_pos = chunk.find(",")
        if comma_pos == -1:
            return entries, deps, False
        key = chunk[:comma_pos].strip()
        if not key or "{" in key or "}" in key or "\\" in key or "#" in key or any(ch.isspace() for ch in key):
            return entries, deps, False
        if etype != "xdata":
            line_no = bisect_right(nl_offsets, m.start(1)) + 1
            excerpt = (raw_lines[line_no - 1].strip() if 1 <= line_no <= len(raw_lines) else f"@{etype}{{{key},")[:160]
            entries.append((rel_bib, line_no, key, excerpt, "bib"))
        entry_deps, entry_aliases, ok_deps = _extract_top_level_crossref_targets(chunk[comma_pos + 1 :])
        if not ok_deps:
            return entries, deps, False
        if entry_deps:
            deps.setdefault(key, set()).update(entry_deps)
        for al in entry_aliases:
            deps.setdefault(al, set()).add(key)
    return entries, deps, True


def _scan_uncited_bibliography(
    entry_tex: Path,
    views: list[tuple[Path, str, str, str, list[int]]],
    total_bytes_used: int,
    include_hits_present: bool,
    has_external_doc: bool,
) -> list[dict[str, Any]]:
    """Return advisory UNCITED_BIBLIOGRAPHY_ENTRY hits when check_academic_style is enabled."""
    if include_hits_present or has_external_doc:
        return []
    root_dir = entry_tex.parent
    cited_keys: set[str] = set()
    bib_targets: list[str] = []
    defined_entries: list[tuple[str, int, str, str, str]] = []
    crossref_deps: dict[str, set[str]] = {}

    for fpath, raw, _uncommented, masked_body, newline_offsets in views:
        if _has_custom_cite_or_bib_macro(raw, masked_body):
            return []
        rel_name = fpath.name if len(views) == 1 else fpath.relative_to(root_dir).as_posix()
        raw_lines = raw.splitlines()
        for grp in _extract_cite_key_groups(masked_body):
            for k in (grp).split(","):
                k_clean = k.strip()
                if not k_clean:
                    continue
                if k_clean == "*" or "\\" in k_clean or "#" in k_clean:
                    return []
                cited_keys.add(k_clean)
        for _, bib_arg in _extract_cmd_brace_args_after_opt_brackets(masked_body, BIB_FILE_CMD_RE):
            for part in (bib_arg).split(","):
                if part.strip():
                    bib_targets.append(part.strip())
        for bi_start, raw_bkey in _extract_cmd_brace_args_after_opt_brackets(masked_body, BIBITEM_DEF_RE):
            bkey = (raw_bkey).strip()
            if not bkey:
                continue
            if "\\" in bkey or "#" in bkey or any(ch.isspace() for ch in bkey):
                return []
            line_no = bisect_right(newline_offsets, bi_start) + 1
            excerpt = (raw_lines[line_no - 1].strip() if 1 <= line_no <= len(raw_lines) else f"\\bibitem{{{bkey}}}")[:160]
            defined_entries.append((rel_name, line_no, bkey, excerpt, "bibitem"))

    seen_bib_files: set[Path] = set()
    bytes_budget = total_bytes_used
    for btok in bib_targets:
        if "\\" in btok:
            return []
        suffix_low = Path(btok).suffix.lower()
        if suffix_low and suffix_low != ".bib":
            return []
        rel_cands = [btok] if suffix_low == ".bib" else [f"{btok}.bib", btok]
        target_loaded = False
        for rel_c in rel_cands:
            try:
                resolved = _resolve_bounded_subpath(root_dir, rel_c)
                if resolved is None or not resolved.is_file() or resolved.suffix.lower() != ".bib":
                    continue
                if resolved in seen_bib_files:
                    target_loaded = True
                    break
                fsize = resolved.stat().st_size
                if bytes_budget + fsize > MAX_TOTAL_BYTES:
                    return []
                seen_bib_files.add(resolved)
                bytes_budget += fsize
                rel_bib = resolved.relative_to(root_dir).as_posix()
                raw_bib = resolved.read_text(encoding="utf-8", errors="replace")
                b_entries, b_deps, parse_ok = _parse_bibtex_entries_with_crossrefs(raw_bib, rel_bib)
                if not parse_ok:
                    return []
                defined_entries.extend(b_entries)
                for k, dset in b_deps.items():
                    crossref_deps.setdefault(k, set()).update(dset)
                target_loaded = True
                break
            except OSError:
                return []
        if not target_loaded:
            return []

    if not defined_entries:
        return []

    frontier = list(cited_keys)
    while frontier:
        cur_k = frontier.pop()
        for dep_k in crossref_deps.get(cur_k, ()):
            if dep_k not in cited_keys:
                cited_keys.add(dep_k)
                frontier.append(dep_k)

    uncited_hits: list[dict[str, Any]] = []
    for rel_path, line_no, key, excerpt, kind in defined_entries:
        if key not in cited_keys:
            kind_desc = (
                f"BibTeX database entry {key!r} in {rel_path} is never cited in the manuscript text"
                if kind == "bib"
                else f"Bibliography item \\bibitem{{{key}}} is listed in references but never cited in the manuscript text"
            )
            uncited_hits.append({
                "code": "UNCITED_BIBLIOGRAPHY_ENTRY",
                "severity": "advisory",
                "locator": f"{rel_path}:L{line_no}",
                "message": f"{kind_desc}; cite it or remove unused reference entries.",
                "excerpt": excerpt,
            })
    return uncited_hits


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
    views, include_hits, total_bytes_used = _collect_tex_tree_views(entry_tex)
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

    for fpath, raw, uncommented, masked_body, newline_offsets in views:
        rel_name = fpath.name if len(views) == 1 else fpath.relative_to(entry_tex.parent).as_posix()
        lines = uncommented.splitlines()
        masked_lines = masked_body.splitlines()

        if EXTERNAL_DOC_RE.search(uncommented):
            has_external_doc = True

        for _d_start, _d_end, _cmd_kind, opts_raw_orig, pkgs_raw_orig in _iter_package_or_class_decls(masked_body):
            opts_raw = opts_raw_orig.lower()
            pkgs_raw = pkgs_raw_orig.lower()
            if CITE_RELEVANT_PKG_RE.search(pkgs_raw) and (
                "numbers" in opts_raw or "super" in opts_raw or "nonatbib" in opts_raw
            ):
                numeric_cite_option_active = True
            if AUTHOR_YEAR_STYLE_PKG_RE.search(pkgs_raw):
                author_year_style_active = True
        if re.search(r"\\setcitestyle\s*\{[^}{\n]*\b(?:numbers|super)\b", uncommented, re.I):
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
                hits.extend(_check_package_options_for_double_blind(masked_body, rel_name, newline_offsets))
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

        for sec_title in _iter_section_titles(masked_body):
            discovered_sections.append(sec_title)
        if CHECKLIST_ENV_RE.search(masked_body):
            discovered_sections.append("NeurIPS Paper Checklist")

        for idx, line in enumerate(lines, 1):
            masked_line = masked_lines[idx - 1] if idx - 1 < len(masked_lines) else ""
            m_ref = UNRESOLVED_REF_RE.search(masked_line)
            unresolved_excerpt = m_ref.group(0) if m_ref else None
            if unresolved_excerpt is None:
                for m_uc in UNRESOLVED_CITE_CALL_RE.finditer(masked_line):
                    uc_body = m_uc.group(1)
                    if "?" in uc_body and any(
                        tok.strip() and set(tok.strip()) == {"?"} for tok in uc_body.split(",")
                    ):
                        unresolved_excerpt = m_uc.group(0)
                        break
            if unresolved_excerpt is not None:
                hits.append({
                    "code": "UNRESOLVED_LATEX_REFERENCE",
                    "severity": "blocker",
                    "locator": f"{rel_name}:L{idx}",
                    "message": "Unresolved citation or cross-reference placeholder detected.",
                    "excerpt": unresolved_excerpt[:160],
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
            for block_kind, blk_start_idx, _blk_end_idx, blk_uncommented in _iter_abstract_and_conclusion_blocks(masked_body):
                blk_start_line = bisect_left(newline_offsets, blk_start_idx) + 1
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
        for fpath, raw, uncommented, masked_body, _ in views:
            rel_name = fpath.name if len(views) == 1 else fpath.relative_to(entry_tex.parent).as_posix()
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
        hits.extend(
            _scan_uncited_bibliography(
                entry_tex=entry_tex,
                views=views,
                total_bytes_used=total_bytes_used,
                include_hits_present=bool(include_hits),
                has_external_doc=has_external_doc,
            )
        )

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
        "files_scanned": len(views),
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

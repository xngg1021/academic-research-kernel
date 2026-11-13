"""核对下载 PDF 的身份：首页文字/元数据与声明的标题、DOI 比对。

文本归一化与比对为纯离线确定性逻辑；PDF 读取需 pymupdf（惰性导入，缺失时明确报错）。
下载成功不等于内容正确，必须核对首页文字，防止下到同名错误文件。
"""
from __future__ import annotations

import argparse
import json
import re
import sys


DEFAULT_THRESHOLD = 0.8


def normalize_text(text) -> str:
    """小写并折叠空白，用于首页文字比对。"""
    return ' '.join((text or '').split()).lower()


def title_tokens(title) -> list:
    """标题切词：CJK 逐字成词，其余 Unicode 字母数字成词 (AV-03 / A02)。"""
    return re.findall(r'[\u4e00-\u9fff]|[^\W_\u4e00-\u9fff]+', (title or '').lower())


def compare_title(expected_title: str, page_text: str, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """标题词在首页文字中的覆盖率；达到 threshold 判 match。
    A02: 使用完整词元集合匹配，拒绝字符级子串误判 (如 expected='AI' 不得命中 'training')。
    """
    tokens = title_tokens(expected_title)
    page_token_set = set(title_tokens(page_text))
    page_normalized = normalize_text(page_text)

    matched, missing = [], []
    for t in tokens:
        if len(t) == 1 and '\u4e00' <= t <= '\u9fff':
            if t in page_normalized:
                matched.append(t)
            else:
                missing.append(t)
        else:
            if t in page_token_set:
                matched.append(t)
            else:
                missing.append(t)

    coverage = len(matched) / len(tokens) if tokens else 0.0
    return {
        'expected_title': expected_title,
        'token_count': len(tokens),
        'token_coverage': round(coverage, 4),
        'missing_tokens': missing,
        'match': bool(tokens) and coverage >= threshold,
    }


DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[^\s<>\"']+")


def extract_dois(text) -> list:
    """从文本提取完整 DOI 字符串列表 (去尾随标点), 用于精确身份比对。"""
    found = []
    for m in DOI_PATTERN.finditer((text or '').lower()):
        candidate = m.group(0).rstrip('.,;:)]}')
        if candidate and candidate not in found:
            found.append(candidate)
    return found


def find_doi(doi: str, page_text: str) -> bool:
    """DOI 在首页文字中的出现判定 (AV-02): 提取完整 DOI 后精确匹配,
    目标 10.1234/abc 不再命中仅含 10.1234/abcd 的文本。"""
    if not doi:
        return False
    target = (doi or '').lower().strip().rstrip('.,;:)]}')
    return target in extract_dois(page_text)


def read_pdf(path: str, max_pages: int = 1) -> dict:
    """在受控隔离子进程中提取前 max_pages 页文字与页数（支持 pymupdf 或 pypdf），校验符号链接、文件大小与超时。"""
    try:
        from academic_research_kernel.research.sources import controlled_read_pdf_pages
    except ImportError:
        from pathlib import Path as _Path
        _src_dir = _Path(__file__).resolve().parents[3] / "src"
        if _src_dir.is_dir() and str(_src_dir) not in sys.path:
            sys.path.insert(0, str(_src_dir))
        from academic_research_kernel.research.sources import controlled_read_pdf_pages
    return controlled_read_pdf_pages(path, max_pages=max_pages)


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

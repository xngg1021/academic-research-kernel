"""核对下载 PDF 的身份：首页文字/元数据与声明的标题、DOI 比对。

文本归一化与比对为纯离线确定性逻辑；PDF 读取需 pymupdf（惰性导入，缺失时明确报错）。
下载成功不等于内容正确，必须核对首页文字，防止下到同名错误文件。
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import sys as _sys
if _sys.platform == "win32":
    for _s in (_sys.stdout, _sys.stderr):
        if _s and hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")

DEFAULT_THRESHOLD = 0.8


def normalize_text(text) -> str:
    """小写并折叠空白，用于首页文字比对。"""
    return ' '.join((text or '').split()).lower()


def title_tokens(title) -> list:
    """标题切词：拉丁字母/数字成词，CJK 逐字成词。"""
    return re.findall(r'[a-z0-9]+|[一-鿿]', (title or '').lower())


def compare_title(expected_title: str, page_text: str, threshold: float = DEFAULT_THRESHOLD) -> dict:
    """标题词在首页文字中的覆盖率；达到 threshold 判 match。"""
    tokens = title_tokens(expected_title)
    page = normalize_text(page_text)
    matched = [t for t in tokens if t in page]
    missing = [t for t in tokens if t not in page]
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
    """用 pymupdf 提取前 max_pages 页文字与页数；pymupdf 缺失时明确报错。"""
    try:
        import pymupdf
    except ImportError as exc:
        raise RuntimeError('pymupdf 未安装；请先 pip install pymupdf 再运行本脚本') from exc
    doc = pymupdf.open(path)
    try:
        pages = min(max_pages, doc.page_count)
        text = '\n'.join(doc[i].get_text() for i in range(pages))
        return {'page_count': doc.page_count, 'pages_read': pages,
                'text': text, 'metadata': dict(doc.metadata or {})}
    finally:
        doc.close()


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='至少给 --title 或 --doi 之一；返回码 0=核对通过，1=不一致或读取失败。')
    parser.add_argument('--pdf', required=True, help='已下载的 PDF 路径')
    parser.add_argument('--title', help='声明的论文标题（与首页文字比对）')
    parser.add_argument('--doi', help='声明的 DOI（在首页文字中查找）')
    parser.add_argument('--pages', type=int, default=1, help='读取页数（默认首页）')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD,
                        help='标题词覆盖率阈值（默认 0.8）')
    args = parser.parse_args(argv)
    if not args.title and not args.doi:
        parser.error('至少给 --title 或 --doi 之一；不凭空判定身份')
    _utf8_stdio()

    try:
        pdf = read_pdf(args.pdf, max_pages=args.pages)
    except (RuntimeError, OSError) as error:
        print(json.dumps({'pdf': args.pdf, 'status': 'failed', 'error': str(error)},
                         ensure_ascii=False, indent=2))
        return 1

    verdict = {
        'pdf': args.pdf,
        'status': 'ok',
        'page_count': pdf['page_count'],
        'pages_read': pdf['pages_read'],
        'first_page_excerpt': ' '.join(pdf['text'].split())[:400],
        'metadata': pdf['metadata'],
    }
    checks = []
    if args.title:
        verdict['title_check'] = compare_title(args.title, pdf['text'], threshold=args.threshold)
        checks.append(verdict['title_check']['match'])
    if args.doi:
        verdict['doi_present'] = find_doi(args.doi, pdf['text']) or find_doi(
            args.doi, json.dumps(pdf['metadata']))
        checks.append(verdict['doi_present'])
    verdict['identity_ok'] = all(checks)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict['identity_ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

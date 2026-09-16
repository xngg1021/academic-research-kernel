"""归一化学术标识符：DOI / arXiv / PMID / OpenAlex ID。纯离线、确定性，无网络访问。"""
from __future__ import annotations

import argparse
import json
import re
import sys

DOI_PREFIXES = (
    'https://doi.org/', 'http://doi.org/', 'https://dx.doi.org/', 'http://dx.doi.org/', 'doi:',
)
ARXIV_PREFIXES = ('https://arxiv.org/abs/', 'http://arxiv.org/abs/', 'arxiv:')
PMID_PREFIXES = ('https://pubmed.ncbi.nlm.nih.gov/', 'http://pubmed.ncbi.nlm.nih.gov/', 'pmid:')
OPENALEX_PREFIX = 'https://openalex.org/'

DOI_RE = re.compile(r'^10\.\d{4,9}/\S+$')
ARXIV_NEW_RE = re.compile(r'^\d{4}\.\d{4,5}(v\d+)?$')
ARXIV_OLD_RE = re.compile(r'^[a-z][a-z-]*(\.[a-z]{2})?/\d{7}(v\d+)?$', re.IGNORECASE)
PMID_RE = re.compile(r'^\d{1,9}$')
OPENALEX_RE = re.compile(r'^[WASTCPFI]\d+$')


def _unknown(raw: str) -> dict:
    return {'input': raw, 'type': 'unknown', 'value': None, 'canonical': None}


def normalize_identifier(raw: str) -> dict:
    """归一化单个标识符，返回 {'input', 'type', 'value', 'canonical'}。

    type ∈ {doi, arxiv, pmid, openalex, unknown}；无法识别时 value/canonical 为 None，
    不猜测、不补全。
    """
    text = (raw or '').strip()
    if not text:
        return _unknown(raw)
    lowered = text.lower()

    for prefix in DOI_PREFIXES:
        if lowered.startswith(prefix):
            candidate = text[len(prefix):].strip().lower().rstrip('.')
            if DOI_RE.match(candidate):
                return {'input': raw, 'type': 'doi', 'value': candidate,
                        'canonical': 'https://doi.org/' + candidate}
            return _unknown(raw)

    arxiv_text = text
    if lowered.startswith(('https://arxiv.org/pdf/', 'http://arxiv.org/pdf/')):
        arxiv_text = text.split('/pdf/', 1)[1]
        arxiv_text = re.sub(r'\.pdf$', '', arxiv_text, flags=re.IGNORECASE)
    else:
        for prefix in ARXIV_PREFIXES:
            if arxiv_text.lower().startswith(prefix):
                arxiv_text = arxiv_text[len(prefix):]
                break
    if arxiv_text != text or ARXIV_NEW_RE.match(arxiv_text) or ARXIV_OLD_RE.match(arxiv_text):
        candidate = arxiv_text.strip().strip('/')
        if ARXIV_NEW_RE.match(candidate) or ARXIV_OLD_RE.match(candidate):
            return {'input': raw, 'type': 'arxiv', 'value': candidate,
                    'canonical': 'https://arxiv.org/abs/' + candidate}
        if arxiv_text != text:
            return _unknown(raw)

    for prefix in PMID_PREFIXES:
        if lowered.startswith(prefix):
            candidate = text[len(prefix):].strip().strip('/')
            if PMID_RE.match(candidate):
                return {'input': raw, 'type': 'pmid', 'value': candidate,
                        'canonical': 'https://pubmed.ncbi.nlm.nih.gov/' + candidate + '/'}
            return _unknown(raw)

    if lowered.startswith(OPENALEX_PREFIX):
        candidate = text[len(OPENALEX_PREFIX):].strip().strip('/').upper()
        if OPENALEX_RE.match(candidate):
            return {'input': raw, 'type': 'openalex', 'value': candidate,
                    'canonical': OPENALEX_PREFIX + candidate}
        return _unknown(raw)

    if DOI_RE.match(lowered):
        return {'input': raw, 'type': 'doi', 'value': lowered,
                'canonical': 'https://doi.org/' + lowered}
    if OPENALEX_RE.match(text.upper()):
        candidate = text.upper()
        return {'input': raw, 'type': 'openalex', 'value': candidate,
                'canonical': OPENALEX_PREFIX + candidate}
    if PMID_RE.match(text):
        return {'input': raw, 'type': 'pmid', 'value': text,
                'canonical': 'https://pubmed.ncbi.nlm.nih.gov/' + text + '/'}
    return _unknown(raw)


def _utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog='示例: python normalize_identifier.py https://doi.org/10.1038/nature14539 arXiv:2106.09624')
    parser.add_argument('identifiers', nargs='+', help='待归一化的标识符（可多个）')
    args = parser.parse_args(argv)
    _utf8_stdio()
    results = [normalize_identifier(item) for item in args.identifiers]
    payload = results[0] if len(results) == 1 else results
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(r['type'] != 'unknown' for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())

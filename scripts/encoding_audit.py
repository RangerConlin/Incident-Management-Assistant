#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import sys
import re
from pathlib import Path
from collections import Counter

# Binary-like extensions to skip
BINARY_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.pdf', '.db', '.db-journal', '.sqlite', '.sqlite3',
    '.pyc', '.pyd', '.pyo', '.dll', '.exe', '.so', '.dylib', '.ttf', '.woff', '.woff2', '.eot', '.otf', '.zip', '.tar', '.gz', '.7z',
    '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'
}

SKIP_DIRS = {'.git', '.venv', '.venv313', '__pycache__', 'node_modules', 'reports'}
SKIP_FILES = {'scripts/encoding_audit.py'}

# Common mojibake sequences when UTF-8 is decoded as Windows-1252/Latin-1
MOJIBAKE_PATTERNS = [
    'â€™', 'â€˜', 'â€œ', 'â€\u009d', 'â€\u009c', 'â€”', 'â€“', 'â€¢', 'â€¦',
    'Â©', 'Â®', 'Â«', 'Â»', 'Â€', 'â‚¬', 'Â·', 'Â ', 'Ã', '�'
]

CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


def is_binary_path(p: Path) -> bool:
    return p.suffix.lower() in BINARY_EXTS


def iter_text_files(root: Path):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = Path(base) / f
            if is_binary_path(p):
                continue
            rel = str(p).replace('\\', '/')
            if any(rel.endswith(s) for s in SKIP_FILES):
                continue
            yield p


def try_read_utf8(path: Path):
    data = path.read_bytes()
    try:
        text = data.decode('utf-8')
        return text, None
    except UnicodeDecodeError as e:
        return None, e


def scan_text(text: str):
    findings = []
    for m in re.finditer('\uFFFD', text):
        line_no = text.count('\n', 0, m.start()) + 1
        col_no = m.start() - (text.rfind('\n', 0, m.start()) + 1)
        excerpt = text.splitlines()[line_no - 1][:200]
        findings.append(('replacement', line_no, col_no, excerpt))
    for m in CONTROL_CHARS_RE.finditer(text):
        line_no = text.count('\n', 0, m.start()) + 1
        col_no = m.start() - (text.rfind('\n', 0, m.start()) + 1)
        excerpt = text.splitlines()[line_no - 1][:200]
        findings.append(('control', line_no, col_no, excerpt))
    for pat in MOJIBAKE_PATTERNS:
        start = 0
        while True:
            idx = text.find(pat, start)
            if idx == -1:
                break
            line_no = text.count('\n', 0, idx) + 1
            col_no = idx - (text.rfind('\n', 0, idx) + 1)
            excerpt = text.splitlines()[line_no - 1][:200]
            findings.append(('mojibake', line_no, col_no, excerpt))
            start = idx + len(pat)
    return findings


def _safe(s: str) -> str:
    try:
        return s.encode('ascii', 'backslashreplace').decode('ascii')
    except Exception:
        return repr(s)


def main():
    ap = argparse.ArgumentParser(description='Scan repository for encoding issues (UTF-8 enforcement).')
    ap.add_argument('--root', type=Path, default=Path.cwd(), help='Root directory to scan')
    ap.add_argument('--fail-on-find', action='store_true', help='Exit non-zero if any issues are found')
    ap.add_argument('--summary', action='store_true', help='Only print summary counts')
    ap.add_argument('--fail-kinds', default='decode-error,mojibake,control,replacement',
                    help='Comma-separated kinds that cause non-zero exit: decode-error, mojibake, control, replacement')
    args = ap.parse_args()

    fail_kinds = set(k.strip() for k in args.fail_kinds.split(',') if k.strip())

    total = 0
    decode_errors = 0
    hits = []

    for p in iter_text_files(args.root):
        total += 1
        text, err = try_read_utf8(p)
        if err is not None:
            decode_errors += 1
            pos = err.start
            data = p.read_bytes()
            context = data[max(0, pos-8):pos+8]
            hexbytes = ' '.join(f'{b:02X}' for b in context)
            print(f'DECODE-ERROR {p} @ byte {pos}: {hexbytes}')
            continue
        findings = scan_text(text)
        for kind, ln, col, ex in findings:
            hits.append((p, kind, ln, col, ex.strip()))

    by_kind = {'decode-error': decode_errors, 'mojibake': 0, 'control': 0, 'replacement': 0}
    for _, kind, *_ in hits:
        by_kind[kind] += 1

    file_counts = Counter(p for p, *_ in hits)

    if not args.summary:
        for p, kind, ln, col, ex in hits[:500]:
            print(f'{kind.upper():12} {p}:{ln}:{col+1}  ' + _safe(ex))
        if len(hits) > 500:
            print(f'... truncated {len(hits) - 500} additional hits ...')
        if file_counts:
            print('\nTop files by hits:')
            for p, c in file_counts.most_common(10):
                print(f'  {p}: {c}')

    print('\nScan complete:')
    print(f'  Files scanned: {total}')
    print(f'  Decode errors: {by_kind["decode-error"]}')
    print(f'  Mojibake hits: {by_kind["mojibake"]}')
    print(f'  Control chars: {by_kind["control"]}')
    print(f'  Replacement chars: {by_kind["replacement"]}')

    if args.fail_on_find:
        for kind, count in by_kind.items():
            if kind in fail_kinds and count:
                sys.exit(1)

if __name__ == '__main__':
    main()

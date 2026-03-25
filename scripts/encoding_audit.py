#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

EXCLUDE_DIRS = {
    '.git', '.hg', '.svn', '.venv', 'venv', '__pycache__', '.mypy_cache', '.pytest_cache',
    'node_modules', 'dist', 'build', '.idea', '.vscode', '.history'
}

BINARY_EXTS = {
    '.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.pdf', '.zip', '.gz', '.7z', '.rar',
    '.mp3', '.mp4', '.avi', '.mov', '.ogg', '.woff', '.woff2', '.ttf', '.otf', '.dll', '.so',
    '.dylib', '.exe'
}

UTF8_BOM = b"\xEF\xBB\xBF"
UTF16_LE_BOM = b"\xFF\xFE"
UTF16_BE_BOM = b"\xFE\xFF"
UTF32_LE_BOM = b"\xFF\xFE\x00\x00"
UTF32_BE_BOM = b"\x00\x00\xFE\xFF"


def is_binary_bytes(sample: bytes) -> bool:
    if b"\x00" in sample:
        return True
    # Heuristic: too many non-text bytes
    text_chars = bytearray({7,8,9,10,12,13,27} | set(range(0x20, 0x100)))
    nontext = sample.translate(None, text_chars)
    return len(nontext) / max(1, len(sample)) > 0.30


def should_skip(path: Path) -> bool:
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    if path.suffix.lower() in BINARY_EXTS:
        return True
    try:
        with path.open('rb') as f:
            sample = f.read(4096)
        return is_binary_bytes(sample)
    except Exception:
        return True


def analyze(path: Path):
    info = {
        'utf8_bom': False,
        'utf16_bom': False,
        'utf32_bom': False,
        'not_utf8': False,
        'crlf': False,
        'error': None,
    }
    try:
        data = path.read_bytes()
        if data.startswith(UTF8_BOM):
            info['utf8_bom'] = True
        elif data.startswith(UTF16_LE_BOM) or data.startswith(UTF16_BE_BOM):
            info['utf16_bom'] = True
        elif data.startswith(UTF32_LE_BOM) or data.startswith(UTF32_BE_BOM):
            info['utf32_bom'] = True
        # EOL check
        if b"\r\n" in data:
            info['crlf'] = True
        # UTF-8 check (ignore BOM by slicing it off)
        to_check = data[3:] if info['utf8_bom'] else data
        to_check.decode('utf-8')
    except UnicodeDecodeError as e:
        info['not_utf8'] = True
        info['error'] = str(e)
    except Exception as e:
        info['error'] = f"{type(e).__name__}: {e}"
    return info


def fix_file(path: Path, normalize_eol: bool = False) -> tuple[bool, str | None]:
    try:
        data = path.read_bytes()
        changed = False
        # Convert UTF-32/16 with BOM to UTF-8
        if data.startswith(UTF32_LE_BOM) or data.startswith(UTF32_BE_BOM):
            text = data.decode('utf-32')
            changed = True
        elif data.startswith(UTF16_LE_BOM) or data.startswith(UTF16_BE_BOM):
            text = data.decode('utf-16')
            changed = True
        else:
            # Strip UTF-8 BOM if present
            if data.startswith(UTF8_BOM):
                data = data[len(UTF8_BOM):]
                changed = True
            # Try utf-8 decode; if fails, re-raise
            text = data.decode('utf-8')
        if normalize_eol:
            new_text = text.replace('\r\n', '\n')
            if new_text != text:
                changed = True
            text = new_text
        if changed:
            path.write_text(text, encoding='utf-8', newline='\n' if normalize_eol else None)
        return changed, None
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    p = argparse.ArgumentParser(description='Audit repository text encodings for UTF-8 without BOM.')
    p.add_argument('--root', default='.', help='Root directory to scan (default: .)')
    p.add_argument('--summary', action='store_true', help='Print summary of findings')
    p.add_argument('--list', dest='list_paths', action='store_true', help='List offending file paths')
    p.add_argument('--fail-on-find', action='store_true', help='Exit with code 1 if any offenders found')
    p.add_argument('--fix', action='store_true', help='Attempt to convert offenders to UTF-8 (no BOM)')
    p.add_argument('--normalize-eol', action='store_true', help='When fixing, normalize CRLF to LF')
    args = p.parse_args()

    root = Path(args.root)
    offenders = {
        'utf8_bom': [],
        'utf16_bom': [],
        'utf32_bom': [],
        'not_utf8': [],
        'crlf': [],
        'errors': {},
    }

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune excluded dirs in-place
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            pth = Path(dirpath, name)
            if should_skip(pth):
                continue
            info = analyze(pth)
            if info['utf8_bom']:
                offenders['utf8_bom'].append(pth)
            if info['utf16_bom']:
                offenders['utf16_bom'].append(pth)
            if info['utf32_bom']:
                offenders['utf32_bom'].append(pth)
            if info['not_utf8']:
                offenders['not_utf8'].append(pth)
            if info['crlf']:
                offenders['crlf'].append(pth)
            if info['error']:
                offenders['errors'][str(pth)] = info['error']

    total_offenders = sum(len(v) for k, v in offenders.items() if k != 'errors')

    if args.fix:
        changed_count = 0
        for pth in offenders['utf8_bom'] + offenders['utf16_bom'] + offenders['utf32_bom'] + offenders['not_utf8']:
            changed, err = fix_file(pth, normalize_eol=args.normalize_eol)
            if err:
                offenders['errors'][str(pth)] = err
            if changed:
                changed_count += 1
        # Recompute offenders after fix pass
        offenders = {
            'utf8_bom': [], 'utf16_bom': [], 'utf32_bom': [], 'not_utf8': [], 'crlf': [], 'errors': offenders['errors']
        }
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
            for name in filenames:
                pth = Path(dirpath, name)
                if should_skip(pth):
                    continue
                info = analyze(pth)
                if info['utf8_bom']:
                    offenders['utf8_bom'].append(pth)
                if info['utf16_bom']:
                    offenders['utf16_bom'].append(pth)
                if info['utf32_bom']:
                    offenders['utf32_bom'].append(pth)
                if info['not_utf8']:
                    offenders['not_utf8'].append(pth)
                if info['crlf']:
                    offenders['crlf'].append(pth)
                if info['error']:
                    offenders['errors'][str(pth)] = info['error']
        total_offenders = sum(len(v) for k, v in offenders.items() if k != 'errors')
        print(f"Fix pass complete. Files changed: {changed_count}")

    if args.summary:
        print("Encoding audit summary:")
        print(f"  UTF-8 BOM: {len(offenders['utf8_bom'])}")
        print(f"  UTF-16 BOM: {len(offenders['utf16_bom'])}")
        print(f"  UTF-32 BOM: {len(offenders['utf32_bom'])}")
        print(f"  Not UTF-8 decodable: {len(offenders['not_utf8'])}")
        print(f"  CRLF endings detected: {len(offenders['crlf'])}")
        if offenders['errors']:
            print(f"  Errors: {len(offenders['errors'])}")
    if args.list_paths:
        for key in ['utf8_bom','utf16_bom','utf32_bom','not_utf8','crlf']:
            if offenders[key]:
                print(f"\n{key}:")
                for p in offenders[key]:
                    print(str(p))
        if offenders['errors']:
            print("\nerrors:")
            for p, e in offenders['errors'].items():
                print(f"{p}: {e}")

    if args.fail_on_find and total_offenders > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()
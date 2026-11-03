#!/usr/bin/env python3
"""Rebuild the reader manuscript, checksums and an optional deterministic ZIP."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {'MANIFEST.json'}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def public_files():
    return sorted(p for p in ROOT.rglob('*') if p.is_file()
                  and p.name not in EXCLUDED
                  and '__pycache__' not in p.parts
                  and not any(part.startswith('.') for part in p.relative_to(ROOT).parts))

def build_book(meta):
    parts = []
    for index, rel in enumerate(meta['reading_order']):
        text = (ROOT / rel).read_text(encoding='utf-8').strip()
        parts.append(text)
        if index == 0:
            headings = [(ROOT / x).read_text(encoding='utf-8').splitlines()[0][2:]
                        for x in meta['chapters']]
            parts.append('## 目录\n\n' + '\n'.join(f'{i}. {h.split(" ", 1)[1]}'
                           for i, h in enumerate(headings, 1)) +
                         '\n\n附录：往来记录、表达示例、常用词与来源说明。')
    return ('\n\n'.join(parts) + '\n').encode('utf-8')

def manifest(meta, book):
    entries = []
    for p in public_files():
        rel = p.relative_to(ROOT).as_posix()
        data = book if rel == 'BOOK.md' else p.read_bytes()
        entries.append({'path': rel, 'bytes': len(data), 'sha256': sha(data)})
    if not any(e['path'] == 'BOOK.md' for e in entries):
        entries.append({'path': 'BOOK.md', 'bytes': len(book), 'sha256': sha(book)})
        entries.sort(key=lambda x: x['path'])
    text = book.decode('utf-8')
    out = {'schema_version': 1, 'title': meta['title'], 'version': meta['version'],
           'status': meta['status'], 'date': meta['date'],
           'algorithm': 'SHA-256', 'manifest_self_excluded': True,
           'chapter_count': len(meta['chapters']),
           'book_unicode_characters': len(text),
           'book_han_characters': len(re.findall(r'[\u4e00-\u9fff]', text)),
           'files': entries}
    return (json.dumps(out, ensure_ascii=False, indent=2) + '\n').encode('utf-8')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--zip', type=Path)
    args = ap.parse_args()
    meta = json.loads((ROOT / 'book.json').read_text(encoding='utf-8'))
    book = build_book(meta)
    if args.check:
        assert (ROOT / 'BOOK.md').read_bytes() == book, 'BOOK.md is out of date'
    else:
        (ROOT / 'BOOK.md').write_bytes(book)
    data = manifest(meta, book)
    if args.check:
        assert (ROOT / 'MANIFEST.json').read_bytes() == data, 'MANIFEST.json is out of date'
    else:
        (ROOT / 'MANIFEST.json').write_bytes(data)
    if args.zip:
        dest = args.zip.resolve()
        if dest == ROOT or ROOT in dest.parents:
            raise ValueError('ZIP output must be outside the source directory')
        dest.parent.mkdir(parents=True, exist_ok=True)
        paths = sorted(public_files() + [ROOT / 'MANIFEST.json'])
        with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_STORED) as archive:
            for p in paths:
                item = zipfile.ZipInfo(ROOT.name + '/' + p.relative_to(ROOT).as_posix(),
                                       date_time=(2026, 11, 3, 0, 0, 0))
                item.create_system = 3
                item.external_attr = 0o100644 << 16
                archive.writestr(item, p.read_bytes())
        print(f'{dest}\nSHA-256 {sha(dest.read_bytes())}')
    print('Verified' if args.check else 'Rebuilt', len(meta['chapters']), 'chapters')

if __name__ == '__main__':
    main()

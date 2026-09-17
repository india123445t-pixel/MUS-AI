from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path.cwd()
SKIP_DIRS = {'.git', 'node_modules', '.next', '.vercel'}
TEMP_FILES = {
    Path('.github/workflows/kite-identity-sweep.yml'),
    Path('scripts/kite_identity_sweep.py'),
}

UPPER = re.compile(r'(?<![A-Za-z0-9])AQLEVON(?![A-Za-z0-9])')
TITLE = re.compile(r'(?<![A-Za-z0-9])Aqlevon(?![A-Za-z0-9])')
LOWER = re.compile(r'(?<![A-Za-z0-9])aqlevon(?![A-Za-z0-9])')


def transform_text(text: str) -> str:
    text = UPPER.sub('KITE', text)
    text = TITLE.sub('Kite', text)
    text = LOWER.sub('kite', text)
    return text


def is_skipped(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    if rel in TEMP_FILES:
        return True
    return any(part in SKIP_DIRS for part in rel.parts)


def text_files():
    for path in ROOT.rglob('*'):
        if not path.is_file() or is_skipped(path):
            continue
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if b'\x00' in raw:
            continue
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            continue
        yield path, text


changed_files = 0
for path, text in list(text_files()):
    updated = transform_text(text)
    if updated != text:
        path.write_text(updated, encoding='utf-8')
        changed_files += 1

renamed_paths = []
for path in sorted(
    [p for p in ROOT.rglob('*') if not is_skipped(p)],
    key=lambda p: len(p.relative_to(ROOT).parts),
    reverse=True,
):
    new_name = transform_text(path.name)
    if new_name == path.name:
        continue
    target = path.with_name(new_name)
    if target.exists():
        raise RuntimeError(f'rename collision: {path} -> {target}')
    old_rel = path.relative_to(ROOT).as_posix()
    path.rename(target)
    renamed_paths.append({'from': old_rel, 'to': target.relative_to(ROOT).as_posix()})

expected_upstream = 'Qwen/Qwen3.8-27B-FP8'
provenance_hits = 0
remaining = []
for path, text in text_files():
    provenance_hits += text.count(expected_upstream)
    for line_no, line in enumerate(text.splitlines(), start=1):
        if UPPER.search(line) or TITLE.search(line) or LOWER.search(line):
            remaining.append(f'{path.relative_to(ROOT)}:{line_no}:{line[:180]}')

if remaining:
    print(json.dumps({'error': 'AQLEVON_IDENTITY_REMAINS', 'matches': remaining[:100]}, indent=2))
    raise SystemExit(2)

if provenance_hits < 1:
    print(json.dumps({'error': 'UPSTREAM_PROVENANCE_MISSING', 'expected': expected_upstream}, indent=2))
    raise SystemExit(3)

print(json.dumps({
    'status': 'PASS',
    'identity': 'Kite',
    'changed_text_files': changed_files,
    'renamed_paths': renamed_paths,
    'upstream_provenance': expected_upstream,
    'upstream_provenance_hits': provenance_hits,
}, indent=2))

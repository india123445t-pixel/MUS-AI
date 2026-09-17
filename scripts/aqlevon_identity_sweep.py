from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path.cwd()
SKIP_DIRS = {'.git', 'node_modules', '.next', '.vercel'}
TEMP_WORKFLOW = Path('.github/workflows/aqlevon-identity-sweep.yml')

UPPER = re.compile(r'(?<![A-Za-z0-9])MUS(?![A-Za-z0-9])')
TITLE = re.compile(r'(?<![A-Za-z0-9])Mus(?![A-Za-z0-9])')
LOWER = re.compile(r'(?<![A-Za-z0-9])mus(?![A-Za-z0-9])')


def transform_text(text: str) -> str:
    text = UPPER.sub('AQLEVON', text)
    text = TITLE.sub('Aqlevon', text)
    text = LOWER.sub('aqlevon', text)
    return text


def transform_name(name: str) -> str:
    return transform_text(name)


def is_skipped(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return True
    if rel == TEMP_WORKFLOW:
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
replacement_files = []
for path, text in list(text_files()):
    updated = transform_text(text)
    if updated != text:
        path.write_text(updated, encoding='utf-8')
        changed_files += 1
        replacement_files.append(path.relative_to(ROOT).as_posix())

renamed_paths = []
for path in sorted(
    [p for p in ROOT.rglob('*') if not is_skipped(p)],
    key=lambda p: len(p.relative_to(ROOT).parts),
    reverse=True,
):
    new_name = transform_name(path.name)
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
remaining_legacy = []
for path, text in text_files():
    if expected_upstream in text:
        provenance_hits += text.count(expected_upstream)
    for line_no, line in enumerate(text.splitlines(), start=1):
        if UPPER.search(line) or TITLE.search(line) or LOWER.search(line):
            remaining_legacy.append(f'{path.relative_to(ROOT)}:{line_no}:{line[:180]}')

if remaining_legacy:
    print(json.dumps({'error': 'LEGACY_IDENTITY_REMAINS', 'matches': remaining_legacy[:100]}, indent=2))
    raise SystemExit(2)

if provenance_hits < 1:
    print(json.dumps({'error': 'UPSTREAM_PROVENANCE_MISSING', 'expected': expected_upstream}, indent=2))
    raise SystemExit(3)

report = {
    'status': 'PASS',
    'identity': 'AQLEVON',
    'changed_text_files': changed_files,
    'renamed_paths': renamed_paths,
    'upstream_provenance': expected_upstream,
    'upstream_provenance_hits': provenance_hits,
    'temporary_exclusions': [TEMP_WORKFLOW.as_posix()],
    'note': 'Legacy product identity removed from repository text/path tokens; upstream Qwen provenance preserved. Temporary workflow is deleted after commit.',
}
Path('AQLEVON_IDENTITY_MIGRATION_REPORT.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))

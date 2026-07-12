#!/usr/bin/env python3
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MD_LINK = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
errors = []

for md in list((ROOT / 'docs').rglob('*.md')) + [ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', ROOT / 'CHANGELOG.md']:
    text = md.read_text(encoding='utf-8')
    for match in MD_LINK.finditer(text):
        target = match.group(1).strip()
        if not target or target.startswith(('http://', 'https://', 'mailto:', '#')):
            continue
        target_path = target.split('#', 1)[0]
        if not target_path:
            continue
        resolved = (md.parent / target_path).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            errors.append(f'{md.relative_to(ROOT)}: link escapes repo: {target}')
            continue
        if not resolved.exists():
            errors.append(f'{md.relative_to(ROOT)}: missing link target: {target}')

if errors:
    print('Markdown link validation failed:')
    for e in errors:
        print(f' - {e}')
    sys.exit(1)

print('Markdown link validation passed.')

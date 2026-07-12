from __future__ import annotations

import re
from pathlib import Path

MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def validate_links(root: Path) -> int:
    files = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        files.extend(docs_dir.rglob("*.md"))
    for name in ["README.md", "CONTRIBUTING.md", "CHANGELOG.md", "MIGRATION.md"]:
        if (root / name).exists():
            files.append(root / name)
    errors: list[str] = []
    for md in files:
        text = md.read_text(encoding="utf-8")
        for match in MD_LINK.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target_path = target.split("#", 1)[0]
            if not target_path:
                continue
            resolved = (md.parent / target_path).resolve()
            try:
                resolved.relative_to(root.resolve())
            except ValueError:
                errors.append(f"{md.relative_to(root)}: link escapes repo: {target}")
                continue
            if not resolved.exists():
                errors.append(f"{md.relative_to(root)}: missing link target: {target}")
    if errors:
        print("Markdown link validation failed:")
        for error in errors:
            print(f" - {error}")
        return 1
    print("Markdown link validation passed.")
    return 0

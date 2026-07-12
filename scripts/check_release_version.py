#!/usr/bin/env python3
"""Verify that package and runtime versions agree with an optional release version."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys
import tomllib


def package_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as stream:
        return str(tomllib.load(stream)["project"]["version"])


def runtime_version(root: Path) -> str:
    module = ast.parse((root / "src/repo_fleet_manager/__init__.py").read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "__version__":
                    value = ast.literal_eval(node.value)
                    if isinstance(value, str):
                        return value
    raise ValueError("__version__ was not found in src/repo_fleet_manager/__init__.py")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("expected", nargs="?", help="Expected version, with or without a leading v")
    parser.add_argument("--root", default=".", help="Repository root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    package = package_version(root)
    runtime = runtime_version(root)
    expected = args.expected.removeprefix("v") if args.expected else package

    errors: list[str] = []
    if package != runtime:
        errors.append(f"pyproject version {package!r} != runtime version {runtime!r}")
    if package != expected:
        errors.append(f"package version {package!r} != expected release version {expected!r}")

    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        return 2

    print(f"[OK] release version {package}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

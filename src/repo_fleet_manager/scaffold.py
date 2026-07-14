from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from . import __version__
from .schema import migrate_config_data, validate_or_raise


BOOTSTRAP_LOCK_VERSION = "1"
DEFAULT_LOCK_FILE = "repo-fleet.lock.json"
SUPPORTED_REPOSITORY_TEMPLATES = ("generic", "python-cli", "python-service", "node-service")
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ScaffoldError(ValueError):
    """Raised when a scaffold request is unsafe or invalid."""


@dataclass(slots=True)
class ScaffoldResult:
    target: Path
    written: list[str]
    skipped: list[str]
    config_path: Path | None = None
    lock_path: Path | None = None


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_relative_path(value: str, *, label: str = "path") -> str:
    text = value.strip().replace("\\", "/")
    if not text:
        raise ScaffoldError(f"{label} must not be empty")
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        raise ScaffoldError(f"{label} must be a portable relative path: {value!r}")
    normalized = path.as_posix()
    if normalized in {".", ""}:
        return "."
    return normalized


def _validate_name(name: str, *, label: str = "name") -> str:
    if not _NAME_RE.fullmatch(name):
        raise ScaffoldError(f"{label} must match {_NAME_RE.pattern}: {name!r}")
    return name


def _package_name(name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_]", "_", name.replace("-", "_"))
    if value and value[0].isdigit():
        value = f"pkg_{value}"
    return value.lower() or "service"


def _class_name(name: str) -> str:
    chunks = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(chunk[:1].upper() + chunk[1:] for chunk in chunks if chunk) or "Project"


def _mit_license(owner: str) -> str:
    return f"""MIT License

Copyright (c) 2026 {owner}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the \"Software\"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


def _provider_config(provider: str, namespace: str) -> dict[str, Any]:
    if provider == "github":
        return {
            "type": "remote",
            "driver": "github",
            "namespace": namespace,
            "host": "github.com",
            "cli": "gh",
            "required_scopes": ["repo"],
            "url_template": "git@github.com:{namespace}/{repo}.git",
        }
    if provider == "gitlab":
        return {
            "type": "remote",
            "driver": "gitlab",
            "namespace": namespace,
            "host": "gitlab.com",
            "cli": "glab",
            "required_scopes": ["api", "write_repository"],
            "url_template": "git@gitlab.com:{namespace}/{repo}.git",
        }
    if provider == "local":
        return {
            "type": "local",
            "driver": "local",
            "namespace": ".repo-fleet/remotes",
            "cli": "git",
            "url_template": "file://{root}/{namespace}/{repo}.git",
        }
    raise ScaffoldError(f"unsupported provider: {provider}")


def new_project_config(
    name: str,
    *,
    branch: str,
    provider: str,
    namespace: str,
    visibility: str,
    description: str | None = None,
) -> dict[str, Any]:
    _validate_name(name, label="project name")
    _validate_name(branch, label="branch")
    providers: dict[str, Any] = {
        "local": _provider_config("local", ".repo-fleet/remotes"),
    }
    if provider != "local":
        providers[provider] = _provider_config(provider, namespace)
    config = {
        "schema_version": "1.0.0",
        "project": {
            "name": name,
            "description": description or f"{name} repository fleet managed by RFM.",
            "default_provider": provider,
            "default_branch": branch,
            "env_prefix": re.sub(r"[^A-Za-z0-9_]", "_", name).upper(),
            "build_dir": ".repo-fleet/build",
        },
        "providers": providers,
        "repositories": [
            {
                "path": ".",
                "repo": name,
                "kind": "root",
                "provider": provider,
                "branch": branch,
                "description": description or f"Root repository for {name}.",
                "source_type": "new",
                "remote_mode": "create",
                "depends_on": [],
                "visibility": visibility,
                "tags": ["root", "platform"],
                "metadata": {
                    "scaffold_template": "project",
                    "generated_by": f"rfm/{__version__}",
                },
            }
        ],
        "groups": {
            "all": {"repositories": [name], "include_dependencies": True},
        },
        "local": {
            "remotes_dir": ".repo-fleet/remotes",
            "workspace_mode": "submodules",
            "operations_dir": ".repo-fleet/operations",
            "lock_file": ".repo-fleet/lock",
            "backups_dir": ".repo-fleet/backups",
            "backup_retention": 5,
            "backup_include_operations": False,
            "cache_dir": ".repo-fleet/cache",
            "cache_retention": 3,
            "default_jobs": 1,
        },
        "fingerprint": {
            "algorithm": "sha256",
            "short_length": 16,
            "exclude": [
                ".git",
                ".repo-fleet",
                ".venv",
                "venv",
                "build",
                "dist",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            ],
        },
    }
    validate_or_raise(config)
    return config


def _project_readme(name: str, description: str) -> str:
    return f"""# {name}

{description}

## Bootstrap

```bash
python3 -m pip install --user repo-fleet-manager
rfm bootstrap verify --config repo-fleet.json
rfm local --config repo-fleet.json bootstrap
rfm local --config repo-fleet.json bootstrap --apply --set-origin
```

The desired repository state lives in `repo-fleet.json`. The reproducible bootstrap
contract is tracked in `{DEFAULT_LOCK_FILE}`.
"""


def _project_ci() -> str:
    return """name: Repository Fleet Validation

on:
  push:
    branches: [main, master]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install Repo Fleet Manager
        run: python -m pip install 'repo-fleet-manager @ git+https://github.com/mhassanzadeh/repo-fleet-manager.git@v0.12.0'
      - name: Validate fleet configuration and bootstrap contract
        run: |
          rfm config --config repo-fleet.json validate --strict
          rfm bootstrap --config repo-fleet.json verify
"""


def project_files(name: str, config: dict[str, Any], *, owner: str, description: str) -> dict[str, str]:
    return {
        "README.md": _project_readme(name, description),
        "LICENSE": _mit_license(owner),
        ".gitignore": """.repo-fleet/\n.venv/\nvenv/\n__pycache__/\n*.py[cod]\nbuild/\ndist/\n.env\n.env.*\n!.env.example\n""",
        ".github/workflows/ci.yml": _project_ci(),
        "repo-fleet.json": _pretty_json(config),
    }


def _template_metadata(name: str, template: str, kind: str) -> str:
    return _pretty_json({
        "schema": "rfm-scaffold-template/v1",
        "name": name,
        "template": template,
        "kind": kind,
        "generated_by": f"rfm/{__version__}",
    })


def repository_template_files(
    name: str,
    *,
    template: str,
    kind: str,
    description: str,
    owner: str,
) -> dict[str, str]:
    if template not in SUPPORTED_REPOSITORY_TEMPLATES:
        raise ScaffoldError(f"unknown repository template: {template}")
    package = _package_name(name)
    common = {
        "README.md": f"# {name}\n\n{description}\n",
        ".rfm-template.json": _template_metadata(name, template, kind),
        "LICENSE": _mit_license(owner),
    }
    if template == "generic":
        common[".gitignore"] = ".env\n.env.*\n!.env.example\n.DS_Store\n"
        return common
    if template == "python-cli":
        common.update({
            ".gitignore": ".venv/\nvenv/\n__pycache__/\n*.py[cod]\nbuild/\ndist/\n*.egg-info/\n.pytest_cache/\n",
            "pyproject.toml": f"""[build-system]\nrequires = [\"setuptools>=77\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"{name}\"\nversion = \"0.1.0\"\ndescription = \"{description}\"\nrequires-python = \">=3.11\"\nlicense = \"MIT\"\n\n[project.scripts]\n{name} = \"{package}.cli:main\"\n\n[tool.setuptools.packages.find]\nwhere = [\"src\"]\n""",
            f"src/{package}/__init__.py": '__version__ = "0.1.0"\n',
            f"src/{package}/cli.py": """from __future__ import annotations\n\n\ndef main() -> int:\n    print(\"ready\")\n    return 0\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n""",
            "tests/test_smoke.py": f"""import unittest\n\nfrom {package}.cli import main\n\n\nclass SmokeTest(unittest.TestCase):\n    def test_main(self):\n        self.assertEqual(main(), 0)\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n""",
            ".github/workflows/ci.yml": _python_ci(),
        })
        return common
    if template == "python-service":
        common.update({
            ".gitignore": ".venv/\nvenv/\n__pycache__/\n*.py[cod]\nbuild/\ndist/\n*.egg-info/\n.pytest_cache/\n",
            "pyproject.toml": f"""[build-system]\nrequires = [\"setuptools>=77\"]\nbuild-backend = \"setuptools.build_meta\"\n\n[project]\nname = \"{name}\"\nversion = \"0.1.0\"\ndescription = \"{description}\"\nrequires-python = \">=3.11\"\nlicense = \"MIT\"\n\n[tool.setuptools.packages.find]\nwhere = [\"src\"]\n""",
            f"src/{package}/__init__.py": '__version__ = "0.1.0"\n',
            f"src/{package}/app.py": """from __future__ import annotations\n\n\ndef health() -> dict[str, str]:\n    return {\"status\": \"ok\"}\n""",
            "tests/test_app.py": f"""import unittest\n\nfrom {package}.app import health\n\n\nclass AppTest(unittest.TestCase):\n    def test_health(self):\n        self.assertEqual(health(), {{\"status\": \"ok\"}})\n\n\nif __name__ == \"__main__\":\n    unittest.main()\n""",
            "Dockerfile": f"""FROM python:3.12-slim\nWORKDIR /app\nCOPY . .\nRUN python -m pip install --no-cache-dir .\nCMD [\"python\", \"-c\", \"from {package}.app import health; print(health())\"]\n""",
            ".github/workflows/ci.yml": _python_ci(),
        })
        return common
    common.update({
        ".gitignore": "node_modules/\ncoverage/\ndist/\n.env\n.env.*\n!.env.example\n",
        "package.json": _pretty_json({
            "name": name,
            "version": "0.1.0",
            "private": True,
            "type": "module",
            "scripts": {"start": "node src/index.js", "test": "node --test"},
            "engines": {"node": ">=20"},
        }),
        "src/index.js": "export function health() { return { status: 'ok' }; }\n\nif (import.meta.url === `file://${process.argv[1]}`) {\n  console.log(JSON.stringify(health()));\n}\n",
        "test/smoke.test.js": "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { health } from '../src/index.js';\n\ntest('health', () => assert.deepEqual(health(), { status: 'ok' }));\n",
        "Dockerfile": "FROM node:22-alpine\nWORKDIR /app\nCOPY package.json ./\nCOPY src ./src\nCMD [\"node\", \"src/index.js\"]\n",
        ".github/workflows/ci.yml": """name: CI\non:\n  push:\n  pull_request:\npermissions:\n  contents: read\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n      - uses: actions/setup-node@v4\n        with:\n          node-version: '22'\n      - run: npm test\n""",
    })
    return common


def _python_ci() -> str:
    return """name: CI
on:
  push:
  pull_request:
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install -e .
      - run: python -m unittest discover -s tests
"""


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _apply_files(root: Path, files: dict[str, str], *, apply: bool, force: bool) -> tuple[list[str], list[str]]:
    written: list[str] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    for relative, content in files.items():
        relative = _safe_relative_path(relative, label="template file")
        target = root / relative
        if target.exists():
            if target.is_dir():
                conflicts.append(relative)
                continue
            if target.read_text(encoding="utf-8") == content:
                skipped.append(relative)
                continue
            if not force:
                conflicts.append(relative)
    if conflicts:
        raise ScaffoldError("refusing to overwrite existing files without --force: " + ", ".join(sorted(conflicts)))
    for relative, content in files.items():
        relative = _safe_relative_path(relative, label="template file")
        target = root / relative
        if target.exists() and target.is_file() and target.read_text(encoding="utf-8") == content:
            continue
        print(f"[{'WRITE' if apply else 'DRY-RUN'}] {target}")
        if apply:
            _atomic_write(target, content)
        written.append(relative)
    return written, skipped


def _apply_files_transaction(
    root: Path,
    files: dict[str, str],
    *,
    apply: bool,
    force: bool,
    managed_overwrites: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    managed_overwrites = managed_overwrites or set()
    normalized: dict[str, str] = {
        _safe_relative_path(relative, label="template file"): content
        for relative, content in files.items()
    }
    written: list[str] = []
    skipped: list[str] = []
    conflicts: list[str] = []
    for relative, content in normalized.items():
        target = root / relative
        if target.exists() and not target.is_file():
            conflicts.append(relative)
        elif target.is_file() and target.read_text(encoding="utf-8") == content:
            skipped.append(relative)
        elif target.exists() and relative not in managed_overwrites and not force:
            conflicts.append(relative)
    if conflicts:
        raise ScaffoldError("refusing to overwrite existing files without --force: " + ", ".join(sorted(conflicts)))
    for relative in normalized:
        if relative in skipped:
            continue
        print(f"[{'WRITE' if apply else 'DRY-RUN'}] {root / relative}")
        written.append(relative)
    if not apply:
        return written, skipped

    backups: dict[Path, bytes | None] = {}
    created_parents: set[Path] = set()
    try:
        for relative in written:
            target = root / relative
            backups[target] = target.read_bytes() if target.is_file() else None
            parent = target.parent
            while parent != root and not parent.exists():
                created_parents.add(parent)
                parent = parent.parent
            _atomic_write(target, normalized[relative])
    except Exception:
        for target, previous in reversed(list(backups.items())):
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(previous)
        for parent in sorted(created_parents, key=lambda value: len(value.parts), reverse=True):
            try:
                parent.rmdir()
            except OSError:
                pass
        raise
    return written, skipped


def _git_init(target: Path, branch: str) -> None:
    if (target / ".git").exists():
        return
    result = subprocess.run(["git", "init", "-b", branch], cwd=target, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        result = subprocess.run(["git", "init"], cwd=target, check=False, text=True, capture_output=True)
        if result.returncode == 0:
            subprocess.run(["git", "checkout", "-B", branch], cwd=target, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise ScaffoldError(result.stderr.strip() or "git init failed")


def _lock_file_candidates(config: dict[str, Any], root: Path, virtual_files: dict[str, str] | None = None) -> dict[str, str]:
    virtual_files = virtual_files or {}
    candidates = {"repo-fleet.json", "README.md", "LICENSE", ".gitignore", ".github/workflows/ci.yml"}
    for repo in config.get("repositories", []):
        repo_path = _safe_relative_path(str(repo.get("path") or "."), label="repository path")
        if repo_path != ".":
            candidates.add(f"{repo_path}/.rfm-template.json")
    files: dict[str, str] = {}
    for relative in sorted(candidates):
        if relative in virtual_files:
            files[relative] = _sha256_bytes(virtual_files[relative].encode("utf-8"))
            continue
        path = root / relative
        if path.is_file():
            files[relative] = _sha256_file(path)
    return files


def build_bootstrap_lock(
    config: dict[str, Any],
    *,
    root: Path,
    virtual_files: dict[str, str] | None = None,
) -> dict[str, Any]:
    migrated, _ = migrate_config_data(config)
    validate_or_raise(migrated)
    repositories: list[dict[str, Any]] = []
    for item in migrated.get("repositories", []):
        path = _safe_relative_path(str(item.get("path") or "."), label="repository path")
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        repositories.append({
            "path": path,
            "repo": str(item.get("repo")),
            "kind": str(item.get("kind") or "module"),
            "provider": item.get("provider") or migrated.get("project", {}).get("default_provider"),
            "branch": str(item.get("branch") or migrated.get("project", {}).get("default_branch") or "main"),
            "source_type": str(item.get("source_type") or "new"),
            "remote_mode": str(item.get("remote_mode") or "create"),
            "depends_on": sorted(str(value) for value in (item.get("depends_on") or [])),
            "template": metadata.get("scaffold_template"),
        })
    repositories.sort(key=lambda row: (row["path"] != ".", row["path"], row["repo"]))
    portable_config = json.loads(json.dumps(migrated))
    return {
        "schema": "rfm-bootstrap-lock/v1",
        "lock_version": BOOTSTRAP_LOCK_VERSION,
        "generated_by": f"rfm/{__version__}",
        "config": {
            "path": "repo-fleet.json",
            "sha256": _sha256_bytes(_json_bytes(portable_config)),
            "schema_version": migrated.get("schema_version"),
        },
        "project": {
            "name": migrated.get("project", {}).get("name"),
            "default_provider": migrated.get("project", {}).get("default_provider"),
            "default_branch": migrated.get("project", {}).get("default_branch"),
        },
        "repositories": repositories,
        "files": _lock_file_candidates(migrated, root, virtual_files),
    }


def bootstrap_lock_content(config: dict[str, Any], *, root: Path, virtual_files: dict[str, str] | None = None) -> str:
    return _pretty_json(build_bootstrap_lock(config, root=root, virtual_files=virtual_files))


def write_bootstrap_lock(
    config: dict[str, Any],
    *,
    root: Path,
    output: str = DEFAULT_LOCK_FILE,
    apply: bool,
    force: bool = False,
    virtual_files: dict[str, str] | None = None,
) -> Path:
    relative = _safe_relative_path(output, label="lock output")
    path = root / relative
    content = bootstrap_lock_content(config, root=root, virtual_files=virtual_files)
    if path.exists() and not path.is_file():
        raise ScaffoldError(f"lock output is not a regular file: {path}")
    if path.is_symlink() and not force:
        raise ScaffoldError(f"refusing to replace a symlink without --force: {path}")
    print(f"[{'WRITE' if apply else 'DRY-RUN'}] {path}")
    if apply:
        _atomic_write(path, content)
    return path


def verify_bootstrap_lock(config: dict[str, Any], *, root: Path, lock_file: str = DEFAULT_LOCK_FILE) -> dict[str, Any]:
    relative = _safe_relative_path(lock_file, label="lock file")
    path = root / relative
    if not path.is_file():
        return {"valid": False, "lock": str(path), "issues": [f"missing lock file: {relative}"]}
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "lock": str(path), "issues": [f"cannot read lock file: {exc}"]}
    issues: list[str] = []
    if stored.get("schema") != "rfm-bootstrap-lock/v1":
        issues.append(f"unsupported lock schema: {stored.get('schema')!r}")
    expected = build_bootstrap_lock(config, root=root)
    stored_config = stored.get("config") if isinstance(stored.get("config"), dict) else {}
    if stored_config.get("sha256") != expected["config"]["sha256"]:
        issues.append("configuration digest mismatch; regenerate the bootstrap lock")
    if stored.get("repositories") != expected.get("repositories"):
        issues.append("repository contract mismatch; regenerate the bootstrap lock")
    stored_files = stored.get("files") if isinstance(stored.get("files"), dict) else {}
    expected_files = expected.get("files") or {}
    for relative_path in sorted(set(stored_files) | set(expected_files)):
        try:
            safe = _safe_relative_path(str(relative_path), label="locked file")
        except ScaffoldError as exc:
            issues.append(str(exc))
            continue
        if relative_path not in stored_files:
            issues.append(f"file is missing from bootstrap lock: {safe}")
            continue
        if relative_path not in expected_files:
            issues.append(f"stale file entry in bootstrap lock: {safe}")
            continue
        file_path = root / safe
        if not file_path.is_file():
            issues.append(f"missing locked file: {safe}")
        elif stored_files[relative_path] != expected_files[relative_path]:
            issues.append(f"locked file digest mismatch: {safe}")
    serialized = json.dumps(stored, ensure_ascii=False)
    if str(root.resolve()) in serialized:
        issues.append("lock file contains an absolute workspace path")
    return {
        "valid": not issues,
        "lock": str(path),
        "project": stored.get("project", {}).get("name") if isinstance(stored.get("project"), dict) else None,
        "repositories": len(stored.get("repositories") or []),
        "files": len(stored.get("files") or {}),
        "issues": issues,
    }


def init_project(
    name: str,
    *,
    directory: Path,
    branch: str = "main",
    provider: str = "local",
    namespace: str = "",
    visibility: str = "private",
    description: str | None = None,
    owner: str = "Project Contributors",
    apply: bool = False,
    force: bool = False,
    git_init: bool = True,
) -> ScaffoldResult:
    name = _validate_name(name, label="project name")
    if provider != "local" and not namespace:
        raise ScaffoldError(f"--namespace is required for provider {provider}")
    if visibility not in {"private", "public", "internal"}:
        raise ScaffoldError(f"unsupported visibility: {visibility}")
    target = directory.expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise ScaffoldError(f"project target is not a directory: {target}")
    if target.is_dir() and not force:
        allowed = {"README.md", "LICENSE", ".gitignore", ".github", ".git", "repo-fleet.json", DEFAULT_LOCK_FILE}
        unexpected = sorted(item.name for item in target.iterdir() if item.name not in allowed)
        if unexpected:
            raise ScaffoldError("project target contains unmanaged files; use --force: " + ", ".join(unexpected))
    config = new_project_config(
        name,
        branch=branch,
        provider=provider,
        namespace=namespace,
        visibility=visibility,
        description=description,
    )
    desc = description or f"{name} repository fleet managed by RFM."
    files = project_files(name, config, owner=owner, description=desc)
    lock_content = bootstrap_lock_content(config, root=target, virtual_files=files)
    files[DEFAULT_LOCK_FILE] = lock_content
    written, skipped = _apply_files(target, files, apply=apply, force=force)
    if apply and git_init:
        _git_init(target, branch)
    return ScaffoldResult(
        target=target,
        written=written,
        skipped=skipped,
        config_path=target / "repo-fleet.json",
        lock_path=target / DEFAULT_LOCK_FILE,
    )


def _split_values(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        for item in value.split(","):
            item = item.strip()
            if item and item not in result:
                result.append(item)
    return result


def scaffold_repository(
    config_path: Path,
    *,
    root: Path,
    name: str,
    path: str,
    template: str,
    kind: str,
    description: str | None,
    branch: str | None,
    provider: str | None,
    visibility: str | None,
    tags: Iterable[str] | None,
    depends_on: Iterable[str] | None,
    owner: str,
    apply: bool,
    force: bool,
    update_lock: bool = True,
) -> ScaffoldResult:
    name = _validate_name(name, label="repository name")
    relative_path = _safe_relative_path(path, label="repository path")
    if relative_path == ".":
        raise ScaffoldError("repository scaffold path cannot be the project root")
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    config, _ = migrate_config_data(raw)
    validate_or_raise(config)
    project = config.get("project") or {}
    repositories = list(config.get("repositories") or [])
    known = {str(item.get("repo")) for item in repositories} | {str(item.get("path")) for item in repositories}
    if name in known or relative_path in known:
        raise ScaffoldError(f"repository already exists in config: {name} / {relative_path}")
    selected_provider = provider or project.get("default_provider")
    if selected_provider not in (config.get("providers") or {}):
        raise ScaffoldError(f"unknown provider: {selected_provider}")
    selected_branch = branch or project.get("default_branch") or "main"
    entry: dict[str, Any] = {
        "path": relative_path,
        "repo": name,
        "kind": kind,
        "provider": selected_provider,
        "branch": selected_branch,
        "description": description or f"{name} generated from the {template} template.",
        "source_type": "new",
        "remote_mode": "create",
        "depends_on": _split_values(depends_on),
        "tags": _split_values(tags),
        "metadata": {
            "scaffold_template": template,
            "generated_by": f"rfm/{__version__}",
        },
    }
    if visibility:
        entry["visibility"] = visibility
    files = repository_template_files(
        name,
        template=template,
        kind=kind,
        description=entry["description"],
        owner=owner,
    )
    target = root / relative_path
    virtual_files = {f"{relative_path}/{key}": value for key, value in files.items()}
    config["repositories"] = [*repositories, entry]
    validate_or_raise(config)
    config_content = _pretty_json(config)
    virtual_files["repo-fleet.json"] = config_content
    lock_content = bootstrap_lock_content(config, root=root, virtual_files=virtual_files) if update_lock else None
    if lock_content is not None:
        virtual_files[DEFAULT_LOCK_FILE] = lock_content

    root_files = {"repo-fleet.json": config_content}
    if lock_content is not None:
        root_files[DEFAULT_LOCK_FILE] = lock_content
    if target.exists() and not target.is_dir():
        raise ScaffoldError(f"repository target is not a directory: {target}")
    if target.is_dir() and not force:
        generated_names = {PurePosixPath(relative).parts[0] for relative in files}
        unexpected = sorted(item.name for item in target.iterdir() if item.name not in generated_names)
        if unexpected:
            raise ScaffoldError("repository target contains unmanaged files; use --force: " + ", ".join(unexpected))

    all_files = {f"{relative_path}/{key}": value for key, value in files.items()}
    all_files.update(root_files)
    written, skipped = _apply_files_transaction(
        root,
        all_files,
        apply=apply,
        force=force,
        managed_overwrites={"repo-fleet.json", DEFAULT_LOCK_FILE},
    )
    return ScaffoldResult(
        target=target,
        written=written,
        skipped=skipped,
        config_path=config_path,
        lock_path=root / DEFAULT_LOCK_FILE if update_lock else None,
    )

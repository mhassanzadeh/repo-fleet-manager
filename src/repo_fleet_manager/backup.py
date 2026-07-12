from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from . import __version__
from .config import ProjectConfig
from .localops import local_bare_path, remotes_dir, resolve_under_root
from .operations import backup_file, backup_path, current_operation, operations_dir, track_created_path, utc_now
from .shell import run

BACKUP_FORMAT_VERSION = "1.0.0"
BACKUP_SUFFIX = ".rfm-backup.tar.gz"


class BackupError(RuntimeError):
    pass


@dataclass(slots=True)
class BackupVerification:
    archive: Path
    valid: bool
    project: str
    created_at: str
    repository_count: int
    file_count: int
    total_bytes: int
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "archive": str(self.archive),
            "valid": self.valid,
            "project": self.project,
            "created_at": self.created_at,
            "repository_count": self.repository_count,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "warnings": self.warnings,
        }


def backups_dir(config: ProjectConfig | None, root: Path, override: str | None = None) -> Path:
    configured = config.local.get("backups_dir") if config else None
    return resolve_under_root(root, override or configured or ".repo-fleet/backups")


def default_backup_path(config: ProjectConfig, root: Path, directory_override: str | None = None) -> Path:
    project = str(config.project.get("name") or "repo-fleet")
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    directory = backups_dir(config, root, directory_override)
    candidate = directory / f"{project}-{stamp}{BACKUP_SUFFIX}"
    sequence = 2
    while candidate.exists():
        candidate = directory / f"{project}-{stamp}-{sequence}{BACKUP_SUFFIX}"
        sequence += 1
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _files_under(root: Path) -> list[Path]:
    return sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.relative_to(root).as_posix())


def _copy_operations(source: Path, destination: Path) -> None:
    active = current_operation()
    active_id = active.id if active else None
    if not source.exists():
        return
    destination.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if active_id and (item.name == f"{active_id}.json" or item.name == active_id):
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, symlinks=False)
        elif item.is_file():
            shutil.copy2(item, target)


def _remote_metadata(path: Path, repo_name: str, branch: str) -> dict[str, Any]:
    if not path.exists():
        return {
            "repo": repo_name,
            "branch": branch,
            "present": False,
            "archive_path": f"payload/remotes/{path.name}",
            "head": None,
            "symbolic_head": None,
            "refs": [],
        }
    fsck = run(["git", f"--git-dir={path}", "fsck", "--full", "--no-progress"])
    if fsck.code != 0:
        raise BackupError(f"git fsck failed for {repo_name}: {fsck.stderr or fsck.stdout}")
    refs_result = run(["git", f"--git-dir={path}", "show-ref"])
    refs: list[dict[str, str]] = []
    if refs_result.code == 0:
        for line in refs_result.stdout.splitlines():
            sha, ref = line.split(" ", 1)
            refs.append({"name": ref, "sha": sha})
    head_result = run(["git", f"--git-dir={path}", "rev-parse", "--verify", "HEAD"])
    symbolic = run(["git", f"--git-dir={path}", "symbolic-ref", "HEAD"])
    return {
        "repo": repo_name,
        "branch": branch,
        "present": True,
        "archive_path": f"payload/remotes/{path.name}",
        "head": head_result.stdout.strip() if head_result.code == 0 else None,
        "symbolic_head": symbolic.stdout.strip() if symbolic.code == 0 else None,
        "refs": refs,
    }


def _write_checksums(stage: Path) -> int:
    entries: list[str] = []
    count = 0
    for path in _files_under(stage):
        relative = path.relative_to(stage).as_posix()
        if relative == "CHECKSUMS.sha256":
            continue
        entries.append(f"{_sha256(path)}  {relative}")
        count += 1
    (stage / "CHECKSUMS.sha256").write_text("\n".join(entries) + "\n", encoding="utf-8")
    return count


def _create_tar(stage: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_output = output.with_name(f".{output.name}.{os.getpid()}.tmp")
    try:
        with tarfile.open(temp_output, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for name in ("manifest.json", "CHECKSUMS.sha256", "payload"):
                path = stage / name
                if path.exists():
                    archive.add(path, arcname=name, recursive=True)
        temp_output.replace(output)
    finally:
        temp_output.unlink(missing_ok=True)


def create_backup(
    config: ProjectConfig,
    root: Path,
    remotes_override: str | None = None,
    output: str | None = None,
    backups_override: str | None = None,
    include_operations: bool = False,
    retention: int | None = None,
    apply: bool = False,
    json_output: bool = False,
) -> int:
    root = root.resolve()
    remotes = remotes_dir(config, root, remotes_override)
    destination = Path(output).expanduser() if output else default_backup_path(config, root, backups_override)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if not destination.name.endswith(BACKUP_SUFFIX):
        raise BackupError(f"backup output must end with {BACKUP_SUFFIX}: {destination}")
    keep = retention if retention is not None else int(config.local.get("backup_retention") or 5)
    if keep < 1:
        raise BackupError("retention must be at least 1")

    plan = {
        "archive": str(destination),
        "root": str(root),
        "remotes": str(remotes),
        "include_operations": include_operations,
        "retention": keep,
        "repositories": [repo.repo for repo in config.repositories],
    }
    if not apply:
        if json_output:
            print(json.dumps({**plan, "dry_run": True}, ensure_ascii=False, indent=2))
        else:
            print(f"[BACKUP] {destination}")
            print(f"         remotes={remotes}")
            print(f"         repositories={len(config.repositories)} include_operations={include_operations} retention={keep}")
            print("[DRY-RUN] no archive was written; add --apply")
        return 0

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise BackupError(f"backup archive already exists: {destination}")
    track_created_path(destination)

    with tempfile.TemporaryDirectory(prefix="rfm-backup-") as temp:
        stage = Path(temp)
        payload = stage / "payload"
        config_dir = payload / "config"
        config_dir.mkdir(parents=True)
        shutil.copy2(config.path, config_dir / "repo-fleet.json")

        workspace = payload / "workspace"
        workspace.mkdir(parents=True)
        gitmodules = root / ".gitmodules"
        if gitmodules.exists():
            shutil.copy2(gitmodules, workspace / ".gitmodules")

        remote_payload = payload / "remotes"
        remote_payload.mkdir(parents=True)
        repositories: list[dict[str, Any]] = []
        missing: list[str] = []
        for repo in config.repositories:
            source = local_bare_path(repo, remotes)
            metadata = _remote_metadata(source, repo.repo, repo.branch)
            repositories.append(metadata)
            if source.exists():
                shutil.copytree(source, remote_payload / source.name, symlinks=False)
            else:
                missing.append(repo.repo)

        if include_operations:
            _copy_operations(operations_dir(root, config.local.get("operations_dir")), payload / "operations")

        manifest = {
            "format_version": BACKUP_FORMAT_VERSION,
            "tool_version": __version__,
            "created_at": utc_now(),
            "project": {
                "name": str(config.project.get("name") or "repo-fleet"),
                "description": config.project.get("description"),
                "default_branch": config.project.get("default_branch"),
            },
            "config_schema_version": config.schema_version,
            "config_file": "payload/config/repo-fleet.json",
            "remotes_dir": str(config.local.get("remotes_dir") or ".repo-fleet/remotes"),
            "operations_dir": str(config.local.get("operations_dir") or ".repo-fleet/operations"),
            "include_operations": include_operations,
            "repositories": repositories,
            "missing_remotes": missing,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        file_count = _write_checksums(stage)
        _create_tar(stage, destination)

    pruned: list[str] = []
    siblings = sorted(destination.parent.glob(f"*{BACKUP_SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in siblings[keep:]:
        if old.resolve() == destination.resolve():
            continue
        backup_file(old)
        old.unlink()
        pruned.append(str(old))

    result = {
        **plan,
        "dry_run": False,
        "file_count": file_count,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "missing_remotes": missing,
        "pruned": pruned,
    }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] backup created: {destination}")
        print(f"     sha256={result['sha256']} size={result['size_bytes']} files={file_count}")
        if missing:
            print(f"[WARN] configured local remotes not present: {', '.join(missing)}")
        for item in pruned:
            print(f"[PRUNE] {item}")
    return 0


def _validate_member(member: tarfile.TarInfo) -> None:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts:
        raise BackupError(f"unsafe archive member: {member.name}")
    if member.issym() or member.islnk() or member.isdev():
        raise BackupError(f"unsupported archive member type: {member.name}")


def _extract_archive(archive_path: Path, destination: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                _validate_member(member)
            for member in members:
                target = destination / member.name
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    raise BackupError(f"unsupported archive member type: {member.name}")
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    raise BackupError(f"cannot extract archive member: {member.name}")
                with source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                target.chmod(member.mode & 0o777)
    except (tarfile.TarError, OSError) as exc:
        raise BackupError(f"cannot read backup archive {archive_path}: {exc}") from exc


def _parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    if not path.exists():
        raise BackupError("backup does not contain CHECKSUMS.sha256")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise BackupError(f"invalid checksum line {number}")
        checksums[parts[1]] = parts[0]
    return checksums


def _verify_extracted(archive_path: Path, extracted: Path) -> BackupVerification:
    manifest_path = extracted / "manifest.json"
    if not manifest_path.exists():
        raise BackupError("backup does not contain manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise BackupError(
            f"unsupported backup format {manifest.get('format_version')!r}; expected {BACKUP_FORMAT_VERSION}"
        )
    checksums = _parse_checksums(extracted / "CHECKSUMS.sha256")
    actual_files = {
        path.relative_to(extracted).as_posix(): path
        for path in _files_under(extracted)
        if path.relative_to(extracted).as_posix() != "CHECKSUMS.sha256"
    }
    missing = sorted(set(checksums) - set(actual_files))
    unlisted = sorted(set(actual_files) - set(checksums))
    if missing:
        raise BackupError(f"backup files missing: {', '.join(missing)}")
    if unlisted:
        raise BackupError(f"backup contains unlisted files: {', '.join(unlisted)}")
    total = 0
    for relative, expected in checksums.items():
        path = actual_files[relative]
        actual = _sha256(path)
        if actual != expected:
            raise BackupError(f"checksum mismatch: {relative}")
        total += path.stat().st_size

    warnings: list[str] = []
    repositories = manifest.get("repositories") or []
    for repo in repositories:
        if not repo.get("present"):
            warnings.append(f"remote missing at backup time: {repo.get('repo')}")
            continue
        remote = extracted / str(repo["archive_path"])
        fsck = run(["git", f"--git-dir={remote}", "fsck", "--full", "--no-progress"])
        if fsck.code != 0:
            raise BackupError(f"restored remote failed git fsck: {repo.get('repo')}: {fsck.stderr or fsck.stdout}")
        refs = run(["git", f"--git-dir={remote}", "show-ref"])
        actual_refs: dict[str, str] = {}
        if refs.code == 0:
            for line in refs.stdout.splitlines():
                sha, name = line.split(" ", 1)
                actual_refs[name] = sha
        for expected_ref in repo.get("refs") or []:
            if actual_refs.get(expected_ref["name"]) != expected_ref["sha"]:
                raise BackupError(f"ref mismatch for {repo.get('repo')}: {expected_ref['name']}")

    return BackupVerification(
        archive=archive_path,
        valid=True,
        project=str((manifest.get("project") or {}).get("name") or ""),
        created_at=str(manifest.get("created_at") or ""),
        repository_count=len(repositories),
        file_count=len(actual_files),
        total_bytes=total,
        warnings=warnings,
    )


def verify_backup(archive: str | Path, json_output: bool = False) -> int:
    archive_path = Path(archive).expanduser().resolve()
    if not archive_path.is_file():
        raise BackupError(f"backup archive not found: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="rfm-verify-") as temp:
        extracted = Path(temp)
        _extract_archive(archive_path, extracted)
        report = _verify_extracted(archive_path, extracted)
    if json_output:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"[OK] backup verified: {archive_path}")
        print(
            f"     project={report.project} created={report.created_at} "
            f"repositories={report.repository_count} files={report.file_count} bytes={report.total_bytes}"
        )
        for warning in report.warnings:
            print(f"[WARN] {warning}")
    return 0


def list_backups(config: ProjectConfig | None, root: Path, directory_override: str | None = None, json_output: bool = False) -> int:
    directory = backups_dir(config, root, directory_override)
    rows: list[dict[str, Any]] = []
    if directory.exists():
        for path in sorted(directory.glob(f"*{BACKUP_SUFFIX}"), key=lambda p: p.stat().st_mtime, reverse=True):
            rows.append({
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
                "sha256": _sha256(path),
            })
    if json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif not rows:
        print(f"No backups found in {directory}")
    else:
        print(f"Backups in {directory}")
        for row in rows:
            print(f"- {row['modified_at']}  {row['size_bytes']:>10} bytes  {row['path']}")
    return 0


def _replace_path(source: Path, target: Path, overwrite: bool) -> None:
    exists_nonempty = target.exists() and (not target.is_dir() or any(target.iterdir()))
    if exists_nonempty and not overwrite:
        raise BackupError(f"restore target already exists; use --overwrite: {target}")
    if target.exists():
        backup_path(target)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    else:
        track_created_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, target, symlinks=False)
    else:
        shutil.copy2(source, target)


def _merge_operations(source: Path, target: Path, overwrite: bool) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if destination.exists():
            if not overwrite:
                raise BackupError(f"operation history already exists; use --overwrite: {destination}")
            backup_path(destination)
            if destination.is_dir() and not destination.is_symlink():
                shutil.rmtree(destination)
            else:
                destination.unlink()
        else:
            track_created_path(destination)
        if item.is_dir():
            shutil.copytree(item, destination, symlinks=False)
        else:
            shutil.copy2(item, destination)


def restore_backup(
    archive: str | Path,
    root: Path,
    config: ProjectConfig | None = None,
    remotes_override: str | None = None,
    config_output: str | None = None,
    restore_config: bool = True,
    restore_operations: bool = False,
    overwrite: bool = False,
    force: bool = False,
    apply: bool = False,
    json_output: bool = False,
) -> int:
    archive_path = Path(archive).expanduser().resolve()
    root = root.resolve()
    if not archive_path.is_file():
        raise BackupError(f"backup archive not found: {archive_path}")

    with tempfile.TemporaryDirectory(prefix="rfm-restore-") as temp:
        extracted = Path(temp)
        _extract_archive(archive_path, extracted)
        report = _verify_extracted(archive_path, extracted)
        manifest = json.loads((extracted / "manifest.json").read_text(encoding="utf-8"))
        current_project = str(config.project.get("name") or "") if config else ""
        backup_project = str((manifest.get("project") or {}).get("name") or "")
        if current_project and backup_project and current_project != backup_project and not force:
            raise BackupError(
                f"backup project {backup_project!r} does not match current project {current_project!r}; "
                "use --force --reason after confirming the target"
            )

        configured_remotes = remotes_override
        if not configured_remotes and config:
            configured_remotes = str(config.local.get("remotes_dir") or "") or None
        if not configured_remotes:
            manifest_remotes = str(manifest.get("remotes_dir") or ".repo-fleet/remotes")
            configured_remotes = manifest_remotes if not Path(manifest_remotes).is_absolute() else ".repo-fleet/remotes"
        target_remotes = resolve_under_root(root, configured_remotes)
        target_config = Path(config_output).expanduser() if config_output else (config.path if config else root / "repo-fleet.json")
        if not target_config.is_absolute():
            target_config = (root / target_config).resolve()
        source_config = extracted / str(manifest.get("config_file") or "payload/config/repo-fleet.json")
        source_remotes = extracted / "payload/remotes"
        source_operations = extracted / "payload/operations"
        operations_value = config.local.get("operations_dir") if config else manifest.get("operations_dir")
        if not config and operations_value and Path(str(operations_value)).is_absolute():
            operations_value = ".repo-fleet/operations"
        target_operations = operations_dir(root, str(operations_value) if operations_value else None)

        plan = {
            "archive": str(archive_path),
            "project": backup_project,
            "target_root": str(root),
            "target_remotes": str(target_remotes),
            "target_config": str(target_config) if restore_config else None,
            "restore_operations": restore_operations and source_operations.exists(),
            "overwrite": overwrite,
            "repository_count": report.repository_count,
        }
        if not apply:
            if json_output:
                print(json.dumps({**plan, "dry_run": True}, ensure_ascii=False, indent=2))
            else:
                print(f"[RESTORE] {archive_path}")
                print(f"          target_root={root}")
                print(f"          remotes={target_remotes}")
                if restore_config:
                    print(f"          config={target_config}")
                print(f"          operations={restore_operations and source_operations.exists()} overwrite={overwrite}")
                print("[DRY-RUN] no files were restored; add --apply")
            return 0

        if not source_remotes.exists():
            raise BackupError("backup does not contain payload/remotes")
        _replace_path(source_remotes, target_remotes, overwrite=overwrite)
        if restore_config:
            if target_config.exists() and target_config.read_bytes() == source_config.read_bytes():
                pass
            else:
                _replace_path(source_config, target_config, overwrite=overwrite)
        if restore_operations and source_operations.exists():
            _merge_operations(source_operations, target_operations, overwrite=overwrite)

        # Verify the copied bare repositories, not only the temporary extraction.
        for repo in manifest.get("repositories") or []:
            if not repo.get("present"):
                continue
            restored = target_remotes / Path(str(repo["archive_path"])).name
            fsck = run(["git", f"--git-dir={restored}", "fsck", "--full", "--no-progress"])
            if fsck.code != 0:
                raise BackupError(f"restored remote failed git fsck: {repo.get('repo')}")
            refs_result = run(["git", f"--git-dir={restored}", "show-ref"])
            restored_refs: dict[str, str] = {}
            if refs_result.code == 0:
                for line in refs_result.stdout.splitlines():
                    sha, name = line.split(" ", 1)
                    restored_refs[name] = sha
            for expected_ref in repo.get("refs") or []:
                if restored_refs.get(expected_ref["name"]) != expected_ref["sha"]:
                    raise BackupError(f"restored ref mismatch for {repo.get('repo')}: {expected_ref['name']}")

    result = {**plan, "dry_run": False, "verified": True}
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] backup restored into {root}")
        print(f"     remotes={target_remotes} repositories={report.repository_count}")
        if restore_config:
            print(f"     config={target_config}")
    return 0

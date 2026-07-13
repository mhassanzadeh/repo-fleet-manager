from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

from . import __version__
from .config import ProjectConfig, Repository, load_config
from .images import detect_container_cli
from .localops import (
    existing_source_path,
    git_is_worktree,
    local_bare_path,
    local_bare_url,
    remotes_dir,
    resolve_under_root,
    upstream_source_url,
    localize,
)
from .operations import backup_file, backup_path, track_created_path, utc_now
from .shell import run, run_interactive

CACHE_FORMAT_VERSION = "1.0.0"
CACHE_SUFFIX = ".rfm-cache.tar.gz"


class OfflineCacheError(RuntimeError):
    pass


@dataclass(slots=True)
class CacheVerification:
    archive: Path
    valid: bool
    complete: bool
    project: str
    created_at: str
    repository_count: int
    image_count: int
    file_count: int
    total_bytes: int
    missing_repositories: list[str]
    missing_images: list[str]
    warnings: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "archive": str(self.archive),
            "valid": self.valid,
            "complete": self.complete,
            "project": self.project,
            "created_at": self.created_at,
            "repository_count": self.repository_count,
            "image_count": self.image_count,
            "file_count": self.file_count,
            "total_bytes": self.total_bytes,
            "missing_repositories": self.missing_repositories,
            "missing_images": self.missing_images,
            "warnings": self.warnings,
        }


def cache_dir(config: ProjectConfig | None, root: Path, override: str | None = None) -> Path:
    configured = config.local.get("cache_dir") if config else None
    return resolve_under_root(root, override or configured or ".repo-fleet/cache")


def default_cache_path(config: ProjectConfig, root: Path, directory_override: str | None = None) -> Path:
    project = str(config.project.get("name") or "repo-fleet")
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    directory = cache_dir(config, root, directory_override)
    candidate = directory / f"{project}-{stamp}{CACHE_SUFFIX}"
    sequence = 2
    while candidate.exists():
        candidate = directory / f"{project}-{stamp}-{sequence}{CACHE_SUFFIX}"
        sequence += 1
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-.")
    return text or "repository"


def _files_under(root: Path) -> list[Path]:
    return sorted((path for path in root.rglob("*") if path.is_file()), key=lambda p: p.relative_to(root).as_posix())


def _write_checksums(stage: Path) -> int:
    rows: list[str] = []
    for path in _files_under(stage):
        relative = path.relative_to(stage).as_posix()
        if relative == "CHECKSUMS.sha256":
            continue
        rows.append(f"{_sha256(path)}  {relative}")
    (stage / "CHECKSUMS.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")
    return len(rows)


def _create_tar(stage: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    try:
        with tarfile.open(temporary, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            for name in ("manifest.json", "CHECKSUMS.sha256", "payload"):
                source = stage / name
                if source.exists():
                    archive.add(source, arcname=name, recursive=True)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def _is_safe_member(member: tarfile.TarInfo) -> bool:
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if member.issym() or member.islnk() or member.isdev():
        return False
    return True


def _extract_archive(archive_path: Path, destination: Path) -> None:
    try:
        source = tarfile.open(archive_path, "r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise OfflineCacheError(f"invalid cache archive: {archive_path}") from exc
    with source:
        members = source.getmembers()
        for member in members:
            if not _is_safe_member(member):
                raise OfflineCacheError(f"unsafe archive member: {member.name}")
        source.extractall(destination, members=members, filter="data")


def _read_checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        raise OfflineCacheError("cache archive is missing CHECKSUMS.sha256")
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if "  " not in line:
            raise OfflineCacheError(f"invalid checksum row: {line}")
        digest, relative = line.split("  ", 1)
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise OfflineCacheError(f"invalid checksum digest: {digest}")
        result[relative] = digest
    return result


def _bundle_heads(bundle: Path) -> list[dict[str, str]]:
    result = run(["git", "bundle", "list-heads", str(bundle)])
    if result.code != 0:
        raise OfflineCacheError(f"invalid Git bundle {bundle.name}: {result.stderr or result.stdout}")
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        sha, ref = line.split(" ", 1)
        ref_name = ref.strip()
        # `git bundle list-heads` may expose the symbolic HEAD pseudo-ref.
        # Bare clones do not report it through `show-ref`, so only persist real refs.
        if ref_name == "HEAD":
            continue
        rows.append({"name": ref_name, "sha": sha.strip()})
    if not rows:
        raise OfflineCacheError(f"Git bundle does not contain refs: {bundle.name}")
    return rows


def _source_for_repo(config: ProjectConfig, root: Path, repo: Repository, remotes_override: str | None) -> tuple[Path | None, str | None, bool]:
    worktree = root if repo.is_root else root / repo.path
    if git_is_worktree(worktree):
        return worktree, "worktree", False
    remotes = remotes_dir(config, root, remotes_override)
    bare = local_bare_path(repo, remotes)
    if bare.exists() and run(["git", f"--git-dir={bare}", "rev-parse", "--is-bare-repository"]).stdout == "true":
        return bare, "local-bare", True
    if repo.source_type == "existing":
        existing = existing_source_path(repo, root)
        if existing and git_is_worktree(existing):
            return existing, "existing", False
    return None, None, False


def _create_bundle(source: Path, output: Path, bare: bool) -> list[dict[str, str]]:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["git", f"--git-dir={source}", "bundle", "create", str(output), "--all"] if bare else ["git", "bundle", "create", str(output), "--all"]
    result = run(command, cwd=None if bare else source)
    if result.code != 0:
        raise OfflineCacheError(f"failed to create Git bundle from {source}: {result.stderr or result.stdout}")
    return _bundle_heads(output)


def _fetch_upstream_bundle(repo: Repository, output: Path, temp: Path) -> list[dict[str, str]]:
    source = upstream_source_url(repo)
    if not source:
        raise OfflineCacheError(f"repository {repo.repo} has no available worktree, local mirror or upstream URL")
    mirror = temp / f"{_safe_slug(repo.repo)}.git"
    clone = run(["git", "clone", "--mirror", source, str(mirror)])
    if clone.code != 0:
        raise OfflineCacheError(f"failed to mirror {repo.repo} from {source}: {clone.stderr or clone.stdout}")
    return _create_bundle(mirror, output, bare=True)


def _configured_images(config: ProjectConfig, extra_images: Iterable[str] | None) -> list[str]:
    values: list[str] = []
    configured = config.compose.get("cache_images") or []
    if isinstance(configured, str):
        configured = [configured]
    for item in [*configured, *(extra_images or [])]:
        text = str(item).strip()
        if text and text not in values:
            values.append(text)
    return values


def _container_engine(config: ProjectConfig | None, preferred: str | None) -> str:
    selected = preferred
    if not selected and config:
        configured = config.compose.get("engine")
        selected = None if configured in {None, "", "auto"} else str(configured)
    return detect_container_cli(selected)


def _save_image(engine: str, image: str, output: Path) -> str | None:
    inspect = run([engine, "image", "inspect", image, "--format", "{{.Id}}"])
    if inspect.code != 0:
        raise OfflineCacheError(f"container image is not available locally: {image}")
    output.parent.mkdir(parents=True, exist_ok=True)
    saved = run([engine, "image", "save", "-o", str(output), image])
    if saved.code != 0:
        raise OfflineCacheError(f"failed to save image {image}: {saved.stderr or saved.stdout}")
    return inspect.stdout.strip() or None


def export_cache(
    config: ProjectConfig,
    root: Path,
    *,
    output: str | None = None,
    cache_override: str | None = None,
    remotes_override: str | None = None,
    images: Iterable[str] | None = None,
    include_images: bool = True,
    engine: str | None = None,
    fetch_missing: bool = False,
    allow_missing: bool = False,
    retention: int | None = None,
    apply: bool = False,
    json_output: bool = False,
) -> int:
    root = root.resolve()
    destination = Path(output).expanduser() if output else default_cache_path(config, root, cache_override)
    if not destination.is_absolute():
        destination = (root / destination).resolve()
    if not destination.name.endswith(CACHE_SUFFIX):
        raise OfflineCacheError(f"cache output must end with {CACHE_SUFFIX}: {destination}")
    keep = retention if retention is not None else int(config.local.get("cache_retention") or 3)
    if keep < 1:
        raise OfflineCacheError("cache retention must be at least 1")
    image_refs = _configured_images(config, images) if include_images else []
    plan = {
        "archive": str(destination),
        "root": str(root),
        "repositories": [repo.repo for repo in config.repositories],
        "images": image_refs,
        "fetch_missing": fetch_missing,
        "allow_missing": allow_missing,
        "retention": keep,
    }
    if not apply:
        payload = {**plan, "dry_run": True}
        if json_output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"[CACHE EXPORT] {destination}")
            print(f"               repositories={len(config.repositories)} images={len(image_refs)}")
            print(f"               fetch_missing={fetch_missing} allow_missing={allow_missing} retention={keep}")
            print("[DRY-RUN] no cache archive was written; add --apply")
        return 0
    if destination.exists():
        raise OfflineCacheError(f"cache archive already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    track_created_path(destination)

    missing_repositories: list[str] = []
    missing_images: list[str] = []
    repository_rows: list[dict[str, Any]] = []
    image_rows: list[dict[str, Any]] = []
    selected_engine: str | None = None

    with tempfile.TemporaryDirectory(prefix="rfm-cache-export-") as temp_name:
        temp = Path(temp_name)
        stage = temp / "stage"
        payload_dir = stage / "payload"
        config_dir = payload_dir / "config"
        bundles_dir = payload_dir / "git"
        images_dir = payload_dir / "images"
        config_dir.mkdir(parents=True)
        shutil.copy2(config.path, config_dir / "repo-fleet.json")

        for index, repo in enumerate(config.repositories, start=1):
            bundle_name = f"{index:04d}-{_safe_slug(repo.repo)}.bundle"
            bundle = bundles_dir / bundle_name
            source, source_kind, bare = _source_for_repo(config, root, repo, remotes_override)
            try:
                if source is not None:
                    heads = _create_bundle(source, bundle, bare=bare)
                elif fetch_missing and repo.source_type == "upstream":
                    heads = _fetch_upstream_bundle(repo, bundle, temp / "mirrors")
                    source_kind = "upstream-fetch"
                else:
                    raise OfflineCacheError(f"no local Git source is available for {repo.repo}")
            except OfflineCacheError as exc:
                if not allow_missing:
                    raise
                missing_repositories.append(repo.repo)
                repository_rows.append({
                    "repo": repo.repo,
                    "path": repo.path,
                    "branch": repo.branch,
                    "present": False,
                    "error": str(exc),
                })
                continue
            repository_rows.append({
                "repo": repo.repo,
                "path": repo.path,
                "branch": repo.branch,
                "present": True,
                "source_kind": source_kind,
                "archive_path": f"payload/git/{bundle_name}",
                "sha256": _sha256(bundle),
                "refs": heads,
            })

        if image_refs:
            selected_engine = _container_engine(config, engine)
            for index, image in enumerate(image_refs, start=1):
                archive_name = f"{index:04d}-{_safe_slug(image)}.tar"
                image_archive = images_dir / archive_name
                try:
                    image_id = _save_image(selected_engine, image, image_archive)
                except OfflineCacheError as exc:
                    if not allow_missing:
                        raise
                    missing_images.append(image)
                    image_rows.append({"reference": image, "present": False, "error": str(exc)})
                    continue
                image_rows.append({
                    "reference": image,
                    "present": True,
                    "engine": selected_engine,
                    "image_id": image_id,
                    "archive_path": f"payload/images/{archive_name}",
                    "sha256": _sha256(image_archive),
                })

        manifest = {
            "format_version": CACHE_FORMAT_VERSION,
            "tool_version": __version__,
            "created_at": utc_now(),
            "complete": not missing_repositories and not missing_images,
            "project": {
                "name": str(config.project.get("name") or "repo-fleet"),
                "description": config.project.get("description"),
                "default_branch": config.project.get("default_branch"),
            },
            "config_schema_version": config.schema_version,
            "config_file": "payload/config/repo-fleet.json",
            "remotes_dir": str(config.local.get("remotes_dir") or ".repo-fleet/remotes"),
            "repositories": repository_rows,
            "images": image_rows,
            "missing_repositories": missing_repositories,
            "missing_images": missing_images,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        file_count = _write_checksums(stage)
        _create_tar(stage, destination)

    siblings = sorted(destination.parent.glob(f"*{CACHE_SUFFIX}"), key=lambda path: path.stat().st_mtime, reverse=True)
    pruned: list[str] = []
    for old in siblings[keep:]:
        if old.resolve() == destination.resolve():
            continue
        backup_file(old)
        old.unlink()
        pruned.append(str(old))

    result = {
        **plan,
        "dry_run": False,
        "complete": not missing_repositories and not missing_images,
        "file_count": file_count,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination),
        "engine": selected_engine,
        "missing_repositories": missing_repositories,
        "missing_images": missing_images,
        "pruned": pruned,
    }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] offline cache exported: {destination}")
        print(f"     repositories={len(repository_rows) - len(missing_repositories)} images={len(image_rows) - len(missing_images)} complete={result['complete']}")
        print(f"     sha256={result['sha256']}")
        for name in missing_repositories:
            print(f"[WARN] missing repository: {name}")
        for name in missing_images:
            print(f"[WARN] missing image: {name}")
    return 0


def _verify_extracted(archive_path: Path, extracted: Path) -> CacheVerification:
    manifest_path = extracted / "manifest.json"
    if not manifest_path.is_file():
        raise OfflineCacheError("cache archive is missing manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise OfflineCacheError("cache manifest is invalid JSON") from exc
    if manifest.get("format_version") != CACHE_FORMAT_VERSION:
        raise OfflineCacheError(f"unsupported cache format: {manifest.get('format_version')}")

    checksums = _read_checksums(extracted / "CHECKSUMS.sha256")
    actual_files = {
        path.relative_to(extracted).as_posix(): path
        for path in _files_under(extracted)
        if path.relative_to(extracted).as_posix() != "CHECKSUMS.sha256"
    }
    if set(checksums) != set(actual_files):
        missing = sorted(set(checksums) - set(actual_files))
        unexpected = sorted(set(actual_files) - set(checksums))
        raise OfflineCacheError(f"cache file inventory mismatch: missing={missing} unexpected={unexpected}")
    total = 0
    for relative, expected in checksums.items():
        path = actual_files[relative]
        total += path.stat().st_size
        if _sha256(path) != expected:
            raise OfflineCacheError(f"checksum mismatch: {relative}")

    repositories = manifest.get("repositories") or []
    for row in repositories:
        if not row.get("present"):
            continue
        bundle = extracted / str(row.get("archive_path") or "")
        heads = _bundle_heads(bundle)
        actual = {item["name"]: item["sha"] for item in heads}
        expected = {item["name"]: item["sha"] for item in (row.get("refs") or [])}
        if actual != expected:
            raise OfflineCacheError(f"Git bundle refs do not match manifest: {row.get('repo')}")
        if row.get("sha256") and _sha256(bundle) != row["sha256"]:
            raise OfflineCacheError(f"Git bundle digest mismatch: {row.get('repo')}")

    images = manifest.get("images") or []
    for row in images:
        if not row.get("present"):
            continue
        image_archive = extracted / str(row.get("archive_path") or "")
        if not image_archive.is_file():
            raise OfflineCacheError(f"image archive is missing: {row.get('reference')}")
        if row.get("sha256") and _sha256(image_archive) != row["sha256"]:
            raise OfflineCacheError(f"image archive digest mismatch: {row.get('reference')}")

    missing_repositories = [str(item) for item in (manifest.get("missing_repositories") or [])]
    missing_images = [str(item) for item in (manifest.get("missing_images") or [])]
    warnings: list[str] = []
    if missing_repositories:
        warnings.append(f"missing repositories: {', '.join(missing_repositories)}")
    if missing_images:
        warnings.append(f"missing images: {', '.join(missing_images)}")
    complete = bool(manifest.get("complete")) and not missing_repositories and not missing_images
    return CacheVerification(
        archive=archive_path,
        valid=True,
        complete=complete,
        project=str((manifest.get("project") or {}).get("name") or ""),
        created_at=str(manifest.get("created_at") or ""),
        repository_count=sum(1 for row in repositories if row.get("present")),
        image_count=sum(1 for row in images if row.get("present")),
        file_count=len(actual_files),
        total_bytes=total,
        missing_repositories=missing_repositories,
        missing_images=missing_images,
        warnings=warnings,
    )


def verify_cache(archive: str | Path, *, require_complete: bool = False, json_output: bool = False) -> int:
    archive_path = Path(archive).expanduser().resolve()
    if not archive_path.is_file():
        raise OfflineCacheError(f"cache archive not found: {archive_path}")
    with tempfile.TemporaryDirectory(prefix="rfm-cache-verify-") as temp:
        extracted = Path(temp)
        _extract_archive(archive_path, extracted)
        report = _verify_extracted(archive_path, extracted)
    if json_output:
        print(json.dumps(report.as_dict(), ensure_ascii=False, indent=2))
    else:
        print(f"[OK] offline cache verified: {archive_path}")
        print(f"     project={report.project} complete={report.complete} repositories={report.repository_count} images={report.image_count}")
        print(f"     files={report.file_count} bytes={report.total_bytes}")
        for warning in report.warnings:
            print(f"[WARN] {warning}")
    if require_complete and not report.complete:
        return 2
    return 0


def list_caches(config: ProjectConfig | None, root: Path, directory_override: str | None = None, *, json_output: bool = False) -> int:
    directory = cache_dir(config, root, directory_override)
    rows: list[dict[str, Any]] = []
    if directory.exists():
        for path in sorted(directory.glob(f"*{CACHE_SUFFIX}"), key=lambda item: item.stat().st_mtime, reverse=True):
            rows.append({
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime)),
                "sha256": _sha256(path),
            })
    if json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    elif not rows:
        print(f"No offline caches found in {directory}")
    else:
        print(f"Offline caches in {directory}")
        for row in rows:
            print(f"- {row['modified_at']}  {row['size_bytes']:>10} bytes  {row['path']}")
    return 0


def _replace_path(source: Path, target: Path, overwrite: bool) -> None:
    exists_nonempty = target.exists() and (not target.is_dir() or any(target.iterdir()))
    if exists_nonempty and not overwrite:
        raise OfflineCacheError(f"import target already exists; use --overwrite: {target}")
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


def _clone_bundle(bundle: Path, target: Path, overwrite: bool) -> None:
    if target.exists():
        if not overwrite:
            raise OfflineCacheError(f"local remote already exists; use --overwrite: {target}")
        backup_path(target)
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    else:
        track_created_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    result = run(["git", "clone", "--mirror", str(bundle), str(target)])
    if result.code != 0:
        raise OfflineCacheError(f"failed to import Git bundle {bundle.name}: {result.stderr or result.stdout}")
    fsck = run(["git", f"--git-dir={target}", "fsck", "--full", "--no-progress"])
    if fsck.code != 0:
        raise OfflineCacheError(f"imported local remote failed git fsck: {target.name}")


def _load_image(engine: str, archive: Path) -> None:
    loaded = run([engine, "image", "load", "-i", str(archive)])
    if loaded.code != 0:
        raise OfflineCacheError(f"failed to load image archive {archive.name}: {loaded.stderr or loaded.stdout}")


def import_cache(
    archive: str | Path,
    root: Path,
    *,
    config: ProjectConfig | None = None,
    remotes_override: str | None = None,
    config_output: str | None = None,
    restore_config: bool = True,
    load_images: bool = True,
    engine: str | None = None,
    overwrite: bool = False,
    allow_incomplete: bool = False,
    apply: bool = False,
    json_output: bool = False,
) -> int:
    archive_path = Path(archive).expanduser().resolve()
    root = root.resolve()
    if not archive_path.is_file():
        raise OfflineCacheError(f"cache archive not found: {archive_path}")

    with tempfile.TemporaryDirectory(prefix="rfm-cache-import-") as temp:
        extracted = Path(temp)
        _extract_archive(archive_path, extracted)
        report = _verify_extracted(archive_path, extracted)
        manifest = json.loads((extracted / "manifest.json").read_text(encoding="utf-8"))
        if not report.complete and not allow_incomplete:
            raise OfflineCacheError("cache is incomplete; pass --allow-incomplete only after reviewing missing artifacts")
        current_project = str(config.project.get("name") or "") if config else ""
        cache_project = str((manifest.get("project") or {}).get("name") or "")
        if current_project and cache_project and current_project != cache_project:
            raise OfflineCacheError(f"cache project {cache_project!r} does not match current project {current_project!r}")

        remotes_value = remotes_override
        if not remotes_value and config:
            remotes_value = str(config.local.get("remotes_dir") or "") or None
        if not remotes_value:
            manifest_value = str(manifest.get("remotes_dir") or ".repo-fleet/remotes")
            remotes_value = manifest_value if not Path(manifest_value).is_absolute() else ".repo-fleet/remotes"
        target_remotes = resolve_under_root(root, remotes_value)
        source_config = extracted / str(manifest.get("config_file") or "payload/config/repo-fleet.json")
        target_config = Path(config_output).expanduser() if config_output else (config.path if config else root / "repo-fleet.json")
        if not target_config.is_absolute():
            target_config = (root / target_config).resolve()
        image_rows = [row for row in (manifest.get("images") or []) if row.get("present")]
        selected_engine = _container_engine(config, engine) if load_images and image_rows else None
        plan = {
            "archive": str(archive_path),
            "project": cache_project,
            "target_root": str(root),
            "target_remotes": str(target_remotes),
            "target_config": str(target_config) if restore_config else None,
            "repositories": report.repository_count,
            "images": report.image_count if load_images else 0,
            "engine": selected_engine,
            "complete": report.complete,
            "overwrite": overwrite,
        }
        if not apply:
            if json_output:
                print(json.dumps({**plan, "dry_run": True}, ensure_ascii=False, indent=2))
            else:
                print(f"[CACHE IMPORT] {archive_path}")
                print(f"               root={root}")
                print(f"               remotes={target_remotes}")
                print(f"               repositories={report.repository_count} images={plan['images']} complete={report.complete}")
                print("[DRY-RUN] no files or images were imported; add --apply")
            return 0

        target_remotes.mkdir(parents=True, exist_ok=True)
        for row in manifest.get("repositories") or []:
            if not row.get("present"):
                continue
            bundle = extracted / str(row["archive_path"])
            target = target_remotes / f"{row['repo']}.git"
            _clone_bundle(bundle, target, overwrite=overwrite)
            actual = run(["git", f"--git-dir={target}", "show-ref"])
            actual_refs: dict[str, str] = {}
            if actual.code == 0:
                for line in actual.stdout.splitlines():
                    sha, ref = line.split(" ", 1)
                    actual_refs[ref] = sha
            for expected in row.get("refs") or []:
                if actual_refs.get(expected["name"]) != expected["sha"]:
                    raise OfflineCacheError(f"imported ref mismatch for {row['repo']}: {expected['name']}")

        if restore_config:
            if target_config.exists() and target_config.read_bytes() == source_config.read_bytes():
                pass
            else:
                _replace_path(source_config, target_config, overwrite=overwrite)

        if selected_engine:
            for row in image_rows:
                _load_image(selected_engine, extracted / str(row["archive_path"]))

    result = {**plan, "dry_run": False, "verified": True}
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] offline cache imported into {root}")
        print(f"     remotes={target_remotes} repositories={report.repository_count} images={plan['images']}")
        if restore_config:
            print(f"     config={target_config}")
    return 0


def _materialize_root_from_cache(config: ProjectConfig, root: Path, remotes_override: str | None, apply: bool) -> int:
    root_repo = config.root_repository
    if root_repo is None:
        raise OfflineCacheError("cache config does not define a root repository")
    remotes = remotes_dir(config, root, remotes_override)
    source = local_bare_path(root_repo, remotes)
    if not source.exists():
        raise OfflineCacheError(f"root repository bundle was not imported: {root_repo.repo}")
    if git_is_worktree(root):
        return 0
    if not apply:
        print(f"[DRY-RUN] materialize root {root_repo.repo} from {source}")
        return 0
    root.mkdir(parents=True, exist_ok=True)
    for path in list(root.iterdir()):
        if path.name == ".repo-fleet":
            continue
        if path.name == "repo-fleet.json":
            path.unlink()
        else:
            raise OfflineCacheError(f"air-gap bootstrap root is not empty: {path}")
    commands = [
        ["git", "init", "-b", root_repo.branch],
        ["git", "remote", "add", "origin", local_bare_url(root_repo, remotes)],
        ["git", "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*", "+refs/tags/*:refs/tags/*"],
        ["git", "checkout", "-B", root_repo.branch, f"refs/remotes/origin/{root_repo.branch}"],
    ]
    for command in commands:
        code = run_interactive(command, cwd=root, dry_run=False)
        if code != 0:
            return code
    return 0


def bootstrap_from_cache(
    archive: str | Path,
    root: Path,
    *,
    remotes_override: str | None = None,
    load_images: bool = True,
    engine: str | None = None,
    overwrite: bool = False,
    allow_incomplete: bool = False,
    jobs: int = 1,
    apply: bool = False,
    json_output: bool = False,
) -> int:
    root = root.resolve()
    if not apply:
        return import_cache(
            archive,
            root,
            remotes_override=remotes_override,
            restore_config=True,
            load_images=load_images,
            engine=engine,
            overwrite=overwrite,
            allow_incomplete=allow_incomplete,
            apply=False,
            json_output=json_output,
        )

    # Import sources first without writing config into the not-yet-materialized root.
    import_cache(
        archive,
        root,
        remotes_override=remotes_override,
        restore_config=False,
        load_images=load_images,
        engine=engine,
        overwrite=overwrite,
        allow_incomplete=allow_incomplete,
        apply=True,
        json_output=False,
    )
    with tempfile.TemporaryDirectory(prefix="rfm-cache-bootstrap-") as temp:
        extracted = Path(temp)
        archive_path = Path(archive).expanduser().resolve()
        _extract_archive(archive_path, extracted)
        manifest = json.loads((extracted / "manifest.json").read_text(encoding="utf-8"))
        source_config = extracted / str(manifest.get("config_file") or "payload/config/repo-fleet.json")
        temporary_config = extracted / "effective-repo-fleet.json"
        shutil.copy2(source_config, temporary_config)
        config = load_config(temporary_config)
        code = _materialize_root_from_cache(config, root, remotes_override, apply=True)
        if code != 0:
            return code
        target_config = root / "repo-fleet.json"
        if not target_config.exists():
            shutil.copy2(source_config, target_config)
        config = load_config(target_config)
        code = localize(
            config,
            root,
            remotes_override,
            apply=True,
            set_origin=True,
            update_mirrors=False,
            jobs=max(1, jobs),
        )
        if code != 0:
            return code
    result = {
        "archive": str(Path(archive).expanduser().resolve()),
        "target_root": str(root),
        "bootstrapped": True,
        "offline": True,
    }
    if json_output:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] air-gapped workspace bootstrapped: {root}")
    return 0

# Changelog

All notable changes to Repo Fleet Manager are documented in this file.

The format follows Keep a Changelog and the project uses Semantic Versioning while the public API remains pre-1.0.

## [Unreleased]

## [0.11.0] - 2026-07-14

### Added

- Interactive `rfm config wizard` with quick and advanced modes.
- Project scanning for Git roots, submodules, nested repositories, Compose files, container images and runtime engine hints.
- Repeatable non-interactive generation from JSON answer files.
- Resumable wizard sessions, dry-run previews and unified config diffs.

### Security

- Secret-like answer keys are rejected before configuration generation.
- Generated filesystem paths must remain relative and portable.
- Existing configs are validated before atomic replacement and receive `.bak` backups by default.

## [0.10.0] - 2026-07-13

### Added

- Verified `rfm cache export`, `verify`, `list`, `import` and `bootstrap` workflows.
- Portable Git bundle archives preserving repository branches and tags.
- Docker/Podman image save/load support for air-gapped environments.
- Cache manifest, SHA-256 inventory, completeness state and configurable retention.
- Provider-free workspace bootstrap using only imported local bare remotes.

### Security

- Cache verification rejects path traversal, links, device entries, unexpected files and checksum tampering.
- Incomplete caches require explicit `--allow-missing` at export and `--allow-incomplete` at import.
- Existing local remotes are not replaced without explicit `--overwrite`.

## [0.9.0] - 2026-07-12

### Added

- `rfm init-project` for generating portable parent projects with config, CI, license and Git initialization.
- Built-in `generic`, `python-cli`, `python-service` and `node-service` repository templates.
- `rfm scaffold repository` with safe config updates, tags, dependencies and automatic lock regeneration.
- Deterministic `repo-fleet.lock.json` bootstrap contracts with config, repository and baseline file digests.
- `rfm bootstrap lock` and `rfm bootstrap verify` commands with JSON output and drift exit codes.

### Security

- Scaffold paths reject absolute paths and parent-directory traversal.
- Existing generated files are not overwritten without explicit `--force`.
- Bootstrap locks reject absolute workspace paths and detect config or baseline-file drift.

## [0.8.0] - 2026-07-12

### Added

- Named configuration profiles with deterministic inheritance and deep overlays.
- Repository-level profile overrides, including `enabled: false`.
- Repository tags and named groups with optional recursive dependency inclusion.
- Repeatable `--profile` and `--group` selectors on config-aware commands.
- `rfm config render`, `profiles`, and `groups` inspection commands.
- Strict validation for profile cycles, unknown parents, selectors, and tags.

### Changed

- The effective config is validated after profile resolution and group filtering.
- Make targets accept `PROFILE` and `GROUP` selection variables.

## [0.7.0] - 2026-07-12

### Added

- Verified `rfm local backup`, `verify-backup`, `backups` and clean-machine `restore` workflows.
- Backup manifest, SHA-256 file inventory, Git object verification and exact ref preservation checks.
- Configurable backup directory, retention policy and optional completed operation-journal capture.
- Directory-aware rollback support for restore operations.

### Security

- Restore rejects archive path traversal, symlink/hardlink/device members, checksum mismatches and project mismatches.
- Existing restore targets require explicit `--overwrite`; forced cross-project restore requires a recorded reason.

## [0.6.3] - 2026-07-12

### Added

- Tag-driven GitHub Release workflow producing wheel, source distribution and SHA-256 checksums.
- Release version consistency validation for `pyproject.toml`, runtime `__version__` and Git tag.
- GitHub issue forms, pull request template, contribution guide and security policy.
- Package metadata, project URLs, classifiers and MIT license file.
- CI artifact upload and manual workflow dispatch.

### Changed

- CI now runs on both `master` and `main` branches.
- Release readiness is represented in the RFM service catalog.

## [0.6.2] - 2026-07-12

### Fixed

- Imported the Git worktree validation helper used by repository publishing.

## [0.6.1] - 2026-07-12

### Fixed

- Migrated legacy repository manifests and provider definitions to schema `1.0.0`.

## [0.6.0] - 2026-07-12

### Added

- Versioned config schema and migration.
- Provider authentication diagnostics and native fork/reconciliation workflows.
- Workspace locking, safety guards, operation journal, resume and rollback.
- Dependency graph and controlled parallel execution.

[Unreleased]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.11.0...HEAD
[0.11.0]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.10.0...v0.11.0
[0.10.0]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.8.0...v0.9.0
[0.8.0]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.7.0...v0.8.0
[0.7.0]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.3...v0.7.0
[0.6.3]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/mhassanzadeh/repo-fleet-manager/releases/tag/v0.6.0

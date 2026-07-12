# Changelog

All notable changes to Repo Fleet Manager are documented in this file.

The format follows Keep a Changelog and the project uses Semantic Versioning while the public API remains pre-1.0.

## [Unreleased]

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

[Unreleased]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.7.0...HEAD
[0.7.0]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.3...v0.7.0
[0.6.3]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/mhassanzadeh/repo-fleet-manager/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/mhassanzadeh/repo-fleet-manager/releases/tag/v0.6.0

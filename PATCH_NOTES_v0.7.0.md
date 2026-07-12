# Repo Fleet Manager v0.7.0 patch notes

## Base version

- RFM base: `0.6.3`
- Target: `0.7.0`
- Config schema remains `1.0.0`
- Backup archive format: `1.0.0`

## Added

### Verified local fleet backup

New commands:

```bash
rfm local backup
rfm local backup --apply
rfm local backups
rfm local verify-backup ARCHIVE
```

The archive includes:

- `repo-fleet.json`;
- `.gitmodules`, when present;
- local bare remotes;
- all Git refs and object databases;
- a machine-readable manifest;
- per-file SHA-256 checksums;
- optional completed operation journals.

### Clean-machine restore

```bash
rfm local --root /srv/platform restore ARCHIVE
rfm local --root /srv/platform restore ARCHIVE --apply
```

Restore does not require an existing config. The restored config and local bare remotes can be used immediately with `rfm local clone` or `rfm local localize`.

### Retention

The new config fields are:

```json
{
  "local": {
    "backups_dir": ".repo-fleet/backups",
    "backup_retention": 5,
    "backup_include_operations": false
  }
}
```

Retention pruning happens only after a successful new backup and is recorded in the operation journal.

### Directory rollback

Operation journals can now preserve and restore complete directories. This is used to roll back an overwrite restore of `.repo-fleet/remotes`.

## Safety and verification

- `git fsck --full` is run before backup and after restore.
- Every archived regular file is covered by `CHECKSUMS.sha256`.
- Exact Git refs recorded in the manifest are checked during verify and restore.
- Unsafe tar paths, symlinks, hardlinks and device nodes are rejected.
- Existing targets require `--overwrite`.
- Cross-project restore requires `--force --reason`.
- Archive creation is atomic.
- The active operation journal and workspace lock are excluded from backup.

## Compatibility

No config migration is required. Existing schema `1.0.0` files remain valid. The new `local` fields are optional.

## Validation

The release test suite covers:

- backup and restore with multiple bare repositories;
- preservation of unpublished branches and tags;
- restore on a directory without config;
- checksum tampering;
- tar path traversal;
- retention pruning;
- directory rollback;
- schema, completion, package and catalog validation.

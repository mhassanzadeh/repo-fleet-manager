# Repo Fleet Manager v0.10.0 patch notes

## Release identity

- Base revision: `2b4e602556cc8b31f1f713f2b6c4561da7725867`
- Base version: `0.9.0`
- Target version: `0.10.0`
- Schema version: `1.0.0` (unchanged)
- Primary scope: GAP-011 — offline source and image cache

## Added commands

```bash
rfm cache export
rfm cache verify ARCHIVE
rfm cache list
rfm cache import ARCHIVE
rfm cache bootstrap ARCHIVE
```

## Functional changes

- Exports every available repository as a standalone Git bundle.
- Preserves branch and tag refs in a machine-readable manifest.
- Saves configured or explicitly selected Docker/Podman images.
- Generates SHA-256 checksums for all cache content.
- Imports bundles into `.repo-fleet/remotes` without provider access.
- Loads image archives without registry access.
- Bootstraps root and submodules entirely from `file://` remotes.
- Supports profile/group filtering during export.
- Supports cache retention under `local.cache_dir`.

## Config additions

```json
{
  "local": {
    "cache_dir": ".repo-fleet/cache",
    "cache_retention": 3
  },
  "compose": {
    "cache_images": [
      "docker.io/library/postgres:16"
    ]
  }
}
```

All new fields are optional and backward-compatible.

## Safety and integrity

- Dry-run remains the default for export/import/bootstrap.
- Archives reject absolute paths, `..`, symlinks, hardlinks and device entries.
- File inventory must exactly match `CHECKSUMS.sha256`.
- Git bundle refs must match the manifest.
- Existing remotes require `--overwrite`.
- Incomplete archives require explicit opt-in on both export and import.

## Validation performed

- Existing test suite
- Git bundle export/import
- Full air-gapped bootstrap with root and submodule
- Simulated Podman image save/load
- Checksum tampering rejection
- Incomplete cache enforcement
- Strict schema validation
- Documentation link validation
- Service catalog evidence validation
- Wheel and source distribution installation

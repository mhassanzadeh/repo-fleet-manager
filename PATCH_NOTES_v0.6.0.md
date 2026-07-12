# Repo Fleet Manager 0.6.0 patch notes

Base version: `0.5.0`

## Added

- Versioned Draft 2020-12 JSON Schema and strict semantic validation.
- In-place config migration with backup and dry-run preview.
- Repository dependency graph and topological, controlled parallel execution.
- Workspace lock with explicit forced-override reason.
- Persistent operation journals, attempts, resume and compensating rollback.
- Git HEAD, file, generated path and remote URL rollback tracking.
- Dirty/diverged/detached/branch-mismatch safety inspection.
- Provider driver/profile/user/scope diagnostics with token redaction.
- Native GitHub and GitLab fork commands.
- Local bare mirror publication and provider metadata reconciliation.
- GitHub Actions and GitLab CI validation pipelines.
- Expanded Bash/Fish completion and Makefile operator targets.

## Upgrade

```bash
unzip repo-fleet-manager-v0.6.0-p0-hardening.zip
cd repo-fleet-manager
make install
rfm config --config /path/to/repo-fleet.json migrate
rfm config --config /path/to/repo-fleet.json migrate --apply
rfm config --config /path/to/repo-fleet.json validate --strict
```

## Validation

```bash
make test
make validate-docs
make catalog-check
bash -n completions/rfm.bash
make build
```

## Compatibility

- Existing 0.3, 0.4 and 0.5 manifests are migrated in memory when loaded.
- `rfm config migrate --apply` writes the normalized schema `1.0.0` form.
- Dry-run remains the default for mutating repository/provider/local commands.

## Rollback

To return the source tree to version 0.5, restore the previous tag/archive or reverse the supplied patch. For an individual RFM operation, use:

```bash
rfm ops --config repo-fleet.json list
rfm ops --config repo-fleet.json rollback OPERATION_ID
```

Provider-side actions may require manual deletion or restoration; the operation journal identifies those cases.


## Git commits

برای stage و commit تفکیک‌شده تغییرات به [`GIT_COMMIT_GUIDE_v0.6.0.md`](GIT_COMMIT_GUIDE_v0.6.0.md) مراجعه کنید.

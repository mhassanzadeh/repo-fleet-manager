# Git commit guide for RFM v0.7.0

RFM is currently a standalone repository without Git submodules. Run these commands from the repository root and keep the current `master` workflow.

## Commit 1 — backup/restore engine

```bash
cd ~/Projects/repo-fleet-manager

git switch master
git pull --ff-only

git add \
  src/repo_fleet_manager/backup.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/operations.py \
  src/repo_fleet_manager/localops.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  src/repo_fleet_manager/data/repo-fleet.schema.json \
  configs \
  completions \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  tests/test_backup_restore.py \
  tests/test_operations.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py

git commit -m "feat(backup): add verified local fleet backup and restore"
```

## Commit 2 — catalog and documentation

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  .github/ISSUE_TEMPLATE/bug_report.yml \
  PATCH_NOTES_v0.7.0.md \
  GIT_COMMIT_GUIDE_v0.7.0.md \
  docs/00-architecture.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/08-local-only-workflows.md \
  docs/11-operational-safety-and-recovery.md \
  docs/12-backup-and-restore.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(backup): document local disaster recovery workflow"
```

## Validate and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.7.0

git push origin master
```

After GitHub Actions succeeds:

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.7.0 -m "Repo Fleet Manager v0.7.0"
git push origin v0.7.0
```

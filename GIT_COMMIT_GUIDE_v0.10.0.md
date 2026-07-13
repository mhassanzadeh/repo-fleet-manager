# Git commit guide for RFM v0.10.0

دستورها از روت پروژه اجرا می‌شوند و شاخه جاری `master` فرض شده است.

## Commit اول: موتور offline cache

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/cache.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/localops.py \
  src/repo_fleet_manager/scaffold.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  src/repo_fleet_manager/data/repo-fleet.schema.json \
  configs \
  repo-fleet.json \
  completions \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  tests/test_offline_cache.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(cache): add air-gapped source and image workflows"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  PATCH_NOTES_v0.10.0.md \
  GIT_COMMIT_GUIDE_v0.10.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/08-local-only-workflows.md \
  docs/15-offline-cache-and-air-gapped-bootstrap.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(cache): document air-gapped fleet bootstrap"
```

## Validation and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.10.0

git push origin master
```

## Tag after successful CI

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.10.0 -m "Repo Fleet Manager v0.10.0"
git push origin v0.10.0
```

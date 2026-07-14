# Git commit guide for RFM v0.13.0

دستورها از روت پروژه اجرا می‌شوند و شاخه جاری `master` فرض شده است.

## Commit اول: خروجی ساخت‌یافته و audit engine

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/observability.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/profiles.py \
  src/repo_fleet_manager/operations.py \
  src/repo_fleet_manager/wizard.py \
  src/repo_fleet_manager/scaffold.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  schemas/rfm-event.schema.json \
  src/repo_fleet_manager/data \
  configs \
  completions \
  tests/test_observability.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(observability): add structured output and audit logs"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  PATCH_NOTES_v0.13.0.md \
  GIT_COMMIT_GUIDE_v0.13.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/11-operational-safety-and-recovery.md \
  docs/18-structured-output-and-audit-logging.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json

git commit -m "docs(observability): document event schema and log workflows"
```

## Validation and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.13.0

git push origin master
```

## Tag after successful CI

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.13.0 -m "Repo Fleet Manager v0.13.0"
git push origin v0.13.0
```

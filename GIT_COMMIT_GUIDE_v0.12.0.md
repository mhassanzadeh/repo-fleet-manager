# Git commit guide for RFM v0.12.0

دستورها از روت پروژه اجرا می‌شوند و شاخه جاری `master` فرض شده است.

## Commit اول: Runtime engine و تست‌ها

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/runtime.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/profiles.py \
  src/repo_fleet_manager/schema.py \
  src/repo_fleet_manager/wizard.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  src/repo_fleet_manager/data/repo-fleet.schema.json \
  configs \
  completions \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  tests/test_runtime_readiness.py \
  tests/test_config_wizard.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(runtime): add health readiness and ordered startup"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  PATCH_NOTES_v0.12.0.md \
  GIT_COMMIT_GUIDE_v0.12.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/16-configuration-wizard.md \
  docs/17-runtime-health-readiness.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(runtime): document readiness diagnostics and probes"
```

## Validation and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.12.0

git push origin master
```

## Tag after successful CI

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.12.0 -m "Repo Fleet Manager v0.12.0"
git push origin v0.12.0
```

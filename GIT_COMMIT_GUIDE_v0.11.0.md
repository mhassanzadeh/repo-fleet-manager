# Git commit guide for RFM v0.11.0

## Commit اول: موتور ویزارد

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/wizard.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/__init__.py \
  tests/test_config_wizard.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  completions \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(config): add interactive configuration wizard"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  PATCH_NOTES_v0.11.0.md \
  GIT_COMMIT_GUIDE_v0.11.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/16-configuration-wizard.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(config): document wizard and safe config generation"
```

## Validation and release

```bash
cd ~/Projects/repo-fleet-manager
make validate
python3 scripts/check_release_version.py 0.11.0
git push origin master
git tag -a v0.11.0 -m "Repo Fleet Manager v0.11.0"
git push origin v0.11.0
```

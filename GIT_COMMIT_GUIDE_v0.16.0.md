# Git commit guide for RFM v0.16.0

## Commit اول: Plugin API و integration

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/plugin_api.py \
  src/repo_fleet_manager/plugins.py \
  src/repo_fleet_manager/artifacts.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/provider.py \
  src/repo_fleet_manager/gitops.py \
  src/repo_fleet_manager/runtime.py \
  src/repo_fleet_manager/service_catalog.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/profiles.py \
  src/repo_fleet_manager/wizard.py \
  src/repo_fleet_manager/scaffold.py \
  src/repo_fleet_manager/__init__.py \
  schemas \
  src/repo_fleet_manager/data \
  configs \
  completions \
  examples \
  tests/test_plugins.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  MANIFEST.in \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(plugins): add stable extension API and artifact backends"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  SECURITY.md \
  CONTRIBUTING.md \
  PATCH_NOTES_v0.16.0.md \
  GIT_COMMIT_GUIDE_v0.16.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/21-stable-plugin-api.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(plugins): publish extension contracts and compatibility policy"
```

## Validation and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.16.0
git push origin master
```

## Tag after successful CI

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.16.0 -m "Repo Fleet Manager v0.16.0"
git push origin v0.16.0
```

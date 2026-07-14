# Git commit guide for RFM v0.15.0

دستورها از روت پروژه اجرا می‌شوند و شاخه جاری `master` فرض شده است.

## Commit اول: Policy Engine و تست‌ها

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/policy.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/profiles.py \
  src/repo_fleet_manager/schema.py \
  src/repo_fleet_manager/wizard.py \
  src/repo_fleet_manager/scaffold.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  schemas/rfm-policy-report.schema.json \
  src/repo_fleet_manager/data \
  configs \
  completions \
  tests/test_policy.py \
  tests/test_profiles_groups.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  MANIFEST.in \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(policy): add governance rules and enforcement gates"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  SECURITY.md \
  PATCH_NOTES_v0.15.0.md \
  GIT_COMMIT_GUIDE_v0.15.0.md \
  docs/02-configuration.md \
  docs/07-command-reference.md \
  docs/11-operational-safety-and-recovery.md \
  docs/16-configuration-wizard.md \
  docs/19-supply-chain-provenance.md \
  docs/20-policy-as-code.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json

git commit -m "docs(policy): document rules exceptions and CI enforcement"
```

## Validation and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.15.0

git push origin master
```

## Tag after successful CI

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.15.0 -m "Repo Fleet Manager v0.15.0"
git push origin v0.15.0
```

# Git commit guide for RFM v0.14.0

دستورها از روت پروژه اجرا می‌شوند و شاخه جاری `master` فرض شده است.

## Commit اول: موتور supply-chain و تست‌ها

```bash
cd ~/Projects/repo-fleet-manager

git add \
  src/repo_fleet_manager/supply_chain.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/profiles.py \
  src/repo_fleet_manager/schema.py \
  src/repo_fleet_manager/wizard.py \
  src/repo_fleet_manager/scaffold.py \
  src/repo_fleet_manager/__init__.py \
  schemas/repo-fleet.schema.json \
  schemas/rfm-provenance.schema.json \
  src/repo_fleet_manager/data \
  configs \
  completions \
  tests/test_supply_chain.py \
  tests/test_cli_completion.py \
  tests/test_release_metadata.py \
  Makefile \
  pyproject.toml \
  .github/workflows/release.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml

git commit -m "feat(supply-chain): add provenance sbom and signature verification"
```

## Commit دوم: مستندات و کاتالوگ

```bash
cd ~/Projects/repo-fleet-manager

git add \
  README.md \
  CHANGELOG.md \
  SECURITY.md \
  PATCH_NOTES_v0.14.0.md \
  GIT_COMMIT_GUIDE_v0.14.0.md \
  docs/02-configuration.md \
  docs/04-source-fingerprint-and-images.md \
  docs/07-command-reference.md \
  docs/19-supply-chain-provenance.md \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  catalog/rfm-service-catalog.json \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(supply-chain): document image trust and provenance policy"
```

## Validation and push

```bash
cd ~/Projects/repo-fleet-manager

make validate
python3 scripts/check_release_version.py 0.14.0

git push origin master
```

## Tag after successful CI

```bash
cd ~/Projects/repo-fleet-manager

git tag -a v0.14.0 -m "Repo Fleet Manager v0.14.0"
git push origin v0.14.0
```

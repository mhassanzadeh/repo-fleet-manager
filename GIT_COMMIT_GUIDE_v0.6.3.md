# Git commit guide — RFM v0.6.3

این پروژه مستقل است و submodule ندارد. دستورها از روت پروژه و روی شاخه `master` اجرا می‌شوند.

## 1. Release automation and package metadata

```bash
cd ~/Projects/repo-fleet-manager

git switch master
git pull --ff-only

git add \
  .github/workflows/ci.yml \
  .github/workflows/release.yml \
  LICENSE \
  MANIFEST.in \
  Makefile \
  pyproject.toml \
  scripts/check_release_version.py \
  src/repo_fleet_manager/__init__.py \
  tests/test_release_metadata.py

git commit -m "feat(release): automate validated GitHub releases"
```

## 2. Community and security files

```bash
cd ~/Projects/repo-fleet-manager

git add \
  .github/ISSUE_TEMPLATE \
  .github/pull_request_template.md \
  CONTRIBUTING.md \
  SECURITY.md

git commit -m "docs(community): add contribution and issue templates"
```

## 3. Changelog, release notes and service catalog

```bash
cd ~/Projects/repo-fleet-manager

git add \
  CHANGELOG.md \
  GIT_COMMIT_GUIDE_v0.6.3.md \
  PATCH_NOTES_v0.6.3.md \
  README.md \
  catalog/rfm-service-catalog.json \
  docs/generated/rfm-service-catalog.md \
  reports/gap-analysis.md \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(release): document v0.6.3 release readiness"
```

## Validation, push and tag

```bash
cd ~/Projects/repo-fleet-manager

make validate
python scripts/check_release_version.py 0.6.3

git push origin master

git tag -a v0.6.3 -m "Repo Fleet Manager v0.6.3"
git push origin v0.6.3
```

Push شدن tag، workflow فایل `.github/workflows/release.yml` را اجرا می‌کند.

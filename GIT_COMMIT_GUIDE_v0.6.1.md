# Git commit guide for RFM 0.6.1

از روت repository و روی شاخه `main` اجرا شود.

## Commit کد و تست

```bash
git switch main
git pull --ff-only

git add \
  pyproject.toml \
  src/repo_fleet_manager/__init__.py \
  src/repo_fleet_manager/schema.py \
  tests/test_schema_migration.py

git commit -m "fix(config): migrate legacy repository manifests to schema 1.0"
```

## Commit مستندات

```bash
git add \
  README.md \
  docs/02-configuration.md \
  PATCH_NOTES_v0.6.1.md \
  GIT_COMMIT_GUIDE_v0.6.1.md

git commit -m "docs(config): document legacy manifest migration workflow"
```

## Tag و push

```bash
git tag -a v0.6.1 -m "Repo Fleet Manager v0.6.1"

git push origin main
git push origin v0.6.1
```

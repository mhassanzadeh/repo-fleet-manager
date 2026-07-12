# Git Commit Guide — RFM v0.6.0

این راهنما برای اعمال تغییرات نسخه `0.6.0` روی بیس `0.5.0` نوشته شده است. فرض بر این است که دستورها از روت پروژه اجرا می‌شوند، شاخه فعال `main` است و feature branch ساخته نمی‌شود.

## 1. بررسی شاخه و همگام‌سازی

```bash
git switch main
git pull --ff-only
```

## 2. Commit قابلیت‌های عملیاتی و کد

```bash
git add \
  .github \
  .gitlab-ci.yml \
  MANIFEST.in \
  Makefile \
  pyproject.toml \
  schemas \
  configs \
  completions \
  src/repo_fleet_manager/__init__.py \
  src/repo_fleet_manager/cli.py \
  src/repo_fleet_manager/config.py \
  src/repo_fleet_manager/gitops.py \
  src/repo_fleet_manager/graph.py \
  src/repo_fleet_manager/localops.py \
  src/repo_fleet_manager/operations.py \
  src/repo_fleet_manager/provider.py \
  src/repo_fleet_manager/safety.py \
  src/repo_fleet_manager/schema.py \
  src/repo_fleet_manager/shell.py \
  src/repo_fleet_manager/data/repo-fleet.schema.json \
  src/repo_fleet_manager/data/rfm.bash \
  src/repo_fleet_manager/data/rfm.fish \
  tests

git commit -m "feat(rfm): add P0 operational hardening and provider workflows"
```

## 3. Commit مستندات، کاتالوگ و اطلاعات انتشار

```bash
git add \
  README.md \
  MIGRATION.md \
  PATCH_NOTES_v0.6.0.md \
  GIT_COMMIT_GUIDE_v0.6.0.md \
  docs \
  reports \
  catalog \
  src/repo_fleet_manager/data/rfm-service-catalog.json

git commit -m "docs(rfm): document v0.6 recovery workflows and resolved gaps"
```

## 4. برچسب نسخه و Push

```bash
git tag -a v0.6.0 -m "Repo Fleet Manager v0.6.0"
git push origin main
git push origin v0.6.0
```

## 5. در صورتی که RFM به‌عنوان submodule در پروژه مادر استفاده شده باشد

از روت پروژه مادر، ابتدا وارد مسیر submodule شوید و commitهای بالا را انجام دهید. سپس به روت پروژه مادر برگردید و pointer ساب‌ماژول را ثبت کنید:

```bash
cd tools/repo-fleet-manager

git switch main
git pull --ff-only
# دستورهای commit بخش‌های 2 و 3 را اجرا کنید.

cd ../../
git add tools/repo-fleet-manager
git commit -m "chore(deps): update repo fleet manager to v0.6.0"
git push origin main
```

مسیر `tools/repo-fleet-manager` نمونه است و باید با مسیر واقعی submodule جایگزین شود.

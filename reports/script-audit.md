# گزارش بررسی اسکریپت‌های ارسالی

## خلاصه

آرشیو ارسالی شامل ۲۲ فایل در مسیر `scripts/` بود؛ جمعاً حدود ۱۳۶۱ خط. اسکریپت‌ها از نظر ایده و نیاز عملیاتی ارزشمند هستند، اما برای تبدیل شدن به یک ابزار قابل نگهداری در پروژه‌های بزرگ چندریپویی باید از حالت پروژه‌محور و hard-code شده خارج شوند.

## دسته‌بندی اسکریپت‌ها

| دسته | اسکریپت‌ها | وضعیت پیشنهادی |
|---|---|---|
| Bootstrap/Submodule | `bootstrap.sh`, `replace-submodule-remotes.sh`, `bootstrap-phase3-19-audit-worker-submodule.sh` | ادغام در `rfm submodules sync` و workflowهای bootstrap |
| Provider/GitHub | `create-github-repos.sh`, `goftaroo-github-remote-audit.py`, `goftaroo-github-remote-sync.sh` | ادغام در `rfm repos audit/create` و پشتیبانی GitLab |
| Docker/Compose | `build-python-service-base.sh`, `goftaroo-compose-up-dev.sh`, `goftaroo-compose-status.sh`, `verify-container-source-digests.sh`, `generate-compose-build-override.py` | ادغام در `rfm source`, `rfm compose`, `rfm images` |
| Catalog/Fingerprint | `goftaroo_service_catalog.py`, `goftaroo-source-fingerprint.py` | جایگزینی با `repo-fleet.json` و `rfm source fingerprint` |
| Validation/Docs | `validate-doc-links.py`, `validate-docker-compose-baseline.sh`, `show-platform-tree.sh`, `clean-python-build-artifacts.sh` | قابل نگهداری به‌عنوان utilities، ولی با config مشترک |
| Phase-specific | `api-gateway-phase-inventory.py`, `generate-phase3-final-report.py`, `diagnose-phase3-9-jwt-signature.sh`, `migrate-identity-db.sh`, `reset-phase3-16-audit-volume.sh` | باید از ابزار عمومی جدا شوند یا به plugin/project scripts منتقل شوند |

## نقاط قوت

- استفاده گسترده از `set -euo pipefail` در shell scripts.
- وجود dry-run در بعضی مسیرهای حساس مثل ساخت repo و sync remote.
- ایده خوب fingerprint سورس و تزریق metadata به compose.
- وجود audit برای `.gitmodules`، origin و وضعیت local path.
- عدم auto-commit در workflowهای push که برای submoduleهای زیاد تصمیم درستی است.

## ریسک‌ها و مشکلات اصلی

### 1. تکرار کاتالوگ ریپوها

لیست repoها در چند فایل تکرار شده است:

- `create-github-repos.sh`
- `replace-submodule-remotes.sh`
- `goftaroo-github-remote-audit.py`
- `goftaroo_service_catalog.py`
- `validate-docker-compose-baseline.sh`

این موضوع باعث drift می‌شود؛ یعنی یک سرویس در یک اسکریپت اضافه می‌شود ولی در اسکریپت دیگر جا می‌ماند. در نسخه جدید، فقط `repo-fleet.json` منبع حقیقت است.

### 2. GitHub-only بودن

اسکریپت‌های فعلی فرض می‌کنند provider همیشه GitHub است و URLها از قالب `git@github.com:OWNER/REPO.git` ساخته می‌شوند. نیاز اعلام‌شده شامل GitHub و GitLab است؛ بنابراین provider باید configurable باشد.

### 3. hard-codeهای پروژه‌ای

مواردی مثل نام `goftaroo`، owner پیش‌فرض، مسیرهای phase-specific، URL سرویس‌ها و حتی database URL در اسکریپت‌ها hard-code شده‌اند. این‌ها باید به config یا `.env` منتقل شوند.

### 4. ارجاع به فایل‌های موجود نبودن در آرشیو

اسکریپت‌ها به فایل‌های زیر ارجاع می‌دهند، اما در آرشیو ارسالی وجود نداشتند:

- `scripts/normalize-audit-worker-submodule.sh`
- `scripts/normalize-docker-build-metadata.py`
- `scripts/normalize-local-git-remotes.sh`
- `scripts/phase2-service-registry.sh`
- `scripts/phase3-final-inventory.py`
- `scripts/smoke-phase3-41-final-hardening.sh`
- `scripts/validate-phase3-19-audit-worker-integration.sh`
- `scripts/validate-phase3-41-final-hardening.sh`
- `scripts/verify-phase3-runtime-routes.sh`

بنابراین بعضی workflowها با همین آرشیو کامل قابل اجرا نیستند.

### 5. عملیات destructive بدون guard کافی

چند نمونه حساس:

- `replace-submodule-remotes.sh` با `: > .gitmodules` فایل را کامل بازنویسی می‌کند.
- `clean-python-build-artifacts.sh` از `rm -rf` روی چند مسیر استفاده می‌کند.
- `reset-phase3-16-audit-volume.sh` volumeهای Docker/Podman را حذف می‌کند.

نسخه جدید برای عملیات تغییردهنده dry-run پیش‌فرض دارد و `--apply` لازم است.

### 6. انتخاب Docker engine ناسازگار

برخی اسکریپت‌ها اول `podman-compose` را ترجیح می‌دهند، برخی مستقیم `podman` یا `docker` را صدا می‌زنند و بعضی مثل status فقط `podman-compose` را فرض کرده‌اند. این منطق در نسخه جدید در یک نقطه متمرکز شده است.

### 7. خروجی machine-readable محدود

برای CI و automation، خروجی JSON باید برای audit و image verification وجود داشته باشد. نسخه جدید برای audit و image verification خروجی JSON دارد.

## تصمیم بازطراحی

به‌جای patch کردن تک‌تک فایل‌ها، یک ابزار واحد با ساختار زیر ساخته شد:

```text
repo-fleet-manager/
├── configs/goftaroo.example.json
├── configs/repo-fleet.example.json
├── src/repo_fleet_manager/
├── docs/
├── reports/script-audit.md
└── legacy-scripts/goftaroo/
```

## نگاشت اسکریپت legacy به فرمان جدید

| Legacy | New CLI |
|---|---|
| `create-github-repos.sh` | `rfm repos create --provider github --apply` |
| `replace-submodule-remotes.sh` | `rfm submodules sync --provider github --apply` |
| `goftaroo-github-remote-audit.py` | `rfm repos audit --check-remote` |
| `goftaroo-github-remote-sync.sh` | `rfm repos create` + `rfm submodules sync` + `rfm git push` |
| `goftaroo-source-fingerprint.py` | `rfm source fingerprint --write` |
| `generate-compose-build-override.py` | داخل `rfm source fingerprint --write` ادغام شده است |
| `goftaroo-compose-up-dev.sh` | `rfm compose up --apply -- -d --build --force-recreate` |
| `verify-container-source-digests.sh` | `rfm images verify` |
| `validate-doc-links.py` | `rfm docs validate-links` |

## پیشنهادهای بعدی

1. اضافه کردن تست end-to-end با یک fixture شامل root repo و دو submodule fake.
2. اضافه کردن plugin mechanism برای اسکریپت‌های phase-specific.
3. اضافه کردن policy برای جلوگیری از push وقتی submodule dirty است.
4. اضافه کردن تولید `.gitignore` و template `Dockerfile` label args.
5. اضافه کردن CI workflow برای `rfm doctor`, `rfm repos audit`, `rfm docs validate-links`.

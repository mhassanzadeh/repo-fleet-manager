# Repo Fleet Manager

[![RFM CI](https://github.com/mhassanzadeh/repo-fleet-manager/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/mhassanzadeh/repo-fleet-manager/actions/workflows/ci.yml)
[![GitHub release](https://img.shields.io/github/v/release/mhassanzadeh/repo-fleet-manager?include_prereleases)](https://github.com/mhassanzadeh/repo-fleet-manager/releases)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


Repo Fleet Manager یک ابزار واحد و config-driven برای مدیریت پروژه‌های بزرگ چندریپویی است؛ مخصوصاً پروژه‌هایی که یک ریپوی ریشه دارند و چندین Git Submodule برای سرویس‌ها، کلاینت‌ها، پکیج‌های مشترک و زیرساخت در آن‌ها نگهداری می‌شود.

این پکیج از روی اسکریپت‌های ارسالی بازطراحی شده و منطق پراکنده را به یک CLI واحد تبدیل می‌کند. اسکریپت‌های اولیه بدون تغییر در مسیر [`legacy-scripts/goftaroo`](legacy-scripts/goftaroo) نگهداری شده‌اند تا مهاجرت مرحله‌ای ممکن باشد.

## قابلیت‌های اصلی

- نصب به‌عنوان ابزار ترمینالی `rfm`
- completion برای Bash و Fish
- مدیریت کاتالوگ پروژه از یک فایل مرکزی `repo-fleet.json`
- audit کردن `.gitmodules`، ریموت‌های محلی، branchها و وضعیت submoduleها
- ساخت ریپوها روی GitHub و GitLab با CLIهای رسمی `gh` و `glab`
- اجرای کامل workflowها به‌صورت local-only با bare remoteهای محلی و URLهای `file://`
- lifecycle رسمی برای repoهای `new`، `upstream` و `existing`
- ساخت workspace محلی از روی config، شامل root repo، submoduleها و `.gitmodules`
- import/mirror/clone محلی برای پروژه‌های GitHub/GitLab یا پروژه‌های موجود روی دیسک
- publish پروژه‌های local روی GitHub/GitLab شخصی بدون خراب کردن origin محلی
- sync کردن ریموت submoduleها از روی config
- اجرای `git status`، `git pull` و `git push` روی root و submoduleها
- fingerprint گرفتن از سورس سرویس‌ها و تزریق label/metadata به Docker Compose
- مقایسه digest سورس با Docker image ساخته‌شده
- اجرای compose stack در محیط local development
- validation لینک‌های مستندات
- کاتالوگ ماشین‌خوان قابلیت‌های RFM، درخت بلوغ و gap analysis اولویت‌بندی‌شده
- JSON Schema نسخه‌دار، migration خودکار و validation معنایی config
- dependency graph و اجرای کنترل‌شده موازی با `--jobs`
- workspace lock، safety guard، operation journal، resume و rollback
- تشخیص identity/scope برای providerها بدون نمایش token
- fork واقعی GitHub/GitLab، انتشار mirror و reconciliation متادیتای remote
- backup و restore تأییدشده برای bare remoteهای محلی، config و operation state

## شروع سریع

نصب ابزار و completionها در مسیر user:

```bash
cd repo-fleet-manager
make install

rfm --version
rfm config --config configs/goftaroo.example.json validate --strict
rfm doctor --config configs/goftaroo.example.json
rfm catalog --config configs/goftaroo.example.json
rfm catalog --root . --view summary
rfm catalog --root . --view gaps --priority P0
```

نصب editable برای توسعه:

```bash
make install-editable
make install-completions
```

یا بدون نصب پکیج:

```bash
./scripts/rfm.sh doctor --config configs/goftaroo.example.json
```

برای استفاده داخل پروژه اصلی، فایل نمونه را کپی کنید:

```bash
cp configs/goftaroo.example.json /path/to/main-platform/repo-fleet.json
cd /path/to/main-platform
rfm doctor
```


## نصب از GitHub Release یا pipx

برای نصب ایزوله آخرین نسخه مستقیم از GitHub:

```bash
pipx install git+https://github.com/mhassanzadeh/repo-fleet-manager.git@v0.7.0
rfm --version
```

یا Wheel را از GitHub Release دانلود و نصب کنید:

```bash
python3 -m pip install ./repo_fleet_manager-0.7.0-py3-none-any.whl
rfm --version
```

Checksum فایل‌های release در `SHA256SUMS` منتشر می‌شود.

## completion

بعد از `make install` فایل‌های completion نصب می‌شوند:

- Bash: `~/.local/share/bash-completion/completions/rfm`
- Fish: `~/.config/fish/completions/rfm.fish`

برای نصب فقط completionها:

```bash
make install-completions
```

برای تولید دستی:

```bash
rfm completion bash > ~/.local/share/bash-completion/completions/rfm
rfm completion fish > ~/.config/fish/completions/rfm.fish
```

برای نصب system-wide می‌توانید مسیرها را override کنید:

```bash
sudo make install-completions \
  BASH_COMPLETION_DIR=/usr/share/bash-completion/completions \
  FISH_COMPLETION_DIR=/usr/share/fish/vendor_completions.d
```

## گیت ایمنی قبل از apply

```bash
rfm config --config repo-fleet.json validate --strict
rfm graph --config repo-fleet.json show
rfm safety --config repo-fleet.json status
rfm auth --config repo-fleet.json status --verbose
```

هر عملیات واقعی یک lock و journal می‌سازد. برای مشاهده، ادامه یا بازگردانی:

```bash
rfm ops --config repo-fleet.json list
rfm ops --config repo-fleet.json show OPERATION_ID
rfm ops --config repo-fleet.json resume OPERATION_ID
rfm ops --config repo-fleet.json rollback OPERATION_ID
```

## جریان‌های کاری پرکاربرد

### 0. اجرای کامل بدون GitHub/GitLab

برای ساخت پروژه محلی از روی config و ایجاد submoduleهای واقعی با bare remoteهای local:

```bash
rfm local --config repo-fleet.json plan
rfm local --config repo-fleet.json localize
rfm local --config repo-fleet.json localize --apply
rfm repos --config repo-fleet.json audit --provider local
```

برای repoهایی که باید mirror/fork محلی داشته باشند، در config از `source_type: upstream` و `upstream_url` یا `fork_from` استفاده کنید؛ `localize` حداقل mirror/clone محلی را انجام می‌دهد. برای انتشار روی GitHub/GitLab شخصی:

```bash
rfm repos --config repo-fleet.json publish --provider github --namespace my-user --remote-name personal
rfm repos --config repo-fleet.json publish --provider github --namespace my-user --remote-name personal --apply
rfm repos --config repo-fleet.json fork --provider github --namespace my-user --apply
rfm repos --config repo-fleet.json reconcile --provider github
```


### 0.1. پشتیبان‌گیری از زیرساخت local-only

```bash
rfm local --config repo-fleet.json backup
rfm local --config repo-fleet.json backup --apply
rfm local verify-backup .repo-fleet/backups/<archive>.rfm-backup.tar.gz
```

بازیابی روی یک سیستم تمیز، بدون نیاز به GitHub یا GitLab:

```bash
mkdir /path/to/restored-platform
rfm local --root /path/to/restored-platform restore /path/to/archive.rfm-backup.tar.gz
rfm local --root /path/to/restored-platform restore /path/to/archive.rfm-backup.tar.gz --apply
```

### 1. بررسی وضعیت root و submoduleها

```bash
rfm repos --config repo-fleet.json audit
rfm repos --config repo-fleet.json audit --check-remote
```

### 2. ساخت ریپوهای GitHub یا GitLab

همه عملیات تغییردهنده به‌صورت پیش‌فرض dry-run هستند:

```bash
rfm repos --config repo-fleet.json create --provider github --namespace my-org
rfm repos --config repo-fleet.json create --provider github --namespace my-org --apply

rfm repos --config repo-fleet.json create --provider gitlab --namespace my-group
rfm repos --config repo-fleet.json create --provider gitlab --namespace my-group --apply
```

### 3. sync کردن `.gitmodules` و origin ساب‌ماژول‌ها

```bash
rfm submodules --config repo-fleet.json sync --provider github --namespace my-org
rfm submodules --config repo-fleet.json sync --provider github --namespace my-org --apply
```

### 4. Pull/Push روی کل پروژه

```bash
rfm git --config repo-fleet.json status
rfm git --config repo-fleet.json pull --apply
rfm git --config repo-fleet.json push --apply
```

### 5. مقایسه سورس با Docker imageها

```bash
rfm source --config repo-fleet.json fingerprint --write
rfm compose --config repo-fleet.json up --apply -- -d --build --force-recreate
rfm images --config repo-fleet.json verify
```

## Makefile

```bash
make install              # نصب rfm و completionها در user scope
make install-cli          # فقط نصب ابزار rfm
make install-editable     # نصب editable برای توسعه
make install-completions  # نصب completionهای Bash و Fish
make uninstall            # حذف پکیج Python
make uninstall-completions
make config-validate CONFIG=repo-fleet.json
make auth-status CONFIG=repo-fleet.json ROOT=/path/to/workspace
make graph CONFIG=repo-fleet.json ROOT=/path/to/workspace
make safety-status CONFIG=repo-fleet.json ROOT=/path/to/workspace
make ops-list CONFIG=repo-fleet.json ROOT=/path/to/workspace
make test
make validate
make local-plan CONFIG=repo-fleet.json ROOT=/path/to/workspace
make local-localize CONFIG=repo-fleet.json ROOT=/path/to/workspace
make local-localize-apply CONFIG=repo-fleet.json ROOT=/path/to/workspace
make local-remotes-update CONFIG=repo-fleet.json ROOT=/path/to/workspace
make local-backup CONFIG=repo-fleet.json ROOT=/path/to/workspace
make local-backup-apply CONFIG=repo-fleet.json ROOT=/path/to/workspace
make local-backup-verify ARCHIVE=/path/to/archive.rfm-backup.tar.gz
make local-restore ROOT=/path/to/restore ARCHIVE=/path/to/archive.rfm-backup.tar.gz
make local-restore-apply ROOT=/path/to/restore ARCHIVE=/path/to/archive.rfm-backup.tar.gz
make publish-github CONFIG=repo-fleet.json ROOT=/path/to/workspace NAMESPACE=my-user
make publish-gitlab CONFIG=repo-fleet.json ROOT=/path/to/workspace NAMESPACE=my-group
make catalog-summary
make catalog-tree
make catalog-gaps
make catalog-docs
make catalog-check
```


## فرآیند انتشار رسمی

CI روی هر دو شاخه `master` و `main` اجرا می‌شود. tagهای `v*`، workflow انتشار را فعال می‌کنند و Wheel، Source Distribution و `SHA256SUMS` را به GitHub Release متصل می‌کنند. قبل از tag:

```bash
make validate
python scripts/check_release_version.py 0.7.0
make release-artifacts
```

راهنمای مشارکت، سیاست امنیتی و تاریخچه تغییرات در [`CONTRIBUTING.md`](CONTRIBUTING.md)، [`SECURITY.md`](SECURITY.md) و [`CHANGELOG.md`](CHANGELOG.md) قرار دارند.

## ساختار پروژه

```text
repo-fleet-manager/
├── catalog/                 # manifest ماشین‌خوان قابلیت‌ها و gapهای RFM
├── completions/             # نسخه static completionها برای Bash و Fish
├── configs/                 # نمونه config برای Goftaroo و قالب عمومی
├── docs/                    # مستندات معماری، workflow و کاتالوگ تولیدشده
├── legacy-scripts/goftaroo/ # اسکریپت‌های اولیه بدون تغییر
├── reports/                 # گزارش audit و gap analysis
├── schemas/                 # JSON Schema رسمی repo-fleet.json
├── .github/workflows/       # CI برای test/validation/package
├── scripts/rfm.sh           # wrapper بدون نصب پکیج
├── src/repo_fleet_manager/  # CLI و منطق اصلی
└── tests/                   # تست‌های پایه
```

## مستندات

- [معماری و تصمیم طراحی](docs/00-architecture.md)
- [نصب و وابستگی‌ها](docs/01-installation.md)
- [راهنمای config](docs/02-configuration.md)
- [workflowهای عملیاتی](docs/03-workflows.md)
- [fingerprint سورس و Docker image](docs/04-source-fingerprint-and-images.md)
- [GitHub/GitLab providers](docs/05-repository-providers.md)
- [workflowهای local-only](docs/08-local-only-workflows.md)
- [مدل lifecycle ریپوها و localization](docs/09-repository-lifecycle.md)
- [برنامه مهاجرت از اسکریپت‌های فعلی](docs/06-migration-plan.md)
- [مرجع فرمان‌ها](docs/07-command-reference.md)
- [راهنمای service catalog](docs/10-service-catalog.md)
- [ایمنی عملیاتی، journal، resume و rollback](docs/11-operational-safety-and-recovery.md)
- [پشتیبان‌گیری و بازیابی local fleet](docs/12-backup-and-restore.md)
- [خروجی کامل service catalog](docs/generated/rfm-service-catalog.md)
- [gap analysis منطقی](reports/gap-analysis.md)
- [گزارش بررسی اسکریپت‌های ارسالی](reports/script-audit.md)

## نکته مهم درباره dry-run

فرمان‌هایی که state را تغییر می‌دهند، مثل ساخت ریپو، sync ریموت، pull/push و compose up/down، تا وقتی `--apply` ندهید فقط دستورهای پیشنهادی را چاپ می‌کنند. با `--apply` نیز lock، safety guard و operation journal فعال می‌شود. عبور اجباری از guard فقط با `--force --reason "..."` ممکن است تا علت تصمیم در journal بماند.


## اصلاح migration کانفیگ‌های قدیمی در 0.6.1

اگر `validate --strict` برای providerهای `type: github` یا فیلدهای قدیمی مانند `project_name` و `repos` خطا داد، ابتدا hotfix `0.6.1` را نصب کرده و سپس اجرا کنید:

```bash
rfm config --config repo-fleet.json validate
rfm config --config repo-fleet.json migrate
rfm config --config repo-fleet.json migrate --apply
rfm config --config repo-fleet.json validate --strict
```

`--strict` عمداً فایل را بدون migration بررسی می‌کند؛ بنابراین برای فایل قدیمی باید بعد از `migrate --apply` استفاده شود.

توجه: نسخه schema مستقل از نسخه ابزار است، اما مقدار استاندارد `schema_version` در config برابر `1.0.0` باقی می‌ماند؛ این دو شماره مستقل هستند.

## Git commit guide

تغییرات، روش انتشار و دستورهای commit نسخه جاری در [`PATCH_NOTES_v0.7.0.md`](PATCH_NOTES_v0.7.0.md)، [`CHANGELOG.md`](CHANGELOG.md) و [`GIT_COMMIT_GUIDE_v0.7.0.md`](GIT_COMMIT_GUIDE_v0.7.0.md) قرار دارد.

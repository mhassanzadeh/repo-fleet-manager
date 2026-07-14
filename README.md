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
- profileهای قابل ارث‌بری، overlayهای محیطی و repository groupهای مبتنی بر نام یا tag
- ساخت پروژه مادر، scaffolding repository/service و bootstrap lockfile قابل‌حمل
- export/import تأییدشده Git bundleها و image archiveها برای bootstrap در محیط air-gapped
- runtime status/doctor/wait و startup ترتیبی Compose بر اساس healthcheck، probe و dependency graph
- خروجی یکپارچه text/JSON/JSONL و audit log پالایش‌شده با correlation به operation journal
- provenance زنجیره تأمین شامل digest ثابت، SBOM، vulnerability scan و Cosign verification
- Policy-as-Code برای repository governance، supply-chain trust، operation guard و exceptionهای زمان‌دار
- ویزارد تعاملی و قابل‌اسکریپت برای scan، ساخت و ویرایش امن `repo-fleet.json`

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
make init-project PROJECT_NAME=banking-platform PROJECT_DIR=./banking-platform
make scaffold-templates
make scaffold-repository CONFIG=repo-fleet.json ROOT=. REPO_NAME=customer-api REPO_PATH=services/customer-api TEMPLATE=python-service REPO_KIND=service
make bootstrap-lock-apply CONFIG=repo-fleet.json ROOT=.
make bootstrap-verify CONFIG=repo-fleet.json ROOT=.
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

### ساخت کانفیگ با ویزارد

برای ساخت تعاملی فایل تنظیمات:

```bash
rfm config wizard --quick --output repo-fleet.json
rfm config wizard --quick --output repo-fleet.json --apply
```

برای شناسایی خودکار Git repositoryها، submoduleها، Compose file و imageها:

```bash
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive --apply
```

برای تولید تکرارپذیر در CI از `--answers answers.json --non-interactive` و برای ادامه جلسه قطع‌شده از `--resume` استفاده کنید. جزئیات کامل در [راهنمای Configuration Wizard](docs/16-configuration-wizard.md) آمده است.


## نصب از GitHub Release یا pipx

برای نصب ایزوله آخرین نسخه مستقیم از GitHub:

```bash
pipx install git+https://github.com/mhassanzadeh/repo-fleet-manager.git@v0.15.0
rfm --version
```

یا Wheel را از GitHub Release دانلود و نصب کنید:

```bash
python3 -m pip install ./repo_fleet_manager-0.15.0-py3-none-any.whl
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

## Profileها و گروه‌های repository

یک config پایه را برای محیط‌های مختلف resolve کنید:

```bash
rfm config --config repo-fleet.json profiles
rfm config --config repo-fleet.json groups
rfm config --config repo-fleet.json --profile ci --group backend render
```

همان انتخاب‌ها روی فرمان‌های عملیاتی نیز کار می‌کنند:

```bash
rfm git --config repo-fleet.json --profile developer --group backend status
rfm local --config repo-fleet.json --profile developer --group backend localize
rfm repos --config repo-fleet.json --profile production --group runtime audit
```

Profileها قابل ارث‌بری هستند، repository overlayها از `enabled: false` پشتیبانی می‌کنند و groupها می‌توانند dependencyها را به‌صورت بازگشتی وارد کنند.

## ساخت پروژه و bootstrap contract

ساخت یک parent project استاندارد:

```bash
rfm init-project banking-platform \
  --directory ./banking-platform \
  --provider github \
  --namespace my-org \
  --apply
```

ساخت repository یا service از template:

```bash
rfm scaffold templates
rfm scaffold repository customer-api \
  --config repo-fleet.json \
  --root . \
  --path services/customer-api \
  --template python-service \
  --kind service \
  --tag backend \
  --apply
```

اعتبارسنجی قرارداد bootstrap:

```bash
rfm bootstrap --config repo-fleet.json --root . verify
```

جزئیات کامل در [راهنمای scaffolding و bootstrap lock](docs/14-project-scaffolding-and-bootstrap-lock.md) آمده است.

<!-- RFM_RUNTIME_READINESS_BEGIN -->
## Runtime health و readiness

وضعیت running و ready را جداگانه بررسی کنید:

```bash
rfm runtime --config repo-fleet.json status
rfm runtime --config repo-fleet.json doctor --logs
rfm runtime --config repo-fleet.json wait --timeout 180
rfm runtime --config repo-fleet.json up --apply
```

`runtime up` سرویس‌ها را بر اساس dependency level راه‌اندازی می‌کند و تا آماده‌شدن هر level صبر می‌کند. جزئیات probeهای HTTP/TCP/command در [راهنمای Runtime health و readiness](docs/17-runtime-health-readiness.md) آمده است.
<!-- RFM_RUNTIME_READINESS_END -->

## خروجی ساخت‌یافته و Audit Logging

تمام فرمان‌ها می‌توانند یک JSON envelope یا JSONL event stream پایدار تولید کنند:

```bash
rfm --format json config --config repo-fleet.json validate --strict
rfm runtime --config repo-fleet.json status --format jsonl
rfm logs --root . list
rfm logs --root . verify RUN_ID
```

Audit log پیش‌فرض در `.repo-fleet/logs` نوشته می‌شود، مقادیر حساس پالایش می‌شوند و mutationها به operation journal مرتبط می‌شوند. جزئیات در [راهنمای خروجی ساخت‌یافته و Audit Logging](docs/18-structured-output-and-audit-logging.md) آمده است.

## Supply-chain provenance و image trust

زنجیره source → image digest → SBOM → vulnerability report → signature/attestation را بررسی کنید:

```bash
rfm supply-chain --config repo-fleet.json resolve --apply
rfm supply-chain --config repo-fleet.json sbom --apply
rfm supply-chain --config repo-fleet.json scan --fail-on high --apply
rfm supply-chain --config repo-fleet.json verify
```

فرمان `collect --apply` مراحل resolve، SBOM و scan را یکجا اجرا می‌کند. verification فقط روی reference ثابت `image@sha256:...` انجام می‌شود و جزئیات در [راهنمای Supply-chain provenance](docs/19-supply-chain-provenance.md) آمده است.

<!-- RFM_POLICY_AS_CODE_BEGIN -->
## Policy-as-Code

قواعد governance را ابتدا در حالت advisory بررسی و سپس در CI یا عملیات واقعی enforce کنید:

```bash
rfm policy --config repo-fleet.json --root . check
rfm policy --config repo-fleet.json --root . enforce
rfm policy --config repo-fleet.json explain RULE_ID
rfm policy --config repo-fleet.json exceptions
```

Ruleهای built-in می‌توانند visibility، branch، provider، remote host، clean tree، signed HEAD، registry و الزامات provenance را کنترل کنند. در `policy.mode: enforce`، عملیات mutation پیش از تغییر workspace یا provider بررسی می‌شوند. exceptionها باید دلیل، تأییدکننده و تاریخ انقضا داشته باشند. OPA/Rego نیز به‌صورت اختیاری پشتیبانی می‌شود. جزئیات در [راهنمای Policy-as-Code](docs/20-policy-as-code.md) آمده است.
<!-- RFM_POLICY_AS_CODE_END -->

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

### 0.2. آماده‌سازی و bootstrap در محیط air-gapped

روی ماشین متصل، سورس‌ها و imageهای موردنیاز را در یک cache قابل‌حمل export کنید:

```bash
rfm cache --config repo-fleet.json export
rfm cache --config repo-fleet.json export --apply
rfm cache verify .repo-fleet/cache/<archive>.rfm-cache.tar.gz --require-complete
```

پس از انتقال archive به شبکه جدا، بدون GitHub، GitLab یا registry خارجی workspace را بسازید:

```bash
rfm cache --root /srv/platform bootstrap /media/cache/platform.rfm-cache.tar.gz
rfm cache --root /srv/platform bootstrap /media/cache/platform.rfm-cache.tar.gz --apply
```

برای cache کردن imageهای مشخص، از `compose.cache_images` در config یا `--image` استفاده کنید. جزئیات کامل در [راهنمای offline cache و air-gapped bootstrap](docs/15-offline-cache-and-air-gapped-bootstrap.md) آمده است.

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
make config-render CONFIG=repo-fleet.json PROFILE=ci GROUP=backend
make config-profiles CONFIG=repo-fleet.json
make config-groups CONFIG=repo-fleet.json
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
make cache-export-apply CONFIG=repo-fleet.json ROOT=. CACHE_OUTPUT=/path/to/fleet.rfm-cache.tar.gz
make cache-verify ARCHIVE=/path/to/fleet.rfm-cache.tar.gz
make cache-import-apply ROOT=/path/to/import ARCHIVE=/path/to/fleet.rfm-cache.tar.gz
make cache-bootstrap-apply ROOT=/path/to/workspace ARCHIVE=/path/to/fleet.rfm-cache.tar.gz
make config-wizard-scan-apply ROOT=. WIZARD_SCAN=. WIZARD_OUTPUT=repo-fleet.json
make logs-list CONFIG=repo-fleet.json ROOT=.
make logs-verify CONFIG=repo-fleet.json ROOT=. RUN_ID=<run-id>
make logs-purge-apply CONFIG=repo-fleet.json ROOT=. RETENTION_DAYS=30
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
python scripts/check_release_version.py 0.15.0
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
- [Profileها، overlayها و repository groupها](docs/13-profiles-overlays-and-groups.md)
- [ساخت پروژه، templateها و bootstrap lock](docs/14-project-scaffolding-and-bootstrap-lock.md)
- [Offline cache و bootstrap در محیط air-gapped](docs/15-offline-cache-and-air-gapped-bootstrap.md)
- [ویزارد ساخت و ویرایش کانفیگ](docs/16-configuration-wizard.md)
- [Runtime health، readiness و startup ترتیبی](docs/17-runtime-health-readiness.md)
- [خروجی ساخت‌یافته و Audit Logging](docs/18-structured-output-and-audit-logging.md)
- [Supply-chain provenance، SBOM و image trust](docs/19-supply-chain-provenance.md)
- [Policy-as-Code و exceptionهای governance](docs/20-policy-as-code.md)
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

تغییرات و روش انتشار نسخه جاری در [`PATCH_NOTES_v0.15.0.md`](PATCH_NOTES_v0.15.0.md)، [`GIT_COMMIT_GUIDE_v0.15.0.md`](GIT_COMMIT_GUIDE_v0.15.0.md) و [`CHANGELOG.md`](CHANGELOG.md) قرار دارد.

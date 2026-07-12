# Repo Fleet Manager

Repo Fleet Manager یک ابزار واحد و config-driven برای مدیریت پروژه‌های بزرگ چندریپویی است؛ مخصوصاً پروژه‌هایی که یک ریپوی ریشه دارند و چندین Git Submodule برای سرویس‌ها، کلاینت‌ها، پکیج‌های مشترک و زیرساخت در آن‌ها نگهداری می‌شود.

این پکیج از روی اسکریپت‌های ارسالی بازطراحی شده و منطق پراکنده را به یک CLI واحد تبدیل می‌کند. اسکریپت‌های اولیه بدون تغییر در مسیر [`legacy-scripts/goftaroo`](legacy-scripts/goftaroo) نگهداری شده‌اند تا مهاجرت مرحله‌ای ممکن باشد.

## قابلیت‌های اصلی

- مدیریت کاتالوگ پروژه از یک فایل مرکزی `repo-fleet.json`
- audit کردن `.gitmodules`، ریموت‌های محلی، branchها و وضعیت submoduleها
- ساخت ریپوها روی GitHub و GitLab با CLIهای رسمی `gh` و `glab`
- sync کردن ریموت submoduleها از روی config
- اجرای `git status`، `git pull` و `git push` روی root و submoduleها
- fingerprint گرفتن از سورس سرویس‌ها و تزریق label/metadata به Docker Compose
- مقایسه digest سورس با Docker image ساخته‌شده
- اجرای compose stack در محیط local development
- validation لینک‌های مستندات

## شروع سریع

```bash
cd repo-fleet-manager
python3 -m venv .venv
. .venv/bin/activate
pip install -e .

rfm doctor --config configs/goftaroo.example.json
rfm catalog --config configs/goftaroo.example.json
```

یا بدون نصب پکیج:

```bash
./scripts/rfm.sh doctor --config configs/goftaroo.example.json
```

برای استفاده داخل پروژه اصلی، فایل نمونه را کپی کنید:

```bash
cp configs/goftaroo.example.json /path/to/main-platform/repo-fleet.json
cd /path/to/main-platform
/path/to/repo-fleet-manager/scripts/rfm.sh doctor
```

## جریان‌های کاری پرکاربرد

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

## ساختار پروژه

```text
repo-fleet-manager/
├── configs/                 # نمونه config برای Goftaroo و قالب عمومی
├── docs/                    # مستندات معماری، نصب، workflow و migration
├── legacy-scripts/goftaroo/ # اسکریپت‌های اولیه بدون تغییر
├── reports/                 # گزارش audit روی اسکریپت‌های اولیه
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
- [برنامه مهاجرت از اسکریپت‌های فعلی](docs/06-migration-plan.md)
- [مرجع فرمان‌ها](docs/07-command-reference.md)
- [گزارش بررسی اسکریپت‌های ارسالی](reports/script-audit.md)

## نکته مهم درباره dry-run

فرمان‌هایی که state را تغییر می‌دهند، مثل ساخت ریپو، sync ریموت، pull/push و compose up/down، تا وقتی `--apply` ندهید فقط دستورهای پیشنهادی را چاپ می‌کنند. این رفتار عمداً انتخاب شده تا روی پروژه‌های بزرگ و حساس تغییر ناخواسته انجام نشود.

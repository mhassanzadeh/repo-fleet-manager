# ساخت پروژه، قالب‌های repository و bootstrap lock

نسخه `0.9.0` مسیر ساخت یک پروژه چندریپویی جدید را استاندارد و قابل تکرار می‌کند. تمام فرمان‌های تغییردهنده به‌صورت پیش‌فرض dry-run هستند و فقط با `--apply` فایل می‌نویسند.

## ساخت پروژه مادر

```bash
rfm init-project banking-platform \
  --directory ./banking-platform \
  --provider github \
  --namespace my-org \
  --visibility private
```

اجرای واقعی:

```bash
rfm init-project banking-platform \
  --directory ./banking-platform \
  --provider github \
  --namespace my-org \
  --visibility private \
  --apply
```

خروجی استاندارد شامل موارد زیر است:

```text
banking-platform/
├── .github/workflows/ci.yml
├── .gitignore
├── LICENSE
├── README.md
├── repo-fleet.json
└── repo-fleet.lock.json
```

به‌صورت پیش‌فرض Git repository نیز با branch انتخاب‌شده initialize می‌شود. برای غیرفعال‌کردن:

```bash
rfm init-project banking-platform --no-git-init --apply
```

RFM فایل‌های موجود با محتوای متفاوت را بدون `--force` بازنویسی نمی‌کند.

## قالب‌های repository

فهرست قالب‌های داخلی:

```bash
rfm scaffold templates
rfm scaffold templates --json
```

قالب‌های فعلی:

| Template | کاربرد | فایل‌های پایه |
|---|---|---|
| `generic` | ماژول یا repository عمومی | README، LICENSE، gitignore و metadata |
| `python-cli` | ابزار خط فرمان Python | pyproject، src layout، unittest و CI |
| `python-service` | سرویس Python | health baseline، tests، Dockerfile و CI |
| `node-service` | سرویس Node.js | package.json، node:test، Dockerfile و CI |

## اضافه‌کردن repository به پروژه

ابتدا dry-run:

```bash
rfm scaffold repository customer-api \
  --config repo-fleet.json \
  --root . \
  --path services/customer-api \
  --template python-service \
  --kind service \
  --tag backend \
  --tag runtime
```

اجرای واقعی:

```bash
rfm scaffold repository customer-api \
  --config repo-fleet.json \
  --root . \
  --path services/customer-api \
  --template python-service \
  --kind service \
  --tag backend \
  --tag runtime \
  --apply
```

این فرمان به‌صورت اتمیک فایل‌های template را می‌سازد، entry جدید را به `repo-fleet.json` اضافه می‌کند و `repo-fleet.lock.json` را بازتولید می‌کند. مسیر repository باید relative باشد و استفاده از مسیر absolute یا `..` رد می‌شود.

برای dependency:

```bash
rfm scaffold repository customer-api \
  --config repo-fleet.json \
  --root . \
  --path services/customer-api \
  --template python-service \
  --kind service \
  --depends-on shared-contracts \
  --apply
```

## bootstrap lock

فایل `repo-fleet.lock.json` قرارداد قابل‌حمل bootstrap است و شامل موارد زیر می‌شود:

- digest کانفیگ نرمال‌شده؛
- branch، provider، lifecycle و dependency هر repository؛
- نام template هر repository تولیدشده؛
- checksum فایل‌های پایه پروژه و metadata قالب‌ها؛
- نسخه schema و نسخه RFM تولیدکننده.

Lockfile هیچ مسیر absolute از سیستم سازنده را ذخیره نمی‌کند.

تولید یا به‌روزرسانی lockfile:

```bash
rfm bootstrap --config repo-fleet.json --root . lock
rfm bootstrap --config repo-fleet.json --root . lock --apply
```

مسیر سفارشی:

```bash
rfm bootstrap \
  --config repo-fleet.json \
  --root . \
  lock \
  --output config/repo-fleet.lock.json \
  --apply
```

اعتبارسنجی:

```bash
rfm bootstrap --config repo-fleet.json --root . verify
```

خروجی JSON:

```bash
rfm bootstrap --config repo-fleet.json --root . verify --json
```

Exit code برابر `2` نشان‌دهنده drift است. تغییر config، حذف repository template metadata یا تغییر فایل‌های baseline باعث شکست validation می‌شود.

## bootstrap توسعه‌دهنده جدید

بعد از clone پروژه مادر:

```bash
rfm bootstrap --config repo-fleet.json --root . verify
rfm config --config repo-fleet.json validate --strict
rfm local --config repo-fleet.json bootstrap
rfm local --config repo-fleet.json bootstrap --apply --set-origin
```

این workflow فقط به مسیرهای relative داخل repository تکیه دارد و به filesystem سیستم سازنده وابسته نیست.

## Makefile

```bash
make init-project PROJECT_NAME=banking-platform PROJECT_DIR=./banking-platform
make init-project-apply PROJECT_NAME=banking-platform PROJECT_DIR=./banking-platform
make scaffold-templates
make scaffold-repository CONFIG=repo-fleet.json ROOT=. REPO_NAME=customer-api REPO_PATH=services/customer-api TEMPLATE=python-service REPO_KIND=service
make scaffold-repository-apply CONFIG=repo-fleet.json ROOT=. REPO_NAME=customer-api REPO_PATH=services/customer-api TEMPLATE=python-service REPO_KIND=service
make bootstrap-lock CONFIG=repo-fleet.json ROOT=.
make bootstrap-lock-apply CONFIG=repo-fleet.json ROOT=.
make bootstrap-verify CONFIG=repo-fleet.json ROOT=.
```

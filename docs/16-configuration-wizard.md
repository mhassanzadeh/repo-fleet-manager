# Configuration Wizard

`rfm config wizard` برای ساخت، scan و ویرایش امن `repo-fleet.json` طراحی شده است. خروجی پیش از نوشتن با JSON Schema و validation معنایی RFM بررسی می‌شود و بدون `--apply` هیچ فایلی تغییر نمی‌کند.

## شروع سریع

```bash
rfm config wizard --quick --output repo-fleet.json
rfm config wizard --quick --output repo-fleet.json --apply
```

حالت `quick` فقط نام پروژه، branch، provider و container engine را دریافت می‌کند و مقادیر قابل‌حمل برای local remotes، backup، cache و fingerprint می‌سازد.

## scan پروژه موجود

```bash
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive --apply
```

Scan موارد زیر را پیشنهاد می‌دهد:

- Git root، origin و branch جاری؛
- `.gitmodules` و nested Git repositories؛
- `Dockerfile`های repositoryها؛
- Compose fileهای متداول در root، `infra-compose`، `infra`، `deploy` یا `ops`؛
- نام سرویس‌ها و imageهای صریح Compose؛
- `.env.example`، `.env.sample` یا `.env` فقط به‌عنوان مسیر، بدون خواندن secretها؛
- Docker، Podman یا حالت `auto`.

تمام مسیرهای ذخیره‌شده نسبی هستند. مسیر مطلق یا شامل `..` رد می‌شود.

## حالت پیشرفته

```bash
rfm config wizard --scan . --advanced
```

حالت advanced علاوه بر تنظیمات پایه، profileهای `developer`، `ci` و `production` و groupهای مبتنی بر tag را پیشنهاد می‌کند.

## ویرایش فایل موجود

```bash
rfm config wizard --config repo-fleet.json --show-diff
rfm config wizard --config repo-fleet.json --show-diff --apply
```

در حالت apply:

1. config نهایی validate می‌شود؛
2. فایل `.bak` ساخته می‌شود؛
3. خروجی با write اتمیک جایگزین می‌شود؛
4. در صورت validation ناموفق، فایل اصلی تغییر نمی‌کند.

برای حذف backup فقط در workflow کنترل‌شده:

```bash
rfm config wizard --config repo-fleet.json --no-backup --apply
```

## جلسه قابل ادامه

پاسخ‌های تعاملی در مسیر زیر با permission محدود ذخیره می‌شوند:

```text
.repo-fleet/wizard/session.json
```

```bash
rfm config wizard --resume
rfm config wizard --reset
```

پس از apply موفق، session حذف می‌شود.

## تولید غیرتعاملی

```bash
rfm config wizard \
  --answers wizard-answers.json \
  --output repo-fleet.json \
  --non-interactive \
  --apply
```

نمونه answer file کامل:

```json
{
  "config": {
    "project": {
      "name": "banking-platform",
      "default_provider": "github",
      "default_branch": "main"
    },
    "providers": {
      "github": {
        "type": "remote",
        "driver": "github",
        "namespace": "bank-platform",
        "host": "github.com",
        "cli": "gh",
        "url_template": "git@github.com:{namespace}/{repo}.git",
        "required_scopes": []
      },
      "local": {
        "type": "local",
        "driver": "local",
        "namespace": ".repo-fleet/remotes",
        "cli": "git",
        "url_template": "file://{root}/{namespace}/{repo}.git",
        "required_scopes": []
      }
    },
    "repositories": [
      {
        "path": ".",
        "repo": "banking-platform",
        "kind": "root",
        "provider": "github",
        "branch": "main",
        "source_type": "existing",
        "depends_on": []
      }
    ]
  }
}
```

Answer keyهایی مانند `token`، `password`، `secret`، `api_key` و `private_key` با مقدار غیرخالی رد می‌شوند. credential باید در provider CLI، credential helper یا environment امن نگهداری شود.

## خروجی JSON

```bash
rfm config wizard --scan . --non-interactive --json
```

خروجی شامل مسیر مقصد، وضعیت تغییر، backup، خلاصه scan و config نهایی است.

## Make targets

```bash
make config-wizard
make config-wizard-apply
make config-wizard-scan WIZARD_SCAN=. WIZARD_OUTPUT=repo-fleet.json
make config-wizard-scan-apply WIZARD_SCAN=. WIZARD_OUTPUT=repo-fleet.json
make config-wizard-answers WIZARD_ANSWERS=answers.json
make config-wizard-reset
```

## Runtime defaults from Compose scan

وقتی scan یک Compose file و serviceهای آن را تشخیص دهد، ویزارد بخش `runtime.services` را با serviceهای required تولید می‌کند. healthcheckهای Compose در زمان اجرا خوانده می‌شوند و کاربر می‌تواند بعداً برای هر service یک HTTP/TCP/command probe یا remediation اختصاصی اضافه کند.

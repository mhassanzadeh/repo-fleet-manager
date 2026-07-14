# خروجی ساخت‌یافته و Audit Logging

RFM از نسخه `0.13.0` یک قرارداد خروجی مشترک برای تمام فرمان‌ها و یک audit log سراسری دارد. هدف این است که اجرای موفق یا ناموفق یک فرمان، بدون اتکا به متن اختصاصی همان فرمان، برای CI، پشتیبانی و تحلیل رخداد قابل مصرف باشد.

## فرمت‌های خروجی

فرمت پیش‌فرض `text` است و رفتار قدیمی CLI را حفظ می‌کند:

```bash
rfm doctor --config repo-fleet.json
```

یک envelope JSON پایدار:

```bash
rfm doctor --config repo-fleet.json --format json
```

جریان JSONL، یک event در هر خط:

```bash
rfm runtime --config repo-fleet.json status --format jsonl
```

گزینه‌های خروجی در ابتدا یا انتهای فرمان پذیرفته می‌شوند:

```bash
rfm --format json config --config repo-fleet.json validate --strict
rfm config --config repo-fleet.json validate --strict --format json
```

گزینه‌های قدیمی `--json` حذف نشده‌اند و payload قبلی همان فرمان را تولید می‌کنند. برای قرارداد مشترک جدید از `--format json` یا `--format jsonl` استفاده کنید.

## JSON envelope

خروجی JSON شامل مشخصات اجرای فرمان و payload اصلی است:

```json
{
  "schema_version": "1.0.0",
  "run_id": "20260714-120000-a1b2c3d4e5",
  "command": "runtime status",
  "argv": ["runtime", "status", "--format", "json"],
  "root": "/srv/platform",
  "operation_id": null,
  "status": "succeeded",
  "exit_code": 0,
  "duration_ms": 148,
  "result": {},
  "stderr": [],
  "audit_log": "/srv/platform/.repo-fleet/logs/20260714-120000-a1b2c3d4e5.jsonl"
}
```

اگر خروجی داخلی فرمان JSON معتبر باشد در `result` به‌صورت object یا array قرار می‌گیرد؛ در غیر این صورت خطوط خروجی در `result.lines` ذخیره می‌شوند.

## Event schema

هر خط JSONL بر اساس [`schemas/rfm-event.schema.json`](../schemas/rfm-event.schema.json) ساخته می‌شود. فیلدهای مهم:

- `run_id` و `event_id`
- `sequence` و `timestamp`
- `type` و `level`
- `command` و argv پالایش‌شده
- `root`، `repo` و `service`
- `operation_id` برای اتصال به operation journal
- `status`، `exit_code` و `duration_ms`
- `message` و `data`

رویدادهای پایه هر اجرا:

```text
run.started
command.output
operation.correlated
run.completed
```

## Audit log

در اجرای عادی ترمینال، log به‌صورت پیش‌فرض در مسیر زیر نوشته می‌شود:

```text
.repo-fleet/logs/<RUN_ID>.jsonl
```

غیرفعال‌کردن موقت:

```bash
rfm doctor --no-audit-log
```

تغییر مسیر:

```bash
rfm doctor --log-dir /var/log/rfm
```

شناسه قابل تعیین توسط caller:

```bash
rfm runtime status --run-id deploy-20260714-42
```

فایل‌های audit با permission محدود ایجاد می‌شوند و retention در شروع اجرای بعدی اعمال می‌شود.

## مدیریت logها

```bash
rfm logs --root . list
rfm logs --root . show RUN_ID
rfm logs --root . verify RUN_ID
rfm logs --root . purge --retention-days 30
rfm logs --root . purge --retention-days 30 --apply
```

خروجی ماشین‌خوان قدیمی این فرمان‌ها نیز در دسترس است:

```bash
rfm logs list --json
rfm logs verify RUN_ID --json
```

`verify` هر خط را با JSON Schema بررسی می‌کند، افزایش sequence را کنترل می‌کند و وجود چند `run_id` در یک فایل را خطا می‌داند.

## اتصال به Operation Journal

در فرمان‌های mutation، به محض ساخته‌شدن journal، `operation_id` در Audit Session ثبت می‌شود:

```text
.repo-fleet/logs/<RUN_ID>.jsonl
.repo-fleet/operations/<OPERATION_ID>.json
```

این ارتباط امکان دنبال‌کردن یک اجرا از output تا stepها و rollback را فراهم می‌کند.

## Redaction

قبل از ثبت structured output و audit log، موارد زیر پالایش می‌شوند:

- کلیدهای `token`، `password`، `secret`، `api_key` و مشابه آن‌ها
- argumentهای حساس مانند `--token VALUE`
- assignmentهایی مانند `PASSWORD=value`
- credentialهای داخل URL
- tokenهای شناخته‌شده GitHub و GitLab

نمونه:

```text
--token ***
PASSWORD=***
https://user:***@example.test/repo.git
```

قرار دادن secret داخل `repo-fleet.json` همچنان توسط strict validation رد می‌شود.

## تنظیمات

```json
{
  "observability": {
    "logs_dir": ".repo-fleet/logs",
    "audit_enabled": true,
    "retention_days": 30,
    "include_output": true,
    "redact_keys": ["custom_credential"]
  }
}
```

- `logs_dir`: مسیر نسبی یا absolute مقصد log
- `audit_enabled`: فعال‌بودن پیش‌فرض audit
- `retention_days`: حذف logهای قدیمی‌تر
- `include_output`: ثبت stdout و stderr در audit file
- `redact_keys`: رزرو برای کلیدهای سازمانی اضافه؛ کلیدهای استاندارد همیشه پالایش می‌شوند

Profileها می‌توانند بخش `observability` را override کنند.

## CI

```bash
rfm --format json config --config repo-fleet.json validate --strict > validation.json
rfm runtime --config repo-fleet.json wait --format jsonl > readiness.jsonl
rfm logs verify "$RUN_ID" --json
```

Exit code اصلی فرمان بدون تغییر حفظ می‌شود؛ بنابراین JSON یا JSONL مانع fail شدن job نمی‌شود.

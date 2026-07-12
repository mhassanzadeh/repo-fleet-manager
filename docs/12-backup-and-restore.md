# پشتیبان‌گیری و بازیابی local fleet

از نسخه `0.7.0`، RFM می‌تواند زیرساخت local-only را بدون وابستگی به GitHub یا GitLab در یک آرشیو قابل‌حمل ذخیره و روی یک سیستم تمیز بازیابی کند.

## چه چیزهایی داخل backup قرار می‌گیرند؟

هر آرشیو شامل این موارد است:

- فایل normalized شده `repo-fleet.json`؛
- فایل `.gitmodules` در صورت وجود؛
- تمام bare repositoryهای مسیر `local.remotes_dir`؛
- همه branchها، tagها و refهای محلی، حتی اگر هنوز روی provider خارجی push نشده باشند؛
- manifest شامل نسخه فرمت، نسخه RFM، پروژه، repositoryها، HEAD و refها؛
- `CHECKSUMS.sha256` برای تمام فایل‌های آرشیو؛
- operation journalهای تکمیل‌شده، در صورت فعال‌کردن `--include-operations`.

فایل lock فعال عمداً وارد backup نمی‌شود.

## تنظیمات پیشنهادی

```json
{
  "local": {
    "remotes_dir": ".repo-fleet/remotes",
    "operations_dir": ".repo-fleet/operations",
    "backups_dir": ".repo-fleet/backups",
    "backup_retention": 5,
    "backup_include_operations": false
  }
}
```

| فیلد | کاربرد |
|---|---|
| `backups_dir` | محل پیش‌فرض نگهداری آرشیوها |
| `backup_retention` | تعداد آخرین آرشیوهایی که بعد از backup موفق حفظ می‌شوند |
| `backup_include_operations` | اضافه‌کردن journalهای تکمیل‌شده به آرشیو |

مقادیر CLI روی config اولویت دارند.

## پیش‌نمایش و ساخت backup

همه عملیات نوشتن مانند بقیه RFM در حالت پیش‌فرض dry-run هستند:

```bash
rfm local --config repo-fleet.json backup
```

ساخت واقعی:

```bash
rfm local --config repo-fleet.json backup --apply
```

تعیین نام فایل و retention:

```bash
rfm local --config repo-fleet.json backup \
  --output /mnt/backup/platform-2026-07-12.rfm-backup.tar.gz \
  --retention 10 \
  --include-operations \
  --apply
```

خروجی JSON برای automation:

```bash
rfm local --config repo-fleet.json backup --json
rfm local --config repo-fleet.json backup --json --apply
```

RFM قبل از ساخت آرشیو روی هر bare remote فرمان `git fsck --full` اجرا می‌کند. backup در فایل موقت ساخته و پس از موفقیت به‌صورت atomic به نام نهایی منتقل می‌شود.

## فهرست backupها

```bash
rfm local --config repo-fleet.json backups
rfm local --config repo-fleet.json backups --json
rfm local --root /path/to/project backups --backups-dir /mnt/backups
```

## اعتبارسنجی مستقل آرشیو

فرمان verify به config نیاز ندارد:

```bash
rfm local verify-backup /mnt/backups/platform.rfm-backup.tar.gz
rfm local verify-backup /mnt/backups/platform.rfm-backup.tar.gz --json
```

این فرمان موارد زیر را بررسی می‌کند:

1. ایمن‌بودن نام و نوع همه اعضای tar؛
2. نسخه فرمت backup؛
3. وجود manifest و checksum inventory؛
4. SHA-256 تمام فایل‌ها؛
5. سلامت object database هر bare remote؛
6. تطابق دقیق branch، tag و refها با manifest.

## بازیابی روی یک سیستم تمیز

برای restore نیازی نیست از قبل `repo-fleet.json` یا Git repository وجود داشته باشد:

```bash
mkdir -p /srv/my-platform

rfm local \
  --root /srv/my-platform \
  restore /mnt/backups/platform.rfm-backup.tar.gz
```

پس از بررسی dry-run:

```bash
rfm local \
  --root /srv/my-platform \
  restore /mnt/backups/platform.rfm-backup.tar.gz \
  --apply
```

در حالت پیش‌فرض این موارد بازیابی می‌شوند:

- `/srv/my-platform/repo-fleet.json`
- `/srv/my-platform/.repo-fleet/remotes/*.git`

سپس می‌توانید workspace را از remoteهای بازیابی‌شده بسازید:

```bash
cd /srv/my-platform
rfm config --config repo-fleet.json validate --strict
rfm local clone --apply
```

برای پروژه‌های parent/submodule:

```bash
rfm local localize --apply
```

## بازیابی روی workspace موجود

RFM به‌صورت پیش‌فرض مقصد موجود را بازنویسی نمی‌کند:

```bash
rfm local --config repo-fleet.json restore backup.rfm-backup.tar.gz --apply
```

در صورت وجود remoteها یا config متفاوت، فرمان متوقف می‌شود. پس از بررسی دقیق:

```bash
rfm local --config repo-fleet.json restore backup.rfm-backup.tar.gz \
  --overwrite \
  --apply
```

اگر نام پروژه داخل backup با config فعلی متفاوت باشد، علاوه بر `--overwrite` باید override ایمنی ثبت‌شده ارائه شود:

```bash
rfm local --config repo-fleet.json restore other-project.rfm-backup.tar.gz \
  --overwrite \
  --apply \
  --force \
  --reason "Disaster-recovery migration approved under ticket DR-142"
```

## گزینه‌های restore

| گزینه | کاربرد |
|---|---|
| `--remotes-dir PATH` | تغییر مسیر مقصد bare remoteها |
| `--config-output PATH` | تغییر مسیر فایل config بازیابی‌شده |
| `--no-config` | بازیابی‌نکردن config |
| `--restore-operations` | merge کردن journalهای موجود در backup |
| `--overwrite` | جایگزینی مقصدهای موجود |
| `--json` | خروجی ماشین‌خوان |
| `--force --reason` | عبور ثبت‌شده از project mismatch یا lock stale |

## rollback بازیابی

Restore واقعی از operation journal استفاده می‌کند. اگر بعد از عملیات نیاز به بازگشت دارید:

```bash
rfm ops --config repo-fleet.json list
rfm ops --config repo-fleet.json rollback OPERATION_ID
```

RFM قبل از جایگزینی directory یا فایل موجود، نسخه کامل آن را در rollback backup عملیات نگه می‌دارد. Rollback می‌تواند remotes directory و config قبلی را برگرداند.

## توصیه عملیاتی

- backupها را روی همان دیسک `.repo-fleet/remotes` نگهداری نکنید؛ حداقل یک کپی خارج از میزبان داشته باشید.
- به‌صورت دوره‌ای `verify-backup` را روی فایل‌های قدیمی اجرا کنید.
- قبل از upgrade بزرگ، publish گروهی یا تغییر ساختار submoduleها backup بگیرید.
- برای پروژه‌های حساس، checksum خود آرشیو را در یک سیستم یا مخزن مستقل ثبت کنید.
- عملیات restore را ابتدا در مسیر موقت آزمایش و سپس روی workspace اصلی اجرا کنید.

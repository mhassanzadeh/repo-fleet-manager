# Offline cache و bootstrap در محیط air-gapped

نسخه `0.10.0` امکان انتقال کامل سورس repositoryها و imageهای container را بین یک ماشین متصل و یک محیط بدون دسترسی به GitHub، GitLab یا registry فراهم می‌کند.

## اجزای cache

هر فایل با پسوند `.rfm-cache.tar.gz` شامل این بخش‌ها است:

- یک Git bundle مستقل برای هر repository موجود در config؛
- `repo-fleet.json` مورد استفاده هنگام export؛
- image archiveهای تولیدشده با `docker image save` یا `podman image save`؛
- `manifest.json` شامل repositoryها، refها، imageها و وضعیت completeness؛
- `CHECKSUMS.sha256` برای تمام فایل‌های داخل archive.

Git bundleها تمام branchها و tagهای قابل دسترس را نگهداری می‌کنند. هنگام import، هر bundle به یک bare repository در `local.remotes_dir` تبدیل و با `git fsck` و refهای ثبت‌شده در manifest کنترل می‌شود.

## تنظیمات پیشنهادی

```json
{
  "local": {
    "remotes_dir": ".repo-fleet/remotes",
    "cache_dir": ".repo-fleet/cache",
    "cache_retention": 3
  },
  "compose": {
    "engine": "podman",
    "cache_images": [
      "docker.io/library/postgres:16",
      "docker.io/library/redis:7-alpine"
    ]
  }
}
```

فیلد `compose.cache_images` اختیاری است. imageهای بیشتر را می‌توان هنگام export با تکرار `--image` اضافه کرد.

## Export روی ماشین متصل

ابتدا dry-run:

```bash
rfm cache --config repo-fleet.json export
```

ساخت archive:

```bash
rfm cache --config repo-fleet.json export --apply
```

تعیین نام، engine و image اضافه:

```bash
rfm cache --config repo-fleet.json export \
  --output /mnt/transfer/platform.rfm-cache.tar.gz \
  --engine podman \
  --image registry.example.com/platform/api:2026.07 \
  --apply
```

در حالت عادی، نبودن حتی یک repository یا image باعث توقف export می‌شود. گزینه `--allow-missing` فقط برای ایجاد cache ناقص و بررسی‌شده است. archive ناقص بدون `--allow-incomplete` import نمی‌شود.

برای repositoryهایی با `source_type: upstream` که worktree یا mirror محلی ندارند:

```bash
rfm cache --config repo-fleet.json export \
  --fetch-missing \
  --apply
```

این گزینه فقط در ماشین متصل استفاده می‌شود و upstream را در یک mirror موقت دریافت می‌کند.

## Verify مستقل

```bash
rfm cache verify /mnt/transfer/platform.rfm-cache.tar.gz
```

برای fail شدن cache ناقص:

```bash
rfm cache verify /mnt/transfer/platform.rfm-cache.tar.gz \
  --require-complete
```

خروجی JSON:

```bash
rfm cache verify /mnt/transfer/platform.rfm-cache.tar.gz --json
```

Verify موارد زیر را کنترل می‌کند:

1. ایمنی مسیرهای داخل tar و نبود symlink/device/path traversal؛
2. تطابق inventory فایل‌ها با `CHECKSUMS.sha256`؛
3. digest هر Git bundle و image archive؛
4. refهای موجود در bundle با manifest؛
5. کامل بودن repositoryها و imageهای مورد انتظار.

## Import در شبکه جدا

Import فقط bare remoteها، config و imageها را بازیابی می‌کند:

```bash
rfm cache --root /srv/platform-import \
  import /media/transfer/platform.rfm-cache.tar.gz
```

اجرای واقعی:

```bash
rfm cache --root /srv/platform-import \
  import /media/transfer/platform.rfm-cache.tar.gz \
  --apply
```

برای import سورس بدون load کردن imageها:

```bash
rfm cache --root /srv/platform-import \
  import /media/transfer/platform.rfm-cache.tar.gz \
  --no-load-images \
  --apply
```

اگر مقصد قبلاً bare remote دارد، import متوقف می‌شود. جایگزینی صریح:

```bash
rfm cache --root /srv/platform-import \
  import /media/transfer/platform.rfm-cache.tar.gz \
  --overwrite \
  --apply
```

## Bootstrap کامل air-gapped

فرمان `bootstrap` import و materialization workspace را یکجا انجام می‌دهد:

```bash
rfm cache --root /srv/platform \
  bootstrap /media/transfer/platform.rfm-cache.tar.gz
```

اعمال واقعی:

```bash
rfm cache --root /srv/platform \
  bootstrap /media/transfer/platform.rfm-cache.tar.gz \
  --apply
```

فرآیند اجرا:

1. archive بدون شبکه verify می‌شود؛
2. Git bundleها به `.repo-fleet/remotes/*.git` تبدیل می‌شوند؛
3. image archiveها با engine انتخاب‌شده load می‌شوند؛
4. root repository از local bare remote materialize می‌شود؛
5. submoduleها فقط با URLهای `file://` اضافه می‌شوند؛
6. origin ریشه و submoduleها به remotes محلی اشاره می‌کنند.

در این مسیر هیچ provider CLI و هیچ دسترسی به remote provider استفاده نمی‌شود.

## انتخاب Profile و Group

Export config-aware است و از selection موجود پشتیبانی می‌کند:

```bash
rfm cache \
  --config repo-fleet.json \
  --profile production \
  --group runtime \
  export --apply
```

فقط repositoryهای config مؤثر به archive اضافه می‌شوند. dependencyهای گروه مطابق قواعد profile/group نسخه `0.8.0` resolve می‌شوند.

## سیاست نگهداری

مقدار `local.cache_retention` تعداد cacheهای نگهداری‌شده در `local.cache_dir` را مشخص می‌کند. override در CLI:

```bash
rfm cache --config repo-fleet.json export \
  --retention 5 \
  --apply
```

نمایش archiveهای موجود:

```bash
rfm cache --config repo-fleet.json list
rfm cache --config repo-fleet.json list --json
```

## ملاحظات امنیتی

- Cache ممکن است شامل سورس خصوصی و imageهای داخلی باشد؛ آن را مانند backup حساس نگهداری کنید.
- Checksum یک کنترل integrity است و جایگزین encryption یا signature نیست.
- برای انتقال سازمانی، archive را در یک کانال رمزگذاری‌شده قرار دهید و checksum بیرونی را جداگانه نگهداری کنید.
- گزینه‌های `--allow-missing` و `--allow-incomplete` باید همراه با دلیل عملیاتی و پس از بررسی manifest استفاده شوند.

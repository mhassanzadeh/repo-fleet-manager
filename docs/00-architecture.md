# معماری Repo Fleet Manager

## مسئله

اسکریپت‌های اولیه برای حل مشکلات واقعی یک monorepo/submodule-platform نوشته شده‌اند، اما منطق‌ها در چند فایل پراکنده شده‌اند: کاتالوگ ریپوها چند بار تکرار شده، GitHub hard-code شده، مسیرها و نام‌های Goftaroo داخل اسکریپت‌ها پخش شده و بعضی workflowها به فایل‌هایی وابسته‌اند که در آرشیو موجود نیستند.

## راهکار

Repo Fleet Manager همه تصمیم‌های پروژه را به یک فایل config مرکزی منتقل می‌کند و CLI واحد `rfm` را روی آن قرار می‌دهد.

```text
repo-fleet.json
      │
      ├── providers: github / gitlab
      ├── repositories: root + submodules
      ├── compose: مسیر compose و env
      └── fingerprint: قواعد hash سورس
              │
              ▼
       rfm CLI commands
              │
              ├── repos audit/create
              ├── submodules sync
              ├── git status/pull/push
              ├── source fingerprint
              ├── compose up/down/ps
              └── images verify
```

## اصول طراحی

1. **Config به‌جای hard-code**: مسیر submodule، نام repo، provider، branch و compose service در config تعریف می‌شود.
2. **Dry-run پیش‌فرض**: هر دستور تغییردهنده باید با `--apply` اجرا شود.
3. **Provider abstraction**: GitHub و GitLab از یک interface استفاده می‌کنند و فقط command template متفاوت دارند.
4. **قابل استفاده برای پروژه‌های دیگر**: نام Goftaroo فقط در config نمونه وجود دارد، نه در منطق اصلی ابزار.
5. **Migration-friendly**: اسکریپت‌های legacy حذف نشده‌اند و در کنار ابزار جدید نگهداری شده‌اند.

## اجزای اصلی کد

| ماژول | مسئولیت |
|---|---|
| `config.py` | خواندن و validate اولیه config |
| `gitops.py` | audit، create repo، sync submodule، pull/push/status |
| `fingerprint.py` | محاسبه digest سورس و تولید compose metadata |
| `compose.py` | انتخاب docker compose/podman-compose و اجرای stack |
| `images.py` | مقایسه label image با digest سورس |
| `docs.py` | validate لینک‌های markdown |
| `cli.py` | تعریف فرمان‌های CLI |

## خروجی‌های تولیدی

وقتی `rfm source fingerprint --write` اجرا شود، مسیر زیر ساخته می‌شود:

```text
.repo-fleet/build/
├── metadata.json
├── build.env
├── compose.env
└── docker-compose.source-metadata.yml
```

این فایل‌ها نباید دستی ویرایش شوند و بهتر است در `.gitignore` قرار بگیرند.

# Repo Fleet Manager 0.6.1 patch notes

## هدف

این نسخه یک hotfix سازگاری برای migration فایل‌های قدیمی `repo-fleet.json` است. نسخه 0.6.0 در برخی فایل‌ها فقط `schema_version` را تشخیص می‌داد، اما providerهای قدیمی و نام‌های قدیمی top-level را به مدل schema جدید تبدیل نمی‌کرد.

## اصلاحات

- پشتیبانی از نسخه‌های کوتاه `0.3`، `0.4`، `0.5` و `0.6`؛
- تبدیل `providers.<name>.type: github|gitlab|generic` به `type: remote` و `driver` متناظر؛
- تبدیل `project_name`، `name`، `default_provider` و `default_branch` به بخش `project`؛
- تبدیل `repos`، `modules`، `services` و `projects` به `repositories`؛
- تبدیل mapهای repository به آرایه استاندارد؛
- تبدیل aliasهای `name`, `directory`, `lifecycle`, `repo_state`, `provider_action` و `publish_mode`؛
- تولید مقدارهای پیش‌فرض امن برای `cli`، `host` و `url_template` providerهای شناخته‌شده؛
- اضافه شدن تست بازتولیدکننده خطای config نسخه 0.6.

## گردش کار ارتقا

```bash
rfm config --config repo-fleet.json validate
rfm config --config repo-fleet.json migrate
rfm config --config repo-fleet.json migrate --apply
rfm config --config repo-fleet.json validate --strict
```

در حالت apply، فایل اصلی پیش از تغییر با پسوند `.bak` نگهداری می‌شود.

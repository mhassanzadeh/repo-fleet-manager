# Patch Notes v0.4.0

## هدف نسخه

این نسخه مدل repository lifecycle را به ابزار اضافه می‌کند تا پروژه‌های بزرگ بعد از clone شدن root بتوانند همه submoduleها و remoteهای موردنیاز را به‌صورت local/offline بسازند یا import کنند.

## قابلیت‌های جدید

- اضافه شدن `source_type` برای هر repository:
  - `new`: پروژه‌هایی که هنوز repository ندارند و باید از صفر ساخته شوند.
  - `upstream`: پروژه‌هایی که روی GitHub/GitLab یا Git URL خارجی هستند و باید حداقل local mirror/clone شوند.
  - `existing`: پروژه‌هایی که قبلاً روی دیسک ساخته شده‌اند و باید وارد workspace و بعداً publish شوند.
- تشخیص خودکار `source_type` از روی فیلدهای legacy:
  - upstream: `upstream_url`, `source_url`, `mirror_source`, `fork_from`, `clone_url`
  - existing: `existing_path`, `local_source`, `import_from`
- فرمان جدید `rfm local plan` برای نمایش نقشه localizing قبل از اجرا.
- فرمان جدید `rfm local localize` برای materialize کردن root clone‌شده به workspace کامل local/offline.
- فرمان جدید `rfm repos publish` برای ساخت remoteهای GitHub/GitLab و push کردن worktreeها یا mirrorهای محلی.
- امکان publish با remote جدا، پیش‌فرض `personal`، تا `origin` محلی خراب نشود.
- پشتیبانی از `remote_mode=mirror` برای push mirror از local bare remote.
- completionهای Bash و Fish به‌روزرسانی شدند.
- Makefile targetهای جدید اضافه شدند:
  - `make local-plan`
  - `make local-localize`
  - `make local-localize-apply`
  - `make local-remotes-update`
  - `make publish-github`
  - `make publish-gitlab`
- نمونه config جدید `configs/repo-fleet.lifecycle.example.json` اضافه شد.
- مستندات جدید `docs/09-repository-lifecycle.md` اضافه شد.

## نکات سازگاری

- `rfm local bootstrap` همچنان وجود دارد و برای سازگاری با نسخه قبلی به مسیر `localize` وصل شده است.
- فرمان‌های destructive همچنان dry-run هستند و برای اجرا به `--apply` نیاز دارند.
- در `localize`، root repo دیگر seed جداگانه در local bare remote نمی‌گیرد تا push root clone‌شده با commitهای خودش reject نشود.

# مرجع فرمان‌ها

## `--version`

```bash
rfm --version
```

نسخه نصب‌شده ابزار را چاپ می‌کند.

## `completion`

```bash
rfm completion bash
rfm completion fish
```

اسکریپت completion برای shell موردنظر را چاپ می‌کند. این خروجی در `make install-completions` برای نصب completionها استفاده می‌شود.

## `doctor`

```bash
rfm doctor [--config repo-fleet.json] [--root .]
```

وابستگی‌ها و خلاصه config را بررسی می‌کند.

## `catalog`

نمای repositoryهای پروژه همچنان رفتار پیش‌فرض است:

```bash
rfm catalog [--config repo-fleet.json] [--root .]
rfm catalog --view repositories --format json
```

کاتالوگ قابلیت‌ها و شکاف‌های خود RFM:

```bash
rfm catalog --root . --view summary
rfm catalog --root . --view tree
rfm catalog --root . --view gaps [--priority P0|P1|P2|P3]
rfm catalog --root . --view all --format text|json|markdown
```

ذخیره خروجی و بررسی evidenceهای اعلام‌شده:

```bash
rfm catalog --root . --view all --format markdown --output docs/generated/rfm-service-catalog.md
rfm catalog --root . --view summary --check-evidence
```

`--json` برای سازگاری نسخه‌های قبل معادل `--format json` است.

## `repos audit`

```bash
rfm repos [--config repo-fleet.json] [--root .] audit [--provider github|gitlab|local] [--namespace NAME] [--check-remote] [--json]
```

موارد زیر را بررسی می‌کند:

- `.gitmodules`
- root git config برای submoduleها
- وجود مسیر محلی
- worktree بودن submodule
- origin URL
- branch
- وجود remote repository در provider، در صورت `--check-remote`

## `repos create`

```bash
rfm repos [--config repo-fleet.json] [--root .] create [--provider github|gitlab|local] [--namespace NAME] [--visibility private|public] [--apply]
```

ریپوهای موجود در config را روی provider می‌سازد. برای `github` و `gitlab` از CLIهای رسمی استفاده می‌شود؛ برای `local` یک bare repository محلی ساخته می‌شود. بدون `--apply` فقط dry-run است.

## `repos publish`

```bash
rfm repos [--config repo-fleet.json] [--root .] publish --provider github|gitlab [--namespace NAME] [--visibility private|public] [--only all|new|upstream|existing] [--remote-name personal] [--no-create] [--apply]
```

remote provider را در صورت نیاز می‌سازد و worktree یا local mirror را push می‌کند. این فرمان از local workflow جداست؛ به‌صورت پیش‌فرض remoteای با نام `personal` اضافه می‌کند تا `origin` بتواند local/file باقی بماند. برای `remote_mode=mirror`، اگر local bare mirror وجود داشته باشد، `git push --mirror` اجرا می‌شود.

## `submodules sync`

```bash
rfm submodules [--config repo-fleet.json] [--root .] sync [--provider github|gitlab|local] [--namespace NAME] [--apply]
```

فایل `.gitmodules` را از config بازسازی می‌کند و origin submoduleهای موجود را تنظیم می‌کند.


## `local plan`

```bash
rfm local [--config repo-fleet.json] [--root .] plan [--remotes-dir .repo-fleet/remotes] [--json]
```

نشان می‌دهد هر repository با چه `source_type` تشخیص داده شده و برای localizing چه کاری روی آن انجام می‌شود.

## `local remotes`

```bash
rfm local [--config repo-fleet.json] [--root .] remotes [--remotes-dir .repo-fleet/remotes] [--mirror-sources] [--update-mirrors] [--seed] [--apply]
```

bare repositoryهای محلی را از روی config می‌سازد. برای `source_type=upstream` از فیلدهایی مثل `upstream_url` یا `mirror_source` برای `git clone --mirror` استفاده می‌شود. با `--seed` برای repositoryهای `source_type=new` یک commit اولیه ساخته می‌شود.

## `local init`

```bash
rfm local [--config repo-fleet.json] [--root .] init [--with-remotes] [--set-origin] [--apply]
```

پوشه‌ها و git worktreeهای محلی را از روی config می‌سازد. این حالت repoهای مستقل ایجاد می‌کند؛ برای ساخت submodule واقعی از `local bootstrap` استفاده کنید.

## `local clone`

```bash
rfm local [--config repo-fleet.json] [--root .] clone [--remotes-dir .repo-fleet/remotes] [--mirror-sources] [--apply]
```

repoهای موجود در local bare remotes را در مسیرهای تعریف‌شده clone می‌کند. این فرمان برای سناریوهای fork/mirror محلی مناسب است.

## `local localize`

```bash
rfm local [--config repo-fleet.json] [--root .] localize [--remotes-dir .repo-fleet/remotes] [--update-mirrors] [--no-set-origin] [--apply]
```

فرمان high-level پیشنهادی بعد از clone پروژه مادر است. بر اساس `source_type`، repoهای جدید را می‌سازد، upstreamها را local mirror می‌کند، repoهای موجود را import می‌کند، submoduleهای missing را اضافه می‌کند و `.gitmodules` را به URLهای local تغییر می‌دهد.

## `local bootstrap`

```bash
rfm local [--config repo-fleet.json] [--root .] bootstrap [--remotes-dir .repo-fleet/remotes] [--mirror-sources] [--set-origin] [--apply]
```

برای سازگاری با نسخه‌های قبلی باقی مانده و عملاً مسیر `localize` را اجرا می‌کند. برای پروژه‌های جدید بهتر است `local localize` استفاده شود.

## `git status|pull|push`

```bash
rfm git [--config repo-fleet.json] [--root .] status
rfm git [--config repo-fleet.json] [--root .] pull --apply
rfm git [--config repo-fleet.json] [--root .] push --apply
```

روی root و همه submoduleها اجرا می‌شود. برای حذف root از عملیات:

```bash
rfm git push --no-root --apply
```

## `source fingerprint`

```bash
rfm source [--config repo-fleet.json] [--root .] fingerprint
rfm source [--config repo-fleet.json] [--root .] fingerprint --write
```

digest سورس سرویس‌ها را محاسبه می‌کند و در حالت `--write` فایل‌های compose metadata را تولید می‌کند.

## `compose`

```bash
rfm compose [--config repo-fleet.json] [--root .] ps
rfm compose [--config repo-fleet.json] [--root .] up --apply -- -d --build --force-recreate
rfm compose [--config repo-fleet.json] [--root .] down --apply
rfm compose [--config repo-fleet.json] [--root .] logs -- --tail=100
```

آرگومان‌های بعد از `--` مستقیماً به compose منتقل می‌شوند.

## `images verify`

```bash
rfm images [--config repo-fleet.json] [--root .] verify
rfm images [--config repo-fleet.json] [--root .] verify --json
```

labelهای image را با metadata سورس مقایسه می‌کند.

## `docs validate-links`

```bash
rfm docs [--root .] validate-links
```

لینک‌های داخلی Markdown را بررسی می‌کند.

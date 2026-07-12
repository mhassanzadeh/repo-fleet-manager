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

```bash
rfm catalog [--config repo-fleet.json] [--root .] [--json]
```

کاتالوگ repositoryها را از config چاپ می‌کند.

## `repos audit`

```bash
rfm repos [--config repo-fleet.json] [--root .] audit [--provider github|gitlab] [--namespace NAME] [--check-remote] [--json]
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
rfm repos [--config repo-fleet.json] [--root .] create [--provider github|gitlab] [--namespace NAME] [--visibility private|public] [--apply]
```

ریپوهای موجود در config را روی provider می‌سازد. بدون `--apply` فقط dry-run است.

## `submodules sync`

```bash
rfm submodules [--config repo-fleet.json] [--root .] sync [--provider github|gitlab] [--namespace NAME] [--apply]
```

فایل `.gitmodules` را از config بازسازی می‌کند و origin submoduleهای موجود را تنظیم می‌کند.

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

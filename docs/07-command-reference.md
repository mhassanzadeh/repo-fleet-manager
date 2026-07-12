# مرجع فرمان‌ها

## `doctor`

```bash
rfm doctor [--config repo-fleet.json] [--root .]
```

وابستگی‌ها و خلاصه config را بررسی می‌کند.

## `catalog`

```bash
rfm catalog [--json]
```

کاتالوگ repositoryها را از config چاپ می‌کند.

## `repos audit`

```bash
rfm repos audit [--provider github|gitlab] [--namespace NAME] [--check-remote] [--json]
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
rfm repos create [--provider github|gitlab] [--namespace NAME] [--visibility private|public] [--apply]
```

ریپوهای موجود در config را روی provider می‌سازد. بدون `--apply` فقط dry-run است.

## `submodules sync`

```bash
rfm submodules sync [--provider github|gitlab] [--namespace NAME] [--apply]
```

فایل `.gitmodules` را از config بازسازی می‌کند و origin submoduleهای موجود را تنظیم می‌کند.

## `git status|pull|push`

```bash
rfm git status
rfm git pull --apply
rfm git push --apply
```

روی root و همه submoduleها اجرا می‌شود. برای حذف root از عملیات:

```bash
rfm git push --no-root --apply
```

## `source fingerprint`

```bash
rfm source fingerprint
rfm source fingerprint --write
```

digest سورس سرویس‌ها را محاسبه می‌کند و در حالت `--write` فایل‌های compose metadata را تولید می‌کند.

## `compose`

```bash
rfm compose ps
rfm compose up --apply -- -d --build --force-recreate
rfm compose down --apply
rfm compose logs -- --tail=100
```

آرگومان‌های بعد از `--` مستقیماً به compose منتقل می‌شوند.

## `images verify`

```bash
rfm images verify
rfm images verify --json
```

labelهای image را با metadata سورس مقایسه می‌کند.

## `docs validate-links`

```bash
rfm docs validate-links
```

لینک‌های داخلی Markdown را بررسی می‌کند.

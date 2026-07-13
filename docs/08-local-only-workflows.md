# Local-only workflows

این صفحه workflowهایی را توضیح می‌دهد که بدون GitHub، GitLab، `gh` یا `glab` اجرا می‌شوند. در این حالت `rfm` از Git معمولی و bare repositoryهای محلی استفاده می‌کند.

## مفاهیم اصلی

- `local remotes`: مجموعه‌ای از bare repositoryها در مسیر پیش‌فرض `.repo-fleet/remotes`.
- `local provider`: providerای که URL آن از نوع `file://` است و از `{root}`، `{namespace}` و `{repo}` ساخته می‌شود.
- `source_type`: نوع lifecycle هر repository. مقادیر اصلی: `new`، `upstream`، `existing`.
- `localize`: فرمان high-level برای تبدیل root clone‌شده به workspace کامل local/offline.
- `publish`: انتشار workspace محلی روی GitHub/GitLab شخصی بدون الزاماً تغییر دادن origin محلی.

## تنظیم provider محلی

حداقل config پیشنهادی:

```json
{
  "project": {
    "name": "my-platform",
    "default_provider": "local",
    "default_branch": "main"
  },
  "local": {
    "remotes_dir": ".repo-fleet/remotes",
    "workspace_mode": "submodules"
  },
  "providers": {
    "local": {
      "type": "local",
      "namespace": ".repo-fleet/remotes",
      "cli": "git",
      "url_template": "file://{root}/{namespace}/{repo}.git"
    }
  }
}
```

می‌توانید `default_provider` را همچنان `github` یا `gitlab` نگه دارید و فقط هنگام اجرای audit/sync از `--provider local` استفاده کنید.

## 1. بررسی plan قبل از اجرا

```bash
rfm local --config repo-fleet.json plan
rfm local --config repo-fleet.json plan --json
```

خروجی plan نشان می‌دهد هر repo چطور local می‌شود:

- `new`: local bare remote ساخته می‌شود و اگر submodule باشد commit اولیه README می‌گیرد.
- `upstream`: از `upstream_url`، `source_url`، `mirror_source`، `fork_from` یا `clone_url` یک mirror محلی ساخته می‌شود.
- `existing`: از `existing_path`، `local_source` یا `import_from` به local bare remote import/push انجام می‌شود.

## 2. ساخت کامل workspace بعد از clone پروژه مادر

وقتی root repository را clone کرده‌اید و داخل آن `repo-fleet.json` وجود دارد:

```bash
cd /path/to/main-platform
rfm local plan
rfm local localize
rfm local localize --apply
```

این فرمان در حالت `--apply` کارهای زیر را انجام می‌دهد:

1. bare remote محلی برای root و همه submoduleها می‌سازد.
2. برای submoduleهای `source_type=new` یک commit اولیه README ایجاد و push می‌کند.
3. برای repoهای `source_type=upstream` یک local mirror از upstream می‌سازد.
4. برای repoهای `source_type=existing` از مسیر موجود import می‌کند.
5. root repo را initialize/commit می‌کند، اگر هنوز Git repo نباشد.
6. submoduleهای missing را با URLهای `file://...` اضافه می‌کند.
7. `.gitmodules` را با URLهای محلی sync می‌کند.
8. origin ریشه را به local bare remote وصل و push می‌کند، مگر اینکه `--no-set-origin` بدهید.

## 3. فقط ساخت bare remoteهای محلی

```bash
rfm local --config repo-fleet.json remotes
rfm local --config repo-fleet.json remotes --apply
rfm local --config repo-fleet.json remotes --apply --seed
rfm local --config repo-fleet.json remotes --apply --update-mirrors
```

`--seed` فقط برای repoهای `source_type=new` commit اولیه می‌سازد. `--update-mirrors` روی mirrorهای موجود `git remote update --prune` اجرا می‌کند.

## 4. ساخت worktreeهای محلی بدون submodule واقعی

برای زمانی که فقط پوشه‌ها و git repoهای مستقل محلی می‌خواهید:

```bash
rfm local --config repo-fleet.json init
rfm local --config repo-fleet.json init --apply --with-remotes --set-origin
```

این حالت repoهای مستقل ایجاد می‌کند؛ برای ساختار submodule واقعی از `local localize` استفاده کنید.

## 5. clone محلی از local bare remotes

برای clone ساده بدون ثبت submodule:

```bash
rfm local --config repo-fleet.json clone
rfm local --config repo-fleet.json clone --apply
```

برای پروژه‌های parent/submodule معمولاً `localize` انتخاب بهتری است، چون `.gitmodules` و submodule gitfile را هم درست می‌کند.

## 6. اجرای کامل بدون GitHub/GitLab

بعد از localization محلی می‌توانید همان workflowهای عادی را اجرا کنید:

```bash
rfm repos --config repo-fleet.json audit --provider local
rfm git --config repo-fleet.json status
rfm git --config repo-fleet.json pull --apply
rfm git --config repo-fleet.json push --apply
rfm source --config repo-fleet.json fingerprint --write
rfm compose --config repo-fleet.json up --apply -- -d --build
rfm images --config repo-fleet.json verify
```

در این مسیر هیچ نیازی به `gh`، `glab`، GitHub یا GitLab نیست. تنها وابستگی اجباری Git است؛ برای بخش compose و image همچنان Docker یا Podman لازم است.

## 7. backup و disaster recovery محلی

قبل از تغییرات مهم روی fleet محلی، ابتدا dry-run و سپس backup واقعی بگیرید:

```bash
rfm local --config repo-fleet.json backup
rfm local --config repo-fleet.json backup --apply
rfm local --config repo-fleet.json backups
```

آرشیو ساخته‌شده config، `.gitmodules`، bare remoteها، branchها، tagها و refهای منتشرنشده را نگه می‌دارد. برای بررسی مستقل:

```bash
rfm local verify-backup .repo-fleet/backups/<archive>.rfm-backup.tar.gz
```

بازیابی در سیستم بدون config موجود:

```bash
mkdir -p /srv/restored-platform
rfm local --root /srv/restored-platform restore /mnt/backups/platform.rfm-backup.tar.gz
rfm local --root /srv/restored-platform restore /mnt/backups/platform.rfm-backup.tar.gz --apply
```

بعد از restore، `rfm local clone --apply` یا `rfm local localize --apply` را برای materialize کردن worktreeها اجرا کنید. راهنمای کامل در [backup و restore](12-backup-and-restore.md) قرار دارد.

## 8. publish جداگانه روی GitHub/GitLab شخصی

localization عمداً از publish جداست. برای اینکه origin محلی خراب نشود، publish به‌صورت پیش‌فرض remote جدا با نام `personal` اضافه می‌کند:

```bash
rfm repos publish --provider github --namespace my-user --remote-name personal
rfm repos publish --provider github --namespace my-user --remote-name personal --apply
```

برای GitLab:

```bash
rfm repos publish --provider gitlab --namespace my-group --remote-name personal --apply
```

برای انتشار فقط یک دسته:

```bash
rfm repos publish --provider github --namespace my-user --only new --apply
rfm repos publish --provider github --namespace my-user --only existing --apply
rfm repos publish --provider github --namespace my-user --only upstream --apply
```

## 9. انتقال workspace به محیط air-gapped

Backup برای disaster recovery از state محلی است؛ offline cache برای انتقال قابل‌کنترل سورس‌ها و imageها به شبکه‌ای بدون provider/registry طراحی شده است.

روی ماشین متصل:

```bash
rfm cache --config repo-fleet.json export --apply
rfm cache verify .repo-fleet/cache/<archive>.rfm-cache.tar.gz --require-complete
```

بعد از انتقال archive:

```bash
rfm cache --root /srv/airgap-platform \
  bootstrap /media/transfer/<archive>.rfm-cache.tar.gz \
  --apply
```

در bootstrap آفلاین، root و submoduleها از Git bundleهای داخل cache ساخته می‌شوند و imageها از archive محلی load می‌شوند. راهنمای کامل در [Offline cache و air-gapped bootstrap](15-offline-cache-and-air-gapped-bootstrap.md) قرار دارد.

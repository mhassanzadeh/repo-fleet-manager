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

## `local backup|backups|verify-backup|restore`

ساخت آرشیو backup در حالت dry-run و apply:

```bash
rfm local --config repo-fleet.json backup
rfm local --config repo-fleet.json backup --apply
rfm local --config repo-fleet.json backup --output /mnt/backups/platform.rfm-backup.tar.gz --retention 10 --include-operations --apply
```

فهرست و اعتبارسنجی مستقل آرشیوها:

```bash
rfm local --config repo-fleet.json backups
rfm local --config repo-fleet.json backups --json
rfm local verify-backup /mnt/backups/platform.rfm-backup.tar.gz
rfm local verify-backup /mnt/backups/platform.rfm-backup.tar.gz --json
```

Restore روی سیستم تمیز به config موجود نیاز ندارد:

```bash
rfm local --root /srv/platform restore /mnt/backups/platform.rfm-backup.tar.gz
rfm local --root /srv/platform restore /mnt/backups/platform.rfm-backup.tar.gz --apply
```

گزینه‌های مهم restore شامل `--overwrite`، `--no-config`، `--config-output`، `--restore-operations` و `--remotes-dir` هستند. جزئیات کامل در [پشتیبان‌گیری و بازیابی](12-backup-and-restore.md) آمده است.

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

## `config wizard`

ساخت تعاملی فایل تنظیمات:

```bash
rfm config wizard --quick --output repo-fleet.json
rfm config wizard --quick --output repo-fleet.json --apply
```

Scan و تولید غیرتعاملی:

```bash
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive --apply
```

ویرایش امن، نمایش diff و ادامه جلسه:

```bash
rfm config wizard --config repo-fleet.json --show-diff
rfm config wizard --config repo-fleet.json --show-diff --apply
rfm config wizard --resume
rfm config wizard --reset
```

تولید از answer file:

```bash
rfm config wizard --answers configs/wizard-answers.example.json --non-interactive --apply
```

گزینه‌های اصلی: `--scan`, `--quick`, `--advanced`, `--answers`, `--non-interactive`, `--resume`, `--reset`, `--session-file`, `--show-diff`, `--no-backup`, `--json` و `--apply`.

## `config validate|migrate`

```bash
rfm config --config repo-fleet.json validate
rfm config --config repo-fleet.json validate --strict
rfm config --config repo-fleet.json validate --json
rfm config --config repo-fleet.json migrate
rfm config --config repo-fleet.json migrate --apply
```

`validate` performs schema and semantic checks. Without `--strict`, legacy defaults are migrated in memory before validation. `migrate` is dry-run by default and writes a backup when applied.

## `auth status`

```bash
rfm auth --config repo-fleet.json status
rfm auth --config repo-fleet.json status --provider github --verbose
rfm auth --config repo-fleet.json status --strict-scopes
```

Shows provider driver/host/profile, expected and active user, required/detected scopes and capability probes without exposing token values.

## `graph show`

```bash
rfm graph --config repo-fleet.json show
rfm graph --config repo-fleet.json show --format json
rfm graph --config repo-fleet.json show --format dot --output fleet.dot
```

Renders validated topological execution levels from repository `depends_on` declarations.

## `safety status`

```bash
rfm safety --config repo-fleet.json status
rfm safety --config repo-fleet.json status --json
```

Reports dirty state, current/configured branch, detached HEAD, upstream, ahead/behind and divergence for root and repository worktrees.

## `repos fork`

```bash
rfm repos --config repo-fleet.json fork \
  --provider github \
  [--namespace my-org] \
  [--remote-name personal] \
  [--strict-scopes] \
  [--apply]
```

Uses native provider fork behavior for `source_type=upstream` and `remote_mode=fork`, then connects the destination remote locally.

## `repos mirror`

```bash
rfm repos --config repo-fleet.json mirror \
  --provider gitlab \
  [--namespace my-group] \
  [--apply]
```

Pushes the corresponding local bare repository using `git push --mirror`. The local mirror must already exist.

## `repos reconcile`

```bash
rfm repos --config repo-fleet.json reconcile --provider github
rfm repos --config repo-fleet.json reconcile --provider github --json
rfm repos --config repo-fleet.json reconcile --provider github --apply
```

Compares remote existence, fork lineage, default branch, visibility and topics against config. Apply mode repairs supported metadata drift.

## `ops list|show|resume|rollback`

```bash
rfm ops --config repo-fleet.json list
rfm ops --config repo-fleet.json show OPERATION_ID
rfm ops --config repo-fleet.json show OPERATION_ID --json
rfm ops --config repo-fleet.json resume OPERATION_ID
rfm ops --config repo-fleet.json rollback OPERATION_ID
```

Applied mutations are persisted under `local.operations_dir`. Resume replays the original desired-state command and adds an attempt to the same journal. Rollback executes recorded compensating actions.

## Common mutation safety flags

```text
--apply
--jobs N
--force --reason "explicit operator reason"
--strict-scopes
```

- `--apply` changes state; without it mutating commands remain dry-run.
- `--jobs` enables bounded parallelism within dependency levels where supported.
- `--force` requires a non-empty `--reason`, stored in the journal.
- `--strict-scopes` rejects provider mutation when configured permission scopes cannot be established.

## Profile and group selection

All config-aware command groups accept:

```text
--profile NAME   Apply a named profile; repeatable or comma-separated
--group NAME     Restrict the effective repository catalog; repeatable or comma-separated
```

Configuration inspection commands:

```bash
rfm config --config repo-fleet.json profiles [--json]
rfm config --config repo-fleet.json groups [--json]
rfm config --config repo-fleet.json --profile NAME --group NAME render [--output FILE]
```

## `init-project`

```bash
rfm init-project NAME \
  [--directory PATH] \
  [--branch main] \
  [--provider local|github|gitlab] \
  [--namespace OWNER] \
  [--visibility private|internal|public] \
  [--no-git-init] \
  [--apply]
```

یک parent project استاندارد شامل `repo-fleet.json`، `repo-fleet.lock.json`، README، LICENSE، gitignore و workflow پایه CI می‌سازد. بدون `--apply` فقط برنامه فایل‌ها چاپ می‌شود.

## `scaffold templates|repository`

```bash
rfm scaffold templates [--json]

rfm scaffold repository NAME \
  --config repo-fleet.json \
  --root . \
  --path services/NAME \
  --template generic|python-cli|python-service|node-service \
  [--kind module|service|tooling|library] \
  [--tag TAG] \
  [--depends-on REPOSITORY] \
  [--apply]
```

فایل‌های template، entry کانفیگ و bootstrap lock را هماهنگ ایجاد می‌کند. `--tag` و `--depends-on` قابل تکرار یا comma-separated هستند.

## `bootstrap lock|verify`

```bash
rfm bootstrap --config repo-fleet.json --root . lock [--output repo-fleet.lock.json] [--apply]
rfm bootstrap --config repo-fleet.json --root . verify [--lock-file repo-fleet.lock.json] [--json]
```

`lock` قرارداد deterministic پروژه را تولید می‌کند. `verify` digest کانفیگ، repository contract، template metadata و فایل‌های baseline را بررسی می‌کند و در صورت drift با exit code برابر `2` خاتمه می‌یابد.

## `cache export|verify|list|import|bootstrap`

### Export

```bash
rfm cache --config repo-fleet.json export \
  [--output FILE.rfm-cache.tar.gz] \
  [--cache-dir DIR] \
  [--remotes-dir DIR] \
  [--image IMAGE] \
  [--engine docker|podman] \
  [--fetch-missing] \
  [--allow-missing] \
  [--retention N] \
  [--no-include-images] \
  [--json] \
  [--apply]
```

Git bundleها، config و image archiveها را با manifest و checksum تولید می‌کند. بدون `--apply` فقط plan چاپ می‌شود.

### Verify

```bash
rfm cache verify FILE.rfm-cache.tar.gz \
  [--require-complete] \
  [--json]
```

Checksum، inventory، Git refها و completeness را کنترل می‌کند. `--require-complete` برای cache ناقص exit code برابر `2` برمی‌گرداند.

### List

```bash
rfm cache --config repo-fleet.json list \
  [--cache-dir DIR] \
  [--json]
```

### Import

```bash
rfm cache --root TARGET import FILE.rfm-cache.tar.gz \
  [--remotes-dir DIR] \
  [--config-output FILE] \
  [--no-config] \
  [--no-load-images] \
  [--engine docker|podman] \
  [--overwrite] \
  [--allow-incomplete] \
  [--json] \
  [--apply]
```

Import روی سیستم بدون config موجود نیز قابل اجرا است.

### Bootstrap

```bash
rfm cache --root TARGET bootstrap FILE.rfm-cache.tar.gz \
  [--remotes-dir DIR] \
  [--no-load-images] \
  [--engine docker|podman] \
  [--overwrite] \
  [--allow-incomplete] \
  [--jobs N] \
  [--json] \
  [--apply]
```

Root و submoduleها را فقط از local bare remoteهای import‌شده materialize می‌کند و provider access ندارد.

## `runtime status|doctor|wait|up`

```bash
rfm runtime --config repo-fleet.json status [--service NAME] [--json]
rfm runtime --config repo-fleet.json doctor [--service NAME] [--logs] [--tail N] [--json]
rfm runtime --config repo-fleet.json wait [--service NAME] [--timeout SECONDS] [--interval SECONDS] [--logs] [--json]
rfm runtime --config repo-fleet.json up [--service NAME] [--timeout SECONDS] [--interval SECONDS] [--apply]
```

`status` تفاوت container state و readiness را نشان می‌دهد. `doctor` برای serviceهای ناموفق remediation و log می‌دهد. `wait` تا آماده‌شدن serviceهای required صبر می‌کند. `up` dependency levelها را ترتیبی start کرده و پس از readiness هر level به مرحله بعد می‌رود. `up` بدون `--apply` فقط plan را چاپ می‌کند.

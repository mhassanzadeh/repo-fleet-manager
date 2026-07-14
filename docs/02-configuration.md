# راهنمای config

فایل config پیش‌فرض `repo-fleet.json` است. نمونه‌ها در مسیر [`../configs`](../configs) قرار دارند.

## بخش `project`

```json
{
  "project": {
    "name": "my-platform",
    "default_provider": "github",
    "default_branch": "main",
    "env_prefix": "MYAPP",
    "build_dir": ".repo-fleet/build"
  }
}
```

| فیلد | توضیح |
|---|---|
| `name` | نام پروژه/پلتفرم |
| `default_provider` | provider پیش‌فرض برای repoها |
| `default_branch` | branch پیش‌فرض |
| `env_prefix` | prefix متغیرهای build metadata |
| `build_dir` | مسیر خروجی fingerprint و compose override |

## بخش `providers`

```json
{
  "providers": {
    "github": {
      "type": "remote",
      "driver": "github",
      "namespace": "my-github-org",
      "host": "github.com",
      "cli": "gh",
      "url_template": "git@github.com:{namespace}/{repo}.git"
    },
    "gitlab": {
      "type": "remote",
      "driver": "gitlab",
      "namespace": "my-gitlab-group",
      "host": "gitlab.com",
      "cli": "glab",
      "url_template": "git@gitlab.com:{namespace}/{repo}.git"
    },
    "local": {
      "type": "local",
      "namespace": ".repo-fleet/remotes",
      "cli": "git",
      "url_template": "file://{root}/{namespace}/{repo}.git"
    }
  }
}
```

`namespace` برای GitHub معمولاً owner یا organization است و برای GitLab معمولاً group یا namespace.

## بخش `repositories`

```json
{
  "path": "services/api",
  "repo": "my-api-service",
  "kind": "service",
  "provider": "github",
  "branch": "main",
  "host_port": 8080,
  "compose_service": "api",
  "docker_context": "services/api",
  "dockerfile": "services/api/Dockerfile",
  "health_url": "http://localhost:8080/healthz"
}
```

| فیلد | توضیح |
|---|---|
| `path` | مسیر repo نسبت به root؛ برای root مقدار `.` است |
| `repo` | نام repository روی provider |
| `kind` | `root`، `service`، `client`، `package`، `infra` یا مقدار دلخواه |
| `provider` | `github` یا `gitlab`؛ اگر نباشد از default استفاده می‌شود |
| `branch` | branch پیش‌فرض برای push/pull |
| `compose_service` | نام سرویس در docker-compose |
| `host_port` و `health_url` | برای status و مستندات operational |

## نکته‌های مهاجرت از اسکریپت‌های فعلی

در اسکریپت‌های اولیه، یک کاتالوگ مشابه در چند فایل وجود داشت. در نسخه جدید فقط `repositories` منبع حقیقت است و همه فرمان‌ها از آن استفاده می‌کنند.

## بخش `local`

```json
{
  "local": {
    "remotes_dir": ".repo-fleet/remotes",
    "workspace_mode": "submodules"
  }
}
```

| فیلد | توضیح |
|---|---|
| `remotes_dir` | مسیر bare repositoryهای محلی؛ اگر نسبی باشد نسبت به `--root` محاسبه می‌شود |
| `workspace_mode` | حالت پیشنهادی workspace؛ فعلاً مقدار اصلی `submodules` است |

Provider محلی از placeholderهای زیر پشتیبانی می‌کند:

| placeholder | مقدار |
|---|---|
| `{root}` | مسیر absolute ریشه workspace |
| `{namespace}` | معمولاً مسیر local remotes مثل `.repo-fleet/remotes` |
| `{repo}` | نام repository از config |
| `{host}` | برای providerهای remote مثل GitHub/GitLab |

## فیلدهای اختیاری برای mirror/fork محلی

در هر repository می‌توانید یکی از این فیلدها را اضافه کنید تا `rfm local remotes --mirror-sources` از آن به‌عنوان منبع mirror استفاده کند:

- `mirror_source`
- `upstream_url`
- `source_url`
- `fork_from`
- `clone_url`
- `local_source`

نمونه:

```json
{
  "path": "services/api",
  "repo": "my-api-service",
  "provider": "local",
  "branch": "main",
  "upstream_url": "file:///opt/upstreams/my-api-service.git",
  "mirror": true
}
```

## Schema version and validation

Current normalized manifests use:

```json
{
  "schema_version": "1.0.0"
}
```

`schema_version` نسخه قرارداد فایل JSON است و با نسخه خود ابزار یکی نیست. برای نمونه، RFM `0.6.1` همچنان schema `1.0.0` را استفاده می‌کند.

`--strict` فایل را دقیقاً در همان ساختار فعلی بررسی می‌کند و هیچ migration سازگاری در حافظه انجام نمی‌دهد. بنابراین برای config قدیمی ابتدا migration را preview و apply کنید و سپس strict validation بگیرید:

```bash
rfm config --config repo-fleet.json validate
rfm config --config repo-fleet.json migrate
rfm config --config repo-fleet.json migrate --apply
rfm config --config repo-fleet.json validate --strict
```

نسخه `0.6.1` این شکل‌های قدیمی را نیز تبدیل می‌کند:

- `schema_version`های کوتاه مانند `0.6` و `0.5`؛
- provider قدیمی `type: github` یا `type: gitlab` به `type: remote` همراه با `driver`؛
- فیلدهای top-level مانند `project_name`، `name` و `default_provider` به بخش `project`؛
- کاتالوگ‌های `repos`، `modules`، `services` و `projects` به `repositories`؛
- نام‌های قدیمی repository مانند `name`، `directory`، `lifecycle` و `provider_action`.

قبل از نوشتن فایل، RFM خروجی dry-run نمایش می‌دهد و در حالت `--apply` یک فایل backup با پسوند `.bak` می‌سازد.

The validation layer checks JSON types and allowed fields as well as provider references, duplicate/nested paths, dependency references, cycles and accidental secret fields. Use `x-*` for extension fields or repository `metadata` for free-form metadata.

## Provider driver, profile and scope policy

```json
{
  "github-work": {
    "type": "remote",
    "driver": "github",
    "namespace": "my-org",
    "host": "github.com",
    "cli": "gh",
    "profile": "work",
    "user": "my-user",
    "required_scopes": ["repo"],
    "url_template": "git@github.com:{namespace}/{repo}.git"
  }
}
```

`driver` determines provider behavior independently of the provider key. This allows names such as `github-work` and `gitlab-customer`. `profile` is diagnostic metadata for the configured CLI/session; `user` is the expected active account. `required_scopes` is optional and can be enforced with `--strict-scopes`.

## Repository dependencies and provider desired state

```json
{
  "path": "services/api",
  "repo": "my-api-service",
  "source_type": "upstream",
  "remote_mode": "fork",
  "fork_from": "frappe/frappe",
  "depends_on": ["shared-contracts"],
  "visibility": "private",
  "topics": ["rfm", "backend"]
}
```

`depends_on` can reference either a configured repository name or path. RFM validates the graph and executes independent repositories in the same topological level concurrently when `--jobs` is greater than one.

`visibility`, `topics` and `branch` form the provider desired state used by `rfm repos reconcile`.

## Local operation state

```json
{
  "local": {
    "remotes_dir": ".repo-fleet/remotes",
    "workspace_mode": "submodules",
    "operations_dir": ".repo-fleet/operations",
    "lock_file": ".repo-fleet/lock",
    "default_jobs": 2,
    "backups_dir": ".repo-fleet/backups",
    "backup_retention": 5,
    "backup_include_operations": false
  }
}
```

| Field | Purpose |
|---|---|
| `operations_dir` | Persistent JSON operation journals and rollback backups |
| `lock_file` | Exclusive lock for applied mutations |
| `default_jobs` | Default controlled parallelism for graph-aware commands |
| `backups_dir` | مسیر پیش‌فرض آرشیوهای local backup |
| `backup_retention` | تعداد آخرین backupهای نگهداری‌شده؛ بین ۱ تا ۳۶۵ |
| `backup_include_operations` | افزودن journalهای تکمیل‌شده به backup پیش‌فرض |

## Profiles, overlays and groups

Optional top-level `profiles` and `groups` allow one base catalog to serve developer, CI and production workflows. Repositories may define `tags`, profiles may inherit and overlay project/provider/local/compose/repository values, and groups select a subset with optional dependency expansion.

```bash
rfm config --config repo-fleet.json profiles
rfm config --config repo-fleet.json groups
rfm config --config repo-fleet.json --profile ci --group backend render
```

See [Profiles, overlays and repository groups](13-profiles-overlays-and-groups.md) for merge semantics and examples.

## تنظیمات offline cache

برای تعیین محل cache، retention و imageهای موردنیاز محیط air-gapped:

```json
{
  "local": {
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

- `local.cache_dir`: مسیر archiveهای `.rfm-cache.tar.gz`؛ نسبی به root پروژه.
- `local.cache_retention`: تعداد archiveهای جدید که بعد از export نگهداری می‌شوند.
- `compose.cache_images`: فهرست image referenceهایی که به‌طور پیش‌فرض در export قرار می‌گیرند.
- `compose.engine`: یکی از `auto`، `docker` یا `podman`.

این فیلدها اختیاری‌اند و schema version همچنان `1.0.0` باقی می‌ماند.

## ساخت config با Configuration Wizard

برای ساخت فایل جدید بدون ویرایش دستی JSON:

```bash
rfm config wizard --quick --output repo-fleet.json
rfm config wizard --quick --output repo-fleet.json --apply
```

برای پروژه موجود:

```bash
rfm config wizard --scan . --advanced --output repo-fleet.json --non-interactive --apply
```

ویزارد خروجی را پیش از نوشتن با همین schema اعتبارسنجی می‌کند. مسیرهای تولیدشده نسبی‌اند، answerهای secret-like رد می‌شوند و ویرایش config موجود به‌طور پیش‌فرض backup می‌سازد. شرح کامل در [Configuration Wizard](16-configuration-wizard.md) آمده است.

# Local-only workflows

این صفحه workflowهایی را توضیح می‌دهد که بدون GitHub، GitLab، `gh` یا `glab` اجرا می‌شوند. در این حالت `rfm` از Git معمولی و bare repositoryهای محلی استفاده می‌کند.

## مفاهیم اصلی

- `local remotes`: مجموعه‌ای از bare repositoryها در مسیر پیش‌فرض `.repo-fleet/remotes`.
- `local provider`: providerای که URL آن از نوع `file://` است و از `{root}`، `{namespace}` و `{repo}` ساخته می‌شود.
- `bootstrap`: ساخت کامل workspace محلی شامل root repo، bare remoteهای محلی، submoduleها و `.gitmodules`.
- `mirror source`: آدرسی اختیاری برای repoهایی که باید از یک منبع موجود mirror یا fork شوند.

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

می‌توانید `default_provider` را همچنان `github` یا `gitlab` نگه دارید و فقط هنگام اجرای محلی از `--provider local` استفاده کنید.

## 1. ساخت کامل پروژه محلی از روی config

برای ساخت workspace کامل با submoduleهای واقعی:

```bash
rfm local --config repo-fleet.json --root /path/to/workspace bootstrap
rfm local --config repo-fleet.json --root /path/to/workspace bootstrap --apply --set-origin
```

این فرمان در حالت `--apply` کارهای زیر را انجام می‌دهد:

1. bare remote محلی برای root و همه submoduleها می‌سازد.
2. برای submoduleهای خالی یک commit اولیه README ایجاد و push می‌کند.
3. root repo را initialize می‌کند.
4. submoduleها را با URLهای `file://...` اضافه می‌کند.
5. `.gitmodules` را با URLهای محلی sync می‌کند.
6. در صورت `--set-origin`، origin ریشه را هم به bare remote محلی وصل و push می‌کند.

## 2. فقط ساخت bare remoteهای محلی

```bash
rfm local --config repo-fleet.json remotes
rfm local --config repo-fleet.json remotes --apply
rfm local --config repo-fleet.json remotes --apply --seed
```

`--seed` برای repoهای خالی یک commit اولیه می‌سازد تا clone/submodule add بدون مشکل انجام شود.

## 3. ساخت worktreeهای محلی بدون submodule واقعی

برای زمانی که فقط پوشه‌ها و git repoهای مستقل محلی می‌خواهید:

```bash
rfm local --config repo-fleet.json init
rfm local --config repo-fleet.json init --apply --with-remotes --set-origin
```

این حالت برای development ساده مناسب است، اما submoduleها را به صورت gitfile-submodule داخل root ثبت نمی‌کند. برای ساختار submodule واقعی از `local bootstrap` استفاده کنید.

## 4. clone محلی برای fork/mirror

برای repoهایی که در config فیلدهایی مثل `upstream_url`، `source_url`، `mirror_source`، `fork_from` یا `local_source` دارند، می‌توانید ابتدا mirror محلی بسازید و بعد از آن clone بگیرید:

```bash
rfm local --config repo-fleet.json remotes --mirror-sources --apply
rfm local --config repo-fleet.json clone --apply
```

نمونه repository با source:

```json
{
  "path": "services/api",
  "repo": "my-api-service",
  "kind": "service",
  "provider": "local",
  "branch": "main",
  "upstream_url": "file:///opt/upstreams/my-api-service.git",
  "mirror": true
}
```

اگر `--mirror-sources` ندهید، remoteهای محلی از صفر ساخته می‌شوند و هیچ ارتباطی با upstream برقرار نمی‌شود.

## 5. اجرای کامل بدون GitHub/GitLab

بعد از bootstrap محلی می‌توانید همان workflowهای عادی را اجرا کنید:

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

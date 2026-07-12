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
      "namespace": "my-github-org",
      "host": "github.com",
      "cli": "gh",
      "url_template": "git@github.com:{namespace}/{repo}.git"
    },
    "gitlab": {
      "namespace": "my-gitlab-group",
      "host": "gitlab.com",
      "cli": "glab",
      "url_template": "git@gitlab.com:{namespace}/{repo}.git"
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

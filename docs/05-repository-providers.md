# GitHub و GitLab providers

Repo Fleet Manager providerها را از config می‌خواند. دو provider آماده در نمونه config وجود دارد: `github` و `gitlab`.

## GitHub

```json
"github": {
  "namespace": "my-org",
  "host": "github.com",
  "cli": "gh",
  "url_template": "git@github.com:{namespace}/{repo}.git"
}
```

فرمان‌های اصلی:

```bash
gh auth login
gh repo view my-org/my-repo
gh repo create my-org/my-repo --private --disable-wiki --description "..."
```

## GitLab

```json
"gitlab": {
  "namespace": "my-group",
  "host": "gitlab.com",
  "cli": "glab",
  "url_template": "git@gitlab.com:{namespace}/{repo}.git"
}
```

فرمان‌های اصلی:

```bash
glab auth login
glab repo view my-group/my-repo
glab repo create my-group/my-repo --private --description "..."
```

## override در زمان اجرا

حتی اگر config روی GitHub باشد، می‌توانید موقتاً GitLab را تست کنید:

```bash
rfm repos audit --provider gitlab --namespace my-group
rfm submodules sync --provider gitlab --namespace my-group
```

## نکته امنیتی

این ابزار token یا credential را در config نگه نمی‌دارد. احراز هویت باید از طریق CLI رسمی provider انجام شود.

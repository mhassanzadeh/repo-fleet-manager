# workflowهای عملیاتی

## Bootstrap اولیه پروژه

```bash
rfm doctor
rfm repos audit
rfm submodules sync --provider github --namespace my-org
rfm submodules sync --provider github --namespace my-org --apply
git submodule update --init --recursive
rfm repos audit
```

## ساخت ریپوها روی GitHub

```bash
rfm repos create --provider github --namespace my-org
rfm repos create --provider github --namespace my-org --apply
```

## ساخت ریپوها روی GitLab

```bash
rfm repos create --provider gitlab --namespace my-group
rfm repos create --provider gitlab --namespace my-group --apply
```

## تغییر provider از GitHub به GitLab

1. در `repo-fleet.json` بخش `providers.gitlab.namespace` را تنظیم کنید.
2. audit بگیرید:

```bash
rfm repos audit --provider gitlab --namespace my-group
```

3. `.gitmodules` و originها را sync کنید:

```bash
rfm submodules sync --provider gitlab --namespace my-group
rfm submodules sync --provider gitlab --namespace my-group --apply
```

4. push بزنید:

```bash
rfm git push --apply
```

## Development loop محلی

```bash
rfm git status
rfm source fingerprint --write
rfm compose up --apply -- -d --build --force-recreate
rfm images verify
```

## Pull همه submoduleها

```bash
rfm git pull --apply
```

## Push همه submoduleها

قبل از push، داخل هر submodule commit مستقل بزنید. ابزار عمداً auto-commit انجام نمی‌دهد.

```bash
rfm git push --apply
```

## Validation مستندات

```bash
rfm docs validate-links
```

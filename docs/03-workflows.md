# workflowهای عملیاتی

## Bootstrap کاملاً محلی و بدون GitHub/GitLab

```bash
rfm local bootstrap
rfm local bootstrap --apply --set-origin
rfm repos audit --provider local
```

برای ساخت bare remoteهای local از روی source/mirrorهای تعریف‌شده در config:

```bash
rfm local remotes --mirror-sources --apply
rfm local clone --apply
```

جزئیات بیشتر در [workflowهای local-only](08-local-only-workflows.md).


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

## Safe apply workflow

Before a significant operation:

```bash
rfm config --config repo-fleet.json validate --strict
rfm graph --config repo-fleet.json show
rfm safety --config repo-fleet.json status
rfm auth --config repo-fleet.json status --verbose
```

Then run the dry-run and apply form:

```bash
rfm local --config repo-fleet.json localize
rfm local --config repo-fleet.json localize --jobs 4 --apply
```

Inspect the resulting journal:

```bash
rfm ops --config repo-fleet.json list
rfm ops --config repo-fleet.json show OPERATION_ID
```

For interruption recovery or compensating rollback:

```bash
rfm ops --config repo-fleet.json resume OPERATION_ID
rfm ops --config repo-fleet.json rollback OPERATION_ID
```

See [operational safety and recovery](11-operational-safety-and-recovery.md).

## Native fork, mirror and reconciliation

For repositories configured with `source_type: upstream` and `remote_mode: fork`:

```bash
rfm repos --config repo-fleet.json fork --provider github
rfm repos --config repo-fleet.json fork --provider github --apply
```

For `remote_mode: mirror`:

```bash
rfm local --config repo-fleet.json remotes --mirror-sources --apply
rfm repos --config repo-fleet.json mirror --provider gitlab --apply
```

After create/fork/publish, compare provider state and repair metadata drift:

```bash
rfm repos --config repo-fleet.json reconcile --provider github
rfm repos --config repo-fleet.json reconcile --provider github --apply
```

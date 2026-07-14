# Stable Plugin API

Repo Fleet Manager 0.16.0 یک API نسخه‌دار برای توسعه extension بدون تغییر core ارائه می‌کند. قرارداد عمومی در `repo_fleet_manager.plugin_api` قرار دارد و pluginها از طریق Python entry point کشف می‌شوند.

## انواع Plugin

| Kind | Entry point group | کاربرد |
| --- | --- | --- |
| Provider | `repo_fleet_manager.providers` | افزودن provider جدید برای auth، create، fork و reconcile |
| Runtime | `repo_fleet_manager.runtimes` | افزودن runtime driver غیر از Compose داخلی |
| Catalog exporter | `repo_fleet_manager.catalog_exporters` | افزودن format جدید برای `rfm catalog` |
| Artifact backend | `repo_fleet_manager.artifact_backends` | ذخیره و بازیابی artifact با URI scheme اختصاصی |

نسخه فعلی قرارداد عمومی `1.0` است. Core فقط major version سازگار را بارگذاری می‌کند.

## ساخت Plugin Package

Plugin باید تنها به API عمومی وابسته باشد:

```python
from repo_fleet_manager.plugin_api import ProviderPluginV1, ProviderRequest, PluginResult

class AcmeProvider(ProviderPluginV1):
    name = "acme-forge"
    version = "1.0.0"
    api_version = "1.0"
    aliases = ("acme",)

    def execute(self, request: ProviderRequest) -> PluginResult:
        return PluginResult(message=f"handled {request.operation}")
```

در `pyproject.toml`:

```toml
[project]
dependencies = ["repo-fleet-manager>=0.16,<0.17"]

[project.entry-points."repo_fleet_manager.providers"]
acme-forge = "acme_rfm_plugin:AcmeProvider"
```

نمونه کامل برای هر چهار نوع plugin در [`examples/rfm-example-plugin`](../examples/rfm-example-plugin/README.md) قرار دارد.

## کشف و عیب‌یابی

```bash
rfm plugins list
rfm plugins list --load
rfm plugins show acme-forge
rfm plugins doctor
```

`list` بدون `--load` فقط metadata entry point را می‌خواند. `doctor` همه pluginهای فعال را import می‌کند، API version و contract را بررسی می‌کند و خطا را بدون crash کردن CLI گزارش می‌دهد.

## تنظیمات

```json
{
  "plugins": {
    "enabled": true,
    "strict": false,
    "allow": [],
    "deny": [],
    "settings": {
      "acme-forge": {
        "endpoint": "https://git.example.com"
      }
    }
  }
}
```

- `strict: true` باعث می‌شود `rfm doctor` در صورت خرابی plugin با خطا خارج شود.
- `allow` allowlist نام entry point است.
- `deny` همیشه بر allow اولویت دارد.
- `settings` به plugin متناظر منتقل می‌شود.
- متغیر `RFM_DISABLE_PLUGINS=1` تمام pluginهای خارجی را برای عیب‌یابی غیرفعال می‌کند.

Secret نباید در `plugins.settings` ذخیره شود؛ plugin باید credential را از environment یا credential store خودش بخواند.

## Provider Plugin

در provider config مقدار `driver` برابر alias plugin قرار می‌گیرد:

```json
{
  "providers": {
    "company": {
      "driver": "acme",
      "host": "git.example.com"
    }
  }
}
```

Core عملیات‌هایی مانند `auth-status`، `repository-get`، `create`، `fork` و `reconcile` را با `ProviderRequest.operation` به plugin واگذار می‌کند. عملیات Git محلی و safety journal همچنان در core باقی می‌مانند.

## Runtime Plugin

```json
{
  "runtime": {
    "driver": "nomad-runtime"
  }
}
```

فرمان‌های `status`، `doctor`، `wait` و `up` به `RuntimePluginV1.execute` واگذار می‌شوند. نتیجه plugin باید JSON-compatible باشد و برای status/doctor ساختار serviceهای runtime را برگرداند.

## Catalog Exporter

Plugin format خود را در `formats` اعلام می‌کند:

```bash
rfm catalog --view all --format csv --output catalog.csv
```

Core کاتالوگ resolve‌شده و filterهای view/priority/status را در `CatalogExportRequest` تحویل می‌دهد.

## Artifact Backend

URI scheme plugin backend را انتخاب می‌کند:

```bash
rfm artifacts put ./dist/app.whl s3rfm://releases/app.whl
rfm artifacts put ./dist/app.whl s3rfm://releases/app.whl --apply
rfm artifacts list s3rfm://releases/
rfm artifacts get s3rfm://releases/app.whl ./downloads/app.whl --apply
rfm artifacts delete s3rfm://releases/app.whl --apply
```

`file://` و مسیر محلی backend داخلی هستند. Backend خارجی باید dry-run را رعایت کند و برای mutation فقط وقتی `ArtifactRequest.apply` درست است state را تغییر دهد.

## Isolation و Conflict

- import error، contract نامعتبر و API major ناسازگار به‌عنوان diagnostic ثبت می‌شوند.
- alias تکراری بین pluginهای خارجی باعث غیرفعال‌شدن هر دو می‌شود؛ انتخاب تصادفی انجام نمی‌شود.
- aliasهای built-in رزرو هستند.
- loader در اولین نیاز plugin را import می‌کند و نتیجه را cache می‌کند.
- plugin در همان process و با دسترسی کاربر RFM اجرا می‌شود؛ sandbox امنیتی نیست.

## Compatibility Contract

در خط `0.16.x` قراردادهای `Plugin*V1` پایدارند. تغییر شکستن ABI فقط با major جدید Plugin API انجام می‌شود. توسعه‌دهنده plugin نباید از `repo_fleet_manager.cli`، `provider`، `runtime` یا سایر ماژول‌های داخلی import کند.

برای بررسی artifact نصب‌شده:

```bash
python3 -c 'from repo_fleet_manager.plugin_api import PLUGIN_API_VERSION; print(PLUGIN_API_VERSION)'
rfm plugins doctor
```

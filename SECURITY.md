# Security Policy

## Supported versions

RFM is currently pre-1.0. Security fixes are provided for the latest published release line only.

| Version | Supported |
| --- | --- |
| 0.6.x | Yes |
| < 0.6 | No |

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability. Use GitHub private vulnerability reporting:

https://github.com/mhassanzadeh/repo-fleet-manager/security/advisories/new

Include the affected command, version, impact, reproduction steps and a proposed mitigation when available. Remove access tokens, credentials and private repository URLs from all logs.

## Security model

RFM executes Git, provider CLI and container commands on the operator's machine. Review dry-run output before adding `--apply`. Keep provider credentials in `gh`, `glab`, environment variables or platform credential stores; never place them in `repo-fleet.json`.

RFM journals local operations to support inspection and recovery. Journals can contain repository paths and command metadata, so protect `.repo-fleet/` with normal workstation access controls and do not publish it.

## Audit log security

از نسخه `0.13.0` خروجی ساخت‌یافته و audit log پیش از ذخیره پالایش می‌شوند. فایل‌های `.repo-fleet/logs/*.jsonl` با permission محدود ساخته می‌شوند. با وجود redaction خودکار، این فایل‌ها ممکن است شامل نام repository، مسیر workspace، commandها و diagnosticهای عملیاتی باشند؛ بنابراین باید با همان سیاست دسترسی operation journalها نگهداری شوند.

## Container supply-chain trust

نسخه `0.14.0` digest ثابت registry، SBOM و reportهای vulnerability را در `.repo-fleet/supply-chain` نگهداری می‌کند. این artifactها ممکن است نام packageها و topology سرویس‌ها را افشا کنند و باید مانند audit logها محافظت شوند. کلید خصوصی Cosign نباید در config یا repository ذخیره شود؛ فقط public key، KMS URI یا keyless certificate identity/issuer در policy ثبت می‌شود.


## Plugin trust model

Pluginهای RFM داخل process اصلی و با همان دسترسی filesystem، network و credentialهای کاربر اجرا می‌شوند؛ Plugin API sandbox امنیتی نیست. فقط packageهای امضاشده یا بررسی‌شده از منبع قابل اعتماد نصب شوند و version dependency آن‌ها pin شود. `rfm plugins doctor` فقط compatibility و سلامت بارگذاری را بررسی می‌کند و جایگزین code review یا supply-chain verification package نیست.

Secretها نباید در `plugins.settings` قرار گیرند. برای توقف فوری extensionهای خارجی از `RFM_DISABLE_PLUGINS=1` استفاده کنید. Alias conflict، API ناسازگار و import failure ایزوله و گزارش می‌شوند، اما کد import‌شده همچنان کد قابل اجرا و مورد اعتماد محسوب می‌شود.

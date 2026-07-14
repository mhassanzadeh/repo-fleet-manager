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

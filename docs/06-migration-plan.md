# برنامه مهاجرت از اسکریپت‌های فعلی

## فاز 1 — Inventory و freeze اسکریپت‌های legacy

- اسکریپت‌های فعلی در `legacy-scripts/goftaroo` نگهداری شوند.
- اجرای مستقیم آن‌ها فقط برای موارد اضطراری مجاز باشد.
- `reports/script-audit.md` به‌عنوان baseline بررسی نگهداری شود.

## فاز 2 — ساخت config مرکزی

- فایل `configs/goftaroo.example.json` را به root پروژه اصلی کپی کنید:

```bash
cp configs/goftaroo.example.json /path/to/platform/repo-fleet.json
```

- owner/group و مسیر compose را اصلاح کنید.
- دستور زیر را اجرا کنید:

```bash
rfm doctor
rfm catalog
```

## فاز 3 — جایگزینی GitHub/remote scripts

اسکریپت‌های زیر با فرمان‌های جدید جایگزین شوند:

| اسکریپت legacy | فرمان جدید |
|---|---|
| `create-github-repos.sh` | `rfm repos create --provider github --apply` |
| `replace-submodule-remotes.sh` | `rfm submodules sync --provider github --apply` |
| `goftaroo-github-remote-audit.py` | `rfm repos audit --check-remote` |
| `goftaroo-github-remote-sync.sh` | ترکیب `rfm repos create`, `rfm submodules sync`, `rfm git push` |

## فاز 4 — جایگزینی Docker/dev scripts

| اسکریپت legacy | فرمان جدید |
|---|---|
| `goftaroo-source-fingerprint.py` | `rfm source fingerprint --write` |
| `generate-compose-build-override.py` | در `rfm source fingerprint --write` ادغام شده |
| `goftaroo-compose-up-dev.sh` | `rfm compose up --apply -- -d --build --force-recreate` |
| `goftaroo-compose-status.sh` | `rfm compose ps` + `rfm images verify` |
| `verify-container-source-digests.sh` | `rfm images verify` |

## فاز 5 — حذف hard-codeهای پروژه‌ای

- نام پروژه، repoها، owner و group فقط در `repo-fleet.json` بماند.
- اسکریپت‌های phase-specific به docs یا ابزارهای پروژه‌ای جدا منتقل شوند.
- DB URL و password از اسکریپت‌ها حذف و به `.env` منتقل شود.

## فاز 6 — CI

در CI حداقل این مراحل اجرا شود:

```bash
rfm doctor
rfm repos audit
rfm source fingerprint --write
rfm docs validate-links
```

# Repo Fleet Manager v0.6.3

## هدف انتشار

نسخه `0.6.3` چرخه انتشار عمومی RFM را تکرارپذیر می‌کند. این نسخه تغییر ناسازگار در `repo-fleet.json` یا CLI ایجاد نمی‌کند و schema تنظیمات همچنان `1.0.0` است.

## تغییرات

- اجرای CI روی شاخه‌های `master` و `main`
- امکان اجرای دستی CI
- ساخت خودکار Wheel و Source Distribution
- کنترل تطابق نسخه tag با `pyproject.toml` و `__version__`
- ساخت GitHub Release از tagهای `v*`
- تولید و انتشار `SHA256SUMS`
- نصب آزمایشی Wheel در virtual environment تمیز
- اضافه‌شدن `LICENSE`، `CHANGELOG.md`، `CONTRIBUTING.md` و `SECURITY.md`
- اضافه‌شدن issue form و pull request template
- تکمیل metadata پکیج و لینک‌های پروژه
- ثبت رفع GAP-017 در service catalog

## اعتبارسنجی محلی

```bash
make validate
python scripts/check_release_version.py 0.6.3
make build
python -m venv /tmp/rfm-release-check
/tmp/rfm-release-check/bin/python -m pip install dist/*.whl
/tmp/rfm-release-check/bin/rfm --version
```

## انتشار

```bash
git tag -a v0.6.3 -m "Repo Fleet Manager v0.6.3"
git push origin master
git push origin v0.6.3
```

Push کردن tag، workflow انتشار را اجرا می‌کند و فایل‌های `dist/` به همراه `SHA256SUMS` را به GitHub Release متصل می‌کند.

## Rollback

تا قبل از commit، پچ را reverse کنید. پس از commit، commitهای نسخه را با `git revert` بازگردانید. اگر release ساخته شده ولی نباید عمومی بماند، ابتدا GitHub Release و سپس tag remote را با بررسی دقیق حذف کنید؛ تاریخچه شاخه را force-push نکنید.

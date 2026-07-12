# نصب و وابستگی‌ها

## پیش‌نیازهای ضروری

- Python 3.11 یا جدیدتر
- Git

## پیش‌نیازهای اختیاری بر اساس workflow

| قابلیت | ابزار لازم |
|---|---|
| ساخت/بررسی ریپوهای GitHub | `gh` و `gh auth login` |
| ساخت/بررسی ریپوهای GitLab | `glab` و authentication مربوطه |
| اجرای stack با Docker | `docker` و Docker Compose v2 |
| اجرای stack با Podman | `podman` و `podman-compose` |
| نمایش tree | `tree` اختیاری است |

## نصب development

```bash
git clone <repo-fleet-manager-url>
cd repo-fleet-manager
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
rfm --version
```

## اجرا بدون نصب

```bash
./scripts/rfm.sh doctor --config configs/goftaroo.example.json
```

## اضافه کردن به پروژه اصلی

در root پروژه‌ای که submoduleها را مدیریت می‌کند:

```bash
cp /path/to/repo-fleet-manager/configs/repo-fleet.example.json ./repo-fleet.json
# سپس فایل را مطابق پروژه ویرایش کنید
/path/to/repo-fleet-manager/scripts/rfm.sh doctor
```

## پیشنهاد `.gitignore`

در پروژه اصلی این موارد را اضافه کنید:

```gitignore
.repo-fleet/build/
.gitmodules.backup.*
```

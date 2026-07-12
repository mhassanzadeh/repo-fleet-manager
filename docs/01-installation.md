# نصب و وابستگی‌ها

## پیش‌نیازهای ضروری

- Python 3.11 یا جدیدتر
- Git
- pip برای نصب پکیج Python

## پیش‌نیازهای اختیاری بر اساس workflow

| قابلیت | ابزار لازم |
|---|---|
| ساخت/بررسی ریپوهای GitHub | `gh` و `gh auth login` |
| ساخت/بررسی ریپوهای GitLab | `glab` و authentication مربوطه |
| اجرای stack با Docker | `docker` و Docker Compose v2 |
| اجرای stack با Podman | `podman` و `podman-compose` |
| completion در Bash | `bash-completion` |
| completion در Fish | Fish shell |
| نمایش tree | `tree` اختیاری است |

## نصب به‌عنوان ابزار ترمینالی

از ریشه پروژه:

```bash
make install
rfm --version
```

این دستور دو کار انجام می‌دهد:

1. پکیج Python را با `pip install --user .` نصب می‌کند و command line entrypoint به نام `rfm` می‌سازد.
2. completionهای Bash و Fish را در مسیرهای user نصب می‌کند.

اگر بعد از نصب، فرمان `rfm` پیدا نشد، مسیر user bin را به `PATH` اضافه کنید:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

برای دائمی شدن، همین خط را در `~/.bashrc`، `~/.zshrc` یا فایل profile مناسب shell خود قرار دهید.

## نصب فقط CLI

```bash
make install-cli
```

## نصب editable برای توسعه

```bash
make install-editable
make install-completions
```

## نصب completionها

مسیرهای پیش‌فرض:

- Bash: `~/.local/share/bash-completion/completions/rfm`
- Fish: `~/.config/fish/completions/rfm.fish`

```bash
make install-completions
```

برای تولید دستی completion:

```bash
rfm completion bash > ~/.local/share/bash-completion/completions/rfm
rfm completion fish > ~/.config/fish/completions/rfm.fish
```

برای نصب system-wide:

```bash
sudo make install-completions \
  BASH_COMPLETION_DIR=/usr/share/bash-completion/completions \
  FISH_COMPLETION_DIR=/usr/share/fish/vendor_completions.d
```

بعد از نصب completion، یک shell جدید باز کنید یا فایل completion را source کنید:

```bash
source ~/.local/share/bash-completion/completions/rfm
```

در Fish معمولاً باز کردن shell جدید کافی است.

## حذف نصب

```bash
make uninstall
make uninstall-completions
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
rfm doctor
```

## پیشنهاد `.gitignore`

در پروژه اصلی این موارد را اضافه کنید:

```gitignore
.repo-fleet/build/
.gitmodules.backup.*
```

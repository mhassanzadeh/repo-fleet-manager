# Repository lifecycle and localization model

این پروژه سه نوع repository را به‌صورت رسمی پشتیبانی می‌کند. هدف این است که بعد از clone کردن پروژه مادر، بتوانید کل workspace را بدون وابستگی اجباری به GitHub/GitLab بسازید و بعداً هر بخش را روی remote شخصی publish کنید.

## 1. پروژه‌های جدید (`source_type: new`)

این‌ها repositoryهایی هستند که هنوز هیچ upstream یا remote واقعی ندارند. `rfm` برای آن‌ها local bare remote می‌سازد، یک commit اولیه ایجاد می‌کند و آن‌ها را به‌عنوان submodule در root اضافه می‌کند.

```json
{
  "path": "apps/custom-app",
  "repo": "erpnext-frappe-custom",
  "kind": "service",
  "branch": "main",
  "source_type": "new"
}
```

## 2. پروژه‌های upstream که باید fork/mirror/clone شوند (`source_type: upstream`)

این‌ها روی GitHub، GitLab یا هر Git URL دیگری وجود دارند. در local mode، `rfm` ابتدا از آن‌ها local bare mirror می‌سازد و سپس submodule را از همان mirror محلی اضافه می‌کند. بنابراین بعد از اولین localization می‌توانید flowهای اصلی را بدون تماس با GitHub/GitLab اجرا کنید.

```json
{
  "path": "vendor/frappe",
  "repo": "frappe",
  "kind": "module",
  "branch": "version-15",
  "source_type": "upstream",
  "remote_mode": "mirror",
  "upstream_url": "https://github.com/frappe/frappe.git"
}
```

فیلدهای قابل قبول برای منبع upstream:

- `upstream_url`
- `source_url`
- `mirror_source`
- `fork_from`
- `clone_url`

اگر `source_type` را ننویسید ولی یکی از فیلدهای بالا را قرار دهید، ابزار به‌صورت خودکار آن repo را `upstream` تشخیص می‌دهد.

## 3. پروژه‌های موجود قبلی (`source_type: existing`)

این‌ها قبلاً در ماشین شما ساخته شده‌اند و حالا باید وارد fleet شوند یا بعداً روی GitHub/GitLab شخصی publish شوند. `rfm` می‌تواند از مسیر موجود، local bare remote بسازد و سپس آن را در workspace به‌عنوان submodule clone کند.

```json
{
  "path": "legacy/tenant-admin",
  "repo": "erpnext-frappe-tenant-admin",
  "kind": "service",
  "branch": "main",
  "source_type": "existing",
  "existing_path": "../old-projects/tenant-admin"
}
```

فیلدهای قابل قبول برای repo موجود:

- `existing_path`
- `local_source`
- `import_from`

اگر `source_type` را ننویسید ولی یکی از فیلدهای بالا را قرار دهید، ابزار به‌صورت خودکار آن repo را `existing` تشخیص می‌دهد.

## فرمان پیشنهادی بعد از clone پروژه مادر

بعد از اینکه root repository را clone کردید و داخل آن `repo-fleet.json` وجود دارد:

```bash
rfm local plan
rfm local localize
rfm local localize --apply
```

`local plan` نشان می‌دهد هر repo از چه نوعی تشخیص داده شده و چه کاری روی آن انجام می‌شود. `localize --apply` کارهای زیر را انجام می‌دهد:

1. برای همه repoها local bare remote می‌سازد.
2. برای repoهای `new` یک commit اولیه می‌سازد.
3. برای repoهای `upstream` از GitHub/GitLab/URL داده‌شده mirror محلی می‌گیرد.
4. برای repoهای `existing` از مسیر موجود import/push محلی انجام می‌دهد.
5. submoduleهای missing را از `file://.../.repo-fleet/remotes/*.git` اضافه می‌کند.
6. `.gitmodules` را با URLهای local بازسازی می‌کند.
7. root repo را commit و به local bare remote push می‌کند.

## publish روی GitHub/GitLab شخصی

localization از publish جداست. در حالت local، بهتر است `origin` همچنان به `file://` محلی اشاره کند. برای انتشار روی remote شخصی، remote جدا مثل `personal` اضافه می‌شود:

```bash
rfm repos publish --provider github --namespace my-user --remote-name personal
rfm repos publish --provider github --namespace my-user --remote-name personal --apply

rfm repos publish --provider gitlab --namespace my-group --remote-name personal --apply
```

برای publish کردن فقط یک دسته:

```bash
rfm repos publish --provider github --namespace my-user --only new --apply
rfm repos publish --provider github --namespace my-user --only existing --apply
rfm repos publish --provider github --namespace my-user --only upstream --apply
```

برای `remote_mode: mirror` اگر local bare mirror وجود داشته باشد، publish با `git push --mirror` انجام می‌شود. برای بقیه حالت‌ها، ابزار remote را به worktree اضافه یا به‌روزرسانی می‌کند و branch تنظیم‌شده را push می‌کند.

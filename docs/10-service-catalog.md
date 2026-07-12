# RFM service catalog

RFM یک کاتالوگ ماشین‌خوان برای قابلیت‌های خود دارد تا تیم بتواند وضعیت پیاده‌سازی، بلوغ، شواهد کد و شکاف‌های منطقی را از یک منبع واحد مشاهده کند.

فایل مرجع:

```text
catalog/rfm-service-catalog.json
```

نسخه قابل استفاده داخل پکیج Python نیز در این مسیر قرار دارد:

```text
src/repo_fleet_manager/data/rfm-service-catalog.json
```

## نماهای کاتالوگ

خلاصه وضعیت:

```bash
rfm catalog --root . --view summary
```

درخت قابلیت‌ها:

```bash
rfm catalog --root . --view tree
```

شکاف‌های منطقی بر اساس اولویت:

```bash
rfm catalog --root . --view gaps
rfm catalog --root . --view gaps --priority P0
rfm catalog --root . --view gaps --priority P1
```

خروجی JSON برای ابزارهای دیگر:

```bash
rfm catalog --root . --view all --format json
```

تولید مستندات Markdown:

```bash
rfm catalog --root . --view all --format markdown \
  --output docs/generated/rfm-service-catalog.md

rfm catalog --root . --view gaps --format markdown \
  --output reports/gap-analysis.md
```

## بررسی شواهد

هر قابلیت پیاده‌سازی‌شده یا partial می‌تواند یک یا چند مسیر فایل را به‌عنوان evidence معرفی کند. این فرمان وجود آن فایل‌ها را بررسی می‌کند:

```bash
rfm catalog --root . --view summary --check-evidence
```

در صورت نبودن evidence، فرمان با exit code برابر `2` خارج می‌شود و برای CI قابل استفاده است.

## مدل وضعیت

- `implemented`: قابلیت در CLI یا کد موجود است و شواهد اجرایی دارد.
- `partial`: مسیر اصلی قابل استفاده است، اما safety، provider coverage یا edge caseهای مهم کامل نیست.
- `planned`: برای roadmap تعریف شده ولی هنوز شروع نشده است.
- `missing`: برای production-grade شدن منطقی است ولی در حال حاضر وجود ندارد.

## مدل اولویت شکاف‌ها

- `P0`: پیش‌نیاز اعتماد عملیاتی و استفاده جدی در پروژه‌های بزرگ.
- `P1`: لازم برای مقیاس، بازیابی، offline واقعی و زنجیره تأمین.
- `P2`: توسعه‌پذیری، governance و integration سازمانی.
- `P3`: بهبودهای اختیاری و تجربه کاربری.

## قاعده نگهداری

هر PR یا patch که قابلیت جدیدی اضافه می‌کند باید حداقل یکی از این تغییرها را نیز داشته باشد:

1. اضافه یا به‌روزرسانی capability در catalog.
2. تغییر وضعیت capability از `missing` یا `partial` به وضعیت جدید.
3. به‌روزرسانی evidence و commandها.
4. بستن یا اصلاح gap مرتبط.
5. اجرای `make catalog-docs catalog-check`.
